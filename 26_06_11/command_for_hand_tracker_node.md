ros2 run camera_ros publisher
ros2 launch manipulator manipulatorCtrl.launch.py
ros2 run mediapipe_hand_tracker hand_tracker_node
(드라이버라면) ros2 topic pub -1 /mediapipe/start std_msgs/msg/String "{data: driver}" 