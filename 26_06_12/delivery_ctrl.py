#!/usr/bin/env python3

'''
[HOME / IDLE]
   ↓ /move_request
[NAVIGATING → ROOM]
   ↓ success
[WAITING /delivery_finish]
   ↓ True
[NAVIGATING → HOME]
   ↓ success
[HOME / IDLE]
'''

import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient

from nav2_msgs.action import NavigateToPose
from geometry_msgs.msg import PoseStamped
from std_msgs.msg import String, Bool, Int32


class DeliveryNavigator(Node):
    def __init__(self):
        super().__init__('delivery_navigator')

        # Action client
        self.client = ActionClient(self, NavigateToPose, 'navigate_to_pose')
        self.get_logger().info('Waiting for Nav2 action server...')
        self.client.wait_for_server()

        # Subscriptions
        self.move_req_sub = self.create_subscription(
            String, '/move_request', self.move_request_callback, 10)

        self.move_resume_sub = self.create_subscription(
            Bool, '/move_resume', self.delivery_finish_callback, 10)
        
        self.move_finish_pub = self.create_publisher(
            Bool, '/move_finish', 10)
        
        self.mediapipe_start_pub = self.create_publisher(
            String, '/mediapipe/start', 10
        )
        
        self.manipulator_start_pub = self.create_publisher(
            Int32, '/manipulator/motion_id', 10
        )
        #### 이 부부은 video_test로 상시 켜기 때문이 필요없을 듯.
        self.cv2_mission_start_pub = self.create_publisher(
            Bool, '/cv2_mission/start', 10
        )
        #### recall 시 inf  video start 및 swich true 추가하기
        self.inference_switch_pub = self.create_publisher(
            Bool, '/inference_switch', 5
        )
        #### recall 시 item_detector start true pub 
        self.item_detector_pub = self.create_publisher(
            Bool, '/item_detector/start', 5
        )       
        # Waypoints (index 0 = Home)
        self.waypoints = {
            "HOME": {'x': 0.013, 'y': -0.608, 'z': 0.02, 'w': 0.999},
            "A":    {'x': 11.928, 'y': -1.442, 'z': 0.805, 'w': 0.592},
            "B":    {'x': 15.66, 'y': 3.16, 'z': 0.203, 'w': 0.97}
        }

        self.current_goal = None
        self.waiting_delivery_finish = False
        self.target_room = None
        self.mode = None
        self.item = None

    # --------------------------------------------------
    # 1. move_request parsing & validation
    # --------------------------------------------------
    def move_request_callback(self, msg):
        try:
            data = msg.data.strip()
            room, item, mode = data.split('_')

            if room not in ['A', 'B']:
                raise ValueError("Invalid room")

            if item not in ['driver', 'block', 'pen', 'wrench']:
                raise ValueError("Invalid item")

            if mode not in ['call', 'recall']:
                raise ValueError("Invalid mode")

            self.get_logger().info(
                f"Valid request received: room={room}, item={item}, mode={mode}"
            )

            self.delivery(room, item, mode)

        except Exception as e:
            self.get_logger().warn(f"Invalid move_request format: {msg.data}")

    # --------------------------------------------------
    # 2. Delivery logic (retry until success)
    # --------------------------------------------------
    def delivery(self, room, item, mode):
        if self.waiting_delivery_finish:
            self.get_logger().warn("Robot is busy. Ignoring request.")
            return

        self.target_room = room
        self.mode = mode
        self.item = item
        self.send_goal(self.waypoints[room])

    def send_goal(self, wp):
        goal = NavigateToPose.Goal()
        goal.pose.header.frame_id = "map"
        goal.pose.header.stamp = self.get_clock().now().to_msg()

        goal.pose.pose.position.x = wp['x']
        goal.pose.pose.position.y = wp['y']
        goal.pose.pose.orientation.z = wp['z']
        goal.pose.pose.orientation.w = wp['w']

        self.get_logger().info("Sending navigation goal...")
        future = self.client.send_goal_async(goal)
        future.add_done_callback(self.goal_response_callback)

    def goal_response_callback(self, future):
        self.goal_handle = future.result()

        if not self.goal_handle.accepted:
            self.get_logger().error("Goal rejected, retrying...")
            self.retry_current_goal()
            return

        result_future = self.goal_handle.get_result_async()
        result_future.add_done_callback(self.result_callback)

    def result_callback(self, future):
        status = future.result().status

        if status == 4:  # SUCCEEDED
            self.get_logger().info("Navigation succeeded.")

            if self.target_room != "HOME" and self.mode != "recall":   ####
                self.get_logger().info("Waiting at destination...")
                self.mediapipe_start_pub.publish(String(data=self.item))
                self.waiting_delivery_finish = True
            elif self.target_room != "HOME" and self.mode == "recall":      ####
                self.get_logger().info("Start Inference & item_detector ... ")
                self.inference_switch_pub.publish(Bool(data=True)) ####
                self.item_detector_pub.publish(Bool(data=True))    ####
                self.waiting_delivery_finish = True
            else:
                self.get_logger().info("Returned to HOME. Waiting for request.")
                
        else:
            self.get_logger().warn("Navigation failed. Retrying...")
            self.retry_current_goal()

    def retry_current_goal(self):
        wp = self.waypoints[self.target_room]
        self.send_goal(wp)

    # --------------------------------------------------
    # 3. Delivery finish → return Home
    # --------------------------------------------------
    def delivery_finish_callback(self, msg):
        if msg.data and self.waiting_delivery_finish:
            self.get_logger().info("Delivery finished. Backing then returning HOME.")
            self.inference_switch_pub.publish(Bool(data=False))   ####
            self.target_room = "HOME"
            self.send_goal(self.waypoints["HOME"])           
            self.move_finish_pub.publish(Bool(data=True))
            self.waiting_delivery_finish = False
        self.waiting_delivery_finish = False
def main(args=None):
    rclpy.init(args=args)
    node = DeliveryNavigator()
    rclpy.spin(node)

if __name__ == '__main__':
    main()
