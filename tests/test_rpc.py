import pytest
from unittest.mock import AsyncMock, patch
import httpx

from erc20_scanner.rpc import EthRPC, RPCError, hex_to_int, int_to_hex


def test_hex_conversions():
    assert hex_to_int("0x0") == 0
    assert hex_to_int("0x10") == 16
    assert hex_to_int("0x0100") == 256
    assert hex_to_int("0x") == 0
    assert hex_to_int(None) == 0
    assert int_to_hex(0) == "0x0"
    assert int_to_hex(255) == "0xff"


@pytest.mark.asyncio
async def test_get_block_number_success():
    mock_response = httpx.Response(
        200,
        json={"jsonrpc": "2.0", "id": 1, "result": "0x10d4f"},
        request=httpx.Request("POST", "http://localhost:8545"),
    )

    client = EthRPC("http://localhost:8545")
    with patch.object(client._client, "post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response
        block_num = await client.get_block_number()
        assert block_num == 68943
        assert mock_post.await_count == 1


@pytest.mark.asyncio
async def test_rpc_error_raising():
    mock_response = httpx.Response(
        200,
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "error": {"code": -32000, "message": "execution reverted"},
        },
        request=httpx.Request("POST", "http://localhost:8545"),
    )

    client = EthRPC("http://localhost:8545")
    with patch.object(client._client, "post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response
        with pytest.raises(RPCError) as exc_info:
            await client.get_block_number()
        assert exc_info.value.code == -32000
        assert "execution reverted" in str(exc_info.value)


@pytest.mark.asyncio
async def test_get_logs_payload():
    mock_response = httpx.Response(
        200,
        json={"jsonrpc": "2.0", "id": 1, "result": []},
        request=httpx.Request("POST", "http://localhost:8545"),
    )

    client = EthRPC("http://localhost:8545")
    with patch.object(client._client, "post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response
        logs = await client.get_logs(
            from_block=100,
            to_block=200,
            address="0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
            topics=["0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"],
        )
        assert logs == []
        called_payload = mock_post.call_args[1]["json"]
        assert called_payload["method"] == "eth_getLogs"
        params = called_payload["params"][0]
        assert params["fromBlock"] == "0x64"
        assert params["toBlock"] == "0xc8"
        assert params["address"] == "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"


@pytest.mark.asyncio
async def test_batch_response_reordering():
    # Some public nodes shuffle batch responses; verify we sort by request id
    batch_result = [
        {"jsonrpc": "2.0", "id": 2, "result": "0x20"},
        {"jsonrpc": "2.0", "id": 1, "result": "0x10"},
    ]
    mock_response = httpx.Response(
        200,
        json=batch_result,
        request=httpx.Request("POST", "http://localhost:8545"),
    )

    client = EthRPC("http://localhost:8545")
    with patch.object(client._client, "post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response
        calls = [
            ("eth_blockNumber", []),
            ("eth_blockNumber", []),
        ]
        res = await client.batch_call(calls)
        assert res == ["0x10", "0x20"]


@pytest.mark.asyncio
async def test_query_limit_exceeded_error_detection():
    # Infura / Alchemy returns -32005 or specific message on oversized block range
    client = EthRPC("http://localhost:8545")
    err = RPCError(-32005, "query returned more than 10000 results")
    assert client.is_range_too_large(err)

    generic_err = RPCError(-32603, "Internal error")
    assert not client.is_range_too_large(generic_err)
