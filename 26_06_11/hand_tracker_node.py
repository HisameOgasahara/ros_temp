#!/home/jetson/mp_env/bin/python3

import sys
sys.path.append('/home/jetson/mp_env/lib/python3.8/site-packages')
import rclpy
from rclpy.node import Node
from std_msgs.msg import String, Int32
from sensor_msgs.msg import CompressedImage
import cv2
import mediapipe as mp
import numpy as np


class HandTrackerNode(Node):
    def __init__(self):
        super().__init__('hand_tracker_node')
        self.get_logger().info("MediaPipe Hand Tracker Node (CompressedImage Subscriber) Started")

        self.manipulator_pub = self.create_publisher(
            Int32, '/manipulator/motion_id', 10
        )

        self.video_sub = self.create_subscription(
            CompressedImage,
            '/camera',
            self.image_callback,
            10
        )

        self.mediapipe_start_sub = self.create_subscription(
            String,
            '/mediapipe/start',
            self.start_callback,
            10
        )

        self.mp_hands = mp.solutions.hands
        self.mp_drawing = mp.solutions.drawing_utils
        self.hands = self.mp_hands.Hands(
            max_num_hands=1,
            min_detection_confidence=0.6,
            min_tracking_confidence=0.5
        )
        self.mediapipe_start = False
        self.items = ['driver', 'pen', 'block', 'wrench']
        self.item = None
        self.thumbs_up_count = 0

    def start_callback(self, msg):
        if msg.data not in self.items:
            return
        self.get_logger().info("Start mediaPipe gesture detection!")
        self.mediapipe_start = True
        self.item = msg.data

    def detect_gesture(self, landmarks):
        thumb_tip = landmarks.landmark[self.mp_hands.HandLandmark.THUMB_TIP]
        thumb_ip = landmarks.landmark[self.mp_hands.HandLandmark.THUMB_IP]
        index_tip = landmarks.landmark[self.mp_hands.HandLandmark.INDEX_FINGER_TIP]
        middle_tip = landmarks.landmark[self.mp_hands.HandLandmark.MIDDLE_FINGER_TIP]
        ring_tip = landmarks.landmark[self.mp_hands.HandLandmark.RING_FINGER_TIP]
        pinky_tip = landmarks.landmark[self.mp_hands.HandLandmark.PINKY_TIP]

        if thumb_tip.y < thumb_ip.y and index_tip.y > thumb_ip.y:
            return "thumbs_up"
        return "unknown"

    def image_callback(self, msg: CompressedImage):
        if not self.mediapipe_start:
            return
        # CompressedImage -> OpenCV BGR
        np_arr = np.frombuffer(msg.data, np.uint8)
        frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        if frame is None:
            self.get_logger().warn("Failed to decode compressed image")
            return

        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.hands.process(rgb_frame)

        gesture_msg = String()
        gesture_msg.data = "unknown"

        if results.multi_hand_landmarks:
            for hand_landmarks in results.multi_hand_landmarks:
                self.mp_drawing.draw_landmarks(frame, hand_landmarks, self.mp_hands.HAND_CONNECTIONS)
                gesture_msg.data = self.detect_gesture(hand_landmarks)

        if gesture_msg.data == "thumbs_up":
            self.thumbs_up_count += 1
        else:
            self.thumbs_up_count = 0
        if self.thumbs_up_count >= 5:
            motion_id = 0
            if self.item == "pen":
                motion_id = 4
            elif self.item == "driver":
                motion_id = 3
            elif self.item == "block":
                motion_id = 1
            elif self.item == "wrench":
                motion_id = 2
            self.manipulator_pub.publish(Int32(data=motion_id))
            self.get_logger().info("Stopping mediaPipe...")
            self.mediapipe_start = False
            self.item = None
            self.thumbs_up_count = 0
            cv2.destroyAllWindows()

        cv2.imshow("MediaPipe Hands from CompressedImage", frame)
        if cv2.waitKey(1) & 0xFF == 27:
            self.get_logger().info("Stopping mediaPipe...")
            cv2.destroyAllWindows()
            self.mediapipe_start = False

    def destroy_node(self):
        self.hands.close()
        cv2.destroyAllWindows()
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = HandTrackerNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
