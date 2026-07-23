# AGV Battery Interruption and Resume Design

## Goal

Add two ROS 2 Jazzy Python nodes to the existing `my_py_pkg` package. The
nodes turn TurtleBot3 Burger in `turtlebot3_world` into an AGV that repeatedly
moves between pickup and drop-off stations, publishes a simulated battery
level, interrupts work to recharge at a low-battery threshold, and resumes the
exact station goal that was interrupted.

## Architecture Choice

Use a single linear polling loop built around Nav2 Simple Commander's
`BasicNavigator`. `AgvCommander` subclasses `BasicNavigator`, so navigation,
battery publication, and the recharge client share one ROS node without a
second executor.

This architecture follows the Simple Commander polling model while replacing
its indefinitely blocking goal-submission and cancellation helpers with
bounded asynchronous waits:

```text
send goal asynchronously
  |
  v
spin_once with monotonic deadlines
  |-- publish elapsed-time battery updates
  |-- compare feedback current_pose to the exact target
  |-- cancel and divert when battery <= 20%
  |-- retain and clean up late goal responses
  v
handle arrival, failure, or recharge
```

Timer callbacks, worker threads, and a continuously spinning executor are not
used for the navigation wait loop. One linear owner advances action, service,
and late-cleanup futures with short `spin_once` calls. This avoids calling
Simple Commander polling methods from an executor callback and prevents
nested-spinning errors.

## Components

### `agv_commander`

- Source: `my_py_pkg/agv_commander.py`
- Node name: `agv_commander`
- Console executable: `agv_commander`
- Base class: `nav2_simple_commander.robot_navigator.BasicNavigator`
- Navigation frame: `map`
- Pickup station: `(2.5, 1.0)`
- Drop-off station: `(0.0, 1.0)`
- Charging station: `(0.0, 0.0)`
- Battery topic: `/burger_battery`
- Battery message type: `std_msgs/msg/Float32`
- Recharge service client: `/recharge`
- Recharge service type: `std_srvs/srv/Trigger`

The node starts with a battery level of `100.0%`, waits for Nav2 to become
active, and sends the pickup goal. After a normal station arrival, it toggles
between pickup and drop-off forever.

Battery consumption is based on monotonic elapsed time rather than loop
iterations. The level drops by `0.5%` per second and is published at one-second
intervals. The value is clamped to the inclusive range `0.0..100.0`.

When the battery first reaches or falls below `20.0%`, the node:

1. stores the current work-station goal;
2. marks the AGV as being in a low-battery recovery cycle;
3. cancels the current Nav2 task;
4. sends the charging-station goal.

The low-battery transition is latched so the current task is not repeatedly
canceled. Battery drain continues while the robot travels to the charging
station, but the value cannot become negative.

After the robot reaches the charging station, the node calls `/recharge`.
When the service returns success, it resets the battery to `100.0%`, publishes
the restored value, clears the recovery latch, and sends the remembered work
goal again. The normal pickup/drop-off toggle happens only after that resumed
goal is actually reached.

### `charging_station`

- Source: `my_py_pkg/charging_station.py`
- Node name: `charging_station`
- Console executable: `charging_station`
- Service: `/recharge`
- Service type: `std_srvs/srv/Trigger`

The service callback logs `正在快充...`, sleeps for approximately three
seconds to simulate charging, and returns a successful response with a clear
completion message. It runs as an independent node, so this deliberate delay
does not block the AGV commander's navigation loop.

### Pure State Logic

ROS-independent helpers live in `my_py_pkg/agv_logic.py`. They cover:

- elapsed-time battery depletion and clamping;
- the one-time low-battery threshold transition;
- normal pickup/drop-off goal toggling;
- preserving and restoring the interrupted goal;
- identity-based ownership of accepted late goal handles, cancellation futures,
  and terminal result futures.

Keeping these transitions independent of ROS allows reliable unit tests on
the Windows editing host.

## Navigation Behavior

Every goal is represented as a `geometry_msgs/msg/PoseStamped` in the `map`
frame with an identity orientation.

The commander submits `NavigateToPose` through the Jazzy
`BasicNavigator.nav_to_pose_client` and advances its send, result, and
cancellation futures in the linear loop. Goal-server availability, send-goal
responses, and cancellation responses have bounded monotonic deadlines.

The commander reads `getFeedback()`, extracts
`current_pose.pose.position`, and computes Euclidean XY distance to the exact
target currently being attempted. If that target-scoped distance is below
`0.25` metres, it requests cancellation of the remaining goal alignment and
treats the position as reached. It never trusts the shared
`distance_remaining` value, because feedback from a preceding cancellation
can arrive during a subsequent submission.

A send-goal response that misses its deadline is not locally canceled or
discarded. A ROS-independent late-goal tracker retains the response future.
Each normal action wait, battery-aware retry pause, recharge wait, and shutdown
drain polls the tracker from the same executor context. If a late response
contains an accepted goal handle, the tracker immediately requests
cancellation on that exact handle and retains the resulting cancel future
until it is acknowledged or fails. Late handles are never installed as the
commander's current active handle.

For ROS 2 Jazzy action-client cleanup, an accepted handle's
`get_result_async()` future is retained and consumed through a non-empty
terminal result response, including after cancellation acknowledgement. A
result exception or empty result is not treated as terminal. Normal navigation
completion and cancellation both use the same ownership-safe result consumer:
an invalid result triggers a bounded goal-specific cancellation and transfers
the exact handle to the late-goal tracker before commander fields are cleared.

