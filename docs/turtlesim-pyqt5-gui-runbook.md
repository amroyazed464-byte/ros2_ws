# ROS2 Turtlesim PyQt5 遥控台运行与录制说明

## 环境

- Ubuntu 24.04 LTS
- ROS 2 Jazzy
- Python 3
- PyQt5
- Turtlesim

检查依赖：

```bash
source /opt/ros/jazzy/setup.bash
ros2 pkg prefix turtlesim
python3 -c "import PyQt5; print('PyQt5 已安装')"
```

如果缺少依赖：

```bash
sudo apt update
sudo apt install ros-jazzy-turtlesim python3-pyqt5
```

## 构建

在 VS Code 中打开 `~/ros2_ws`，然后在终端执行：

```bash
cd ~/ros2_ws
source /opt/ros/jazzy/setup.bash
colcon build --packages-select my_py_pkg --symlink-install
source install/setup.bash
```

构建后可确认程序和 Launch 文件已经安装：

```bash
ros2 pkg executables my_py_pkg | grep turtle_gui
test -f install/my_py_pkg/share/my_py_pkg/launch/turtle_gui.launch.py
```

## 一键运行

```bash
cd ~/ros2_ws
source /opt/ros/jazzy/setup.bash
source install/setup.bash
ros2 launch my_py_pkg turtle_gui.launch.py
```

该命令会同时打开：

- Turtlesim 仿真窗口。
- “ROS2 海龟遥控台”PyQt5 窗口。

状态灯由橙色“等待 Turtlesim”变为绿色“已连接”后即可操作。

## 控制方式

| 操作 | 按钮 | 键盘 | 速度指令 |
| --- | --- | --- | --- |
| 前进 | 前进 | ↑ | `linear.x = 2.0` |
| 后退 | 后退 | ↓ | `linear.x = -2.0` |
| 左转 | 左转 | ← | `angular.z = 2.0` |
| 右转 | 右转 | → | `angular.z = -2.0` |
| 停止 | 停止 | Space | 全部为 `0.0` |

每次操作后，遥控台底部会显示当前线速度与角速度。关闭遥控台时，
程序会先发送一次停止指令。

## ROS2 验证

保持演示程序运行，在另一个终端执行：

```bash
source /opt/ros/jazzy/setup.bash
source ~/ros2_ws/install/setup.bash
ros2 node list
ros2 topic info /turtle1/cmd_vel -v
ros2 topic echo /turtle1/cmd_vel
```

预期节点：

```text
/turtle_gui_controller
/turtlesim
```

点击按钮时，`ros2 topic echo` 应显示对应的
`geometry_msgs/msg/Twist` 消息。

## 自动化测试

```bash
cd ~/ros2_ws
source /opt/ros/jazzy/setup.bash
QT_QPA_PLATFORM=offscreen python3 -m pytest src/my_py_pkg/test -q
colcon test --packages-select my_py_pkg --event-handlers console_direct+
colcon test-result --verbose
```

## 演示视频录制

1. 将 Turtlesim 放在屏幕左侧，遥控台放在右侧。
2. 确认两个窗口完整可见，状态显示“已连接”。
3. 开始录制后依次演示：
   `前进 → 左转 → 前进 → 右转 → 后退 → 停止`。
4. 最后保持停止状态约两秒。
5. 建议视频长度为 20–40 秒。
6. 视频只需展示运行效果，不必录制安装和构建过程。

Ubuntu 可使用系统自带的截图/录屏入口：

```text
按 Print Screen，切换到“录制屏幕”，选择包含两个窗口的区域。
```

## 常见问题

### 状态一直显示“等待 Turtlesim”

检查 Turtlesim 节点和话题：

```bash
ros2 node list
ros2 topic info /turtle1/cmd_vel
```

如果没有 `/turtlesim`，关闭当前程序后重新执行一键运行命令。

### 通过 SSH 启动时没有窗口

图形程序应优先在 Ubuntu 桌面的 VS Code 终端中运行。普通 SSH 会话
通常没有 `DISPLAY` 和桌面会话信息。

### 构建报告 Launch 目标文件不存在

如果旧工作区残留了一个空的 Launch 安装目录，可先确认该目录确实
为空，再仅移除该空目录并重建：

```bash
test -z "$(find install/my_py_pkg/share/my_py_pkg/launch \
  -mindepth 1 -maxdepth 1 -print -quit)"
rmdir install/my_py_pkg/share/my_py_pkg/launch
colcon build --packages-select my_py_pkg --symlink-install
```

不要删除整个 `build/`、`install/` 或 `log/` 目录。
