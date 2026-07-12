# Turtle Square Design

## Goal

Provide two ROS 2 Python nodes that use pose feedback to draw successive, nested squares in turtlesim while accepting side-length updates without restarting either node.

## Architecture

`set_side_length` reads positive floating-point values from standard input in its own terminal and publishes them as `std_msgs/msg/Float32` messages on `/square_side_length`.

`turtle_square` subscribes to `/turtle1/pose` (`turtlesim/msg/Pose`) and `/square_side_length`, then publishes `geometry_msgs/msg/Twist` commands to `/turtle1/cmd_vel`. A 20 Hz timer implements a two-state feedback controller: drive toward the active corner using distance error, then rotate toward the next side using wrapped heading error. No sleep calls or elapsed-time movement logic are used.

On a valid new side length, the controller uses the latest turtle pose as the first corner, resets its corner index to zero, and immediately begins the next square. The previous square remains on screen, producing nested paths as smaller sizes are entered.

## Interfaces and behavior

- Node/executable: `turtle_square`; subscribes `/turtle1/pose`, `/square_side_length`; publishes `/turtle1/cmd_vel`.
- Node/executable: `set_side_length`; publishes `/square_side_length`.
- All application topics use queue depth 10. `/turtle1/pose` uses the standard depth-10 subscription matching turtlesim defaults.
- Values must be finite and strictly greater than zero. Invalid input is rejected with ROS logging and does not interrupt the nodes.
- At each completed side, position tolerance and heading tolerance stop motion before changing controller state, reducing overshoot at the corners.

## Dependencies and verification

The package declares `geometry_msgs`, `std_msgs`, and `turtlesim` alongside `rclpy`. Verification on Ubuntu 24.04 with ROS 2 Jazzy consists of a `colcon build --packages-select my_py_pkg --symlink-install` build, running turtlesim and both nodes in separate terminals, and entering `3.0`, `2.0`, then `1.0`.
