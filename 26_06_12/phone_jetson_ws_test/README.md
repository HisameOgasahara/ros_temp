# Phone-Jetson WebSocket Test

이 폴더는 현재 ROS2 프로젝트와 무관하게, 핸드폰 브라우저와 Jetson Nano 사이의 WebSocket 통신만 확인하기 위한 테스트 파일입니다.

## 1. Jetson Nano에서 실행

Jetson Nano 터미널에서:

```bash
python3 -m pip install websockets
python3 ws_echo_server_jetson.py
```

정상 실행되면 아래 두 서버가 같이 열립니다.

```text
WebSocket: ws://0.0.0.0:3000
HTML page: http://0.0.0.0:8000/phone_ws_client.html
```

## 2. 핸드폰에서 열기

핸드폰 브라우저에서 아래 주소로 들어가고 `Send Test Message` 버튼을 누릅니다.

```text
http://10.59.121.144:8000/phone_ws_client.html
```

현재 기본 접속 주소:

```text
ws://10.59.121.144:3000
```

이 주소는 `custom.md`에 적힌, 핸드폰 핫스팟 Wi-Fi에 접속한 Jetson Nano의 IP입니다.

## 성공 기준

- 핸드폰 화면에 `connected`가 표시됨
- 버튼을 누르면 핸드폰 화면에 `received: echo: hello from phone` 표시
- Jetson 터미널에 `received: hello from phone` 출력

## 실패 시 확인

Jetson에서 진단 모드 실행:

```bash
python3 ws_echo_server_jetson.py --diagnose
```

Jetson에서 현재 IP 확인:

```bash
hostname -I
```

Jetson에서 3000번/8000번 포트가 열렸는지 확인:

```bash
ss -ltnp | grep -E '3000|8000'
```

`0.0.0.0:3000`과 `0.0.0.0:8000`으로 떠야 핸드폰에서 접속할 수 있습니다.

핸드폰 HTML은 연결 실패 시 다음 정보를 화면에 출력합니다.

- 연결 타임아웃 여부
- WebSocket close code
- 현재 접속 대상 URL
- Jetson IP, 포트 바인딩, 핫스팟 통신 차단 확인 힌트
