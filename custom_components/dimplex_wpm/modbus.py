"""Schlanker Modbus-TCP-Client für den Wärmepumpenmanager.

Bewusst ohne pymodbus: Der WPM braucht nur wenige Funktionscodes, und so gibt es
keine Versionskonflikte mit der Modbus-Integration von Home Assistant.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
import logging
import struct
from typing import AsyncIterator

_LOGGER = logging.getLogger(__name__)

FC_READ_COILS = 0x01
FC_READ_HOLDING = 0x03
FC_READ_INPUT = 0x04
FC_WRITE_COIL = 0x05
FC_WRITE_REGISTER = 0x06


class ModbusError(Exception):
    """Verbindungs- oder Protokollfehler."""


class ModbusExceptionResponse(ModbusError):
    """Der WPM hat mit einer Modbus-Exception geantwortet (z. B. ungültige Adresse)."""

    def __init__(self, function: int, code: int) -> None:
        super().__init__(f"Modbus-Exception {code} auf Funktion {function}")
        self.function = function
        self.code = code


class DimplexModbusClient:
    """Modbus-TCP-Verbindung mit Sperre, damit Schreibfolgen nicht unterbrochen werden."""

    def __init__(self, host: str, port: int, unit: int, timeout: float = 3.0) -> None:
        self.host = host
        self.port = port
        self.unit = unit
        self.timeout = timeout
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._transaction = 0
        self._lock = asyncio.Lock()
        # Ältere Gateways antworten nur auf Funktion 4, neuere nur auf 3
        self._read_fc = FC_READ_HOLDING

    @asynccontextmanager
    async def session(self) -> AsyncIterator[DimplexModbusClient]:
        """Exklusiver Zugriff für zusammenhängende Lese- oder Schreibfolgen."""
        async with self._lock:
            yield self

    async def close(self) -> None:
        if self._writer is not None:
            self._writer.close()
            try:
                await self._writer.wait_closed()
            except OSError:
                pass
        self._reader = self._writer = None

    async def _connect(self) -> None:
        if self._writer is not None and not self._writer.is_closing():
            return
        try:
            self._reader, self._writer = await asyncio.wait_for(
                asyncio.open_connection(self.host, self.port), self.timeout
            )
        except (OSError, TimeoutError) as err:
            self._reader = self._writer = None
            raise ModbusError(f"Keine Verbindung zu {self.host}:{self.port}: {err}") from err

    async def _request(self, function: int, payload: bytes) -> bytes:
        await self._connect()
        assert self._reader is not None and self._writer is not None
        self._transaction = (self._transaction + 1) % 0x10000
        pdu = bytes([function]) + payload
        header = struct.pack(">HHHB", self._transaction, 0, len(pdu) + 1, self.unit)
        try:
            self._writer.write(header + pdu)
            await self._writer.drain()
            while True:
                head = await asyncio.wait_for(self._reader.readexactly(7), self.timeout)
                transaction, _, length, _ = struct.unpack(">HHHB", head)
                body = await asyncio.wait_for(self._reader.readexactly(length - 1), self.timeout)
                if transaction == self._transaction:
                    break
                _LOGGER.debug("Verspätete Antwort %s verworfen", transaction)
        except (OSError, TimeoutError, asyncio.IncompleteReadError) as err:
            await self.close()
            raise ModbusError(f"Übertragung fehlgeschlagen: {err}") from err
        if body[0] == function | 0x80:
            raise ModbusExceptionResponse(function, body[1])
        if body[0] != function:
            await self.close()
            raise ModbusError(f"Unerwartete Funktion {body[0]} statt {function}")
        return body[1:]

    async def read_registers(self, address: int, count: int = 1) -> list[int]:
        """Register lesen, als vorzeichenlose 16-Bit-Werte."""
        payload = struct.pack(">HH", address, count)
        try:
            data = await self._request(self._read_fc, payload)
        except ModbusExceptionResponse as err:
            if err.code != 1:
                raise
            # Funktion nicht unterstützt: auf den anderen Lesecode wechseln
            self._read_fc = FC_READ_INPUT if self._read_fc == FC_READ_HOLDING else FC_READ_HOLDING
            data = await self._request(self._read_fc, payload)
        if data[0] != count * 2:
            raise ModbusError("Antwortlänge passt nicht")
        return list(struct.unpack(f">{count}H", data[1:]))

    async def read_coils(self, address: int, count: int = 1) -> list[bool]:
        data = await self._request(FC_READ_COILS, struct.pack(">HH", address, count))
        bits = data[1:]
        return [bool(bits[i // 8] >> (i % 8) & 1) for i in range(count)]

    async def write_register(self, address: int, value: int) -> None:
        await self._request(FC_WRITE_REGISTER, struct.pack(">HH", address, value & 0xFFFF))

    async def write_coil(self, address: int, value: bool) -> None:
        await self._request(FC_WRITE_COIL, struct.pack(">HH", address, 0xFF00 if value else 0))
