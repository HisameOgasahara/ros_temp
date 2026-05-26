import rclpy
from rclpy.node import Node
from example_interfaces.srv import AddTwoInts

class SumSever(Node):
    def __init__(self):
        super().__init__('sum_server')
        self.srv = self.create_service(AddTwoInts, 'add_sum', self.add_callback)
        self.get_logger().info('Service "add_sum" is ready.')

    def add_callback(self, request, response):
        self.get_logger().info(f"Incoming request: a={request.a}, b={request.b}, sum={response.sum}")
        response.sum = request.a + request.b
        return response

def main():
    rclpy.init()
    node = SumSever()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
