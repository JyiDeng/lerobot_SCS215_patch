#!/usr/bin/env python3
"""读取和设置 SCS215 的保护、负载和电压寄存器。

SCS215 没有可直接读取的电流反馈寄存器。本工具读取 Present_Load，
它表示舵机内部估计的负载，不等于安培数。实际电流需要在电源与驱动板之间
使用外部电流表或电流计测量。
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass

import scservo_sdk as scs


PROTOCOL_VERSION = 1
BAUDRATE = 1_000_000
DEFAULT_IDS = tuple(range(1, 7))
EXPECTED_MODEL = 1315

# SCS control table addresses.
MAX_TORQUE_LIMIT = 16
PROTECTIVE_TORQUE = 37
PROTECTION_TIME = 38
OVERLOAD_TORQUE = 39
TORQUE_ENABLE = 40
LOCK = 48
PRESENT_POSITION = 56
PRESENT_LOAD = 60
PRESENT_VOLTAGE = 62
PRESENT_TEMPERATURE = 63
STATUS = 65


@dataclass
class ServoClient:
    port: object
    packet: object


def parse_ids(args: argparse.Namespace) -> list[int]:
    if args.all_ids and args.ids:
        raise ValueError("--all-ids 和 --ids 不能同时使用")
    ids = list(DEFAULT_IDS) if args.all_ids else (args.ids or [6])
    if any(not 0 <= motor_id <= 253 for motor_id in ids):
        raise ValueError("舵机 ID 必须在 0 到 253 之间")
    return ids


def open_client(path: str) -> ServoClient:
    port = scs.PortHandler(path)
    packet = scs.PacketHandler(PROTOCOL_VERSION)
    if not port.openPort():
        raise RuntimeError(f"无法打开串口 {path}")
    if not port.setBaudRate(BAUDRATE):
        port.closePort()
        raise RuntimeError(f"无法设置波特率 {BAUDRATE}")
    return ServoClient(port, packet)


def check_motor(client: ServoClient, motor_id: int) -> int:
    model, comm, error = client.packet.ping(client.port, motor_id)
    if comm != scs.COMM_SUCCESS:
        raise RuntimeError(f"ID {motor_id} 通信失败：{client.packet.getTxRxResult(comm)}")
    if error != 0:
        raise RuntimeError(f"ID {motor_id} 返回错误：{client.packet.getRxPacketError(error)}")
    if model != EXPECTED_MODEL:
        raise RuntimeError(f"ID {motor_id} 返回型号 {model}，预期型号为 {EXPECTED_MODEL}")
    return model


def read_byte(client: ServoClient, motor_id: int, address: int) -> int:
    value, comm, error = client.packet.read1ByteTxRx(client.port, motor_id, address)
    if comm != scs.COMM_SUCCESS:
        raise RuntimeError(client.packet.getTxRxResult(comm))
    if error != 0:
        raise RuntimeError(client.packet.getRxPacketError(error))
    return int(value)


def read_word(client: ServoClient, motor_id: int, address: int) -> int:
    value, comm, error = client.packet.read2ByteTxRx(client.port, motor_id, address)
    if comm != scs.COMM_SUCCESS:
        raise RuntimeError(client.packet.getTxRxResult(comm))
    if error != 0:
        raise RuntimeError(client.packet.getRxPacketError(error))
    return int(value)


def write_byte(client: ServoClient, motor_id: int, address: int, value: int) -> None:
    comm, error = client.packet.write1ByteTxRx(client.port, motor_id, address, value)
    if comm != scs.COMM_SUCCESS:
        raise RuntimeError(client.packet.getTxRxResult(comm))
    if error != 0:
        raise RuntimeError(client.packet.getRxPacketError(error))


def write_word(client: ServoClient, motor_id: int, address: int, value: int) -> None:
    comm, error = client.packet.write2ByteTxRx(client.port, motor_id, address, value)
    if comm != scs.COMM_SUCCESS:
        raise RuntimeError(client.packet.getTxRxResult(comm))
    if error != 0:
        raise RuntimeError(client.packet.getRxPacketError(error))


def set_torque(client: ServoClient, motor_id: int, enabled: bool) -> None:
    write_byte(client, motor_id, TORQUE_ENABLE, int(enabled))
    write_byte(client, motor_id, LOCK, int(enabled))


def inspect_one(client: ServoClient, motor_id: int) -> None:
    check_motor(client, motor_id)
    print(
        f"id={motor_id} "
        f"position={read_word(client, motor_id, PRESENT_POSITION)} "
        f"load_raw={read_word(client, motor_id, PRESENT_LOAD)} "
        f"voltage={read_byte(client, motor_id, PRESENT_VOLTAGE) / 10:.1f}V "
        f"temperature={read_byte(client, motor_id, PRESENT_TEMPERATURE)}C "
        f"status={read_byte(client, motor_id, STATUS)} "
        f"max_torque={read_word(client, motor_id, MAX_TORQUE_LIMIT)} "
        f"protective_torque={read_byte(client, motor_id, PROTECTIVE_TORQUE)} "
        f"protection_time={read_byte(client, motor_id, PROTECTION_TIME)} "
        f"overload_torque={read_byte(client, motor_id, OVERLOAD_TORQUE)}"
    )


def inspect_command(args: argparse.Namespace) -> None:
    ids = parse_ids(args)
    client = open_client(args.port)
    try:
        for motor_id in ids:
            try:
                inspect_one(client, motor_id)
            except Exception as exc:
                print(f"id={motor_id} 读取失败：{exc}", file=sys.stderr)
    finally:
        client.port.closePort()


def require_percent(name: str, value: int) -> int:
    if not 0 <= value <= 100:
        raise ValueError(f"{name} 必须在0到100之间")
    return value


def write_settings_command(args: argparse.Namespace) -> None:
    ids = parse_ids(args)
    if args.max_torque_limit is not None and not 0 <= args.max_torque_limit <= 1000:
        raise ValueError("--max-torque-limit 必须在0到1000之间，1000表示100%")
    if args.protective_torque is not None:
        require_percent("--protective-torque", args.protective_torque)
    if args.overload_torque is not None:
        require_percent("--overload-torque", args.overload_torque)
    if args.protection_time is not None and not 0 <= args.protection_time <= 255:
        raise ValueError("--protection-time 必须在0到255之间")
    if all(value is None for value in (args.max_torque_limit, args.protective_torque, args.protection_time, args.overload_torque)):
        raise ValueError("至少提供一个要修改的参数")

    print("将修改以下舵机：", ", ".join(map(str, ids)))
    print("修改前请确认机械臂已托住，且没有人和物体处于运动范围内。")
    if not args.yes:
        input("按回车继续，按 Ctrl+C 取消。")

    client = open_client(args.port)
    torque_disabled: list[int] = []
    try:
        for motor_id in ids:
            check_motor(client, motor_id)
            set_torque(client, motor_id, False)
            torque_disabled.append(motor_id)

        for motor_id in ids:
            if args.max_torque_limit is not None:
                write_word(client, motor_id, MAX_TORQUE_LIMIT, args.max_torque_limit)
            if args.protective_torque is not None:
                write_byte(client, motor_id, PROTECTIVE_TORQUE, args.protective_torque)
            if args.protection_time is not None:
                write_byte(client, motor_id, PROTECTION_TIME, args.protection_time)
            if args.overload_torque is not None:
                write_byte(client, motor_id, OVERLOAD_TORQUE, args.overload_torque)

        print("参数写入完成。")
    finally:
        for motor_id in torque_disabled:
            try:
                set_torque(client, motor_id, True)
            except Exception as exc:
                print(f"id={motor_id} 恢复力矩失败：{exc}", file=sys.stderr)
        client.port.closePort()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["inspect", "set"])
    parser.add_argument("--port", required=True)
    parser.add_argument("--ids", nargs="+", type=int)
    parser.add_argument("--all-ids", action="store_true")
    parser.add_argument("--max-torque-limit", type=int)
    parser.add_argument("--protective-torque", type=int)
    parser.add_argument("--protection-time", type=int)
    parser.add_argument("--overload-torque", type=int)
    parser.add_argument("--yes", action="store_true")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.command == "inspect":
        inspect_command(args)
    else:
        write_settings_command(args)


if __name__ == "__main__":
    main()
