from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass(frozen=True, slots=True)
class BlockRange:
    start: int
    end: int

    def __post_init__(self):
        if self.start > self.end:
            raise ValueError(f"start block ({self.start}) cannot exceed end block ({self.end})")

    @property
    def count(self) -> int:
        return self.end - self.start + 1


@dataclass(frozen=True, slots=True)
class TokenMeta:
    address: str
    symbol: str = "???"
    name: str = "Unknown Token"
    decimals: int = 18


@dataclass(slots=True)
class TransferEvent:
    """Decoded ERC-20 Transfer log."""
    contract: str
    from_address: str
    to_address: str
    value: int
    block_number: int
    tx_hash: str
    log_index: int
    timestamp: Optional[int] = None


@dataclass(slots=True)
class ApprovalEvent:
    contract: str
    owner: str
    spender: str
    value: int
    block_number: int
    tx_hash: str
    log_index: int
    timestamp: Optional[int] = None


@dataclass(slots=True)
class RawLog:
    address: str
    topics: list[str]
    data: str
    block_number: int
    tx_hash: str
    log_index: int
    removed: bool = False

    @classmethod
    def from_rpc(cls, item: Dict[str, Any]) -> "RawLog":
        # Some nodes return blockNumber as hex, others as decimal ints depending on proxy
        bn = item["blockNumber"]
        block_num = int(bn, 16) if isinstance(bn, str) and bn.startswith("0x") else int(bn)

        li = item.get("logIndex", "0x0")
        log_idx = int(li, 16) if isinstance(li, str) and li.startswith("0x") else int(li)

        return cls(
            address=item["address"].lower(),
            topics=item.get("topics", []),
            data=item.get("data", "0x"),
            block_number=block_num,
            tx_hash=item.get("transactionHash", ""),
            log_index=log_idx,
            removed=bool(item.get("removed", False)),
        )
