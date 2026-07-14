# 海龟召唤师设计

## 目标

在 `my_py_pkg` 中提供 ROS 2 Python 节点 `turtle_summoner`，实战演练一个节点同时作为服务端和服务客户端的级联调用。

## 接口与参数

- 节点名：`turtle_summoner`
- 可执行文件：`turtle_summoner`
- 对外服务：`/turtle_summoner`，类型 `std_srvs/srv/SetBool`
- 依赖服务：`/spawn`（`turtlesim/srv/Spawn`）与 `/kill`（`turtlesim/srv/Kill`）
- 启动参数：`x`、`y` 与 `turtle_name`；默认名称为 `summoned_turtle`。学生在终端通过 ROS 参数提供自己的唯一坐标。

## 行为

节点初始化时等待 `/kill` 服务可用，并调用它清除 `turtle1`。之后：

- `data: true`：调用 `/spawn`，在 `x`、`y`、朝向 `0.0` 处生成 `turtle_name`。
- `data: false`：调用 `/kill`，驱逐 `turtle_name`。

回调以服务异步请求完成后更新 `SetBool` 响应。服务不可用、请求失败、重复生成或不存在的海龟均通过 `success: false` 和说明性 `message` 返回。

## 验证

在 Ubuntu 24.04 + ROS 2 Jazzy 中启动 `turtlesim_node`，再以参数启动该节点。分别调用 `SetBool` 的 `true`、`false` 请求，确认海龟生成与驱逐，并截取包含仿真器窗口及终端交互的画面。
