"""Cascaded service node that spawns and removes a turtlesim turtle."""

from threading import Lock

import rclpy
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from std_srvs.srv import SetBool
from turtlesim.srv import Kill, Spawn

from my_py_pkg.turtle_summoner_logic import validate_position


class TurtleSummoner(Node):
    """Expose a boolean service that manages one named turtlesim turtle."""

    def __init__(self):
        super().__init__('turtle_summoner')
        self.declare_parameter('x', 7.3)
        self.declare_parameter('y', 3.8)
        self.declare_parameter('turtle_name', 'summoned_turtle')

        self._callback_group = ReentrantCallbackGroup()
        self._spawn_client = self.create_client(
            Spawn, '/spawn', callback_group=self._callback_group
        )
        self._kill_client = self.create_client(
            Kill, '/kill', callback_group=self._callback_group
        )
        self._service = self.create_service(
            SetBool,
            '/turtle_summoner',
            self._handle_request,
            callback_group=self._callback_group,
        )
        self._spawned = False
        self._operation_lock = Lock()
        self._operation_pending = False

        self._remove_default_turtle()

    def _remove_default_turtle(self) -> None:
        """Request removal of turtle1 without making startup failure fatal."""
        if not self._kill_client.wait_for_service(timeout_sec=3.0):
            self.get_logger().warning('The /kill service was unavailable at startup')
            return

        request = Kill.Request()
        request.name = 'turtle1'
        future = self._kill_client.call_async(request)
        future.add_done_callback(self._log_startup_kill_failure)

    def _log_startup_kill_failure(self, future) -> None:
        """Log a warning if the optional startup cleanup cannot complete."""
        try:
            future.result()
        except Exception as error:
            self.get_logger().warning(f'Unable to remove turtle1 at startup: {error}')

    def _parameters(self) -> tuple[float, float, str]:
        """Read configured coordinates and turtle name with numeric conversion."""
        x = float(self.get_parameter('x').value)
        y = float(self.get_parameter('y').value)
        turtle_name = str(self.get_parameter('turtle_name').value)
        return x, y, turtle_name

    async def _handle_request(
        self, request: SetBool.Request, response: SetBool.Response
    ) -> SetBool.Response:
        """Dispatch the requested spawn or kill operation and await its result."""
        try:
            x, y, turtle_name = self._parameters()
        except (TypeError, ValueError) as error:
            response.success = False
            response.message = f'Invalid turtle position: {error}'
            return response

        valid, message = validate_position(x, y)
        if not valid:
            response.success = False
            response.message = f'Invalid turtle position: {message}'
            return response

        with self._operation_lock:
            if self._operation_pending:
                response.success = False
                response.message = 'Another turtle operation is already in progress'
                return response

            if request.data:
                if self._spawned:
                    response.success = False
                    response.message = f'{turtle_name} is already spawned'
                    return response
            elif not self._spawned:
                response.success = False
                response.message = f'{turtle_name} is not spawned'
                return response

            self._operation_pending = True

        try:
            if request.data:
                return await self._spawn_turtle(x, y, turtle_name, response)
            return await self._kill_turtle(turtle_name, response)
        finally:
            with self._operation_lock:
                self._operation_pending = False

    async def _spawn_turtle(
        self, x: float, y: float, turtle_name: str, response: SetBool.Response
    ) -> SetBool.Response:
        """Spawn the configured turtle and update state only after success."""
        if not self._spawn_client.wait_for_service(timeout_sec=3.0):
            response.success = False
            response.message = 'The /spawn service is unavailable'
            return response

        request = Spawn.Request()
        request.x = x
        request.y = y
        request.theta = 0.0
        request.name = turtle_name
        try:
            spawn_response = await self._spawn_client.call_async(request)
        except Exception as error:
            response.success = False
            response.message = f'Failed to spawn {turtle_name}: {error}'
            return response

        if spawn_response.name != turtle_name:
            response.success = False
            response.message = (
                f'Spawn response name {spawn_response.name!r} did not match '
                f'requested name {turtle_name!r}'
            )
            return response

        with self._operation_lock:
            self._spawned = True
        response.success = True
        response.message = f'Spawned {turtle_name}'
        return response

    async def _kill_turtle(
        self, turtle_name: str, response: SetBool.Response
    ) -> SetBool.Response:
        """Kill the configured turtle and update state only after success."""
        if not self._kill_client.wait_for_service(timeout_sec=3.0):
            response.success = False
            response.message = 'The /kill service is unavailable'
            return response

        request = Kill.Request()
        request.name = turtle_name
        try:
            await self._kill_client.call_async(request)
        except Exception as error:
            response.success = False
            response.message = f'Failed to kill {turtle_name}: {error}'
            return response

        with self._operation_lock:
            self._spawned = False
        response.success = True
        response.message = f'Removed {turtle_name}'
        return response


def main(args=None) -> None:
    """Run the turtle summoner with an executor safe for nested services."""
    rclpy.init(args=args)
    node = TurtleSummoner()
    executor = MultiThreadedExecutor(num_threads=2)
    executor.add_node(node)
    try:
        executor.spin()
    finally:
        executor.shutdown()
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
