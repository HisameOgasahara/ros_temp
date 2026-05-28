# robot_status_pub.py

import rclpy
from rclpy.node import Node
from user_interfaces.msg import RobotStatus


class RobotStatusPublisher(Node):

    def __init__(self):
        super().__init__('robot_status_publisher')

        self.status_pub = self.create_publisher(
            RobotStatus,
            'robot_status',
            10
        )

        self.timer = self.create_timer(1.0, self.pub_status)

    def pub_status(self):
        msg = RobotStatus()

        msg.robot_name = "RtreeBot"
        msg.battery = 90.9
        msg.is_moving = True

        self.status_pub.publish(msg)

        self.get_logger().info(
            f'Publish: {msg.robot_name}, '
            f'{msg.battery}, '
            f'{msg.is_moving}'
        )


def main(args=None):
    rclpy.init(args=args)

    node = RobotStatusPublisher()

    rclpy.spin(node)

    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()