# Phone-Jetson WebSocket Test

이 폴더는 현재 ROS2 프로젝트와 무관하게, 핸드폰 브라우저와 Jetson Nano 사이의 WebSocket 통신만 확인하기 위한 테스트 파일입니다.

## 성공한 방식

Jetson이 HTML을 HTTP로 제공하고, 핸드폰은 그 URL로 접속합니다.

```text
Phone browser
-> http://{{JETSON_IP}}:8000/phone_ws_client.html
-> ws://{{JETSON_IP}}:3000
-> Jetson WebSocket server
```

`{{JETSON_IP}}`에는 Jetson에서 서버 실행 시 출력되는 핫스팟/Wi-Fi IP를 넣습니다.

성공 당시 예시:

```text
{{JETSON_IP}} = 10.59.121.144
```

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

서버 출력 중 아래 부분을 봅니다.

```text
hostname -I: {{JETSON_IP}} ...

Use this on the phone browser:
  http://{{JETSON_IP}}:8000/phone_ws_client.html
This page will connect WebSocket to:
  ws://{{JETSON_IP}}:3000
```

폰에서는 `Use this on the phone browser:` 아래에 출력된 주소를 그대로 입력하면 됩니다.

## 2. 핸드폰에서 열기

핸드폰 브라우저 주소창에 아래 주소를 입력합니다.

```text
http://{{JETSON_IP}}:8000/phone_ws_client.html
```

예시:

```text
http://10.59.121.144:8000/phone_ws_client.html
```

화면에서 `Send Test Message` 버튼을 누릅니다.

## 성공 기준

- 핸드폰 화면에 `connected` 표시
- 핸드폰 화면에 `received: echo: hello from phone` 표시
- Jetson 터미널에 `received: hello from phone` 출력

## 실패 원인과 대처

### 1. 폰에서 HTML 파일을 직접 열면 실패할 수 있음

증상:

```text
page origin: content://...
closed: code=1006
```

원인:

폰 파일 앱/브라우저가 HTML을 `content://...` 출처로 열면 외부 `ws://{{JETSON_IP}}:3000` WebSocket 연결이 실패할 수 있습니다. 일반적인 fetch/ajax CORS라기보다는 모바일 브라우저의 로컬 파일/content origin 보안 정책 문제에 가깝습니다.

대처:

HTML을 폰에서 파일로 직접 열지 말고, Jetson에서 HTTP로 제공합니다.

```bash
python3 ws_echo_server_jetson.py
```

폰에서는 아래처럼 HTTP URL로 접속합니다.

```text
http://{{JETSON_IP}}:8000/phone_ws_client.html
```

### 2. `404 File not found`

증상:

```text
GET /phone_ws_client.html HTTP/1.1 404
```

원인:

HTTP 서버가 보고 있는 폴더에 `phone_ws_client.html`이 없습니다.

대처:

최신 `ws_echo_server_jetson.py`는 `phone_ws_client.html`이 없으면 자동 생성합니다. 최신 파일을 Jetson에 복사한 뒤 다시 실행합니다.

## 테스트 코드 설명

`ws_echo_server_jetson.py`는 Jetson에서 실행하는 단일 테스트 서버입니다.

실행하면 다음을 함께 수행합니다.

- Jetson의 Python 실행 경로와 버전 출력
- Jetson의 현재 네트워크 주소 출력
- `phone_ws_client.html`이 없으면 자동 생성
- `0.0.0.0:8000`에서 HTML 테스트 페이지 제공
- `0.0.0.0:3000`에서 WebSocket echo 서버 제공

즉 폰에서는 파일을 직접 열 필요 없이 아래 주소만 열면 됩니다.

```text
http://{{JETSON_IP}}:8000/phone_ws_client.html
```

`phone_ws_client.html`은 핸드폰 브라우저에서 열리는 테스트 페이지입니다.

이 페이지는 다음을 수행합니다.

- 현재 접속한 Jetson host를 기준으로 WebSocket 주소 자동 설정
- `ws://<현재 Jetson IP>:3000`에 연결
- 연결 성공/실패 로그 표시
- `Send Test Message` 버튼으로 `hello from phone` 전송
- Jetson에서 받은 echo 응답 표시

## IP가 바뀌었을 때

다른 핸드폰 핫스팟이나 다른 Wi-Fi를 쓰면 Jetson IP가 바뀔 수 있습니다.

먼저 Jetson에서 서버를 실행했을 때 출력되는 `Use this on the phone browser:` 주소를 확인합니다.

예를 들어 새 IP가 `10.59.121.200`이면 `{{JETSON_IP}}` 자리에 그 값을 넣습니다.

```text
http://{{JETSON_IP}}:8000/phone_ws_client.html
```

테스트용 `phone_ws_client.html`은 HTTP로 열면 현재 접속한 host를 기준으로 WebSocket 주소를 자동 생성합니다.

```text
http://{{JETSON_IP}}:8000/phone_ws_client.html
-> ws://{{JETSON_IP}}:3000
```

따라서 순수 WebSocket 테스트에서는 보통 폰 주소창의 IP만 새 Jetson IP로 바꾸면 됩니다.

실제 프로젝트의 `customized_files/user.html`은 기본 WebSocket 주소가 파일 안에 들어 있습니다. Jetson IP가 바뀌면 아래 값을 새 IP로 바꿉니다.

```javascript
const DEFAULT_WS_URL = 'ws://{{JETSON_IP}}:3000';
```

예:

```javascript
const DEFAULT_WS_URL = 'ws://10.59.121.200:3000';
```

또한 예전 주소를 자동 교체하려면 `LEGACY_WS_URLS`에도 이전 주소를 추가할 수 있습니다.

```javascript
const LEGACY_WS_URLS = ['ws://localhost:3000', 'ws://192.168.0.90:3000'];
```

단, `user.html`에는 IP 설정 버튼이 있으므로 폰 화면에서 직접 새 IP와 포트 `3000`을 저장해도 됩니다.
