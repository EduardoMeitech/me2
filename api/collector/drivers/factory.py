"""Factory for creating PLC driver instances from configuration dicts."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from .modbus_driver import ModbusDriver
from .snap7_driver import Snap7Driver
from .opcua_driver import OpcUaDriver

if TYPE_CHECKING:
    from .base import BaseDriver

logger = logging.getLogger(__name__)

_PROTOCOL_MAP: dict[str, type] = {
    "modbus": ModbusDriver,
    "s7": Snap7Driver,
    "opcua": OpcUaDriver,
}


def create_driver(config: dict) -> BaseDriver:
    """Instantiate the appropriate driver based on ``config["protocol"]``.

    Expected config structure::

        {
            "serial_number": "EQ-001",
            "protocol": "modbus",         # or "s7" / "opcua"
            "connection": {
                "host": "192.168.1.10",
                "port": 502,              # optional, protocol default used
                ...                       # extra params forwarded to driver
            }
        }

    Raises:
        ValueError: If the protocol is unknown or connection info is missing.
    """
    protocol = config.get("protocol", "").lower()
    if protocol not in _PROTOCOL_MAP:
        raise ValueError(
            f"Unknown protocol '{protocol}'. "
            f"Supported: {', '.join(sorted(_PROTOCOL_MAP))}"
        )

    connection: dict = config.get("connection", {})
    if not connection.get("host"):
        raise ValueError(
            f"Missing 'host' in connection config for equipment "
            f"'{config.get('serial_number', '?')}'"
        )

    driver_cls = _PROTOCOL_MAP[protocol]
    name = config.get("serial_number", "unknown")

    # Build keyword arguments from the connection dict.
    # The driver __init__ will pick what it needs and **kwargs absorbs the rest.
    kwargs = {**connection, "name": name}

    logger.info(
        "Creating %s driver for '%s' -> %s:%s",
        protocol,
        name,
        connection.get("host"),
        connection.get("port", "(default)"),
    )
    return driver_cls(**kwargs)
