from __future__ import annotations

import asyncio
from collections import defaultdict
from datetime import UTC, datetime, timedelta
import logging

from ..message import Command, Message

logger = logging.getLogger(__name__)


class Manager:
    def __init__(self, cache_age: timedelta) -> None:
        self.cache_age = cache_age
        self.server_connections: dict[asyncio.Protocol, asyncio.WriteTransport] = {}
        self.client_connection: asyncio.WriteTransport | None = None
        self.pending_responses: dict[bytes, set[asyncio.Protocol]] = defaultdict(set)
        self.cached_responses: dict[bytes, tuple[datetime, Message]] = {}

        self.client_connection_attempt = 0
        self.on_con_lost: asyncio.Future[None] | None = None

    def register_server_connection(
        self, protocol: asyncio.Protocol, transport: asyncio.WriteTransport
    ) -> None:
        """Register HA or EVCC connection."""
        self.server_connections[protocol] = transport

    def register_client_connection(self, transport: asyncio.WriteTransport) -> None:
        """Register RCT inverter connection."""
        assert self.client_connection is None
        self.client_connection = transport

    def remove_server_connection(self, protocol: asyncio.Protocol) -> None:
        """Remove HA or EVCC connection."""
        self.server_connections.pop(protocol)
        for tracking in self.pending_responses.values():
            tracking.discard(protocol)

    def remove_client_connection(self) -> None:
        """Remove RCT inverter connection."""
        self.client_connection = None

    def handle_server_message(self, sender: asyncio.Protocol, message: Message) -> None:
        """Message received from HA or EVCC."""
        logger.debug(f"[HA] new message:\t{message.raw.hex(" ")}")
        assert self.client_connection is not None
        cached_response = self.cached_responses.get(message.id)
        if message.command == Command.READ:
            if (
                cached_response
                and cached_response[0] > datetime.now(UTC) - self.cache_age
            ):
                logger.debug(f"Use cached response for {message.id.hex(" ")}")
                self.server_connections[sender].write(cached_response[1].raw)
                return

            self.pending_responses[message.id].add(sender)
        self.client_connection.write(message.raw)

    def handle_client_message(self, message: Message) -> None:
        """Message received from RCT inverter."""
        logger.debug(f"[RCT] new message:\t{message.raw.hex(" ")}")
        assert message.command.is_response()
        self.cached_responses[message.id] = (datetime.now(UTC), message)
        awaiting_response = self.pending_responses.get(message.id, ())
        if not awaiting_response:
            logger.debug(f"Discard response: {message.raw.hex(" ")}")
            return

        for sender in awaiting_response:
            self.server_connections[sender].write(message.raw)
        awaiting_response.clear()
