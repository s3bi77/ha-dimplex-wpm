"""Gemeinsame Test-Fixtures: ein simulierter Wärmepumpenmanager."""

from __future__ import annotations

import asyncio
import struct

import pytest

from custom_components.dimplex_wpm.modbus import ModbusExceptionResponse

# Werte wie bei einer SIW 8TES mit WPM M3.17
REGISTERS = {
    1: 85,  # Außen 8,5 °C
    2: 249,
    3: 534,
    4: 0,
    5: 248,
    6: 261,
    7: 153,
    11: 215,
    12: 0,
    13: 480,
    19: 0xFC19,  # -99,9 °C: kein Fühler
    20: 0xFC19,
    53: 260,
    58: 53,
    65: 13,
    66: 3,
    67: 17,
    **{a: 1000 + a for a in range(71, 80)},
    103: 2,
    104: 0,
    105: 0,
    106: 0,
    5015: 1,
    5016: 0,
    5017: 0,
    5036: 19,
    5037: 35,
    5038: 40,
    5045: 10,
    5046: 0,
    5047: 53,
    5048: 60,
    5096: 1234,
    5097: 5,
    5098: 0,
    5099: 10,
    5100: 1,
    5101: 0,
    5127: 4321,
    5128: 7,
    5129: 0,
    5130: 0,
    5145: 30,
    5167: 0,
    5168: 520,
    5169: 0,
    5170: 130,
}
COILS = {3: False, 4: False, 5: False, 6: False, **{a: False for a in range(41, 72)}}
COILS[41] = True
COILS[45] = True


class FakeClient:
    """Ersetzt den Modbus-Client; Lücken in der Tabelle gelten als ungültige Adresse."""

    def __init__(self, host: str, port: int, unit: int, timeout: float = 3.0) -> None:
        self.host = host
        self.registers = dict(REGISTERS)
        self.coils = dict(COILS)
        self.writes: list[tuple[int, int]] = []
        self._lock = asyncio.Lock()
        FakeClient.last = self

    def session(self):
        return self._lock

    async def close(self) -> None:
        pass

    async def read_registers(self, address: int, count: int = 1) -> list[int]:
        values = [self.registers.get(a) for a in range(address, address + count)]
        if None in values:
            raise ModbusExceptionResponse(3, 2)
        return values

    async def read_coils(self, address: int, count: int = 1) -> list[bool]:
        values = [self.coils.get(a) for a in range(address, address + count)]
        if None in values:
            raise ModbusExceptionResponse(1, 2)
        return values

    async def write_register(self, address: int, value: int) -> None:
        self.writes.append((address, value))
        self.registers[address] = value

    async def write_coil(self, address: int, value: bool) -> None:
        self.coils[address] = value


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Lädt die Integration aus custom_components."""
    yield


@pytest.fixture
def fake_client(monkeypatch) -> type[FakeClient]:
    monkeypatch.setattr("custom_components.dimplex_wpm.coordinator.DimplexModbusClient", FakeClient)
    monkeypatch.setattr("custom_components.dimplex_wpm.config_flow.DimplexModbusClient", FakeClient)
    monkeypatch.setattr("custom_components.dimplex_wpm.const.ROOM_SWITCH_DELAY", 0)
    monkeypatch.setattr("custom_components.dimplex_wpm.coordinator.ROOM_SWITCH_DELAY", 0)
    return FakeClient


class ModbusServer:
    """Minimaler Modbus-TCP-Server für Tests des echten Clients."""

    def __init__(self, registers: dict[int, int], supported=(1, 3, 5, 6)) -> None:
        self.registers = registers
        self.supported = supported
        self.server: asyncio.base_events.Server | None = None
        self.port = 0

    async def start(self) -> None:
        self.server = await asyncio.start_server(self._handle, "127.0.0.1", 0)
        self.port = self.server.sockets[0].getsockname()[1]

    async def stop(self) -> None:
        self.server.close()
        await self.server.wait_closed()

    async def _handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            while True:
                head = await reader.readexactly(7)
                tid, _, length, unit = struct.unpack(">HHHB", head)
                pdu = await reader.readexactly(length - 1)
                writer.write(self._reply(tid, unit, pdu))
                await writer.drain()
        except asyncio.IncompleteReadError:
            writer.close()

    def _reply(self, tid: int, unit: int, pdu: bytes) -> bytes:
        function = pdu[0]
        address, value = struct.unpack(">HH", pdu[1:5])
        if function not in self.supported:
            body = bytes([function | 0x80, 1])
        elif function in (3, 4):
            values = [self.registers.get(a) for a in range(address, address + value)]
            if None in values:
                body = bytes([function | 0x80, 2])
            else:
                body = bytes([function, value * 2]) + struct.pack(f">{value}H", *values)
        elif function == 1:
            bits = 0
            for i in range(value):
                bits |= (self.registers.get(address + i, 0) & 1) << i
            nbytes = (value + 7) // 8
            body = bytes([function, nbytes]) + bits.to_bytes(nbytes, "little")
        else:
            self.registers[address] = value if function == 6 else int(value == 0xFF00)
            body = pdu[:5]
        return struct.pack(">HHHB", tid, 0, len(body) + 1, unit) + body
