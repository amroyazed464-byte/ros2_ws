# AGENTS.md

## 1. 项目概述

本仓库是一个 **ROS 2 Jazzy 工作空间**。

开发流程采用：

- **Windows 主机**：编写代码、使用 AI 修改项目、进行 Git 提交与推送。
- **Ubuntu 虚拟机**：拉取代码、编译 ROS 2 工作空间、运行节点、调试和验证功能。
- **GitHub 远程仓库**：用于主机与虚拟机之间同步代码。

环境信息：

- 主机系统：Windows
- 虚拟机系统：Ubuntu 24.04 LTS
- ROS 版本：ROS 2 Jazzy
- 构建工具：colcon
- C++ 标准：C++17
- Python：Python 3
- C++ 构建系统：ament_cmake
- Python 构建系统：ament_python

---

## 2. AI 必读要求

任何 AI、Agent、代码助手或自动化工具在修改本仓库之前，必须：

1. 阅读本文件。
2. 查看仓库目录结构。
3. 阅读任务相关源码。
4. 检查已有的 `CMakeLists.txt`、`package.xml`、`setup.py` 或配置文件。
5. 先理解当前实现，再进行修改。
6. 优先进行最小范围修改。
7. 不进行与当前任务无关的重构。
8. 不删除现有功能，除非用户明确要求。
9. 不修改自动生成目录。
10. 完成后检查修改结果并给出测试方法。

当用户要求“完成项目”“直接实现”或“帮我修改仓库”时，应直接编辑仓库中的文件，而不是只在聊天中提供示例代码。

---

## 3. 仓库结构

标准目录结构如下：

```text
ros2_ws/
├── AGENTS.md
├── .gitignore
├── src/
│   ├── <ros2_package_1>/
│   ├── <ros2_package_2>/
│   └── ...
├── build/
├── install/
└── log/
```

主要开发目录：

```text
src/
```

自动生成目录：

```text
build/
install/
log/
```

AI 不得手动修改以下目录：

- `build/`
- `install/`
- `log/`

这些目录由 `colcon build` 自动生成，也不得提交到 Git。

---

## 4. Windows 与 Ubuntu 的职责

### Windows 主机

Windows 主机主要负责：

- 编辑代码
- 使用 Codex、Claude Code、Copilot 或其他 AI 工具
- 查看项目文件
- 提交 Git 变更
- 推送代码到 GitHub

Windows 主机通常不负责：

- 编译 ROS 2 Jazzy
- 运行 ROS 2 节点
- 验证 Linux 下的 ROS 2 依赖
- 运行 Ubuntu 专用脚本

### Ubuntu 虚拟机

Ubuntu 虚拟机主要负责：

- 从 GitHub 拉取最新代码
- 加载 ROS 2 Jazzy 环境
- 编译工作空间
- 运行 ROS 2 节点
- 查看话题、服务、参数和日志
- 执行最终测试

不得在源码中写死 Windows 路径，例如：

```text
C:\Users\...
D:\Projects\...
```

也不得依赖 Windows 专用库、DLL、注册表或 Visual Studio 工程。

---

## 5. Git 工作流

### Windows 主机修改代码后

```bash
git status
git add .
git commit -m "描述本次修改"
git push
```

### Ubuntu 虚拟机获取代码

```bash
cd ~/ros2_ws
git pull
```

然后编译：

```bash
source /opt/ros/jazzy/setup.bash
colcon build --symlink-install
source install/setup.bash
```

### Ubuntu 修改后同步回 Windows

在 Ubuntu 中：

```bash
git status
git add .
git commit -m "描述本次修改"
git push
```

在 Windows 中：

```bash
git pull
```

### Git 安全规则

未经用户明确允许，不得执行：

```bash
git push --force
git reset --hard
git clean -fd
git rebase
```

不得擅自：

- 删除分支
- 覆盖远程历史
- 删除用户未提交的修改
- 修改 Git 用户信息
- 更改远程仓库地址

---

## 6. `.gitignore` 要求

仓库至少应忽略：

```gitignore
build/
install/
log/

__pycache__/
*.pyc
*.pyo

.vscode/
.idea/

CMakeCache.txt
CMakeFiles/

*.swp
*.tmp
*~
.DS_Store
Thumbs.db
```

如果发现自动生成目录已经被 Git 跟踪，应先说明情况，再建议用户处理，不得擅自删除重要文件。

---

