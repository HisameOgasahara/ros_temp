# ROS2 Manipulator 실습 기록: Dynamixel 위치값, 토크, 가동 범위 분석

## 1. 실습 개요

이 실습은 ROS2 기반 로봇팔 매니퓰레이션 실습이다. 로봇팔은 Dynamixel XL430 계열 모터 5개를 사용하며, GUI를 통해 로봇팔 자세를 직접 티칭하고 저장한 뒤, ROS2 토픽으로 모션 번호를 호출해 실행하는 구조다.

전체 흐름은 다음과 같다.

```text
Torque OFF
-> 손으로 로봇팔 자세를 잡음
-> 현재 Dynamixel 위치값 읽기
-> Step에 저장
-> 여러 Step을 Motion으로 구성
-> saved_motions.json에 저장
-> /manipulator/motion_id 토픽으로 Motion 실행
```

이 실습에서 중요한 점은 로봇팔 동작이 "좌표"나 "방향"으로 직접 저장되는 것이 아니라, 각 Dynamixel 모터의 위치값 조합으로 저장된다는 것이다.

## 2. 하드웨어 구성과 모터 ID

강의자료 기준 Manipulator에 사용된 Dynamixel 모터 ID는 다음과 같다.

```text
ID 11: 바닥 회전 관절
ID 12: 어깨 관절
ID 13: 팔꿈치 관절
ID 14: 손목 관절
ID 15: 그리퍼 관절
```

각 ID의 역할은 조립 방향에 따라 체감 동작이 조금 달라질 수 있지만, 기본적으로 각 모터 하나가 로봇팔의 관절 하나를 담당한다.

로봇팔의 한 자세는 다음과 같은 5개 숫자 조합으로 표현된다.

```text
ID11 = 4059
ID12 = 695
ID13 = 2763
ID14 = 2890
ID15 = 3284
```

이 숫자 조합이 하나의 Step이며, 여러 Step을 순서대로 실행하면 하나의 Motion이 된다.

## 3. Joint State, 자유도, Local Joint Angle

이 실습에서 가장 먼저 잡아야 할 개념은 Dynamixel 숫자들이 로봇팔의 자유도 상태를 나타낸다는 점이다.

로봇팔 상태는 다음과 같은 joint state 벡터로 볼 수 있다.

```text
q = [q11, q12, q13, q14, q15]

q11 = ID11 바닥 회전 관절 값
q12 = ID12 어깨 관절 값
q13 = ID13 팔꿈치 관절 값
q14 = ID14 손목 관절 값
q15 = ID15 그리퍼 관절 값
```

즉 ID 11~15의 5개 값이 이 로봇팔의 주요 자유도 상태다. GUI에서 저장하는 Step은 사실상 이 joint state 한 장면을 저장하는 것이다.

중요한 점은 이 값들이 공통 월드 좌표계 기준 각도가 아니라, 각 모터 출력축 기준의 local joint angle이라는 점이다.

```text
ID11 = 2048
ID12 = 2048
ID13 = 2048
```

이라고 해서 세 관절이 공간에서 같은 방향을 본다는 뜻은 아니다. 각 모터마다 자기 출력축 기준의 2048 위치를 의미한다. 모터의 조립 방향, 혼 체결 방향, 브래킷 방향이 다르기 때문에 같은 숫자라도 실제 로봇팔에서 보이는 자세는 다를 수 있다.

따라서 이 값들은 다음처럼 이해해야 한다.

```text
각 Dynamixel position value = 각 모터의 local joint value
ID11~ID15 전체 조합 = 로봇팔의 joint state
joint state + 링크 구조 + 조립 방향 = 실제 end-effector 위치와 자세
```

이 개념은 TF와도 연결된다. TF가 링크와 좌표계 사이의 위치/회전 관계를 표현한다면, joint value들은 그 TF 관계를 만들어내는 관절 변수다. 관절값이 바뀌면 링크들의 TF도 바뀌고, 최종적으로 그리퍼의 위치와 방향도 바뀐다.

로봇팔을 계층 구조로 보면 다음과 같다.

```text
base_link
  -> joint11(q11)
    -> link1
      -> joint12(q12)
        -> link2
          -> joint13(q13)
            -> link3
              -> joint14(q14)
                -> wrist/link4
                  -> joint15(q15)
                    -> gripper
```

여기서 ID11을 돌리면 ID12~ID15의 숫자 자체가 같이 변하는 것은 아니다.

```text
ID11 값: 변함
ID12 값: 그대로
ID13 값: 그대로
ID14 값: 그대로
ID15 값: 그대로
```

