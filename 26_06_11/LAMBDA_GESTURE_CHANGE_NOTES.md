# Lambda Gesture Change Notes

목적: 현재 엄지척(`thumbs_up`) 수신호를, 카메라가 손바닥 쪽을 볼 때 왼손이 대문자 `Λ`처럼 보이는 수신호로 바꿀 때 수정할 위치를 기록한다.

## [A] 현재 흐름: 수신호가 동작 ID로 이어지는 순서

화살표는 데이터가 다음 처리 단계로 넘어간다는 뜻이다.

```text
/mediapipe/start
  -> start_callback()
  -> image_callback()
  -> detect_gesture()
  -> 연속 프레임 카운트
  -> /manipulator/motion_id
```

| 단계 | 현재 코드 위치 | 현재 역할 |
| --- | --- | --- |
| 시작 신호 | `hand_tracker_node.py`의 `start_callback()` | `/mediapipe/start` 문자열이 `motion_map_json` 키와 맞으면 감지를 시작한다. |
| 영상 처리 | `hand_tracker_node.py`의 `image_callback()` | `/camera` 압축 이미지를 MediaPipe Hands에 넣고 손 랜드마크를 얻는다. |
| 수신호 판정 | `hand_tracker_node.py`의 `detect_gesture()` | 랜드마크 좌표로 현재는 `thumbs_up` 또는 `unknown`을 반환한다. |
| 확정 처리 | `hand_tracker_node.py`의 `image_callback()` | `thumbs_up`이 연속으로 `thumbs_up_required_count`만큼 나오면 동작 ID를 발행한다. |

## [A1] `detect_gesture()`: 엄지척 조건을 `Λ` 조건으로 교체

현재 판정은 `hand_tracker_node.py`의 `detect_gesture()` 안에 있다.

```python
if thumb_tip.y < thumb_ip.y and index_tip.y > thumb_ip.y:
    return "thumbs_up"
return "unknown"
```

나중에 코드 변경 시 이 조건을 `lambda_sign` 판정으로 바꾼다.

왼손 손바닥이 카메라를 향한 상태에서 `Λ` 모양은 다음처럼 잡는다.

```text
카메라 화면 기준

          thumb_tip ~= index_tip
                 /\
                /  \
       index_mcp    thumb_mcp 또는 thumb_cmc

x: 화면 오른쪽으로 갈수록 커짐
y: 화면 아래쪽으로 갈수록 커짐
```

판정에 추가로 사용할 MediaPipe 랜드마크 후보는 다음과 같다.

| 랜드마크 | 사용할 이유 |
| --- | --- |
| `THUMB_TIP` | 엄지 끝점이다. `Λ`의 위쪽 꼭짓점 후보로 쓴다. |
| `INDEX_FINGER_TIP` | 검지 끝점이다. 엄지 끝점과 가까워야 `Λ` 꼭짓점처럼 보인다. |
| `THUMB_MCP` 또는 `THUMB_CMC` | 엄지 쪽 아래 기준점이다. |
| `INDEX_FINGER_MCP` | 검지 쪽 아래 기준점이다. |
| `MIDDLE_FINGER_TIP`, `RING_FINGER_TIP`, `PINKY_TIP` | 나머지 손가락이 펴진 오인식을 줄이는 데 쓴다. |
| `MIDDLE_FINGER_PIP`, `RING_FINGER_PIP`, `PINKY_PIP` | 나머지 손가락이 접혔는지 비교하는 기준점이다. |

## [A2] `Λ` 판정 조건 후보

처음 Jetson에서 확인할 조건은 아래 네 가지로 둔다.

| 조건 | 의미 |
| --- | --- |
| `thumb_tip`과 `index_tip` 사이 거리가 작다. | 엄지와 검지 끝이 만나거나 거의 붙어 `Λ`의 위 꼭짓점이 된다. |
| `thumb_tip.y`와 `index_tip.y`가 각각 아래 기준점보다 작다. | 화면에서 손끝이 아래 관절보다 위에 있어야 한다. |
| `index_mcp.x < thumb_mcp.x`이다. | 왼손 손바닥 기준으로 검지 쪽이 화면 왼쪽, 엄지 쪽이 화면 오른쪽에 있어야 한다. |
| 중지, 약지, 새끼손가락 끝이 각 PIP보다 아래에 있다. | `Λ`가 아닌 열린 손 모양을 줄인다. |

처음 튜닝할 숫자는 정규화 좌표 기준으로 아래처럼 시작한다.

| 값 | 시작 후보 | 조정 기준 |
| --- | ---: | --- |
| 엄지-검지 끝 거리 | `0.08` 이하 | 손이 멀거나 가까울 때 꼭짓점 인식이 흔들리면 조정한다. |
| 아래 기준점 좌우 간격 | `0.08` 이상 | 손가락 두 줄기가 너무 붙은 모양을 제외할 때 키운다. |
| 손끝이 기준점보다 위인지 보는 여유값 | `0.03` | 카메라 각도 때문에 손끝 높이가 애매하면 줄인다. |

## [A3] 반환 문자열과 카운터 이름

`detect_gesture()`가 반환하는 문자열은 현재 `thumbs_up`이다. `Λ` 수신호로 바꿀 때는 새 문자열을 하나로 통일한다.

권장 이름:

```text
lambda_sign
```

함께 바꿀 위치는 다음과 같다.

| 현재 이름 | 바꿀 이름 후보 | 위치 |
| --- | --- | --- |
| `"thumbs_up"` | `"lambda_sign"` | `detect_gesture()` 반환값 |
| `gesture_msg.data == "thumbs_up"` | `gesture_msg.data == "lambda_sign"` | `image_callback()`의 연속 프레임 카운트 조건 |
| `thumbs_up_count` | `lambda_sign_count` | `__init__()`와 `image_callback()`의 카운터 변수 |
| `thumbs_up_required_count` | `lambda_sign_required_count` | ROS 파라미터 이름 |

파라미터 이름은 바로 바꾸면 launch 파일이나 외부 실행 명령도 같이 바꿔야 한다. Jetson에서 먼저 테스트할 때는 내부 판정 문자열만 바꾸고, 파라미터 이름은 기존 `thumbs_up_required_count`를 임시로 유지해도 된다.

## [A4] 코드 변경 전 확인 순서

1. 디버그 창에서 왼손 손바닥이 카메라를 향하게 한다.
2. 엄지와 검지 끝을 붙이거나 가깝게 해서 화면에 `Λ`처럼 보이게 한다.
3. `THUMB_TIP`, `INDEX_FINGER_TIP`, `THUMB_MCP`, `INDEX_FINGER_MCP` 좌표가 조건과 맞는지 확인한다.
4. 중지, 약지, 새끼손가락을 접은 상태에서만 `lambda_sign`이 나오는지 확인한다.
5. 같은 자세가 연속 프레임 기준을 채웠을 때만 `/manipulator/motion_id`가 발행되는지 확인한다.
