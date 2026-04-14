"""Snap7 (S7comm) driver for Siemens S7 PLCs."""

from __future__ import annotations

import asyncio
from typing import Any

import snap7
import snap7.util

from .base import BaseDriver


class Snap7Driver(BaseDriver):
    """Driver for Siemens S7 PLCs using the snap7 library.

    Because snap7.client.Client is synchronous, every blocking call is
    dispatched to a thread via ``asyncio.to_thread``.
    """

    MAX_RETRIES = 1
    RETRY_DELAY_S = 2.0

    def __init__(
        self,
        host: str,
        rack: int = 0,
        slot: int = 1,
        name: str = "s7",
        **kwargs,
    ):
        # port is not user-configurable for S7 (always 102)
        super().__init__(host=host, port=102, name=name, **kwargs)
        self.rack = rack
        self.slot = slot
        self._client: snap7.client.Client | None = None

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------

    async def connect(self) -> bool:
        """Connect to the S7 PLC."""
        self.logger.info(
            "Connecting to S7 PLC %s rack=%d slot=%d", self.host, self.rack, self.slot
        )
        try:
            client = snap7.client.Client()
            await asyncio.to_thread(client.connect, self.host, self.rack, self.slot)
            connected = await asyncio.to_thread(client.get_connected)
            if connected:
                self._client = client
                self.logger.info("S7 connected to %s", self.host)
            else:
                self.logger.error("S7 connection FAILED for %s", self.host)
            return bool(connected)
        except Exception:
            self.logger.exception("S7 connect exception for %s", self.host)
            return False

    async def disconnect(self) -> None:
        """Disconnect from the PLC."""
        if self._client is not None:
            self.logger.info("Disconnecting S7 %s", self.host)
            try:
                await asyncio.to_thread(self._client.disconnect)
            except Exception:
                self.logger.exception("S7 disconnect error for %s", self.host)
            finally:
                self._client = None

    async def is_connected(self) -> bool:
        """Return True if the snap7 client reports a live connection."""
        if self._client is None:
            return False
        try:
            return await asyncio.to_thread(self._client.get_connected)
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Reconnect helper
    # ------------------------------------------------------------------

    async def _ensure_connected(self) -> bool:
        """Attempt reconnection up to MAX_RETRIES times if not connected."""
        if await self.is_connected():
            return True

        for attempt in range(1, self.MAX_RETRIES + 1):
            self.logger.warning(
                "S7 reconnect attempt %d/%d for %s",
                attempt,
                self.MAX_RETRIES,
                self.host,
            )
            # Tear down any stale client before retrying
            await self.disconnect()
            if await self.connect():
                return True
            await asyncio.sleep(self.RETRY_DELAY_S)

        self.logger.error("S7 reconnect exhausted for %s", self.host)
        return False

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    async def read_variable(self, address: dict) -> Any:
        """Read a variable described by *address*.

        Supported address dict fields:
            db     : int    -- data block number
            byte   : int    -- starting byte offset inside the DB
            type   : str    -- "bit" | "byte" | "word" | "dword" | "real" | "string"
            bit    : int    -- bit offset within the byte (only for type=="bit")
            length : int    -- max string length (only for type=="string")
        """
        if not await self._ensure_connected():
            return None

        db_number: int = address["db"]
        byte_offset: int = address["byte"]
        var_type: str = address.get("type", "word")

        try:
            if var_type == "bit":
                return await self._read_bit(db_number, byte_offset, address.get("bit", 0))
            elif var_type == "byte":
                return await self._read_byte(db_number, byte_offset)
            elif var_type == "word":
                return await self._read_word(db_number, byte_offset)
            elif var_type == "dword":
                return await self._read_dword(db_number, byte_offset)
            elif var_type == "real":
                return await self._read_real(db_number, byte_offset)
            elif var_type == "string":
                length = address.get("length", 254)
                return await self._read_string(db_number, byte_offset, length)
            else:
                self.logger.error("Unsupported S7 type '%s'", var_type)
                return None
        except Exception:
            self.logger.exception(
                "S7 read error db=%d byte=%d type=%s on %s",
                db_number,
                byte_offset,
                var_type,
                self.host,
            )
            return None

    async def _read_bit(self, db: int, byte_offset: int, bit_offset: int) -> bool | None:
        self.logger.debug("Reading S7 bit DB%d.DBX%d.%d", db, byte_offset, bit_offset)
        data = await asyncio.to_thread(self._client.db_read, db, byte_offset, 1)
        value = snap7.util.get_bool(data, 0, bit_offset)
        self.logger.debug("S7 bit DB%d.DBX%d.%d = %s", db, byte_offset, bit_offset, value)
        return value

    async def _read_byte(self, db: int, byte_offset: int) -> int | None:
        self.logger.debug("Reading S7 byte DB%d.DBB%d", db, byte_offset)
        data = await asyncio.to_thread(self._client.db_read, db, byte_offset, 1)
        value = data[0]
        self.logger.debug("S7 byte DB%d.DBB%d = %d", db, byte_offset, value)
        return value

    async def _read_word(self, db: int, byte_offset: int) -> int | None:
        self.logger.debug("Reading S7 word DB%d.DBW%d", db, byte_offset)
        data = await asyncio.to_thread(self._client.db_read, db, byte_offset, 2)
        value = snap7.util.get_int(data, 0)
        self.logger.debug("S7 word DB%d.DBW%d = %d", db, byte_offset, value)
        return value

    async def _read_dword(self, db: int, byte_offset: int) -> int | None:
        self.logger.debug("Reading S7 dword DB%d.DBD%d", db, byte_offset)
        data = await asyncio.to_thread(self._client.db_read, db, byte_offset, 4)
        value = snap7.util.get_dword(data, 0)
        self.logger.debug("S7 dword DB%d.DBD%d = %d", db, byte_offset, value)
        return value

    async def _read_real(self, db: int, byte_offset: int) -> float | None:
        self.logger.debug("Reading S7 real DB%d.DBD%d", db, byte_offset)
        data = await asyncio.to_thread(self._client.db_read, db, byte_offset, 4)
        value = snap7.util.get_real(data, 0)
        self.logger.debug("S7 real DB%d.DBD%d = %.4f", db, byte_offset, value)
        return round(value, 4)

    async def _read_string(self, db: int, byte_offset: int, length: int) -> str | None:
        """Read an S7 STRING.

        S7 strings have a 2-byte header (max_len, actual_len) followed by the
        character data.  We read ``length + 2`` bytes so snap7's get_string
        can decode the header.
        """
        size = length + 2
        self.logger.debug("Reading S7 string DB%d.DBB%d len=%d", db, byte_offset, length)
        data = await asyncio.to_thread(self._client.db_read, db, byte_offset, size)
        value = snap7.util.get_string(data, 0)
        self.logger.debug("S7 string DB%d.DBB%d = '%s'", db, byte_offset, value)
        return value

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    async def write_variable(self, address: dict, value: Any) -> bool:
        """Write a value to the PLC data block.

        Currently supports 'word' and 'bit' types.
        """
        if not await self._ensure_connected():
            return False

        db_number: int = address["db"]
        byte_offset: int = address["byte"]
        var_type: str = address.get("type", "word")

        try:
            if var_type == "word":
                return await self._write_word(db_number, byte_offset, int(value))
            elif var_type == "bit":
                bit_offset = address.get("bit", 0)
                return await self._write_bit(db_number, byte_offset, bit_offset, bool(value))
            else:
                self.logger.error("S7 write not implemented for type '%s'", var_type)
                return False
        except Exception:
            self.logger.exception(
                "S7 write exception db=%d byte=%d type=%s on %s",
                db_number,
                byte_offset,
                var_type,
                self.host,
            )
            return False

    async def _write_word(self, db: int, byte_offset: int, value: int) -> bool:
        self.logger.debug("Writing S7 word DB%d.DBW%d = %d", db, byte_offset, value)
        data = await asyncio.to_thread(self._client.db_read, db, byte_offset, 2)
        snap7.util.set_int(data, 0, value)
        await asyncio.to_thread(self._client.db_write, db, byte_offset, data)
        self.logger.info("S7 write OK DB%d.DBW%d = %d", db, byte_offset, value)
        return True

    async def _write_bit(self, db: int, byte_offset: int, bit_offset: int, value: bool) -> bool:
        self.logger.debug(
            "Writing S7 bit DB%d.DBX%d.%d = %s", db, byte_offset, bit_offset, value
        )
        data = await asyncio.to_thread(self._client.db_read, db, byte_offset, 1)
        snap7.util.set_bool(data, 0, bit_offset, value)
        await asyncio.to_thread(self._client.db_write, db, byte_offset, data)
        self.logger.info("S7 write OK DB%d.DBX%d.%d = %s", db, byte_offset, bit_offset, value)
        return True