하지만 공간상으로는 ID12~ID15가 붙어 있는 팔 전체가 ID11의 회전에 따라 같이 돌아간다. 즉 숫자는 local joint 기준으로 그대로지만, 월드 좌표계에서의 팔과 그리퍼 위치는 바뀐다.

비유하면 사람이 팔꿈치를 접은 상태로 몸통을 돌리는 것과 비슷하다.

```text
팔꿈치 각도는 그대로
몸통 방향은 바뀜
손의 월드 좌표 위치는 바뀜
```

따라서 특정 관절 하나의 숫자만 보고 그리퍼의 실제 위치를 알 수 없다. 그리퍼의 실제 위치와 자세는 전체 joint state를 링크 구조에 따라 순서대로 적용해야 나온다.

```text
end_effector_pose = T11(q11) * T12(q12) * T13(q13) * T14(q14) * T15(q15)
```

이 관계가 forward kinematics의 기본 감각이다. 이 실습의 GUI는 forward kinematics를 계산해서 보여주는 도구라기보다, 사람이 직접 joint state를 티칭하고 저장하는 도구에 가깝다.

## 4. Dynamixel 위치값의 의미

Dynamixel XL430-W250-T 기준으로 Position Control Mode에서 기본 위치 단위는 다음과 같이 이해할 수 있다.

```text
0 ~ 4095 ~= 0 ~ 360 degrees
1 count ~= 0.088 degrees
```

예를 들면 다음과 같다.

```text
0    ~= 0 degrees
1024 ~= 90 degrees
2048 ~= 180 degrees
3072 ~= 270 degrees
4095 ~= 360 degrees 직전
```

단, 이 값은 "방 기준 북쪽/남쪽" 같은 절대 방향이 아니다. 모터 내부의 출력축 기준 위치값이다. 따라서 조립 방향, 혼(horn) 체결 방향, 브래킷 방향에 따라 같은 숫자라도 실제 로봇팔의 시각적 자세는 달라질 수 있다.

즉 `0~4095`는 모든 모터가 공통으로 사용하는 숫자 범위지만, 그 기준 방향은 모터마다 따로 존재한다. 그러므로 모션 티칭 시에는 각 ID별로 다음처럼 실제 자세와 숫자를 함께 기록하는 것이 좋다.

```text
ID12 = 700 부근: 어깨가 낮게 내려간 자세
ID13 = 2800 부근: 팔꿈치가 접힌 자세
ID15 = 3280 부근: 그리퍼가 닫힌 자세
```

이런 기록은 나중에 모션 디버깅이나 면접 설명에서 "숫자가 어떤 물리 상태를 의미했는지"를 설명하는 데 도움이 된다.

## 5. 토크 ON/OFF의 의미

GUI의 ON/OFF 버튼은 Torque Enable 상태를 바꾸는 버튼이다.

```text
Torque OFF:
  모터가 힘을 주지 않는다.
  손으로 로봇팔 관절을 움직일 수 있다.
  위치 센서와 통신은 살아 있으므로 current position은 계속 읽힌다.

Torque ON:
  모터가 힘을 준다.
  현재 위치 또는 목표 위치를 유지하려고 한다.
  run step/run motion 명령 시 목표 위치로 이동한다.
```

중요한 점은 Torque OFF가 센서를 끄는 것이 아니라는 점이다. 모터 몸통은 브래킷에 고정되어 있지만, 출력축과 혼이 팔 링크에 연결되어 있기 때문에 손으로 팔을 움직이면 출력축이 돌아간다. Dynamixel 내부 위치 센서는 이 출력축의 회전 상태를 읽고 current position 값을 갱신한다.

## 6. GUI 티칭 흐름

자세 하나를 저장할 때의 기본 순서는 다음과 같다.

```text
1. Motion과 Step 선택
2. Torque OFF
3. 손으로 로봇팔 자세 잡기
4. Torque ON
5. read positions from dxl
6. current 값 확인
7. save step
8. saved 값 확인
9. run step으로 테스트
```

`current`와 `saved`의 의미는 다음과 같다.

```text
current:
  지금 실제 모터의 위치값

saved:
  현재 선택한 Step에 저장된 목표 위치값
```

`run step`을 누르면 saved 값이 Goal Position으로 전송된다.

## 7. 실습 중 확인한 모터 상태

DynamixelSDK를 직접 사용해 ID 11~15의 상태를 확인했다. 확인 스크립트는 `check_dxl_limits.py`로 작성했으며, 각 모터의 operating mode, torque 상태, min/max position limit, present position, voltage, temperature, hardware error를 읽었다.

실제 확인 결과는 다음과 같았다.