Cancellation or result failures are centralized as unresolved ownership. A
handle receives at most one actual shutdown retry; merely waiting for an
already pending future does not consume that retry. Once a non-empty terminal
result has been consumed, the tracker releases the handle and all associated
futures. It retains only a lifetime terminal counter and the last 16
handle-free diagnostic strings, keeping memory bounded across the infinite
pickup/drop-off loop.

If Nav2 reports success, the goal is complete. If it reports failure, the node
keeps the same target, waits three seconds, and retries. A cancellation is
treated as an arrival only when the commander initiated it because the
distance tolerance had already been satisfied; a low-battery cancellation
continues into the charging transition.

## Error Handling and Shutdown

- Nav2 activation is awaited with progress logging.
- If `/recharge` is unavailable, the commander remains in charging state and
  retries without discarding the interrupted target.
- A `/recharge` response has a 10-second monotonic deadline. Timeout cancels
  the local service wait but preserves recovery and the interrupted target.
- A failed recharge response or service exception is logged and retried after
  a short delay.
- A failed navigation goal retains and retries the same target.
- Timed-out send-goal responses and accepted handles' goal-specific
  cancellation and result futures remain owned until terminal cleanup.
  Shutdown interleaves polling with each handle's one permitted retry and
  reports pending response, cancellation, result, and unresolved-handle
  counts when its bounded drain expires.
- Navigation result exceptions and empty responses never discard an accepted
  handle; they initiate bounded cancellation and late cleanup before retry.
- Unexpected missing feedback does not imply arrival; the final task result is
  still checked.
- `Ctrl+C` cancels an active navigation task, destroys the node, and shuts down
  `rclpy`.
- Important transitions use ROS logging: new work goal, battery update,
  low-battery interruption, charging arrival, recharge request/result, resumed
  goal, navigation failure, and retry.

## Package Changes

`setup.py` registers:

```text
agv_commander = my_py_pkg.agv_commander:main
charging_station = my_py_pkg.charging_station:main
```

`package.xml` declares both `nav2_simple_commander` and the directly imported
`nav2_msgs` action package in addition to the existing `rclpy`,
`geometry_msgs`, `std_msgs`, and `std_srvs` dependencies.

The repository does not contain the TurtleBot3 Nav2 parameter file, so this
change does not copy or modify `nav2_params.yaml`. Runtime instructions will
note that the global and local costmap `inflation_radius` may need to be
reduced to `0.12` in the active TurtleBot3 Nav2 configuration if paths are
aborted by inflated obstacles.

No generated files under `build/`, `install/`, or `log/` are modified.

## Test Strategy

Implementation follows test-driven development.

Windows-hosted automated checks cover:

- exact elapsed-time battery drain and lower clamping;
- target-scoped Euclidean distance;
- a single threshold crossing at `20.0%`;
- pickup/drop-off alternation;
- retention of an interrupted target through charging;
- late response retention, accepted-goal cancellation, rejection cleanup, and
  cancellation outcome cleanup using ROS-independent fake futures;
- source contracts for required topic, service, message types, coordinates,
  bounded cancellation, feedback tolerance, recharge timeout, late cleanup,
  simulation time, and ROS logs;
- both console-script registrations and the package dependency;
- all existing `my_py_pkg` tests;
- Python syntax compilation and Git whitespace checks.

Ubuntu 24.04 with ROS 2 Jazzy runtime verification covers:

```bash
cd ~/ros2_ws
source /opt/ros/jazzy/setup.bash
colcon build --packages-select my_py_pkg --symlink-install
source install/setup.bash
colcon test --packages-select my_py_pkg
colcon test-result --verbose
```

With `turtlebot3_world` and Nav2 running, start the two nodes independently:

```bash
ros2 run my_py_pkg charging_station
ros2 run my_py_pkg agv_commander --ros-args -p use_sim_time:=true
```

Runtime acceptance checks confirm:

- `/burger_battery` has type `std_msgs/msg/Float32`;
- `/recharge` has type `std_srvs/srv/Trigger`;
- the AGV alternates between the two work stations;
- low battery cancels the active work goal and diverts to `(0.0, 0.0)`;
- a successful recharge restores `100.0%`;
- the interrupted work goal is resumed before normal alternation continues;
- logs clearly expose the complete interruption and resume sequence.

ROS 2 compilation, Nav2 behavior, and TurtleBot3 simulation cannot be claimed
as verified until these commands are run in the Ubuntu virtual machine.

## Git Delivery

Work is developed on `agent/agv-battery-resume`. After local checks, the
branch is pushed to GitHub, a pull request targeting `main` is created, and the
pull request is merged as requested. GitHub publication requires an installed
and authenticated GitHub CLI session on the Windows host.

## Acceptance Criteria

- The two requested nodes exist in `my_py_pkg` and are runnable through
  `ros2 run`.
- Battery starts at `100.0%`, drains at `0.5%` per second, and publishes once
  per second as `Float32`.
- A level at or below `20.0%` interrupts exactly one active work goal.
- The interrupted goal is preserved through the charging trip and service
  call.
- Successful charging restores the battery to `100.0%` and resumes the saved
  goal.
- Pickup/drop-off alternation continues after the resumed goal completes.
- Navigation uses target-scoped current-pose Euclidean distance for the
  `0.25 m` arrival tolerance and retries failed goals.
- Navigation submission, cancellation, recharge response, and shutdown late
  cleanup are bounded without threads or an outer executor.
- The recharge service logs charging and returns success after its simulated
  delay.
- Existing package functionality remains registered and tested.
- Generated workspace directories remain untouched.
