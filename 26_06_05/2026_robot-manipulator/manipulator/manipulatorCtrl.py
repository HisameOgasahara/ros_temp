#!/usr/bin/env python3

import json
import time
import os
import rclpy
from rclpy.node import Node
from std_msgs.msg import Int32, Bool
from dynamixel_sdk_custom_interfaces.msg import SetPosition

DXL_IDS = [11, 12, 13, 14, 15]


class MotionPlayer(Node):
    def __init__(self):
        super().__init__('motion_player')

        # -----------------------
        # Load motion json
        # -----------------------
        current_dir = os.path.dirname(os.path.abspath(__file__))
        json_path = os.path.join(current_dir, 'saved_motions.json')
        with open(json_path, 'r') as f:
            self.data = json.load(f)

        self.motions = self.data['motions']
        self.times = self.data['times']
        self.next_motions = self.data['next_motions']

        # -----------------------
        # Publisher / Subscriber
        # -----------------------
        self.pos_pub = self.create_publisher(
            SetPosition, '/set_position', 10
        )

        self.move_resume_pub = self.create_publisher(
            Bool, '/move_resume', 10
        )

        self.create_subscription(
            Int32,
            '/manipulator/motion_id',
            self.motion_id_callback,
            10
        )

        self.is_playing = False
        self.get_logger().info('MotionPlayer node ready')

    # -----------------------
    # Motion ID callback
    # -----------------------
    def motion_id_callback(self, msg):
        motion_id = msg.data

        if motion_id <= 0:
            self.get_logger().warn('motion_id must be >= 1')
            return

        if self.is_playing:
            self.get_logger().warn('Motion already playing, ignore command')
            return

        self.get_logger().info(f'Start motion {motion_id}')
        self.execute_motion(motion_id)

    # -----------------------
    # Execute motion
    # -----------------------
    def execute_motion(self, motion_id):
        self.is_playing = True

        idx = motion_id - 1

        if idx >= len(self.motions):
            self.get_logger().error('Invalid motion id')
            self.is_playing = False
            return

        steps = self.motions[idx]
        times = self.times[idx]

        for step_idx, joint_positions in enumerate(steps):
            move_time, stop_time = times[step_idx]

            self.get_logger().info(
                f'Motion {motion_id} | Step {step_idx} | move={move_time}s stop={stop_time}s'
            )

            # 각 관절에 목표값 발행
            for j, pos in enumerate(joint_positions):
                msg = SetPosition()
                msg.id = DXL_IDS[j]
                msg.position = int(pos)
                msg.runtime = float(move_time)
                self.pos_pub.publish(msg)

            # 이동 시간 대기
            time.sleep(move_time)

            # 멈춤 시간 대기
            if stop_time > 0.0:
                time.sleep(stop_time)

        # -----------------------
        # Next motion
        # -----------------------
        next_motion = self.next_motions[idx]

        self.is_playing = False

        if next_motion != 0:
            self.get_logger().info(f'Auto start next motion {next_motion}')
            self.execute_motion(next_motion)
        else:
            self.get_logger().info('Motion sequence finished')
            self.move_resume_pub.publish(Bool(data=True))

def main(args=None):
    rclpy.init(args=args)
    node = MotionPlayer()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()

