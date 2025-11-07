from __future__ import annotations

import pytest

from rctlib.message import calculate_crc16, parse_message, Command


@pytest.mark.parametrize(
    ("cmd", "is_long"),
    [
        pytest.param(
            Command.READ,
            False,
            id="read",
        ),
        pytest.param(
            Command.WRITE,
            False,
            id="write",
        ),
        pytest.param(
            Command.LONG_WRITE,
            True,
            id="long_write",
        ),
        pytest.param(
            Command.RESPONSE,
            False,
            id="response",
        ),
        pytest.param(
            Command.LONG_RESPONSE,
            True,
            id="long_response",
        ),
        pytest.param(
            Command.READ_PERIODICALLY,
            False,
            id="read_periodically",
        ),
    ],
)
def test_commands(cmd: Command, is_long: bool) -> None:
    assert cmd.is_long_cmd() is is_long


@pytest.mark.parametrize(
    ("input_str", "checksum"),
    [
        pytest.param(
            "01 04 a5 9c 84 28",
            60395,
        ),
        pytest.param(
            "05 08 a5 9c 84 28 00 00 00 00",
            53776,
        ),
        pytest.param(
            "01 04 2b c1 e7 2b",
            58892,
        ),
        pytest.param(
            "05 08 2b c1 e7 2b 00 00 00 00",
            52791,
        ),
    ]
)
def test_calculate_crc16(input_str: str, checksum: int) -> None:
    data = bytes.fromhex(input_str)
    assert calculate_crc16(data) == checksum


@pytest.mark.parametrize(
    ("buffer_str", "cmd", "id_str", "msg_data_str"),
    [
        pytest.param(
            "2b 01 04 a5 9c 84 28 eb eb",
            Command.READ,
            "a5 9c 84 28",
            None,
            id="read",
        ),
        pytest.param(
            "2b 05 08 a5 9c 84 28 00 00 00 00 d2 10",
            Command.RESPONSE,
            "a5 9c 84 28",
            "00 00 00 00",
            id="response",
        ),
        pytest.param(
            "2b 01 04 2d 2b c1 e7 2d 2b e6 0c",
            Command.READ,
            "2b c1 e7 2b",
            None,
            id="read_with_escapes",
        ),
        pytest.param(
            "2b 05 08 2d 2b c1 e7 2d 2b 00 00 00 00 ce 37",
            Command.RESPONSE,
            "2b c1 e7 2b",
            "00 00 00 00",
            id="response_with_escapes",
        ),
        pytest.param(
            "2b 01 04 40 0f 01 5b 58 b4",
            Command.READ,
            "40 0f 01 5b",
            None,
            id="doc_read_battery_power",
        ),
        pytest.param(
            "2b 01 04 db 2d 2d 69 ae 55 ab",
            Command.READ,
            "db 2d 69 ae",
            None,
            id="doc_read_inverter_ac_power",
        ),
    ],
)
def test_parse_message(
    buffer_str: str, cmd: Command, id_str: str, msg_data_str: str | None
) -> None:
    buffer = bytes.fromhex(buffer_str)
    message, consumed_bytes = parse_message(buffer)
    assert message is not None
    assert message.command == cmd
    assert message.id == bytes.fromhex(id_str)
    if msg_data_str is not None:
        assert message.data == bytes.fromhex(msg_data_str)
    else:
        assert message.data is None
    assert len(buffer) == consumed_bytes


@pytest.mark.parametrize(
    ("buffer_str", "is_message", "consumed_bytes_expected"),
    [
        pytest.param(
            "00 00",
            False,
            0,
            id="no_start_token_1"
        ),
        pytest.param(
            "00 00 2d 2b 00 00",
            False,
            0,
            id="no_start_token_2"
        ),
        pytest.param(
            "00 00 2b 01 04 a5",
            False,
            2,
            id="incomplete_message",
        ),
        pytest.param(
            "00 00 2b 01 04 a5 9c 84 28 eb eb",
            True,
            11,
            id="ignore_front_padding"
        ),
        pytest.param(
            "00 00 2b 01 04 a5 9c 84 28 eb eb 2b 01 04",
            True,
            11,
            id="two_messages_only_one_parsed_incomplete"
        ),
        pytest.param(
            "00 00 2b 01 04 a5 9c 84 28 eb eb 2b 01 04 a5 9c 84 28 eb eb",
            True,
            11,
            id="two_messages_only_one_parsed"
        ),
        pytest.param(
            "00 00 2b 01 04 a5 9c 84 28 eb ff",
            False,  # No message for invalid checksum
            11,
            id="invalid_checksum"
        ),
    ],
)
def test_parse_message_partial_buffer(
    buffer_str: str, is_message: bool, consumed_bytes_expected: int
) -> None:
    buffer = bytes.fromhex(buffer_str)
    message, consumed_bytes = parse_message(buffer)
    assert (message is not None) == is_message
    assert consumed_bytes == consumed_bytes_expected
