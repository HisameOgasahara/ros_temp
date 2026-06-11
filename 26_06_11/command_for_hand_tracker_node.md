### 1) ros2 run camera_ros publisher
### 2) ros2 launch manipulator manipulatorCtrl.launch.py
### 3) ros2 run mediapipe_hand_tracker hand_tracker_node
### 4) (드라이버라면) ros2 topic pub -1 /mediapipe/start std_msgs/msg/String "{data: driver}" 