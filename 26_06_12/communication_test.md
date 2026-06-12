# 통신 테스트 순서

로봇 이동 없이, 핸드폰 `user.html`에서 Jetson ROS2 토픽까지 명령이 도착하는지만 확인합니다.

## 1. 터미널 1: HTML 서버

`user.html`이 있는 폴더에서 실행합니다.

```bash
cd customized_files
python3 -m http.server 8000 --bind 0.0.0.0
```

폰 브라우저에서 엽니다.

```text
http://{{JETSON_IP}}:8000/user.html
```

예시:

```text
http://10.59.121.144:8000/user.html
```

## 2. 터미널 2: WebSocket/ROS 브릿지

```bash
cd ~/turtlebot3_ws
source install/setup.bash
ros2 run rtreebot delivery_bridge
```

## 3. 터미널 3: ROS 토픽 확인

```bash
ros2 topic echo /move_request
```

## 4. 폰에서 주문

폰에서 `user.html`을 열고 방/물품을 선택한 뒤 주문합니다.

성공하면 터미널 3에 다음처럼 출력됩니다.

```text
data: A_driver_call
```

또는 선택에 따라:

```text
data: B_pen_call
```

## 주의

이 테스트에서는 `delivery_ctrl`을 실행하지 않습니다.

```bash
ros2 run rtreebot delivery_ctrl
```

위 명령은 Nav2가 준비된 상태에서 `/move_request`를 받으면 실제 이동 goal을 보냅니다.
