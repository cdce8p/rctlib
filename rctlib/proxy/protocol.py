from __future__ import annotations

import asyncio
import logging

from ..message import parse_message
from .manager import Manager

logger = logging.getLogger(__name__)


class ProtocolBase(asyncio.Protocol):
    def __init__(self, manager: Manager) -> None:
        self.manager = manager
        self.buffer = bytearray()


class ClientProtocol(ProtocolBase):
    """Connection to RCT inverter."""

    def connection_made(self, transport: asyncio.WriteTransport) -> None:
        self.manager.register_client_connection(transport)

    def data_received(self, data: bytes) -> None:
        self.buffer += data
        while True:
            message, consumed_bytes = parse_message(self.buffer)
            if consumed_bytes:
                self.buffer = self.buffer[consumed_bytes:]
            if message is None:
                break
            self.manager.handle_client_message(message)

    def connection_lost(self, exc: Exception | None) -> None:
        logger.info("The inverter closed the connection")
        self.manager.remove_client_connection()
        assert self.manager.on_con_lost
        self.manager.on_con_lost.set_result(None)


class ServerProtocol(ProtocolBase):
    """Connection with HA and EVCC."""

    def connection_made(self, transport: asyncio.WriteTransport) -> None:
        self.manager.register_server_connection(self, transport)

    def data_received(self, data: bytes) -> None:
        self.buffer += data
        while True:
            message, consumed_bytes = parse_message(self.buffer)
            if consumed_bytes:
                self.buffer = self.buffer[consumed_bytes:]
            if message is None:
                break
            self.manager.handle_server_message(self, message)

    def connection_lost(self, exc: Exception | None) -> None:
        logger.info("The proxy server closed the connection")
        self.manager.remove_server_connection(self)
