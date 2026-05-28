import rclpy
from rclpy.node import Node
from user_interfaces.srv import AddTwoInts


class AddClient(Node):
    def __init__(self):
        super().__init__('add_client')
        self.client = self.create_client(
            AddTwoInts,
            'add_two_ints'
        )

        while not self.client.wait_for_service(timeout_sec=1.0):
            self.get_logger().info('waiting for service...')
        self.send_request()

    def send_request(self):
        self.request = AddTwoInts.Request()
        self.request.a = 100
        self.request.b = 200

        self.future = self.client.call_async(self.request)
        self.future.add_done_callback(self.callback)

    def callback(self, future):
        try:
            response = future.result()
            self.get_logger().info(f'Result: {response.sum}')
        except Exception as e:
            self.get_logger().error(f'Service call failed: {e}')


def main():
    rclpy.init()
    node = AddClient()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