```text
device=/dev/ttyACM1, baudrate=1000000
position unit: 0~4095 = 0~360 degrees, about 0.088 degree per count

ID11
  operating mode : 3 (Position Control)
  drive mode     : 4
  torque         : OFF
  min limit      : 0
  max limit      : 4095
  goal position  : 4059
  current pos    : 4059
  velocity       : 0
  temperature    : 39 C
  voltage        : 12.0 V
  hardware error : 0

ID12
  operating mode : 3 (Position Control)
  min limit      : 0
  max limit      : 4095
  current pos    : 695
  hardware error : 0

ID13
  operating mode : 3 (Position Control)
  min limit      : 0
  max limit      : 4095
  current pos    : 2763
  hardware error : 0

ID14
  operating mode : 3 (Position Control)
  min limit      : 0
  max limit      : 4095
  current pos    : 2890
  hardware error : 0

ID15
  operating mode : 3 (Position Control)
  min limit      : 0
  max limit      : 4095
  current pos    : 3284
  hardware error : 0
```

이 결과로 확인한 내용은 다음과 같다.

```text
1. ID 11~15 모터 모두 통신 가능
2. 모두 Position Control Mode, 즉 Operating Mode 3
3. Goal Position 제한은 0~4095
4. 전압 12.0V로 정상
5. 온도 36~39도 수준으로 정상
6. hardware error = 0으로 모터 내부 에러 없음
```

## 8. Goal Position Limit과 Present Position의 차이

실습 중 중요한 차이를 확인했다.

```text
Goal Position:
  모터에게 명령으로 보낼 목표 위치값
  Position Control Mode에서는 Min/Max Position Limit의 영향을 받음
  실습 장비에서는 0~4095

Present Position:
  현재 모터 출력축이 실제로 어디에 있는지 읽은 값
  Torque OFF 상태에서 손으로 돌리면 0~4095를 넘는 값도 관측될 수 있음
```

즉 `max limit = 4095`라고 해서 `Present Position`이 항상 4095 이하로만 읽힌다는 뜻은 아니다. Torque OFF 상태에서 손으로 출력축을 돌리면 다음과 같이 증가할 수 있다.

```text
4059
5018
5155
5395
5636
```

이 값들은 "Goal Position으로 안전하게 명령할 수 있는 값"이라기보다, 토크가 꺼진 상태에서 손으로 돌려 발생한 현재 위치 readback 값에 가깝다.

따라서 모션 저장 시에는 다음 원칙을 세웠다.

```text
current 값이 0~4095 안에 있을 때만 save step
0보다 작거나 4095보다 크면 저장하지 않음
```

## 9. 음수/초과값 관련 로그와 분석

특정 방향으로 관절을 움직이면서 current 값이 0을 향해 감소하다가, 0 아래로 내려가는 구간에서 노드가 죽는 문제가 발생했다.

로그 핵심은 다음과 같았다.

```text
AssertionError: The 'position' field must be an integer in [-2147483648, 2147483647]
```

발생 위치는 SDK 노드의 `/get_position` 서비스 응답 처리 부분이었다.

```text
read_write_node_omx.py
get_position_callback()
response.position = dxl_present_position
```

원인 해석:

```text
1. Dynamixel Present Position은 4바이트 값으로 읽힘
2. 0 아래로 내려간 값이 unsigned 32-bit처럼 해석될 수 있음
3. 예를 들어 -1이 4294967295처럼 보일 수 있음
4. ROS2 custom service의 position 필드는 int32
5. int32 최대값 2147483647보다 큰 값을 response.position에 넣으면서 AssertionError 발생
```

예상 변환 관계는 다음과 같다.

```text
-1  -> 4294967295
-2  -> 4294967294
-10 -> 4294967286
```

따라서 이 문제는 "모터가 물리적으로 고장났다"기보다, `Present Position` readback 값을 ROS2 int32 응답에 그대로 넣으면서 생긴 signed/unsigned 해석 문제로 판단했다.

## 10. 코드 수정 검토

수정 방안으로 처음에는 `% 4096` 정규화를 고려했다.

```python
dxl_present_position = dxl_present_position % 4096
```

하지만 이 방식은 문제가 있다.

```text
5636 -> 1540
4097 -> 1
-1   -> 4095
```

이렇게 값이 겉으로는 0~4095 안에 들어오지만, 실제로는 "한 바퀴 이상 돌아갔다" 또는 "음수 방향으로 넘어갔다"는 정보가 사라진다. GUI가 이 값을 그대로 저장하면, 이상 상태를 정상 위치처럼 저장할 수 있다.

