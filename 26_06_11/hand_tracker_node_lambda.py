#!/usr/bin/env python3

import json
import rclpy
from rclpy.node import Node
from std_msgs.msg import String, Int32
from sensor_msgs.msg import CompressedImage
import cv2
import mediapipe as mp
import numpy as np


class HandTrackerNode(Node):
    def __init__(self):
        super().__init__('hand_tracker_node_lambda')
        self.declare_parameter(
            'motion_map_json',
            '{"block": 1, "wrench": 2, "driver": 3, "pen": 4}'
        )
        self.declare_parameter('thumbs_up_required_count', 5)
        self.declare_parameter('show_debug_window', True)

        self.get_logger().info(
            "MediaPipe Lambda Gesture Node Started"
        )

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
        # Practice values used on Jetson:
        # sys.path.append('/home/jetson/mp_env/lib/python3.8/site-packages')
        self.motion_map = json.loads(
            self.get_parameter(
                'motion_map_json'
            ).get_parameter_value().string_value
        )
        self.items = list(self.motion_map.keys())
        self.item = None
        self.lambda_sign_count = 0

    def start_callback(self, msg):
        if msg.data not in self.items:
            return
        self.get_logger().info("Start mediaPipe lambda gesture detection!")
        self.mediapipe_start = True
        self.item = msg.data

    def detect_gesture(self, landmarks):
        thumb_tip = landmarks.landmark[self.mp_hands.HandLandmark.THUMB_TIP]
        thumb_mcp = landmarks.landmark[self.mp_hands.HandLandmark.THUMB_MCP]
        index_tip = landmarks.landmark[
            self.mp_hands.HandLandmark.INDEX_FINGER_TIP
        ]
        index_mcp = landmarks.landmark[
            self.mp_hands.HandLandmark.INDEX_FINGER_MCP
        ]
        middle_tip = landmarks.landmark[
            self.mp_hands.HandLandmark.MIDDLE_FINGER_TIP
        ]
        middle_pip = landmarks.landmark[
            self.mp_hands.HandLandmark.MIDDLE_FINGER_PIP
        ]
        ring_tip = landmarks.landmark[
            self.mp_hands.HandLandmark.RING_FINGER_TIP
        ]
        ring_pip = landmarks.landmark[
            self.mp_hands.HandLandmark.RING_FINGER_PIP
        ]
        pinky_tip = landmarks.landmark[self.mp_hands.HandLandmark.PINKY_TIP]
        pinky_pip = landmarks.landmark[self.mp_hands.HandLandmark.PINKY_PIP]

        tip_dx = thumb_tip.x - index_tip.x
        tip_dy = thumb_tip.y - index_tip.y
        tip_distance = (tip_dx * tip_dx + tip_dy * tip_dy) ** 0.5

        tip_distance_max = 0.08
        base_distance_min = 0.08
        vertical_margin = 0.03

        tips_are_close = tip_distance <= tip_distance_max
        tips_are_above_bases = (
            thumb_tip.y < thumb_mcp.y - vertical_margin and
            index_tip.y < index_mcp.y - vertical_margin
        )
        left_palm_lambda_direction = index_mcp.x < thumb_mcp.x
        bases_are_separated = (
            abs(thumb_mcp.x - index_mcp.x) >= base_distance_min
        )
        other_fingers_are_folded = (
            middle_tip.y > middle_pip.y and
            ring_tip.y > ring_pip.y and
            pinky_tip.y > pinky_pip.y
        )

        if (
            tips_are_close and
            tips_are_above_bases and
            left_palm_lambda_direction and
            bases_are_separated and
            other_fingers_are_folded
        ):
            return "lambda_sign"
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
                self.mp_drawing.draw_landmarks(
                    frame,
                    hand_landmarks,
                    self.mp_hands.HAND_CONNECTIONS
                )
                gesture_msg.data = self.detect_gesture(hand_landmarks)

        if gesture_msg.data == "lambda_sign":
            self.lambda_sign_count += 1
        else:
            self.lambda_sign_count = 0
        required_count = self.get_parameter(
            'thumbs_up_required_count'
        ).get_parameter_value().integer_value
        if self.lambda_sign_count >= required_count:
            motion_id = int(self.motion_map.get(self.item, 0))
            self.manipulator_pub.publish(Int32(data=motion_id))
            self.get_logger().info("Stopping mediaPipe...")
            self.mediapipe_start = False
            self.item = None
            self.lambda_sign_count = 0
            if self.get_parameter(
                'show_debug_window'
            ).get_parameter_value().bool_value:
                cv2.destroyAllWindows()

        if self.get_parameter(
            'show_debug_window'
        ).get_parameter_value().bool_value:
            cv2.imshow("MediaPipe Lambda Gesture from CompressedImage", frame)
            if cv2.waitKey(1) & 0xFF == 27:
                self.get_logger().info("Stopping mediaPipe...")
                cv2.destroyAllWindows()
                self.mediapipe_start = False

    def destroy_node(self):
        self.hands.close()
        if self.get_parameter(
            'show_debug_window'
        ).get_parameter_value().bool_value:
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
