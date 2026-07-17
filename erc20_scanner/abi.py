from typing import Optional, Union
from erc20_scanner.models import ApprovalEvent, RawLog, TransferEvent

# keccak256('Transfer(address,address,uint256)')
TRANSFER_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
# keccak256('Approval(address,address,uint256)')
APPROVAL_TOPIC = "0x8c5be1e5eb7849e29572304149266f6b102764b3f279377f699992de02e0ce6e"


def decode_address(topic_or_hex: str) -> str:
    raw = topic_or_hex.lower()
    if raw.startswith("0x"):
        raw = raw[2:]
    # topics are 32 bytes padded left with zeros; address is the last 20 bytes (40 hex chars)
    if len(raw) > 40:
        raw = raw[-40:]
    return f"0x{raw.zfill(40)}"


def decode_uint256(data_hex: str) -> int:
    if not data_hex or data_hex == "0x":
        return 0
    raw = data_hex[2:] if data_hex.startswith("0x") else data_hex
    # FIXME: rare garbage data from buggy contracts that emit >32 bytes in data payload
    if len(raw) > 64:
        raw = raw[:64]
    return int(raw, 16)


def parse_raw_log(log: RawLog) -> Optional[Union[TransferEvent, ApprovalEvent]]:
    if log.removed or not log.topics:
        return None

    topic0 = log.topics[0].lower()
    # print(f"DEBUG: log {log.tx_hash} topic0={topic0}")

    if topic0 == TRANSFER_TOPIC:
        # standard transfer: topics=[sig, from, to], data=value
        if len(log.topics) == 3:
            return TransferEvent(
                contract=log.address,
                from_address=decode_address(log.topics[1]),
                to_address=decode_address(log.topics[2]),
                value=decode_uint256(log.data),
                block_number=log.block_number,
                tx_hash=log.tx_hash,
                log_index=log.log_index,
            )
        # non-standard: unindexed params packed inside data (some pre-ERC20 or broken tokens)
        elif len(log.topics) == 1 and len(log.data) >= 130:  # 0x + 3 * 64 chars
            d = log.data[2:]
            from_addr = f"0x{d[24:64].lower()}"
            to_addr = f"0x{d[88:128].lower()}"
            val = int(d[128:192], 16) if len(d) >= 192 else int(d[128:], 16)
            return TransferEvent(
                contract=log.address,
                from_address=from_addr,
                to_address=to_addr,
                value=val,
                block_number=log.block_number,
                tx_hash=log.tx_hash,
                log_index=log.log_index,
            )
        return None

    if topic0 == APPROVAL_TOPIC:
        if len(log.topics) == 3:
            return ApprovalEvent(
                contract=log.address,
                owner=decode_address(log.topics[1]),
                spender=decode_address(log.topics[2]),
                value=decode_uint256(log.data),
                block_number=log.block_number,
                tx_hash=log.tx_hash,
                log_index=log.log_index,
            )
        return None

    return None