따라서 더 안전한 판단은 다음과 같다.

```text
1. Present Position readback은 unsigned -> signed 변환만 적용
2. %4096으로 조용히 감싸지 않음
3. 0~4095 밖의 current 값은 사람이 보고 저장하지 않음
4. Goal Position은 0~4095 밖이면 실행하지 않도록 방어하는 것이 안전
```

최소 수정 예시는 다음과 같다.

```python
raw_position = dxl_present_position

if raw_position > 0x7FFFFFFF:
    dxl_present_position = raw_position - 0x100000000
else:
    dxl_present_position = raw_position

response.position = int(dxl_present_position)
```

이렇게 하면 `4294967295`가 `-1`로 바뀌어 ROS2 int32 범위 안에 들어오고, 노드는 죽지 않는다. 동시에 `5000` 같은 초과값은 그대로 보이므로 사람이 이상 상태를 판단할 수 있다.

Goal Position 전송부에서는 다음과 같은 검증을 고려할 수 있다.

```python
goal_position = int(msg.position)

if goal_position < 0 or goal_position > 4095:
    self.get_logger().error(
        f'[ID: {msg.id}] Goal Position {goal_position} outside 0..4095. Ignore command.'
    )
    return
```

이 방식은 `%4096`으로 값을 몰래 바꾸는 것보다 안전하다. 예를 들어 `5636`을 자동으로 `1540`으로 바꿔 실행하면, 사용자는 잘못 저장된 모션을 알아차리기 어렵다.

## 11. 실제 가동 범위 기록의 필요성

제조사/모터 기준 범위와 실제 로봇팔의 안전 범위는 다르다.

```text
모터 내부 limit:
  0~4095

실제 로봇팔 안전 범위:
  브래킷 간섭, 케이블 장력, 링크 충돌, 그리퍼 간섭을 고려해야 함
```

따라서 모션 티칭 전에는 각 관절별로 실제 안전 범위를 기록하는 것이 좋다.

기록표 예시는 다음과 같다.

```text
ID11 바닥 회전
  왼쪽 안전 한계:
  오른쪽 안전 한계:
  실사용 범위:

ID12 어깨
  위쪽 안전 한계:
  아래쪽 안전 한계:
  실사용 범위:

ID13 팔꿈치
  접힘 한계:
  펴짐 한계:
  실사용 범위:

ID14 손목
  위쪽 한계:
  아래쪽 한계:
  실사용 범위:

ID15 그리퍼
  열림 값:
  닫힘 값:
  물건을 안정적으로 잡는 값:
```

측정 방법은 다음과 같다.

```text
1. Torque OFF
2. 관절을 손으로 천천히 움직임
3. 물리적으로 걸리기 직전에서 멈춤
4. Torque ON
5. read positions from dxl
6. current 값 기록
7. 반대 방향도 동일하게 기록
8. 실제 사용값은 한계값보다 여유를 둠
```

예를 들어 물리적 한계가 700이라면 실제 모션에는 800 이상을 사용하는 식으로 안전 여유를 둔다.

### 실습 중 기록한 관절별 실사용 끝단값

아래 값들은 실제 물리 한계에 딱 닿는 극한값이 아니라, 충돌/간섭 원인을 확인한 뒤 약간의 여유를 두고 정한 실사용 끝단값이다. 괄호 안의 내용은 해당 방향의 가동 범위를 제한하는 주요 원인이다.

```text
ID11 바닥 회전
  특징:
    거의 360도 가까이 회전 가능
    다른 관절보다 0 아래 또는 4095 초과 readback 문제가 발생하기 쉬움
    모션 저장 시 current 값이 0~4095 안에 있는지 특히 확인 필요

ID12 어깨
  실사용 범위:
    800 (로봇 바닥판 간섭) ~ 3000 (LiDAR 간섭)

ID13 팔꿈치
  실사용 범위:
    800 (모터 간섭) ~ 2700 (로봇팔 링크 간섭)

ID14 손목
  실사용 범위:
    880 (전선 간섭) ~ 2800 (전선 간섭)

ID15 그리퍼
  실사용 범위:
    3300 ~ 3800
  제한 원인:
    양쪽 모두 집게 구조/그리퍼 기구 한계
```

이 기록으로 확인한 점은 다음과 같다.

```text
1. 코드상 Dynamixel Goal Position Limit은 모든 모터가 0~4095로 동일하다.
2. 하지만 실제 조립된 로봇팔에서는 관절마다 물리적 간섭 때문에 실사용 범위가 훨씬 좁다.
3. ID12~ID15는 로봇 바닥판, LiDAR, 모터, 팔 링크, 전선, 그리퍼 구조 때문에 대략 180도 전후의 제한된 범위에서 사용된다.
4. ID11은 바닥 회전 관절이라 상대적으로 넓게 회전하고, 이 때문에 Present Position이 0 아래 또는 4095 이상으로 넘어가는 readback 문제가 주로 발생한다.
```

