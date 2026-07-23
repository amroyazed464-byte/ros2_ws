# ROS 2 作业七运行与验证

本文是 **Ubuntu + ROS 2 Jazzy** 的运行手册。以下仿真命令尚未在当前
Windows 主机执行；请在已经安装 TurtleBot3、Nav2 和本工作空间依赖的 Ubuntu
环境中完成验收。

## Ubuntu 构建与包测试

```bash
cd ~/ros2_ws
source /opt/ros/jazzy/setup.bash
colcon build --packages-select my_py_pkg --symlink-install
source install/setup.bash
colcon test --packages-select my_py_pkg
colcon test-result --verbose
```

## 启动 TurtleBot3、定位和 Nav2

每个新终端都先加载 ROS 2 和工作空间。以下命令假定 TurtleBot3 Jazzy 的
`burger` 仿真已经正确安装；将地图文件路径替换为实际的绝对路径。

终端 1：启动 TurtleBot3 World。

```bash
cd ~/ros2_ws
source /opt/ros/jazzy/setup.bash
source install/setup.bash
export TURTLEBOT3_MODEL=burger
ros2 launch turtlebot3_gazebo turtlebot3_world.launch.py
```

终端 2：启动地图定位和 Nav2（`/absolute/path/to/map.yaml` 必须存在）。

```bash
cd ~/ros2_ws
source /opt/ros/jazzy/setup.bash
source install/setup.bash
export TURTLEBOT3_MODEL=burger
ros2 launch nav2_bringup bringup_launch.py map:=/absolute/path/to/map.yaml use_sim_time:=True
```

在 RViz 中使用 **2D Pose Estimate** 设置 Burger 的初始位姿，确认 Nav2 已激活
后再启动 AGV 节点。若本机 TurtleBot3 Jazzy 安装为不同的仿真/定位启动文件，
请遵循该安装包的等效启动方式，但必须提供 `/map`、`/tf`、`/odom`、`/scan` 和
可用的 Nav2 `navigate_to_pose` 动作服务器。

## 启动作业节点

终端 3：先启动充电站服务。

```bash
cd ~/ros2_ws
source /opt/ros/jazzy/setup.bash
source install/setup.bash
ros2 run my_py_pkg charging_station
```

终端 4：启动 AGV 调度器。

```bash
cd ~/ros2_ws
source /opt/ros/jazzy/setup.bash
source install/setup.bash
ros2 run my_py_pkg agv_commander
```

## ROS 接口检查

在另一个已加载工作空间的终端中执行：

```bash
ros2 node list
ros2 topic info /burger_battery
ros2 topic echo /burger_battery
ros2 service type /recharge
ros2 service call /recharge std_srvs/srv/Trigger "{}"
```

预期 `/burger_battery` 的类型为 `std_msgs/msg/Float32`，`/recharge` 的类型为
`std_srvs/srv/Trigger`。`ros2 node list` 应包含 `agv_commander` 与
`charging_station`；手动调用服务时，充电站终端应打印“正在快充...”，约 3 秒后
返回成功消息。手动服务调用会与 AGV 的自动充电请求并发，因此建议在开始自动验收
前或停止 `agv_commander` 后执行。

## 仿真验收顺序

1. 确认 AGV 日志显示 Nav2 已激活，并先向取料区 `[2.5, 1.0]` 导航。
2. 到达后，确认它在取料区和卸料区 `[0.0, 1.0]` 之间循环。
3. 观察 `/burger_battery`：电量从 `100.0` 开始，按约每秒 `0.5` 下降。
4. 电量达到或低于 `20.0` 时，确认当前导航任务被取消，且日志记录返航充电。
5. 确认 Burger 导航到充电站 `[0.0, 0.0]`，随后请求 `/recharge`。
6. 确认充电站打印“正在快充...”，约 3 秒后返回成功。
7. 确认电量发布恢复为 `100.0`，日志显示恢复此前被中断的目标。
8. 确认被中断目标完成后，正常的取料/卸料循环继续。

## Nav2 `inflation_radius` 排障

如果空旷通道仍出现 `Goal Aborted`，检查**实际加载的** TurtleBot3
`nav2_params.yaml`。可适当减小全局和局部 costmap 中的 `inflation_radius`，例如：

```yaml
inflation_layer:
  inflation_radius: 0.12
```

修改后重启 Nav2 再试。不要修改 `build/`、`install/` 或 `log/` 中的生成副本；
应修改源配置文件或启动时实际传入的参数文件。
