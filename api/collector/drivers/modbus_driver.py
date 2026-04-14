"""Modbus TCP driver using pymodbus AsyncModbusTcpClient."""

from __future__ import annotations

import asyncio
import struct
from typing import Any

from pymodbus.client import AsyncModbusTcpClient

from .base import BaseDriver


class ModbusDriver(BaseDriver):
    """Driver for PLCs accessible via Modbus TCP (holding registers)."""

    MAX_RETRIES = 1
    RETRY_DELAY_S = 2.0

    def __init__(
        self,
        host: str,
        port: int = 502,
        unit_id: int = 1,
        name: str = "modbus",
        **kwargs,
    ):
        super().__init__(host=host, port=port, name=name, **kwargs)
        self.unit_id = unit_id
        self._client: AsyncModbusTcpClient | None = None

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------

    async def connect(self) -> bool:
        """Connect to the Modbus TCP server."""
        self.logger.info(
            "Connecting to Modbus TCP %s:%d (unit=%d)", self.host, self.port, self.unit_id
        )
        try:
            self._client = AsyncModbusTcpClient(
                host=self.host,
                port=self.port,
            )
            connected = await self._client.connect()
            if connected:
                self.logger.info("Modbus TCP connected to %s:%d", self.host, self.port)
            else:
                self.logger.error("Modbus TCP connection FAILED for %s:%d", self.host, self.port)
            return bool(connected)
        except Exception:
            self.logger.exception("Modbus TCP connect exception for %s:%d", self.host, self.port)
            return False

    async def disconnect(self) -> None:
        """Close the Modbus TCP connection."""
        if self._client is not None:
            self.logger.info("Disconnecting Modbus TCP %s:%d", self.host, self.port)
            self._client.close()
            self._client = None

    async def is_connected(self) -> bool:
        """Return True if the underlying transport is open."""
        if self._client is None:
            return False
        return self._client.connected

    # ------------------------------------------------------------------
    # Reconnect helper
    # ------------------------------------------------------------------

    async def _ensure_connected(self) -> bool:
        """Attempt reconnection up to MAX_RETRIES times if not connected."""
        if await self.is_connected():
            return True

        for attempt in range(1, self.MAX_RETRIES + 1):
            self.logger.warning(
                "Modbus reconnect attempt %d/%d for %s:%d",
                attempt,
                self.MAX_RETRIES,
                self.host,
                self.port,
            )
            if await self.connect():
                return True
            await asyncio.sleep(self.RETRY_DELAY_S)

        self.logger.error("Modbus reconnect exhausted for %s:%d", self.host, self.port)
        return False

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    async def read_variable(self, address: dict) -> Any:
        """Read a variable described by *address*.

        Supported address dict fields:
            register : int           -- starting holding-register address
            type     : str           -- "word" | "dword" | "real" | "string" | "bit"
            count    : int           -- number of registers to read (for strings)
            overflow_fix : bool      -- if True and type=="word", apply signed fix
        """
        if not await self._ensure_connected():
            return None

        register: int = address["register"]
        var_type: str = address.get("type", "word")
        overflow_fix: bool = address.get("overflow_fix", False)

        try:
            if var_type == "word":
                return await self._read_word(register, overflow_fix)
            elif var_type == "dword":
                return await self._read_dword(register)
            elif var_type == "real":
                return await self._read_real(register)
            elif var_type == "string":
                count = address.get("count", 1)
                return await self._read_string(register, count)
            elif var_type == "bit":
                bit_index = address.get("bit", 0)
                return await self._read_bit(register, bit_index)
            else:
                self.logger.error("Unsupported Modbus type '%s'", var_type)
                return None
        except Exception:
            self.logger.exception(
                "Modbus read error register=%d type=%s on %s:%d",
                register,
                var_type,
                self.host,
                self.port,
            )
            return None

    async def _read_word(self, register: int, overflow_fix: bool = False) -> int | None:
        """Read a single 16-bit holding register."""
        self.logger.debug("Reading word register=%d", register)
        result = await self._client.read_holding_registers(
            address=register, count=1, slave=self.unit_id
        )
        if result.isError():
            self.logger.error("Modbus read error at register %d: %s", register, result)
            return None
        value = result.registers[0]
        if overflow_fix and value >= 32768:
            value -= 65536
        self.logger.debug("Word register=%d value=%d", register, value)
        return value

    async def _read_dword(self, register: int) -> int | None:
        """Read a 32-bit unsigned value from two consecutive registers."""
        self.logger.debug("Reading dword register=%d", register)
        result = await self._client.read_holding_registers(
            address=register, count=2, slave=self.unit_id
        )
        if result.isError():
            self.logger.error("Modbus read error at register %d: %s", register, result)
            return None
        high, low = result.registers[0], result.registers[1]
        value = (high << 16) | low
        self.logger.debug("Dword register=%d value=%d", register, value)
        return value

    async def _read_real(self, register: int) -> float | None:
        """Read an IEEE-754 32-bit float from two consecutive registers."""
        self.logger.debug("Reading real register=%d", register)
        result = await self._client.read_holding_registers(
            address=register, count=2, slave=self.unit_id
        )
        if result.isError():
            self.logger.error("Modbus read error at register %d: %s", register, result)
            return None
        raw = struct.pack(">HH", result.registers[0], result.registers[1])
        value = struct.unpack(">f", raw)[0]
        self.logger.debug("Real register=%d value=%.4f", register, value)
        return round(value, 4)

    async def _read_string(self, register: int, count: int) -> str | None:
        """Read a string from *count* consecutive registers (2 ASCII chars each)."""
        self.logger.debug("Reading string register=%d count=%d", register, count)
        result = await self._client.read_holding_registers(
            address=register, count=count, slave=self.unit_id
        )
        if result.isError():
            self.logger.error("Modbus read error at register %d: %s", register, result)
            return None
        chars: list[str] = []
        for reg in result.registers:
            high_byte = (reg >> 8) & 0xFF
            low_byte = reg & 0xFF
            if high_byte:
                chars.append(chr(high_byte))
            if low_byte:
                chars.append(chr(low_byte))
        value = "".join(chars).rstrip("\x00")
        self.logger.debug("String register=%d value='%s'", register, value)
        return value

    async def _read_bit(self, register: int, bit_index: int) -> bool | None:
        """Read a single bit from a holding register."""
        self.logger.debug("Reading bit register=%d bit=%d", register, bit_index)
        result = await self._client.read_holding_registers(
            address=register, count=1, slave=self.unit_id
        )
        if result.isError():
            self.logger.error("Modbus read error at register %d: %s", register, result)
            return None
        value = bool((result.registers[0] >> bit_index) & 1)
        self.logger.debug("Bit register=%d.%d value=%s", register, bit_index, value)
        return value

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    async def write_variable(self, address: dict, value: Any) -> bool:
        """Write a value to a holding register (currently supports 'word' type only)."""
        if not await self._ensure_connected():
            return False

        register: int = address["register"]
        var_type: str = address.get("type", "word")

        if var_type != "word":
            self.logger.error("Modbus write not implemented for type '%s'", var_type)
            return False

        try:
            self.logger.debug("Writing word register=%d value=%d", register, int(value))
            result = await self._client.write_register(
                address=register, value=int(value), slave=self.unit_id
            )
            if result.isError():
                self.logger.error("Modbus write error at register %d: %s", register, result)
                return False
            self.logger.info("Modbus write OK register=%d value=%d", register, int(value))
            return True
        except Exception:
            self.logger.exception(
                "Modbus write exception register=%d on %s:%d", register, self.host, self.port
            )
            return False