따라서 모션 티칭 시 판단 기준은 다음과 같이 정리할 수 있다.

```text
ID11:
  0~4095 범위 이탈 여부를 우선 확인
  overflow/underflow성 readback에 주의

ID12~ID14:
  기록한 실사용 범위 안에서만 자세 저장
  괄호 안의 간섭 원인을 기억하고 극한값 근처 사용 자제

ID15:
  단순 각도 관절이라기보다 그리퍼 열림/닫힘 값으로 관리
  물건별 안정적으로 잡히는 값을 추가로 기록하면 좋음
```

## 12. 포트폴리오/면접에서 설명하기 좋은 포인트

이 실습은 단순히 GUI로 로봇팔을 움직인 것이 아니라, 실제 하드웨어 로그를 기반으로 위치값과 제어 흐름을 분석한 경험으로 정리할 수 있다.

면접에서 설명할 수 있는 구체적 상황:

```text
Dynamixel XL430 기반 ROS2 manipulator를 사용해 motion teaching을 수행했다.
각 Dynamixel position value가 월드 좌표계 기준 각도가 아니라 각 모터 출력축 기준의 local joint value이며, ID11~ID15의 조합이 로봇팔의 joint state/DOF 상태를 구성한다는 점을 확인했다.
GUI에서 Torque OFF 후 손으로 자세를 잡고, /get_position 서비스로 각 모터의 Present Position을 읽어 Step으로 저장했다.
제조사 기준 Goal Position Limit은 0~4095였지만, 실제 조립된 로봇팔에서는 로봇 바닥판, LiDAR, 모터, 팔 링크, 전선, 그리퍼 구조 등으로 인해 ID12~ID15의 실사용 범위가 훨씬 좁다는 것을 확인하고 관절별 안전 끝단값을 기록했다.
실습 중 특정 관절을 0 근처로 이동할 때 read_write_node_omx.py가 AssertionError로 종료되는 문제가 발생했다.
로그를 분석해 Present Position의 unsigned 32-bit readback 값이 ROS2 int32 service field 범위를 초과한 것이 원인임을 확인했다.
또한 Goal Position Limit 0~4095와 Torque OFF 상태의 Present Position readback 범위가 다를 수 있음을 구분했다.
%4096 정규화는 값 손실과 잘못된 모션 저장을 유발할 수 있어, unsigned->signed 변환 및 0~4095 범위 검증이 더 안전하다고 판단했다.
```

기술 키워드:

```text
ROS2
rclpy
DynamixelSDK
XL430-W250-T
Position Control Mode
Torque Enable
Present Position
Goal Position
Joint Limit
Joint State
Local Joint Angle
Forward Kinematics
TF
Motion Teaching
Hardware Bringup
Log Analysis
Signed/Unsigned Integer
ROS2 Topic/Service
```

면접용 요약 문장:

```text
ROS2 기반 Dynamixel manipulator를 실습하면서, 각 Dynamixel position value가 개별 모터의 local joint angle이며 ID11~ID15의 조합이 로봇팔의 joint state를 구성한다는 관점으로 모션 티칭을 진행했습니다.
GUI 티칭 과정에서 발생한 Present Position overflow 문제를 로그로 분석했습니다.
모터의 Goal Position Limit은 0~4095였지만, Torque OFF 상태에서 손으로 관절을 돌릴 때 Present Position은 multi-turn 또는 signed 32-bit 범위로 읽힐 수 있었습니다.
이 값이 ROS2 int32 service response에 그대로 들어가면서 AssertionError가 발생했고, 단순히 %4096으로 보정하면 잘못된 자세를 정상값처럼 저장할 위험이 있음을 확인했습니다.
따라서 readback은 signed 변환으로 노드 크래시를 막고, 모션 저장/실행 시에는 0~4095 범위를 검증하는 방향이 안전하다고 판단했습니다.
```

## 13. 참고

- ROBOTIS XL430-W250-T e-Manual  
  https://emanual.robotis.com/docs/en/dxl/x/xl430-w250/

- 주요 레지스터

```text
Operating Mode        : address 11
Torque Enable         : address 64
Hardware Error Status : address 70
Goal Position         : address 116
Present Velocity      : address 128
Present Position      : address 132
Present Input Voltage : address 144
Present Temperature   : address 146
```