## 7. ROS 2 包规则

所有 ROS 2 包必须放在：

```text
src/
```

### C++ 包

C++ ROS 2 包应使用：

```text
ament_cmake
```

常见结构：

```text
src/<package_name>/
├── CMakeLists.txt
├── package.xml
├── include/
│   └── <package_name>/
├── src/
└── launch/
```

### Python 包

Python ROS 2 包应使用：

```text
ament_python
```

常见结构：

```text
src/<package_name>/
├── package.xml
├── setup.py
├── setup.cfg
├── resource/
├── <package_name>/
│   ├── __init__.py
│   └── <node_file>.py
└── launch/
```

不得把 ROS 2 包创建在：

- 仓库根目录
- `build/`
- `install/`
- `log/`

---

## 8. C++ 开发规范

C++ ROS 2 节点应使用：

```cpp
#include "rclcpp/rclcpp.hpp"
```

代码要求：

- 使用 C++17。
- 类名使用 `PascalCase`。
- 函数名和变量名使用 `snake_case`。
- 常量命名保持统一。
- 使用智能指针管理 ROS 2 对象。
- 避免不必要的全局变量。
- 回调函数保持清晰和简洁。
- 对关键逻辑添加必要注释。
- 不添加无意义注释。
- 不使用 `printf` 代替 ROS 2 日志。
- 不在代码中写死系统绝对路径。

日志应使用：

```cpp
RCLCPP_DEBUG(...)
RCLCPP_INFO(...)
RCLCPP_WARN(...)
RCLCPP_ERROR(...)
RCLCPP_FATAL(...)
```

创建新节点或可执行文件后，必须同步检查和修改：

- `CMakeLists.txt`
- `package.xml`

典型 CMake 配置应包括：

```cmake
find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
```

创建可执行文件时：

```cmake
add_executable(<executable_name> src/<source_file>.cpp)

ament_target_dependencies(
  <executable_name>
  rclcpp
)
```

安装可执行文件时：

```cmake
install(
  TARGETS <executable_name>
  DESTINATION lib/${PROJECT_NAME}
)
```

文件末尾必须保留：

```cmake
ament_package()
```

---

## 9. Python 开发规范

Python ROS 2 节点应使用：

```python
import rclpy
from rclpy.node import Node
```

代码要求：

- 使用类封装节点。
- 包含 `main()` 函数。
- 正确调用 `rclpy.init()`。
- 正确调用 `rclpy.spin()`。
- 正确销毁节点。
- 正确调用 `rclpy.shutdown()`。
- 不依赖 Windows 专用模块。
- 不写死绝对路径。
- 使用 ROS 2 日志接口。
- 必要时添加异常处理。

基本结构：

```python
def main(args=None):
    rclpy.init(args=args)

    node = ExampleNode()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()
```

新增 Python 节点后，必须检查：

- `setup.py`
- `setup.cfg`
- `package.xml`
- `console_scripts`

示例：

```python
entry_points={
    "console_scripts": [
        "example_node = package_name.example_node:main",
    ],
},
```

---

## 10. ROS 2 通信规则

创建发布者、订阅者、服务、客户端或 Action 时，必须明确：

- 节点名称
- 可执行文件名称
- 话题、服务或 Action 名称
- 消息类型
- 发布频率
- QoS 设置
- 输入行为
- 输出行为
- 错误处理方式

优先使用 ROS 2 标准消息：

- `std_msgs`
- `example_interfaces`
- `geometry_msgs`
- `sensor_msgs`
- `nav_msgs`
- `builtin_interfaces`

只有在标准消息无法满足需求时，才创建自定义接口。

### 发布者

应明确：

- 发布周期
- 消息内容
- 计时器频率
- 是否允许参数配置

### 订阅者

应明确：

- 订阅话题
- 消息类型
- QoS
- 收到消息后的处理逻辑
- 异常数据处理方式

### 服务和客户端

应明确：

- 服务名称
- 服务类型
- 请求格式
- 响应格式
- 超时策略

---

## 11. QoS 规则

不要在不了解场景时随意设置复杂 QoS。

普通教学项目可优先使用：

```cpp
rclcpp::QoS(10)
```

传感器数据可考虑：

```cpp
rclcpp::SensorDataQoS()
```

修改 QoS 时，应说明：

- 为什么需要修改
- 可靠性设置
- 持久性设置
- 队列深度
- 可能造成的兼容问题

---

