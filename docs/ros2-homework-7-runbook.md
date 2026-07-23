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
`burger` 仿真已经正确安装。导航使用 `$HOME/map.yaml`：它应是前一次 SLAM
作业中为同一个 `turtlebot3_world` 创建的地图。

终端 1：启动 TurtleBot3 World。

```bash
cd ~/ros2_ws
source /opt/ros/jazzy/setup.bash
source install/setup.bash
export TURTLEBOT3_MODEL=burger
ros2 launch turtlebot3_gazebo turtlebot3_world.launch.py
```

如果 `$HOME/map.yaml` 不存在，先保持终端 1 的 World 运行，并用以下三个终端
创建地图。建图完成后停止 Cartographer 和遥控节点（在各自终端按 `Ctrl+C`），
再启动 Navigation2；不要让 SLAM 与 Navigation2 同时运行。

终端 2：启动 Cartographer SLAM。

```bash
cd ~/ros2_ws
source /opt/ros/jazzy/setup.bash
source install/setup.bash
export TURTLEBOT3_MODEL=burger
ros2 launch turtlebot3_cartographer cartographer.launch.py use_sim_time:=True
```

终端 3：使用键盘探索并建立覆盖 World 的地图。

```bash
source /opt/ros/jazzy/setup.bash
export TURTLEBOT3_MODEL=burger
ros2 run turtlebot3_teleop teleop_keyboard
```

终端 4：完成探索后保存地图。

```bash
source /opt/ros/jazzy/setup.bash
ros2 run nav2_map_server map_saver_cli -f "$HOME/map"
```

确认生成 `$HOME/map.yaml` 与 `$HOME/map.pgm` 后，停止上面的 SLAM 和遥控节点。

终端 2：检查地图存在并启动定位与 Navigation2。

```bash
cd ~/ros2_ws
source /opt/ros/jazzy/setup.bash
source install/setup.bash
export TURTLEBOT3_MODEL=burger
if [ ! -f "$HOME/map.yaml" ]; then
  echo "地图文件不存在：$HOME/map.yaml。请先按本节的 SLAM 建图步骤生成它。" >&2
else
  ros2 launch turtlebot3_navigation2 navigation2.launch.py \
    map:="$HOME/map.yaml" \
    use_sim_time:=True
fi
```

确认 Gazebo 左下角显示暂停按钮而不是播放三角形；如果显示播放三角形，先点击它恢复
仿真。然后在 Navigation2 的 RViz 中使用 **2D Pose Estimate** 设置 Burger 的
初始位姿，并确认激光雷达扫描与地图墙体对齐。点击 Navigation 2 面板中的
**Startup**，等待 `Navigation: active` 和 `Localization: active` 同时出现后，
再启动 `agv_commander`。

可在另一个已加载 ROS 2 环境的终端中检查 Nav2 是否真正就绪：

```bash
ros2 lifecycle get /bt_navigator
ros2 topic echo /amcl_pose --once
ros2 action info /navigate_to_pose
```

预期 `/bt_navigator` 为 `active`，能够收到一条 `/amcl_pose`，并且
`/navigate_to_pose` 存在可用的动作服务器。

若本机 TurtleBot3 Jazzy 安装为不同的仿真/定位启动文件，请遵循该安装包的等效
启动方式，但必须提供 `/map`、`/tf`、`/odom`、`/scan` 和可用的 Nav2
`navigate_to_pose` 动作服务器。

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
ros2 run my_py_pkg agv_commander --ros-args -p use_sim_time:=true
```

调度器保持单线程线性运行，不启动外层 executor、线程或定时器回调。导航目标提交与
取消直接使用 Jazzy `BasicNavigator` 提供的 `nav_to_pose_client`、目标句柄和异步
future，并以短周期 `spin_once` 推进；等待期间会继续更新和发布电量。动作服务器、
目标响应和取消响应均有单调时钟截止时间，超时后保留当前搬运目标并重试或进入充电
恢复。`/recharge` 响应等待上限为 10 秒，超过上限时保持恢复状态并重试。

## 机器人不运动排障

如果所有终端都已启动但 Burger 不运动，先看 RViz Navigation 2 面板和
`agv_commander` 日志，不要立即修改导航参数。

- Gazebo 左下角出现播放三角形时，仿真处于暂停状态。点击播放按钮并确认仿真时间、
  激光数据和机器人状态继续更新。
- RViz 显示 `Navigation: inactive` 时，导航生命周期节点尚未启动。先设置
  **2D Pose Estimate**，再点击 **Startup**，等待 Navigation 和 Localization
  都变为 `active`。
- `agv_commander` 持续打印 `Waiting for amcl_pose to be received` 时，说明它还在
  等待定位结果，尚未进入搬运循环。确认 `/amcl_pose` 可接收，并确认启动命令包含
  `--ros-args -p use_sim_time:=true`。
- `map:="$MAP_YAML"` 报 `malformed launch argument 'map:='` 时，说明当前终端中的
  `MAP_YAML` 为空。直接使用 `map:="$HOME/map.yaml"`，并先确认该文件存在。

综合检查命令：

```bash
ros2 topic echo /clock --once
ros2 lifecycle get /bt_navigator
ros2 topic echo /amcl_pose --once
ros2 action info /navigate_to_pose
ros2 param get /agv_commander use_sim_time
```

只有当仿真时间在推进、`/bt_navigator` 为 `active`、定位消息可接收、动作服务器
可用且 `agv_commander` 的 `use_sim_time` 为 `True` 时，调度器才会开始发送搬运
目标。正常日志应从等待定位切换为“Nav2 已激活，开始搬运循环”。

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
