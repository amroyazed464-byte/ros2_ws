# Battery, LED Panel, and Turtle Controller Design

## Goal

Add three ROS 2 Jazzy Python nodes to `my_py_pkg` that simulate an automatic
battery charge cycle, expose battery exhaustion through LED 3, and teleport
the default turtlesim turtle between a safe charging position and the pool
center. The simulator and all three nodes must be runnable in separate
Terminator panes so their synchronized behavior can be recorded.

## Architecture and Data Flow

The nodes form a one-way pipeline:

```text
battery --/battery_level--> led_panel --/led_panel--> turtle_controller
                                                        |
                                                        v
                                      /turtle1/teleport_absolute
```

Each node has one responsibility:

- `battery` owns the numeric battery level and charge/discharge state.
- `led_panel` translates battery boundary events into a latched LED state.
- `turtle_controller` translates LED 3 state transitions into turtlesim
  `TeleportAbsolute` service requests.

This keeps the transport contracts visible and independently testable while
using only standard ROS 2 interfaces.

## Node Contracts

### `battery`

- Node and executable name: `battery`
- Publishes: `/battery_level`
- Message type: `std_msgs/msg/Int32`
- QoS: reliable, transient-local, depth 1
- Parameters:
  - `initial_level` (`int`, default `100`, valid range `0..100`)
  - `update_period` (`double`, default `1.0`, must be greater than `0.0`)
  - `step` (`int`, default `10`, valid range `1..100`)
- Startup mode: discharge unless `initial_level` is `0`, in which case charge
- Behavior:
  - Publish the initial level immediately.
  - On each timer tick, decrease the level while discharging or increase it
    while charging, clamping the result to `0..100`.
  - Switch to charging after publishing `0` and switch to discharging after
    publishing `100`.
  - Log every level update with either `Discharging` or `Charging` so the
    terminal video exposes the state transition.
- Invalid parameters cause node construction to fail with a clear message.

### `led_panel`

- Node and executable name: `led_panel`
- Subscribes: `/battery_level` as `std_msgs/msg/Int32`
- Publishes: `/led_panel` as `std_msgs/msg/UInt8MultiArray`
- Subscription QoS: reliable, transient-local, depth 1
- Publisher QoS: reliable, transient-local, depth 1
- LED payload: exactly four entries representing LEDs 0 through 3; values
  are `0` for off and `1` for on.
- Behavior:
  - Start with all LEDs off.
  - Clamp received battery values to `0..100` for boundary evaluation and log
    a warning when an out-of-range value is received.
  - When level reaches `0`, latch LED 3 on and publish `[0, 0, 0, 1]`.
  - Keep LED 3 on throughout charging.
  - When level reaches `100`, latch LED 3 off and publish `[0, 0, 0, 0]`.
  - Republish the current array for every battery update, but emit a distinct
    state-change log only when LED 3 changes.

### `turtle_controller`

- Node and executable name: `turtle_controller`
- Subscribes: `/led_panel` as `std_msgs/msg/UInt8MultiArray`
- Subscription QoS: reliable, transient-local, depth 1
- Service client: `/turtle1/teleport_absolute`
- Service type: `turtlesim/srv/TeleportAbsolute`
- Targets:
  - LED 3 on: `(x=11.0, y=11.0, theta=0.0)`
  - LED 3 off: `(x=5.5, y=5.5, theta=0.0)`
- Behavior:
  - Ignore messages containing fewer than four entries and log a warning.
  - Treat only the value `1` as on; treat `0` as off; reject other LED 3
    values with a warning.
  - Call the service on the first valid LED message and on each subsequent
    LED 3 transition. Repeated identical states do not issue duplicate calls.
  - Wait asynchronously for service availability without blocking subscription
    processing. If turtlesim starts late, retain the most recent requested
    target and send it when the service becomes available.
  - Allow at most one service request in flight. If the LED changes while a
    request is pending, send the latest target after that request completes.
  - Log requested and completed teleports; log service errors without crashing.

## Package Registration and Dependencies

`setup.py` registers these console scripts:

```text
led_panel = my_py_pkg.led_panel:main
battery = my_py_pkg.battery:main
turtle_controller = my_py_pkg.turtle_controller:main
```

The existing `std_msgs`, `rclpy`, and `turtlesim` dependencies in
`package.xml` cover the implementation. No new third-party dependency is
required.

## Test Strategy

Pure logic is separated from ROS plumbing where useful so tests can run on the
Windows editing host without a ROS installation. Automated tests cover:

- battery clamping, direction changes, and exact `0`/`100` boundary behavior;
- LED 3 latching from exhaustion until full charge;
- controller validation and target selection;
- suppression of duplicate LED states;
- all three `console_scripts` registration entries.

Ubuntu ROS 2 validation covers:

- `colcon build --packages-select my_py_pkg --symlink-install`;
- discovery of all three executables;
- topic types and the teleport service type;
- the turtle moving to `(11.0, 11.0)` when LED 3 turns on and returning to
  `(5.5, 5.5)` when it turns off;
- matching battery, LED, and controller logs during at least one complete
  discharge-and-charge cycle.

## Demonstration and Video Export

Use Terminator with four panes to run:

1. `ros2 run turtlesim turtlesim_node`
2. `ros2 run my_py_pkg led_panel`
3. `ros2 run my_py_pkg battery`
4. `ros2 run my_py_pkg turtle_controller`

Arrange Terminator and the turtlesim window so both the turtle and terminal
logs are visible. Record at least one transition to the safe corner and one
return to center. Export the recording as an MP4 file. Video capture is a
desktop-environment activity and must be performed in the Ubuntu 24.04 VM
where ROS 2 Jazzy, Terminator, turtlesim, and a recorder are available.

## Acceptance Criteria

- The three requested source files exist under `my_py_pkg` and are registered.
- The package builds on Ubuntu 24.04 with ROS 2 Jazzy.
- `/battery_level` and `/led_panel` use the specified standard message types.
- LED 3 remains on from empty battery through charging until the level is full.
- `turtle1` teleports to `(11.0, 11.0)` when LED 3 turns on and to
  `(5.5, 5.5)` when it turns off.
- Duplicate LED messages do not cause repeated teleport requests.
- Terminal logs visibly match the turtle behavior.
- An MP4 recording containing the simulator and logs is exported from the
  Ubuntu desktop environment.

