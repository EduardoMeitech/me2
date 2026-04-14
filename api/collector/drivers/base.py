"""Abstract base class for PLC communication drivers."""

from abc import ABC, abstractmethod
from typing import Any
import logging


class BaseDriver(ABC):
    """Base class that all PLC drivers must implement.

    Provides a uniform interface for connecting to, reading from, and writing
    to industrial PLCs regardless of the underlying protocol.
    """

    def __init__(self, host: str, port: int, name: str = "unknown", **kwargs):
        self.host = host
        self.port = port
        self.name = name
        self.logger = logging.getLogger(f"{__name__}.{name}")

    @abstractmethod
    async def connect(self) -> bool:
        """Establish connection to the PLC. Returns True on success."""
        ...

    @abstractmethod
    async def disconnect(self) -> None:
        """Gracefully close the connection."""
        ...

    @abstractmethod
    async def is_connected(self) -> bool:
        """Check whether the driver currently has an active connection."""
        ...

    @abstractmethod
    async def read_variable(self, address: dict) -> Any:
        """Read a single variable from the PLC.

        Args:
            address: Protocol-specific address descriptor (register, DB, node, etc.).

        Returns:
            The decoded value, or None on failure.
        """
        ...

    @abstractmethod
    async def write_variable(self, address: dict, value: Any) -> bool:
        """Write a value to the PLC.

        Args:
            address: Protocol-specific address descriptor.
            value: The value to write.

        Returns:
            True on success, False on failure.
        """
        ...
