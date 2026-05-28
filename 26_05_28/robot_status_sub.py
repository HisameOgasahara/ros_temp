# robot_status_sub.py

import rclpy
from rclpy.node import Node
from user_interfaces.msg import RobotStatus


class RobotStatusSubscriber(Node):

    def __init__(self):
        super().__init__('robot_status_subscriber')

        self.status_sub = self.create_subscription(
            RobotStatus,
            'robot_status',
            self.listener_callback,
            10
        )

    def listener_callback(self, msg):

        self.get_logger().info(
            f'Receive: '
            f'{msg.robot_name}, '
            f'{msg.battery}, '
            f'{msg.is_moving}'
        )


def main(args=None):
    rclpy.init(args=args)

    node = RobotStatusSubscriber()

    rclpy.spin(node)

    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()