## 12. 参数规则

可配置值应优先考虑 ROS 2 参数，而不是写死在源码中。

示例：

```cpp
this->declare_parameter<int>("publish_rate", 10);
```

读取参数：

```cpp
const auto publish_rate =
  this->get_parameter("publish_rate").as_int();
```

参数应有：

- 合理默认值
- 清晰名称
- 必要的类型检查
- 必要的范围检查

---

## 13. Launch 文件规则

当项目包含多个节点、参数或命名空间时，应考虑提供 Launch 文件。

Launch 文件应放在：

```text
launch/
```

C++ 包中安装 Launch 文件：

```cmake
install(
  DIRECTORY launch
  DESTINATION share/${PROJECT_NAME}
)
```

Python 包中应通过 `setup.py` 安装 Launch 文件。

Launch 文件应避免：

- 写死用户目录
- 写死 Windows 路径
- 使用不存在的包路径
- 隐藏关键配置

---

## 14. 依赖管理

添加新依赖时，必须同时检查：

- 源码中的 `#include` 或 `import`
- `CMakeLists.txt`
- `package.xml`
- `setup.py`
- 系统安装要求

不得添加与任务无关的第三方依赖。

在不确定依赖是否已安装时，应明确说明：

```text
该依赖尚未在 Ubuntu ROS 2 Jazzy 环境中验证。
```

不得假设 Windows 已安装的库在 Ubuntu 中也可用。

---

## 15. 构建命令

完整构建：

```bash
cd ~/ros2_ws
source /opt/ros/jazzy/setup.bash
colcon build --symlink-install
source install/setup.bash
```

仅构建指定包：

```bash
colcon build --packages-select <package_name> --symlink-install
```

重新构建指定包：

```bash
rm -rf build/<package_name> install/<package_name>
colcon build --packages-select <package_name> --symlink-install
```

除非确有必要，不要建议用户删除整个：

```text
build/
install/
log/
```

如果需要清理整个工作空间，必须先说明原因和影响。

---

## 16. 运行与调试命令

运行节点：

```bash
ros2 run <package_name> <executable_name>
```

运行 Launch 文件：

```bash
ros2 launch <package_name> <launch_file>.launch.py
```

查看节点：

```bash
ros2 node list
ros2 node info <node_name>
```

查看话题：

```bash
ros2 topic list
ros2 topic info <topic_name>
ros2 topic echo <topic_name>
ros2 topic hz <topic_name>
```

手动发布消息：

```bash
ros2 topic pub <topic_name> <message_type> "<message_data>"
```

查看服务：

```bash
ros2 service list
ros2 service type <service_name>
```

调用服务：

```bash
ros2 service call <service_name> <service_type> "<request_data>"
```

查看参数：

```bash
ros2 param list
ros2 param get <node_name> <parameter_name>
ros2 param set <node_name> <parameter_name> <value>
```

---

## 17. AI 执行流程

AI 接到任务后，应按以下步骤执行：

1. 阅读 `AGENTS.md`。
2. 运行或检查 `git status`。
3. 查看仓库目录结构。
4. 找到相关 ROS 2 包。
5. 阅读相关源码和构建文件。
6. 明确任务目标和验收标准。
7. 给出简短实施计划。
8. 修改源码。
9. 同步修改依赖和构建配置。
10. 检查潜在编译问题。
11. 检查 `git diff`。
12. 总结修改内容。
13. 提供 Ubuntu 虚拟机中的编译命令。
14. 提供运行和验证命令。
15. 明确哪些内容尚未实际验证。

不得只生成一段孤立代码，而忽略：

- 文件路径
- 构建配置
- 依赖声明
- 可执行文件注册
- 运行命令
- 测试方法

---

## 18. 修改原则

AI 应遵循：

- 优先最小修改。
- 保留已有功能。
- 保持现有代码风格。
- 避免重复实现。
- 避免无关重构。
- 避免引入复杂架构。
- 不为了“看起来高级”而增加不必要抽象。
- 不创建没有实际用途的文件。
- 不擅自改变节点、话题或包名称。
- 不擅自替换技术栈。
- 不隐藏错误。
- 不声称未完成的测试已经通过。

如果发现现有代码存在明显问题，可以修复，但必须说明：

- 原问题是什么
- 为什么会出错
- 修改了什么
- 是否可能影响其他功能

---

## 19. 禁止操作

未经用户明确要求，不得：

