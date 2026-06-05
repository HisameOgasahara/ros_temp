#!/usr/bin/env python3

import sys, os
import threading
from PyQt5.QtWidgets import *
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5 import uic
sys.path.append("/home/asilia/colcon_ws/src/manipulator/manipulator")

import rclpy, time, json
from rclpy.node import Node
from rclpy.qos import QoSProfile
from std_msgs.msg import Int16, Bool
from dynamixel_sdk_custom_interfaces.msg import SetPosition, SetTorque
from dynamixel_sdk_custom_interfaces.srv import GetPosition

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UI_PATH = os.path.join(BASE_DIR, "manipulatorGUI.ui")
form_class = uic.loadUiType(UI_PATH)[0]

class JsonLoaderThread(QThread):
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, json_path):
        super().__init__()
        self.json_path = json_path

    def run(self):
        import json, os
        try:
            if not os.path.exists(self.json_path):
                self.error.emit("JSON 파일이 존재하지 않습니다.")
                return

            with open(self.json_path, 'r') as f:
                data = json.load(f)

            self.finished.emit(data)

        except Exception as e:
            self.error.emit(f"JSON 로딩 오류: {str(e)}")

class DynamixelMotor:
    def __init__(self, dxl_id, node, positionClient, positionPublisher, torquePublisher):
        self.dxl_id = dxl_id
        self.node = node
        self.positionClient = positionClient
        self.positionPublisher = positionPublisher
        self.torquePublisher = torquePublisher
        self.curPosition = 2048
        self.torque_enabled = False

    def publish_position(self, value, runTime):
        msg = SetPosition()
        msg.id = self.dxl_id
        msg.position = value
        msg.runtime = runTime
        self.positionPublisher.publish(msg)

    def request_position(self, callback):
        request = GetPosition.Request()
        request.id = self.dxl_id
        future = self.positionClient.call_async(request)
        future.add_done_callback(lambda fut: callback(self.dxl_id, fut))

    def set_torque(self, enable):
        msg = SetTorque()
        msg.torque = enable
        msg.id = self.dxl_id
        self.torquePublisher.publish(msg)
        self.torque_enabled = enable


