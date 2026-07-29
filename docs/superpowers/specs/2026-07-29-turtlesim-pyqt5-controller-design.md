# ROS2 Turtlesim PyQt5 遥控台设计

## 1. 目标

在 Ubuntu 24.04 LTS、ROS 2 Jazzy 和 PyQt5 环境中，扩展现有 ROS2
Python 包 `my_py_pkg`。新增程序提供图形遥控面板，通过
`geometry_msgs/msg/Twist` 消息向 `/turtle1/cmd_vel` 发布速度指令，
控制 Turtlesim 中 `turtle1` 前进、后退、左转、右转和停止。

最终演示应能在同一画面中同时展示 PyQt5 遥控台与 Turtlesim 窗口，
并清楚看到按钮操作与海龟运动同步联动。

## 2. 范围

本次实现包含：

- 深色主题的 PyQt5 遥控台。
- 前进、后退、左转、右转和停止五个按钮。
- 方向键与空格键快捷控制。
- 当前线速度和角速度显示。
- Turtlesim 订阅连接状态显示。
- 关闭窗口时自动发布停止指令。
- 同时启动 Turtlesim 与遥控台的 ROS2 Launch 文件。
- 自动化测试、运行说明和视频录制步骤。

本次实现不包含：

- 海龟位姿订阅或轨迹规划。
- 多海龟切换。
- 可调速度滑块。
- 遥控器硬件或网络远程控制。

## 3. 包结构

新功能放在现有 `src/my_py_pkg/` 包中。虚拟机中已有的 `led_bridge.py`、
`config/burger_fast.yaml` 和 `setup.py` 修改先单独提交，再从功能分支
实现本作业，避免把两项工作混在同一个提交中。

```text
src/my_py_pkg/
├── launch/
│   └── turtle_gui.launch.py
├── test/
│   ├── test_turtle_gui_logic.py
│   └── test_turtle_gui_registration.py
├── my_py_pkg/
│   ├── turtle_gui_logic.py
│   └── turtle_gui.py
├── package.xml
└── setup.py
```

## 4. 架构

采用单进程、单 GUI 主线程架构。`QApplication` 负责 PyQt5 事件循环，
`QTimer` 以非阻塞方式定期调用 `rclpy.spin_once()`，使 Qt 与 ROS2
共享同一线程，避免额外线程的同步与退出复杂度。

组件职责如下：

- `turtle_gui_logic.py`：将动作名称映射为线速度与角速度，不依赖 PyQt5
  或 ROS2，可独立测试。
- `turtle_gui.py`：创建 ROS2 节点、发布者和 PyQt5 窗口，处理按钮、
  键盘、状态刷新与安全退出。
- `turtle_gui.launch.py`：同时启动 `turtlesim_node` 与 GUI 节点。
- `setup.py`：注册 `turtle_gui` 控制台入口并安装 Launch 文件。
- `package.xml`：声明 PyQt5 运行时依赖。

ROS2 接口：

- 节点名称：`turtle_gui_controller`
- 可执行入口：`turtle_gui`
- 发布话题：`/turtle1/cmd_vel`
- 消息类型：`geometry_msgs/msg/Twist`
- QoS：默认可靠通信，队列深度 10
- 发布方式：每次用户动作立即发布一条速度消息

## 5. 界面与交互

窗口采用深色卡片式布局，默认尺寸约为 560 × 620 像素：

- 顶部显示“ROS2 海龟遥控台”标题和连接状态。
- 中部使用十字方向布局放置四个方向按钮。
- 中央放置高对比度红色停止按钮。
- 底部显示当前线速度、角速度和快捷键提示。

速度映射：

| 动作 | `linear.x` | `angular.z` |
| --- | ---: | ---: |
| 前进 | 2.0 | 0.0 |
| 后退 | -2.0 | 0.0 |
| 左转 | 0.0 | 2.0 |
| 右转 | 0.0 | -2.0 |
| 停止 | 0.0 | 0.0 |

按钮采用点击后保持动作的方式：新的按钮指令会替换上一条指令，直到
点击停止或关闭窗口。键盘方向键映射到四个方向，空格键映射到停止。

GUI 定期使用 ROS2 图信息检查 `/turtle1/cmd_vel` 的订阅者数量：

- 至少一个订阅者时显示绿色“已连接”。
- 没有订阅者时显示橙色“等待 Turtlesim”。

## 6. 数据流

1. 用户点击按钮或按下快捷键。
2. GUI 将输入转换为动作名称。
3. `turtle_gui_logic` 返回对应的线速度与角速度。
4. ROS2 节点创建 `Twist` 消息并立即发布。
5. Turtlesim 订阅 `/turtle1/cmd_vel` 并更新海龟运动。
6. GUI 同步刷新当前动作与速度显示。

## 7. 错误处理与退出

- 未知动作由 `turtle_gui_logic` 明确拒绝并抛出 `ValueError`。
- GUI 只绑定已定义动作，异常会通过 ROS2 日志记录。
- Turtlesim 未启动时 GUI 保持运行并显示等待状态。
- 窗口关闭时先尝试发布全零 `Twist`，再停止计时器、销毁节点并关闭
  ROS2 上下文。
- 清理操作使用状态检查，避免重复关闭导致异常。

## 8. 测试与验收

自动化测试覆盖：

- 五种动作对应的速度值。
- 未知动作被拒绝。
- 包名、控制台入口、依赖项和 Launch 文件注册。
- Launch 文件包含 Turtlesim 与 GUI 两个节点。

Ubuntu 验证包括：

1. 使用 `colcon build --packages-select my_py_pkg
   --symlink-install` 构建成功。
2. 包测试无失败。
3. `ros2 launch my_py_pkg turtle_gui.launch.py` 能同时打开
   Turtlesim 与 PyQt5 窗口。
4. 五个按钮发布正确速度，海龟按预期运动。
5. 方向键和空格键行为与按钮一致。
6. 关闭 GUI 后 `/turtle1/cmd_vel` 收到停止指令。
7. 虚拟机中原有的未提交源代码已在独立提交中完整保留。

## 9. 版本控制与交付

版本控制按以下顺序进行：

1. 在虚拟机 `main` 分支单独提交已有的源代码与配置改动，不提交
   `build/`、`install/` 或 `log/` 自动生成内容。
2. 同步 Windows 与虚拟机仓库后，新建功能分支
   `feature/turtlesim-pyqt5-gui`。
3. 在功能分支完成测试、实现、说明文档与 Ubuntu 验证，并提交代码。
4. 将功能分支合并回 `main`，重新运行关键验证。
5. 将 `main` 推送到 GitHub `origin`。

## 10. 演示视频

录制前将两个窗口并排摆放，确保按钮文字和海龟均清晰可见。建议按
“前进 → 左转 → 前进 → 右转 → 后退 → 停止”的顺序演示，并在最后
停留两秒展示停止效果。视频控制在 20 至 40 秒，不需要录制安装或
构建过程。
