from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, IntEnum
import logging

logger = logging.getLogger(__name__)

START_TOKEN = 0x2b
ESCAPE_TOKEN = 0x2d


def calculate_crc16(data: bytes) -> int:
    crcsum = 0xFFFF
    buffer = bytearray(data)

    # Add padding
    if len(data) & 0x01:
        buffer.append(0)

    for byte in buffer:
        for j in range(8):
            bit = byte >> (7 - j) & 1 == 1
            c15 = (crcsum >> 15) & 1 == 1
            crcsum <<= 1
            if c15 ^ bit:
                crcsum ^= 0x1021
        crcsum &= 0xFFFF
    return crcsum


class Command(IntEnum):
    READ = 0x01
    WRITE = 0x02
    LONG_WRITE = 0x03
    RESPONSE = 0x05
    LONG_RESPONSE = 0x06
    READ_PERIODICALLY = 0x08

    def is_long_cmd(self) -> bool:
        return self in {
            Command.LONG_WRITE,
            Command.LONG_RESPONSE,
        }

    def is_response(self) -> bool:
        return self in {
            Command.RESPONSE,
            Command.LONG_RESPONSE,
        }


@dataclass
class Message:
    command: Command
    id: bytes
    data: bytes | None
    raw: bytes


class State(Enum):
    START = 0
    COMMAND = 1
    LENGTH = 2
    ID = 4
    DATA = 5
    CRC = 6
    DONE = 7


def parse_message(buffer: bytes) -> tuple[Message | None, int]:
    data = bytearray()
    consumed_bytes = 0

    command: Command | None = None
    id: bytes | None = None
    msg_data: bytes | None = None
    raw: bytes | None = None

    flag_escape = False
    start_token = 0
    data_length = 0
    is_long_command = False
    state = State.START

    for i, d in enumerate(buffer):
        if flag_escape:
            flag_escape = False
            if d == START_TOKEN and len(data) == 0:
                continue
        elif d == ESCAPE_TOKEN:
            flag_escape = True
            continue

        c = d.to_bytes()
        if len(data) == 0:
            if d == START_TOKEN:
                start_token = i
                consumed_bytes += 1
                state = State.COMMAND
                data += c
            continue
        data += c

        match state:
            case State.START:
                assert False, "invalid state"
            case State.COMMAND:
                command = Command(data[-1])
                is_long_command = command.is_long_cmd()
                consumed_bytes += 1
                state = State.LENGTH
            case State.LENGTH:
                if is_long_command and len(data) - consumed_bytes != 2:
                    continue
                length_cnt = 2 if is_long_command else 1
                data_length = int.from_bytes(data[-length_cnt:])
                consumed_bytes += length_cnt
                state = State.ID
            case State.ID:
                if len(data) - consumed_bytes != 4:
                    continue
                id = bytes(data[-4:])
                consumed_bytes += 4
                data_length -= 4
                if data_length > 0:
                    state = State.DATA
                elif data_length == 0:
                    state = State.CRC
                else:
                    assert False, "data_length should not be negative"
            case State.DATA:
                # Skipped if data length is 0
                assert data_length > 0
                if len(data) - consumed_bytes != data_length:
                    continue
                msg_data = bytes(data[-data_length:])
                consumed_bytes += data_length
                state = State.CRC
            case State.CRC:
                if len(data) - consumed_bytes != 2:
                    continue
                consumed_bytes = i + 1
                raw = bytes(buffer[start_token:start_token + consumed_bytes])
                checksum = calculate_crc16(data[1:-2])
                if int.from_bytes(data[-2:]) != checksum:
                    logger.warning(
                        f"Invalid checksum for buffer: {raw.hex(" ")}, "
                        f"checksum={checksum}"
                    )
                    start_token = consumed_bytes
                    break
                state = State.DONE
                break

    if state != State.DONE:
        return None, start_token

    assert command is not None
    assert id is not None
    assert raw is not None

    message = Message(
        command=command,
        id=id,
        data=msg_data,
        raw=raw,
    )
    return message, consumed_bytes
