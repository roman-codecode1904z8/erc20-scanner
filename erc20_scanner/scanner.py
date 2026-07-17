import time
from typing import Callable, Generator, Optional

from erc20_scanner.abi import decode_log, TRANSFER_TOPIC, APPROVAL_TOPIC
from erc20_scanner.models import DecodedEvent, ScanConfig
from erc20_scanner.rpc import RpcClient, EthRpcError
from erc20_scanner.storage import BaseStorage


class Scanner:
    """Orchestrates log fetching, dynamic chunk sizing, and decoding."""

    def __init__(self, rpc: RpcClient, storage: Optional[BaseStorage] = None):
        self.rpc = rpc
        self.storage = storage
        self._ts_cache: dict[int, int] = {}  # block_num -> unix timestamp

    def _get_timestamp(self, block_num: int) -> Optional[int]:
        if block_num in self._ts_cache:
            return self._ts_cache[block_num]
        try:
            ts = self.rpc.get_block_timestamp(block_num)
            if len(self._ts_cache) > 5000:
                # naive eviction so we don't blow memory on giant scans
                self._ts_cache.clear()
            self._ts_cache[block_num] = ts
            return ts
        except Exception:
            return None

    def scan_range(
        self,
        config: ScanConfig,
        progress_cb: Optional[Callable[[int, int, int], None]] = None,
    ) -> Generator[DecodedEvent, None, None]:
        start = config.from_block
        end = config.to_block if config.to_block is not None else self.rpc.get_block_number()
        chunk_size = config.chunk_size
        min_chunk = 5

        topics = []
        if config.events == "all":
            topics = [[TRANSFER_TOPIC, APPROVAL_TOPIC]]
        elif config.events == "transfers":
            topics = [[TRANSFER_TOPIC]]
        elif config.events == "approvals":
            topics = [[APPROVAL_TOPIC]]

        current = start
        total_found = 0
        batch_buffer = []
        batch_size = 200

        while current <= end:
            chunk_end = min(current + chunk_size - 1, end)

            try:
                logs = self.rpc.get_logs(
                    from_block=current,
                    to_block=chunk_end,
                    address=config.contract_address,
                    topics=topics if topics else None,
                )
            except EthRpcError as err:
                # Alchemy/Infura error on >10k results or timeout: split chunk and try smaller
                err_msg = str(err).lower()
                if "query returned more than" in err_msg or "response size exceeded" in err_msg or "timeout" in err_msg or "limit exceeded" in err_msg:
                    if chunk_size > min_chunk:
                        chunk_size = max(min_chunk, chunk_size // 2)
                        continue
                raise

            # print(f"DEBUG: chunk {current}-{chunk_end} returned {len(logs)} logs")

            for raw in logs:
                ev = decode_log(raw)
                if ev is None:
                    continue

                if config.account_filter:
                    acc = config.account_filter.lower()
                    if hasattr(ev, "from_address") and ev.from_address.lower() != acc and ev.to_address.lower() != acc:
                        continue
                    if hasattr(ev, "owner") and ev.owner.lower() != acc and ev.spender.lower() != acc:
                        continue

                if config.include_timestamps and ev.timestamp is None:
                    ev.timestamp = self._get_timestamp(ev.block_number)

                total_found += 1
                if self.storage:
                    batch_buffer.append(ev)
                    if len(batch_buffer) >= batch_size:
                        self.storage.save_batch(batch_buffer)
                        batch_buffer = []
                yield ev

            if progress_cb:
                progress_cb(chunk_end, end, total_found)

            # adaptive recovery: grow chunk size if we are below limit
            if chunk_size < config.chunk_size and len(logs) < 100:
                chunk_size = min(config.chunk_size, chunk_size * 2)

            current = chunk_end + 1

        # flush remaining unwritten events
        if self.storage and batch_buffer:
            self.storage.save_batch(batch_buffer)
