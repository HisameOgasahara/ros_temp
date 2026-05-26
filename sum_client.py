import rclpy
from rclpy.node import Node
from example_interfaces.srv import AddTwoInts

class SumClient(Node):
    def __init__(self):
        super().__init__('sum_client')
        self.client = self.create_client(AddTwoInts, 'add_sum')
        while not self.client.wait_for_service(timeout_sec=1.0):
            self.get_logger().info('Waiting for service...')
            self.send_request()

    def send_request(self):
        request = AddTwoInts.Request()
        request.a = 8
        request.b = 8
        self.future = self.client.call_async(request)
        self.future.add_done_callback(self.callback)

    def callback(self, future):
        try:
            response = future.result()
            self.get_logger().info(f"Result: {response.sum}")
        except Exception as e:
            self.get_logger().error(f"Service call failed: {e}")
    
def main():
    rclpy.init()
    node = SumClient()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':    
    main()