class manipulatorGUINode(Node, QMainWindow, form_class):
    def __init__(self):
        Node.__init__(self, 'manipulatorGUI')
        QMainWindow.__init__(self)
        self.setupUi(self)

        qos_profile = QoSProfile(depth=10)
        self.positionPublisher = self.create_publisher(SetPosition, '/set_position', qos_profile)
        self.torquePublisher = self.create_publisher(SetTorque, '/set_torque', qos_profile)
        self.positionClient = self.create_client(GetPosition, '/get_position')

        while not self.positionClient.wait_for_service(timeout_sec=1.0):
            self.get_logger().info('Service not available, waiting...')

        self.motor_ids = list(range(11, 16))
        self.motors = [
            DynamixelMotor(dxl_id, self, self.positionClient, self.positionPublisher, self.torquePublisher)
            for dxl_id in self.motor_ids
        ]
        
        # 모션별 반복수, 다음 실행 모션 저장 
        self.spinNumberBoxes = {}  # motion_index -> QSpinBox
        self.nextMotionBoxes = {}  # motion_index -> QSpinBox
        
        # 모션-스텝-각 ID별 포지션 값을 저장하는 리스트 바깥 범위부터 순서대로 모션-스텝-ID별position
        self.motions = [[[0, 0, 0, 0, 0]]]
        
        # 현재 모션과 스텝을 저장하기 위한 변수
        self.motion = 0
        self.step = 0
        
        self.motionTab.removeTab(0)
        self.add_motion_tab(0)
        
        # 모션 진행 시간과 종료 후 대기시간 저장용 리스트
        self.times = [[[1.0, 0.0]]]

        # UI 버튼 연결
        self.readButton.clicked.connect(self.readButton_callback)
        self.stepReadButton.clicked.connect(self.stepReadButton_callback)
        self.torqueOnButton.clicked.connect(self.torqueOnButton_callback)
        self.torqueOffButton.clicked.connect(self.torqueOffButton_callback)
        self.stepRunButton.clicked.connect(self.stepRunButton_callback)
        self.stepAddButton.clicked.connect(self.stepAddButton_callback)
        self.stepDeleteButton.clicked.connect(self.stepDeleteButton_callback)
        self.motionRunButton.clicked.connect(self.motionRunButton_callback)
        self.motionStopButton.clicked.connect(self.motionStopButton_callback)
        self.motionAddButton.clicked.connect(self.motionAddButton_callback)
        self.motionDeleteButton.clicked.connect(self.motionDeleteButton_callback)
        self.dxlAllSelectButton.clicked.connect(self.dxlAllSelectButton_callback)
        self.dxlAllUnSelectButton.clicked.connect(self.dxlAllUnSelectButton_callback)
        self.saveToJsonButton.clicked.connect(self.saveToJsonButton_callback)
        self.writeFromJsonButton.clicked.connect(self.writeFromJsonButton_callback)
        
        # UI 탭 연결
        self.motionTab.currentChanged.connect(self.motionTab_callback)
        self.stepTab_motion1.currentChanged.connect(self.stepTab_motion1_callback)
        
        # ID별 current position 표시 QLineEdit 연결
        self.currentLineEdits = {
            11: self.lineEdit_ID11_current,
            12: self.lineEdit_ID12_current,
            13: self.lineEdit_ID13_current,
            14: self.lineEdit_ID14_current,
            15: self.lineEdit_ID15_current,
        }

        # ID별 saved position 표시 QLineEdit 연결
        self.savedLineEdits = {
            11: self.lineEdit_ID11_saved,
            12: self.lineEdit_ID12_saved,
            13: self.lineEdit_ID13_saved,
            14: self.lineEdit_ID14_saved,
            15: self.lineEdit_ID15_saved,
        }

        # GroupBox에 해당하는 ID 체크 여부에 따른 동작 처리
        self.groupBoxes = {
            11: self.Group_ID11,
            12: self.Group_ID12,
            13: self.Group_ID13,
            14: self.Group_ID14,
            15: self.Group_ID15,
        }
        
        # motion1에 해당하는 각 step별 runTime, endDelay
        self.runTimeSpinBoxStep1_motion1.valueChanged.connect(self.m1s1_time_callback)
        self.endDelaySpinBoxStep1_motion1.valueChanged.connect(self.m1s1_time_callback)

    def position_response_callback(self, dxl_id, future):
        try:
            response = future.result()
            motor = self.motors[dxl_id - 11]
            motor.curPosition = response.position
            if dxl_id in self.currentLineEdits:
                self.currentLineEdits[dxl_id].setText(str(motor.curPosition))
            else:
                self.get_logger().warn(f"No QLineEdit mapped for ID {dxl_id}")
        except Exception as e:
            self.get_logger().error(f"[ID {dxl_id}] Service call failed: {e}")

    def readButton_callback(self):
        for motor in self.motors:
            if self.groupBoxes[motor.dxl_id].isChecked():
                motor.request_position(self.position_response_callback)
        self.InfoLabel.setText("(Read Dynamixels to current positions : Motion=%d, Step=%d)"%(self.motion+1, self.step+1))

    def stepReadButton_callback(self):
        for motor in self.motors:
            if self.groupBoxes[motor.dxl_id].isChecked():
                text = self.currentLineEdits[motor.dxl_id].text()
                self.savedLineEdits[motor.dxl_id].setText(text)
                self.motions[self.motion][self.step][int(motor.dxl_id)-11] = int(text)
        self.InfoLabel.setText("(Read current positions to Step : motion%d, step%d)"%(self.motion+1, self.step+1))

    def stepRunButton_callback(self):
        for motor in self.motors:
            if self.groupBoxes[motor.dxl_id].isChecked():
                value = int(self.savedLineEdits[motor.dxl_id].text())
                runTime = self.times[self.motion][self.step][0]
                motor.publish_position(value, runTime)
                self.currentLineEdits[motor.dxl_id].setText(str(value))
        self.InfoLabel.setText("(Write saved positions to Dynamixels : Motion=%d, Step=%d)"%(self.motion+1, self.step+1))

    def motionRunButton_callback(self):
        self.spin_trigger = True
        self.run_motion(self.motion)

    def motionStopButton_callback(self):
        self.spin_trigger = False

    def run_motion(self, motion_idx):
        if not (0 <= motion_idx < len(self.motions)):
            self.InfoLabel.setText(f"(Invalid motion index: {motion_idx})")
            return

        self.motion = motion_idx
        total_steps = len(self.motions[motion_idx])

        motion_name = f"motion{motion_idx+1}"
        spin_box_name = f"spinNumberSpinBox_{motion_name}"
        next_box_name = f"nextMotionSpinBox_{motion_name}"

        spin_box = self.spinNumberBoxes.get(motion_idx)
        next_box = self.nextMotionBoxes.get(motion_idx)

        if spin_box is None or next_box is None:
            self.InfoLabel.setText(f"(Error: SpinBoxes not found for {motion_name})")
            return

        spin_count = spin_box.value()
        next_motion = next_box.value() - 1  # 1-based to 0-based

        for spin in range(spin_count):
            if self.spin_trigger == True:
                self.InfoLabel.setText(f"(Run Motion {motion_idx+1}, Spin {spin+1}/{spin_count})")
                QApplication.processEvents()

                for step_idx in range(total_steps):
                    self.step = step_idx
                    for motor in self.motors:
                        if self.groupBoxes[motor.dxl_id].isChecked():
                            value = int(self.motions[motion_idx][step_idx][motor.dxl_id - 11])
                            run_time = self.times[motion_idx][step_idx][0]
                            motor.publish_position(value, run_time)

                    self.InfoLabel.setText(f"(Run motions : Motion={motion_idx+1}, Step={step_idx+1})")
                    QApplication.processEvents()
                    time.sleep(self.times[motion_idx][step_idx][0] + self.times[motion_idx][step_idx][1])

        self.step = 0
        if self.spin_trigger == True:
            if next_box.value() > 0 and 0 <= next_motion < len(self.motions):
                self.InfoLabel.setText(f"(Switching to next motion {next_motion+1})")
                QApplication.processEvents()
                self.run_motion(next_motion)
            else:
                self.InfoLabel.setText("(No next motion specified. Execution finished.)")

    def add_motion_tab(self, motion_index):
        motion_name = f"motion{motion_index+1}"
        if len(self.motions) <= motion_index:
            self.motions.append([[0, 0, 0, 0, 0]])
            self.times.append([[1.0, 0.0]])

        motion_widget = QWidget()
        motion_layout = QVBoxLayout(motion_widget)

        step_tab = QTabWidget()
        step_tab.setObjectName(f"stepTab_{motion_name}")
        motion_layout.addWidget(step_tab)

        step1_widget = QWidget()
        step1_layout = QFormLayout(step1_widget)

        run_time_spin = QDoubleSpinBox()
        run_time_spin.setObjectName(f"runTimeSpinBoxStep1_{motion_name}")
        run_time_spin.setRange(1.0, 10.0)
        run_time_spin.setSingleStep(0.1)
        run_time_spin.setDecimals(1)
        run_time_spin.setValue(1.0)

        end_delay_spin = QDoubleSpinBox()
        end_delay_spin.setObjectName(f"endDelaySpinBoxStep1_{motion_name}")
        end_delay_spin.setRange(0.0, 10.0)
        end_delay_spin.setSingleStep(0.1)
        end_delay_spin.setDecimals(1)
        end_delay_spin.setValue(0.0)

        step1_layout.addRow("Run Time (s):", run_time_spin)
        step1_layout.addRow("End Delay (s):", end_delay_spin)
        step_tab.addTab(step1_widget, "step1")

        motion_params_widget = QWidget()
        motion_params_layout = QFormLayout(motion_params_widget)

        # spin number
        spin_number_spin = QSpinBox()
        spin_number_spin.setObjectName(f"spinNumberSpinBox_{motion_name}")
        spin_number_spin.setRange(1, 99)
        spin_number_spin.setValue(1)
        self.spinNumberBoxes[motion_index] = spin_number_spin

        # next motion
        next_motion_spin = QSpinBox()
        next_motion_spin.setObjectName(f"nextMotionSpinBox_{motion_name}")
        next_motion_spin.setRange(0, 99)
        next_motion_spin.setValue(0)
        self.nextMotionBoxes[motion_index] = next_motion_spin

        motion_params_layout.addRow("spin number:", spin_number_spin)
        motion_params_layout.addRow("next motion:", next_motion_spin)

        motion_layout.addWidget(motion_params_widget)
        self.motionTab.insertTab(motion_index, motion_widget, f"Motion {motion_index+1}")

        run_time_spin.valueChanged.connect(lambda: self.update_time_from_spinbox(motion_index, 0, run_time_spin, end_delay_spin))
        end_delay_spin.valueChanged.connect(lambda: self.update_time_from_spinbox(motion_index, 0, run_time_spin, end_delay_spin))

        if not hasattr(self, 'stepTabs'):
            self.stepTabs = {}
        self.stepTabs[motion_index] = step_tab
        step_tab.currentChanged.connect(lambda idx, m=motion_index: self.update_step_from_tab(m, idx))

        if motion_index == 0:
            self.stepTab_motion1 = step_tab

    def update_time_from_spinbox(self, motion_idx, step_idx, run_spinbox, delay_spinbox):
        self.times[motion_idx][step_idx][0] = run_spinbox.value()
        self.times[motion_idx][step_idx][1] = delay_spinbox.value()
        self.InfoLabel.setText(f"(motion{motion_idx+1} step{step_idx+1} time : {run_spinbox.value():.1f} {delay_spinbox.value():.1f})")

    def update_step_from_tab(self, motion_idx, step_idx):
        self.motion = motion_idx
        self.step = step_idx
        for motor in self.motors:
            if self.groupBoxes[motor.dxl_id].isChecked():
                self.savedLineEdits[motor.dxl_id].setText(
                    str(self.motions[self.motion][self.step][motor.dxl_id-11])
                )
        self.InfoLabel.setText(f"(Open Motion & Step : motion{motion_idx+1}, step{step_idx+1})")

    def motionAddButton_callback(self):
        self.add_motion_tab(len(self.motions))


    def motionDeleteButton_callback(self):
        if len(self.motions) <= 1:
            self.InfoLabel.setText("Cannot delete the last remaining motion.")
            return

        index_to_delete = self.motion

        # 데이터 제거
        self.motions.pop(index_to_delete)
        self.times.pop(index_to_delete)
        if hasattr(self, 'stepTabs') and index_to_delete in self.stepTabs:
            del self.stepTabs[index_to_delete]

        # 탭 제거
        self.motionTab.removeTab(index_to_delete)

        # 인덱스 재정렬 (stepTabs dict 등의 인덱스 수정)
        if hasattr(self, 'stepTabs'):
            new_stepTabs = {}
            for i, key in enumerate(sorted(self.stepTabs.keys())):
                if key > index_to_delete:
                    new_stepTabs[key - 1] = self.stepTabs[key]
                elif key < index_to_delete:
                    new_stepTabs[key] = self.stepTabs[key]
            self.stepTabs = new_stepTabs

        # 현재 선택된 모션 인덱스 갱신
        self.motion = max(0, index_to_delete - 1)
        self.motionTab.setCurrentIndex(self.motion)

        # 초기화
        self.step = 0
        self.InfoLabel.setText(f"(Motion {index_to_delete+1} deleted. Now at motion {self.motion+1})")

    def stepAddButton_callback(self):
        motion_idx = self.motion
        step_idx = len(self.motions[motion_idx])
        motion_name = f"motion{motion_idx+1}"

        # 데이터 리스트에 새 step 추가
        self.motions[motion_idx].append([0, 0, 0, 0, 0])
        self.times[motion_idx].append([1.0, 0.0])

        # stepTab 위젯 불러오기
        step_tab = self.stepTabs[motion_idx]

        # 새 step 위젯 생성
        step_widget = QWidget()
        step_layout = QFormLayout(step_widget)

        run_spin = QDoubleSpinBox()
        run_spin.setObjectName(f"runTimeSpinBoxStep{step_idx+1}_{motion_name}")
        run_spin.setRange(1.0, 10.0)
        run_spin.setSingleStep(0.1)
        run_spin.setDecimals(1)
        run_spin.setValue(1.0)

        delay_spin = QDoubleSpinBox()
        delay_spin.setObjectName(f"endDelaySpinBoxStep{step_idx+1}_{motion_name}")
        delay_spin.setRange(0.0, 10.0)
        delay_spin.setSingleStep(0.1)
        delay_spin.setDecimals(1)
        delay_spin.setValue(0.0)

        # 레이아웃에 배치
        step_layout.addRow("Run Time (s):", run_spin)
        step_layout.addRow("End Delay (s):", delay_spin)

        # stepTab에 추가
        step_tab.addTab(step_widget, f"step{step_idx+1}")

        # 콜백 연결
        run_spin.valueChanged.connect(lambda: self.update_time_from_spinbox(motion_idx, step_idx, run_spin, delay_spin))
        delay_spin.valueChanged.connect(lambda: self.update_time_from_spinbox(motion_idx, step_idx, run_spin, delay_spin))

        self.InfoLabel.setText(f"(Step {step_idx+1} added to Motion {motion_idx+1})")

    def stepDeleteButton_callback(self):
        motion_idx = self.motion
        step_idx = self.step

        if len(self.motions[motion_idx]) <= 1:
            self.InfoLabel.setText("Cannot delete the last remaining step.")
            return

        # 데이터 삭제
        self.motions[motion_idx].pop(step_idx)
        self.times[motion_idx].pop(step_idx)

        # stepTab에서 탭 삭제
        step_tab = self.stepTabs[motion_idx]
        step_tab.removeTab(step_idx)

        # 인덱스 재조정
        new_step = max(0, step_idx - 1)
        step_tab.setCurrentIndex(new_step)
        self.step = new_step

        self.InfoLabel.setText(f"(Step {step_idx+1} deleted from Motion {motion_idx+1})")

    def motionTab_callback(self):
        self.motion = self.motionTab.currentIndex()
        self.step = 0
        for motor in self.motors:
            if self.groupBoxes[motor.dxl_id].isChecked():
                self.savedLineEdits[motor.dxl_id].setText(
                    str(self.motions[self.motion][self.step][int(motor.dxl_id)-11])
                )
        self.InfoLabel.setText("(Open Motion & Step : motion%d, step%d)"%(self.motion+1, self.step+1))
        
    def stepTab_motion1_callback(self):
        self.step = self.stepTab_motion1.currentIndex()
        for motor in self.motors:
            if self.groupBoxes[motor.dxl_id].isChecked():
                self.savedLineEdits[motor.dxl_id].setText(
                    str(self.motions[self.motion][self.step][int(motor.dxl_id)-11])
                )
        self.InfoLabel.setText("(Open Motion & Step : motion%d, step%d)"%(self.motion+1, self.step+1))
    
    def dxlAllSelectButton_callback(self):
        for dxl_id in range(11, 16):
            self.groupBoxes[dxl_id].setChecked(True)
    
    def dxlAllUnSelectButton_callback(self):
        for dxl_id in range(11, 16):
            self.groupBoxes[dxl_id].setChecked(False)
    
    def torqueOnButton_callback(self):
        for motor in self.motors:
            if self.groupBoxes[motor.dxl_id].isChecked():
                motor.set_torque(True)
        self.InfoLabel.setText("(Torque Control : Torque ON)")

    def torqueOffButton_callback(self):
        for motor in self.motors:
            if self.groupBoxes[motor.dxl_id].isChecked():
                motor.set_torque(False)
        self.InfoLabel.setText("(Torque Control : Torque OFF)")

    def m1s1_time_callback(self):
        self.times[self.motion][self.step][0] = self.runTimeSpinBoxStep1_motion1.value()
        self.times[self.motion][self.step][1] = self.endDelaySpinBoxStep1_motion1.value()
        self.InfoLabel.setText("(motion%d step%d time : %.1f %.1f)"%(self.motion+1, self.step+1, self.times[self.motion][self.step][0], self.times[self.motion][self.step][1]))
        
    def saveToJsonButton_callback(self):
        spin_numbers = []
        next_motions = []

        for i in range(len(self.motions)):
            spin_box = self.spinNumberBoxes.get(i)
            next_box = self.nextMotionBoxes.get(i)

            spin_numbers.append(spin_box.value() if spin_box else 1)
            next_motions.append(next_box.value() if next_box else 0)

        data = {
            "motions": self.motions,
            "times": self.times,
            "spin_numbers": spin_numbers,
            "next_motions": next_motions
        }

        try:
            json_path = os.path.join(BASE_DIR, "saved_motions.json")
            with open(json_path, "w") as f:
                json.dump(data, f, indent=2)
            self.InfoLabel.setText("(Motions successfully saved to 'saved_motions.json')")
        except Exception as e:
            self.InfoLabel.setText(f"(Error saving motions: {e})")

    def writeFromJsonButton_callback(self):
        json_path = os.path.join(BASE_DIR, "saved_motions.json")
        self.InfoLabel.setText("(loading motion data...)")
        self.json_thread = JsonLoaderThread(json_path)
        self.json_thread.finished.connect(self.handle_json_loaded)
        self.json_thread.error.connect(self.handle_json_error)
        self.json_thread.start()
        
    def handle_json_loaded(self, data):
        self.motions = data.get("motions", [[[0, 0, 0, 0, 0]]])
        self.times = data.get("times", [[[1.0, 0.0]]])
        spin_numbers = data.get("spin_numbers", [1] * len(self.motions))
        next_motions = data.get("next_motions", [0] * len(self.motions))

        # UI 초기화
        self.motionTab.clear()
        self.stepTabs = {}
        self.spinNumberBoxes.clear()
        self.nextMotionBoxes.clear()

        self.motion = 0
        self.step = 0

        for motion_idx, motion_steps in enumerate(self.motions):
            self.add_motion_tab(motion_idx)  # 기존 함수로 탭 및 spinBox 구성

            # spin, next 설정
            self.spinNumberBoxes[motion_idx].setValue(spin_numbers[motion_idx])
            self.nextMotionBoxes[motion_idx].setValue(next_motions[motion_idx])

            step_tab = self.stepTabs[motion_idx]
            step_tab.blockSignals(True)  # signal 차단

            # 기본 step1 삭제 후 재생성
            step_tab.removeTab(0)

            for step_idx, _ in enumerate(motion_steps):
                run_val = self.times[motion_idx][step_idx][0]
                delay_val = self.times[motion_idx][step_idx][1]

                step_widget = QWidget()
                step_layout = QFormLayout(step_widget)

                run_spin = QDoubleSpinBox()
                run_spin.setRange(1.0, 10.0)
                run_spin.setSingleStep(0.1)
                run_spin.setDecimals(1)
                run_spin.setValue(run_val)

                delay_spin = QDoubleSpinBox()
                delay_spin.setRange(0.0, 10.0)
                delay_spin.setSingleStep(0.1)
                delay_spin.setDecimals(1)
                delay_spin.setValue(delay_val)

                step_layout.addRow("Run Time (s):", run_spin)
                step_layout.addRow("End Delay (s):", delay_spin)
                step_tab.addTab(step_widget, f"step{step_idx+1}")

                # 연결
                run_spin.valueChanged.connect(lambda _, m=motion_idx, s=step_idx, r=run_spin, d=delay_spin:
                                              self.update_time_from_spinbox(m, s, r, d))
                delay_spin.valueChanged.connect(lambda _, m=motion_idx, s=step_idx, r=run_spin, d=delay_spin:
                                                self.update_time_from_spinbox(m, s, r, d))

            step_tab.blockSignals(False)
            step_tab.setCurrentIndex(0)
            step_tab.currentChanged.connect(lambda idx, m=motion_idx: self.update_step_from_tab(m, idx))

        self.motionTab.setCurrentIndex(0)
        self.stepTab_motion1 = self.stepTabs[0] if 0 in self.stepTabs else None
        self.InfoLabel.setText("(Successfully loaded saved motion data.)")


    def handle_json_error(self, msg):
        self.InfoLabel.setText(f"(JSON error: {msg})")

def ros_spin(node):
    rclpy.spin(node)


def main():
    rclpy.init()
    app = QApplication(sys.argv)

    window = manipulatorGUINode()
    window.show()

    ros_thread = threading.Thread(target=ros_spin, args=(window,), daemon=True)
    ros_thread.start()

    app.exec_()

    window.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()

