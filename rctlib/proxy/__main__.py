from __future__ import annotations

from argparse import ArgumentParser, Namespace
import asyncio
from collections.abc import Sequence
from datetime import timedelta
import logging
import socket
import sys
from typing import cast

from ..const import DEFAULT_CACHE_AGE, DEFAULT_CLIENT_PORT, DEFAULT_SERVER_PORT
from ..utils import configure_logger
from .manager import Manager
from .protocol import ClientProtocol, ServerProtocol

logger = logging.getLogger(__name__)

background_tasks: set[asyncio.Task[None]] = set()


async def create_client_connect_task(
    args: Arguments, manager: Manager, delay: int = 0
) -> None:
    task = asyncio.create_task(connect_client(args, manager, delay))
    background_tasks.add(task)
    task.add_done_callback(background_tasks.discard)


async def connect_client(args: Arguments, manager: Manager, delay: int = 0) -> None:
    if delay:
        await asyncio.sleep(delay)
    loop = asyncio.get_running_loop()
    manager.client_connection_attempt += 1
    if manager.client_connection_attempt < 4:
        logger.info("Try to connect to inverter")
    try:
        await loop.create_connection(
            protocol_factory=lambda: ClientProtocol(manager),
            host=args.client_host,
            port=args.client_port,
        )
    except OSError:
        await create_client_connect_task(args, manager, 5)
        return

    logger.info("Connected to inverter")
    manager.client_connection_attempt = 0
    manager.on_con_lost = loop.create_future()
    await manager.on_con_lost
    manager.on_con_lost = None
    await create_client_connect_task(args, manager, 5)


async def run_app(args: Arguments) -> None:
    loop = asyncio.get_running_loop()
    manager = Manager(cache_age=timedelta(seconds=15))
    await create_client_connect_task(args, manager, 1)
    logger.info("Start server")
    server = await loop.create_server(
        lambda: ServerProtocol(manager),
        # host="127.0.0.1",
        port=args.server_port,
        family=socket.AF_INET,
    )

    try:
        async with server:
            await server.serve_forever()
    except asyncio.CancelledError:
        logger.info("Stopping server")
    finally:
        if manager.client_connection is not None:
            manager.client_connection.close()


class Arguments(Namespace):
    verbose: int
    server_port: int
    client_host: str
    client_port: int
    cache_age: int


def create_args_parser() -> ArgumentParser:
    parser = ArgumentParser()
    parser.add_argument(
        "-v", "--verbose",
        action="count",
        default=0,
        help="Print debug log",
    )
    parser.add_argument(
        "--server-port",
        metavar="PORT",
        type=int,
        default=DEFAULT_SERVER_PORT,
        help=f"Port to expose the proxy server on [default: {DEFAULT_SERVER_PORT}]"
    )
    parser.add_argument(
        "--client-port",
        metavar="PORT",
        default=DEFAULT_CLIENT_PORT,
        help=f"Port for RCT inverter [default: {DEFAULT_CLIENT_PORT}]",
    )
    parser.add_argument(
        "--cache-age",
        metavar="SECONDS",
        type=int,
        default=DEFAULT_CACHE_AGE,
        help=f"Allowed message cache age [default: {DEFAULT_CACHE_AGE}s]",
    )

    group = parser.add_argument_group("Required arguments")
    group.add_argument(
        "--client-host",
        metavar="HOST",
        required=True,
        help="Address for RCT inverter",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    argv = argv or sys.argv[1:]
    parser = create_args_parser()
    args = cast(Arguments, parser.parse_args(argv))

    configure_logger(verbose=args.verbose != 0)
    logger.debug(f"Arguments: {args}")
    asyncio.run(run_app(args), debug=args.verbose != 0)
    return 0


if __name__ == "__main__":
    sys.exit(main())
