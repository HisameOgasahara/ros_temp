

import cv2
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import CompressedImage

def gstreamer_pipeline(
    sensor_id=0,
    capture_width=1280,
    capture_height=720,
    display_width=1280,
    display_height=720,
    framerate=30,
    flip_method=2, #상하좌우 반전. 2는 180도 회전, 1은 90도 회전    
):
    return (
        "nvarguscamerasrc sensor-id=%d ! " 
        "video/x-raw(memory:NVMM), width=(int)%d, height=(int)%d, "
        "format=(string)NV12, framerate=(fraction)%d/1 ! "
        "nvvidconv flip-method=%d ! "
        "video/x-raw, width=(int)%d, height=(int)%d, format=(string)BGRx ! "
        "videoconvert ! "
        "video/x-raw, format=(string)BGR ! appsink"
        % (
            sensor_id,
            capture_width,
            capture_height,
            framerate,
            flip_method,
            display_width,
            display_height,
        )
    )
    

class CSIVideoPublisher(Node):
    def __init__(self):
        super().__init__('csi_video_publisher')
        
        self.publisher = self.create_publisher(
            CompressedImage, 'camera', 5
        )

        pipeline = gstreamer_pipeline()
        self.get_logger().info(f"Gstreamer pipeline:\n{pipeline}")

        self.cap = cv2.VideoCapture(
            pipeline, cv2.CAP_GSTREAMER
        )

        if not self.cap.isOpened():
            self.get_logger().error("Failed to CSI camera with Gstreamer")
            raise RuntimeError("CSI camera open failed")
        
        self.timer = self.create_timer(1.0/30.0, self.timer_callback)
        self.get_logger().info("CSI camera video publisher started")

    def timer_callback(self):
        ret, frame = self.cap.read()
        if not ret:
            self.get_logger().warn("Frame capture failed")
            return
        success, jpg = cv2.imencode(
            ".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80]
        )
        if not success:
            return
        
        msg = CompressedImage()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.format = "jpeg"
        msg.data = jpg.tobytes()

        self.publisher.publish(msg)

def main():
    rclpy.init()
    node = CSIVideoPublisher()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    
    node.cap.release()
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()