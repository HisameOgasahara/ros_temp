from launch import LaunchDescription
from launch.actions import ExecuteProcess, TimerAction
from launch_ros.actions import Node


def generate_launch_description():

    # 1️⃣ chmod 먼저
    chmod_dev = ExecuteProcess(
        cmd=['sudo', 'chmod', '777', '/dev/ttyACM1'],
        output='screen'
    )

    # 2️⃣ Dynamixel low-level node
    dynamixel_node = ExecuteProcess(
        cmd=[
            'python3',
            '/home/jetson/turtlebot3_ws/src/DynamixelSDK/ros/dynamixel_sdk_examples/src/read_write_node_omx.py'
        ],
        output='log'
    )

    # 3️⃣ Manipulator motion controller
    manipulator_ctrl = Node(
        package='manipulator',
        executable='manipulatorCtrl',
        name='manipulatorCtrl',
        output='screen'
    )

    return LaunchDescription([
        chmod_dev,

        # 포트 권한 잡힌 뒤 실행되도록 약간 딜레이
        TimerAction(
            period=1.0,
            actions=[dynamixel_node]
        ),

        TimerAction(
            period=2.0,
            actions=[manipulator_ctrl]
        ),
    ])

