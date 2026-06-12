# 실행 명령어

## 터미널 1: HTML 서버

```bash
cd user.html이_있는_폴더
python3 -m http.server 8000 --bind 0.0.0.0
```

폰:

```text
http://{{JETSON_IP}}:8000/user.html
```

## 터미널 2: Robot Bringup

```bash
export TURTLEBOT3_MODEL=waffle
ros2 launch turtlebot3_bringup robot.launch.py
```

## 터미널 3: Navigation2

```bash
export TURTLEBOT3_MODEL=waffle
ros2 launch turtlebot3_navigation2 navigation2.launch.py map:=$HOME/map_6f.yaml
```

## 터미널 4: WebSocket/ROS 브릿지

```bash
ros2 run rtreebot delivery_bridge
```

## 터미널 5: 배송 제어

```bash
ros2 run rtreebot delivery_ctrl
```

## 선택: 토픽 확인

```bash
ros2 topic echo /move_request
```

## 선택: HOME 복귀 트리거

```bash
ros2 topic pub --once /move_resume std_msgs/Bool "data: true"
```

## 선택: Mediapipe

```bash
ros2 run camera_ros publisher
ros2 run mediapipe_hand_tracker hand_tracker_node
```
