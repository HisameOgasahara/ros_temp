#!/usr/bin/env python3

import argparse

from dynamixel_sdk import COMM_SUCCESS, PacketHandler, PortHandler


DXL_IDS = [11, 12, 13, 14, 15]

PROTOCOL_VERSION = 2.0
DEFAULT_BAUDRATE = 1_000_000
DEFAULT_DEVICE = "/dev/ttyACM1"

ADDR_OPERATING_MODE = 11
ADDR_DRIVE_MODE = 10
ADDR_TORQUE_ENABLE = 64
ADDR_MAX_POSITION_LIMIT = 48
ADDR_MIN_POSITION_LIMIT = 52
ADDR_GOAL_POSITION = 116
ADDR_PRESENT_POSITION = 132
ADDR_PRESENT_VELOCITY = 128
ADDR_PRESENT_TEMPERATURE = 146
ADDR_PRESENT_INPUT_VOLTAGE = 144
ADDR_HARDWARE_ERROR_STATUS = 70

MODE_NAMES = {
    0: "Current Control",
    1: "Velocity Control",
    3: "Position Control",
    4: "Extended Position Control",
    5: "Current-based Position Control",
    16: "PWM Control",
}


def read(packet, port, dxl_id, address, size, label):
    if size == 1:
        value, result, error = packet.read1ByteTxRx(port, dxl_id, address)
    elif size == 2:
        value, result, error = packet.read2ByteTxRx(port, dxl_id, address)
    elif size == 4:
        value, result, error = packet.read4ByteTxRx(port, dxl_id, address)
    else:
        raise ValueError(f"unsupported size: {size}")

    if result != COMM_SUCCESS:
        raise RuntimeError(f"{label}: {packet.getTxRxResult(result)}")
    if error != 0:
        raise RuntimeError(f"{label}: {packet.getRxPacketError(error)}")
    return value


def main():
    parser = argparse.ArgumentParser(
        description="Read DYNAMIXEL XL430 position limits and current state."
    )
    parser.add_argument("--device", default=DEFAULT_DEVICE, help="ex: /dev/ttyACM1")
    parser.add_argument("--baudrate", type=int, default=DEFAULT_BAUDRATE)
    parser.add_argument("--ids", type=int, nargs="+", default=DXL_IDS)
    args = parser.parse_args()

    port = PortHandler(args.device)
    packet = PacketHandler(PROTOCOL_VERSION)

    if not port.openPort():
        raise SystemExit(f"Failed to open port: {args.device}")
    if not port.setBaudRate(args.baudrate):
        port.closePort()
        raise SystemExit(f"Failed to set baudrate: {args.baudrate}")

    print(f"device={args.device}, baudrate={args.baudrate}")
    print("position unit: 0~4095 = 0~360 degrees, about 0.088 degree per count")
    print()

    try:
        for dxl_id in args.ids:
            print(f"ID {dxl_id}")
            try:
                operating_mode = read(
                    packet, port, dxl_id, ADDR_OPERATING_MODE, 1, "operating_mode"
                )
                drive_mode = read(packet, port, dxl_id, ADDR_DRIVE_MODE, 1, "drive_mode")
                torque = read(packet, port, dxl_id, ADDR_TORQUE_ENABLE, 1, "torque")
                min_pos = read(
                    packet, port, dxl_id, ADDR_MIN_POSITION_LIMIT, 4, "min_position"
                )
                max_pos = read(
                    packet, port, dxl_id, ADDR_MAX_POSITION_LIMIT, 4, "max_position"
                )
                goal_pos = read(packet, port, dxl_id, ADDR_GOAL_POSITION, 4, "goal")
                cur_pos = read(
                    packet, port, dxl_id, ADDR_PRESENT_POSITION, 4, "present"
                )
                velocity = read(
                    packet, port, dxl_id, ADDR_PRESENT_VELOCITY, 4, "velocity"
                )
                temp = read(
                    packet, port, dxl_id, ADDR_PRESENT_TEMPERATURE, 1, "temperature"
                )
                voltage_raw = read(
                    packet, port, dxl_id, ADDR_PRESENT_INPUT_VOLTAGE, 2, "voltage"
                )
                hw_error = read(
                    packet, port, dxl_id, ADDR_HARDWARE_ERROR_STATUS, 1, "hw_error"
                )

                mode_name = MODE_NAMES.get(operating_mode, "Unknown")
                print(f"  operating mode : {operating_mode} ({mode_name})")
                print(f"  drive mode     : {drive_mode}")
                print(f"  torque         : {'ON' if torque else 'OFF'}")
                print(f"  min limit      : {min_pos}")
                print(f"  max limit      : {max_pos}")
                print(f"  goal position  : {goal_pos}")
                print(f"  current pos    : {cur_pos}")
                print(f"  velocity       : {velocity}")
                print(f"  temperature    : {temp} C")
                print(f"  voltage        : {voltage_raw / 10:.1f} V")
                print(f"  hardware error : {hw_error}")
            except RuntimeError as exc:
                print(f"  ERROR: {exc}")
            print()
    finally:
        port.closePort()


if __name__ == "__main__":
    main()
