#! /usr/bin/env python3

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import PoseStamped
from nav2_msgs.action import NavigateToPose
from rclpy.action import ActionClient

class WaypointNavigation(Node):
    def __init__(self):
      super().__init__('patrol_robot')
      self.client = ActionClient(self, NavigateToPose, 'navigate_to_pose')
      
      # Define waypoints
      self.waypoints = [
      	#{'x': 0.013, 'y':-0.608, 'z':0.02, 'w':0.999},
      	{'x': 11.928, 'y':-1.442, 'z':0.805, 'w':0.592}
        #{'x': 15.66, 'y':3.16, 'z':0.203, 'w':0.97} 	
      ] 
      self.current_index = 0
      
      # Wait for the action server to be ready
      self.get_logger().info('Waiting for action server...')
      self.client.wait_for_server()
      
      self.navigate_to_next_waypoint()
      
      
    def navigate_to_next_waypoint(self):
      # Check if there are more waypoints to visit
      if self.current_index >= len(self.waypoints):
         self.get_logger().info('All waypoints visited.')
         rclpy.shutdown()
         return
         
         
      # Get the next waypoint
      waypoint = self.waypoints[self.current_index]
      self.get_logger().info(f"Navigating to waypoint {self.current_index + 1}: {waypoint}")
      
      # Create goal messages
      goal_msg = NavigateToPose.Goal()
      goal_msg.pose.header.frame_id = "map"
      goal_msg.pose.header.stamp = self.get_clock().now().to_msg()
      goal_msg.pose.pose.position.x = waypoint['x']
      goal_msg.pose.pose.position.y = waypoint['y']
      goal_msg.pose.pose.orientation.z = waypoint['z']
      goal_msg.pose.pose.orientation.w = waypoint['w']
      
      # Send goal to the action server
      self.future = self.client.send_goal_async(goal_msg, feedback_callback=self.feedback_callback)
      self.future.add_done_callback(self.goal_response_callback)
      
      
    def feedback_callback(self, feedback_msg):
      self.get_logger().info('Feedback received')
      
      
    def goal_response_callback(self, future):
      goal_handle = future.result()
      if not goal_handle.accepted:
         self.get_logger().error('Goal was rejected.')
         rclpy.shutdown()
         return
         
      self.get_logger().info('Goal accepted')
      result_future = goal_handle.get_result_async()
      result_future.add_done_callback(self.result_callback)
      
      
    def result_callback(self, future):
      result = future.result()
      if result.status == 4: #SUCCEEDED
         self.get_logger().info('Waypoint reached successfully.')
      else:
         self.get_logger().warn('Failed to reach waypoint.')
         
         
      # Proceed to the next waypoint
      self.current_index += 1
      self.navigate_to_next_waypoint()
      
      
def main(args=None):
    rclpy.init(args=args)
    navigator = WaypointNavigation()
    rclpy.spin(navigator)
    
    
if __name__ == '__main__':
    main()
    
    
    
    
    
    
    
    
      
      
      
      
      
      
      
      
      
      
      
      
      
      
      
      
      
      
      
      
      
      
      
      
      
      
      
      
