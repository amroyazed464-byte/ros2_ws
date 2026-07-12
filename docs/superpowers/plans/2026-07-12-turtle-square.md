# Turtle Square Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add closed-loop turtlesim square drawing and interactive side-length publishing to `my_py_pkg`.

**Architecture:** `set_side_length` publishes validated `Float32` values supplied on stdin. `turtle_square` stores the turtlesim pose and runs a timer-driven drive/turn state machine, calculating each velocity command from distance or heading error and resetting its square origin when a new side length arrives.

**Tech Stack:** Python 3, ROS 2 Jazzy, rclpy, turtlesim, geometry_msgs, std_msgs, pytest.

## Global Constraints

- Target platform: Ubuntu 24.04 with ROS 2 Jazzy.
- Do not modify generated `build/`, `install/`, or `log/` directories.
- Do not use `time.sleep()` or any elapsed-time movement sequence.
- Use standard ROS 2 message types only.

---

### Task 1: Closed-loop square controller

**Files:**
- Create: `src/my_py_pkg/my_py_pkg/turtle_square.py`
- Test: `src/my_py_pkg/test/test_turtle_square_math.py`

**Interfaces:** Consumes `turtlesim.msg.Pose` and `std_msgs.msg.Float32`; publishes `geometry_msgs.msg.Twist` on `/turtle1/cmd_vel`.

- [ ] Write tests for wrapped angle error and square-corner generation; confirm they fail before implementation.
- [ ] Implement `angle_error(target, current)` using `atan2(sin(delta), cos(delta))` and `corner_from_origin(x, y, side, index)` for four vertices.
- [ ] Create `TurtleSquare(Node)` with pose/side-length subscriptions, Twist publisher, and 20 Hz timer.
- [ ] In DRIVE, scale forward speed by distance, stop at 0.03 m, and transition to TURN; in TURN, scale bounded angular speed by wrapped heading error, stop at 0.03 rad, then select the next side.
- [ ] Reset origin and first target from the latest pose on a finite positive side-length message; publish zero velocity before pose/side availability and at shutdown.
- [ ] Run the math tests and commit the controller work.

### Task 2: Interactive side-length publisher

**Files:**
- Create: `src/my_py_pkg/my_py_pkg/set_side_length.py`
- Test: `src/my_py_pkg/test/test_set_side_length.py`

**Interfaces:** Consumes stdin lines; publishes positive `std_msgs.msg.Float32` values on `/square_side_length`.

- [ ] Write tests for parsing valid positive floats and rejecting empty, nonnumeric, nonfinite, and nonpositive input; confirm they fail.
- [ ] Implement `parse_side_length(text)` returning a positive finite float or `None`.
- [ ] Create `SetSideLength(Node)` with depth-10 publisher, a daemon stdin reader thread, and a 20 Hz queue-draining publish timer.
- [ ] Log a clear input prompt and warn about rejected input without stopping the node.
- [ ] Run validation tests and commit the publisher work.

### Task 3: Package integration and verification

**Files:**
- Modify: `src/my_py_pkg/setup.py`
- Modify: `src/my_py_pkg/package.xml`

- [ ] Add `geometry_msgs`, `std_msgs`, and `turtlesim` as package dependencies.
- [ ] Register `turtle_square = my_py_pkg.turtle_square:main` and `set_side_length = my_py_pkg.set_side_length:main`.
- [ ] Run `python -m py_compile src/my_py_pkg/my_py_pkg/turtle_square.py src/my_py_pkg/my_py_pkg/set_side_length.py`.
- [ ] Run the package tests, `git diff --check`, and inspect the scoped diff.
- [ ] On Ubuntu, run `colcon build --packages-select my_py_pkg --symlink-install`, then test turtlesim with inputs `3.0`, `2.0`, and `1.0`.

