

import cv2
import rclpy
import numpy as np
from rclpy.node import Node
from sensor_msgs.msg import CompressedImage

class VideoTest(Node):
    def __init__(self):
        super().__init__('video_test_node')
        self.videosubscriber = self.create_subscription(
            CompressedImage,
            '/camera',
            self.videosubscriber_callback,
            10
        )

    def videosubscriber_callback(self, msg):
        try: 
            np_arr = np.frombuffer(msg.data, np.uint8)
            src = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        except Exception as e:
            self.get_logger().error(f"Error decoding compressed image: {e}")
            return
        
        cv2.imshow('video', src)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            cv2.destroyAllWindows()
            self.destroy_node()
            rclpy.shutdown()

def main():
    rclpy.init()
    node = VideoTest()
    try: 
        rclpy.spin(node)
    except KeyboardInterrupt:
        node.get_logger().info("Keyboard Interrupt (SIGINT)")
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()