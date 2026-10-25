"""Tests des Modbus-TCP-Clients gegen einen lokalen Server."""

from __future__ import annotations

import pytest

from custom_components.dimplex_wpm.modbus import (
    DimplexModbusClient,
    ModbusError,
    ModbusExceptionResponse,
)

from .conftest import ModbusServer


@pytest.fixture
async def server(socket_enabled):
    server = ModbusServer({1: 0xFFF6, 2: 249, 5047: 53, 41: 1, 42: 0, 43: 1})
    await server.start()
    yield server
    await server.stop()


async def test_read_and_write(server: ModbusServer) -> None:
    client = DimplexModbusClient("127.0.0.1", server.port, 1)
    async with client.session():
        assert await client.read_registers(1, 2) == [0xFFF6, 249]
        assert await client.read_coils(41, 3) == [True, False, True]
        await client.write_register(5047, 55)
        assert await client.read_registers(5047) == [55]
    await client.close()


async def test_illegal_address(server: ModbusServer) -> None:
    client = DimplexModbusClient("127.0.0.1", server.port, 1)
    with pytest.raises(ModbusExceptionResponse) as err:
        await client.read_registers(3, 1)
    assert err.value.code == 2
    await client.close()


async def test_falls_back_to_input_registers(socket_enabled) -> None:
    server = ModbusServer({1: 85}, supported=(4,))
    await server.start()
    client = DimplexModbusClient("127.0.0.1", server.port, 1)
    assert await client.read_registers(1) == [85]
    await client.close()
    await server.stop()


async def test_connection_refused(socket_enabled, unused_tcp_port) -> None:
    client = DimplexModbusClient("127.0.0.1", unused_tcp_port, 1, timeout=1)
    with pytest.raises(ModbusError):
        await client.read_registers(1)