- 删除整个 ROS 2 包
- 删除用户源码
- 重命名包
- 重命名公共话题
- 修改 Git 历史
- 强制推送
- 修改系统 ROS 安装
- 执行 `sudo rm -rf`
- 安装大量无关依赖
- 修改虚拟机网络配置
- 修改主机系统设置
- 创建 Windows 专用构建文件
- 提交 `build/`、`install/`、`log/`
- 声称代码已经在 ROS 2 中运行成功，除非确实完成验证

---

## 20. 完成任务后的输出格式

AI 完成任务后，应按照以下格式汇报：

### 修改文件

- `路径/文件名`
  - 修改内容
  - 修改原因

### 实现结果

说明：

- 完成了什么
- 节点名称
- 可执行文件名称
- 话题、服务或接口名称
- 消息类型
- 主要运行逻辑

### Ubuntu 编译命令

```bash
cd ~/ros2_ws
source /opt/ros/jazzy/setup.bash
colcon build --packages-select <package_name> --symlink-install
source install/setup.bash
```

### 运行命令

```bash
ros2 run <package_name> <executable_name>
```

### 测试方法

给出可复制执行的测试命令。

### 未验证内容

如果 AI 当前无法访问 Ubuntu ROS 2 环境，必须明确写：

```text
代码修改已完成，但尚未在 Ubuntu 24.04 + ROS 2 Jazzy 环境中实际编译和运行验证。
```

### 风险说明

列出：

- 可能缺少的依赖
- 可能的编译风险
- 可能的运行风险
- 需要用户在虚拟机中确认的内容

---

## 21. 项目任务说明

在开始具体开发前，应在本节记录当前项目目标。

### 当前项目名称

```text
待填写
```

### 当前项目目标

```text
待填写
```

### 当前已有功能

```text
待填写
```

### 当前需要完成的功能

```text
待填写
```

### 输入

```text
待填写
```

### 输出

```text
待填写
```

### 使用的 ROS 2 包

```text
待填写
```

### 使用的节点

```text
待填写
```

### 使用的话题、服务或 Action

```text
待填写
```

### 验收标准

```text
1. colcon build 编译通过。
2. 节点可通过 ros2 run 或 ros2 launch 启动。
3. 节点名称、话题名称和消息类型符合设计。
4. 功能可以通过 ROS 2 命令行工具验证。
5. 不提交 build、install、log。
6. 不破坏现有功能。
```

---

## 22. 给 AI 的推荐任务格式

用户可以按照以下格式向 AI 下达任务：

```text
请先阅读仓库根目录的 AGENTS.md，并严格遵守其中的规则。

项目目标：
在这里描述最终要实现的功能。

当前状态：
在这里描述目前已经完成的内容。

需要完成：
1. 功能一
2. 功能二
3. 功能三

技术要求：
- ROS 2 Jazzy
- Ubuntu 24.04
- C++17 或 Python 3
- 所有 ROS 2 包放在 src 目录
- 不修改 build、install、log
- 不引入不必要的第三方依赖

验收标准：
- colcon build 能通过
- 节点可以正常启动
- 话题、服务或 Action 名称正确
- 消息类型正确
- 可以通过 ROS 2 命令行完成验证

执行要求：
- 直接修改仓库文件
- 不要只给示例代码
- 完成后检查 git diff
- 列出所有修改文件
- 给出 Ubuntu 中的编译、运行和测试命令
- 明确说明尚未验证的内容
```

---

## 23. 冲突处理

如果用户要求与本文件冲突：

1. 用户当前明确指令优先。
2. AI 应指出冲突和可能风险。
3. 不得擅自扩大用户授权。
4. 对可能造成代码丢失或仓库损坏的操作，必须先提醒用户。

如果多个说明文件存在冲突，优先级如下：

1. 用户当前明确指令
2. `AGENTS.md`
3. 项目内更具体目录中的 `AGENTS.md`
4. `README.md`
5. 其他 AI 工具说明文件

---

## 24. 最终原则

本仓库的目标不是让 AI 生成看起来复杂的代码，而是生成：

- 能在 Ubuntu 24.04 上使用
- 能在 ROS 2 Jazzy 中编译
- 结构清晰
- 易于理解
- 易于运行
- 易于调试
- 易于继续维护
- 不破坏现有项目
- 能通过 Git 在 Windows 主机和 Ubuntu 虚拟机之间稳定同步的代码
