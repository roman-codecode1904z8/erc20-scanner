import pytest
from erc20_scanner.abi import (
    TRANSFER_TOPIC,
    APPROVAL_TOPIC,
    decode_transfer_log,
    decode_approval_log,
    extract_address_from_topic,
)

SAMPLE_TRANSFER_LOG = {
    "address": "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48",
    "topics": [
        TRANSFER_TOPIC,
        "0x000000000000000000000000d8da6bf26964af9d7eed9e03e53415d37aa96045",
        "0x00000000000000000000000028c6c06298d514db089934071355e5743bf21d60",
    ],
    "data": "0x0000000000000000000000000000000000000000000000000000000005f5e100",
    "blockNumber": "0x10d4f20",
    "transactionHash": "0xabc123",
    "logIndex": "0x2a",
}

SAMPLE_APPROVAL_LOG = {
    "address": "0x6b175474e89094c44da98b954eedeac495271d0f",
    "topics": [
        APPROVAL_TOPIC,
        "0x0000000000000000000000001111111111111111111111111111111111111111",
        "0x0000000000000000000000002222222222222222222222222222222222222222",
    ],
    "data": "0xffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff",
    "blockNumber": "0x10d4f21",
    "transactionHash": "0xdef456",
    "logIndex": "0x00",
}

def test_decode_transfer():
    ev = decode_transfer_log(SAMPLE_TRANSFER_LOG)
    assert ev is not None
    assert ev.contract == "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"
    assert ev.from_addr == "0xd8da6bf26964af9d7eed9e03e53415d37aa96045"
    assert ev.to_addr == "0x28c6c06298d514db089934071355e5743bf21d60"
    assert ev.amount == 100000000
    assert ev.block_number == 17649440
    assert ev.tx_hash == "0xabc123"

def test_decode_approval():
    ev = decode_approval_log(SAMPLE_APPROVAL_LOG)
    assert ev is not None
    assert ev.owner == "0x1111111111111111111111111111111111111111"
    assert ev.spender == "0x2222222222222222222222222222222222222222"
    assert ev.amount == 2**256 - 1

def test_decode_mismatched_topic():
    assert decode_transfer_log(SAMPLE_APPROVAL_LOG) is None
    assert decode_approval_log(SAMPLE_TRANSFER_LOG) is None

def test_zero_value_transfer():
    # Some spam contracts emit 0-value transfers with empty data or 32 zero bytes
    log = dict(SAMPLE_TRANSFER_LOG)
    log["data"] = "0x" + "0" * 64
    ev = decode_transfer_log(log)
    assert ev is not None
    assert ev.amount == 0

def test_empty_data_defaults_to_zero():
    log = dict(SAMPLE_TRANSFER_LOG)
    log["data"] = "0x"
    ev = decode_transfer_log(log)
    assert ev is not None
    assert ev.amount == 0

def test_malformed_topics_skipped():
    log = dict(SAMPLE_TRANSFER_LOG)
    # missing 'to' topic (erc721 or weird custom token)
    log["topics"] = [TRANSFER_TOPIC, "0x000000000000000000000000d8da6bf26964af9d7eed9e03e53415d37aa96045"]
    assert decode_transfer_log(log) is None

def test_extract_address_from_topic():
    topic = "0x000000000000000000000000d8da6bf26964af9d7eed9e03e53415d37aa96045"
    addr = extract_address_from_topic(topic)
    assert addr == "0xd8da6bf26964af9d7eed9e03e53415d37aa96045"
