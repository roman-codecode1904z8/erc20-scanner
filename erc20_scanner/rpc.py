import time
import httpx
from typing import Any, Dict, List, Optional, Tuple
from erc20_scanner.models import LogEntry


class RPCError(Exception):
    def __init__(self, code: int, message: str, data: Any = None):
        self.code = code
        self.message = message
        self.data = data
        super().__init__(f"RPC Error {code}: {message}")


class RangeLimitExceeded(Exception):
    """Raised when the node complains about too many blocks or results."""
    pass


class NodeClient:
    """Barebones JSON-RPC client tuned for log queries and batching."""

    def __init__(self, endpoint: str, timeout: float = 30.0, max_retries: int = 6):
        self.endpoint = endpoint
        self.timeout = timeout
        self.max_retries = max_retries
        self._client = httpx.Client(timeout=timeout)
        self._req_id = 0
        # tracks consecutive fast responses to slowly relax backoff
        self._success_streak = 0

    def close(self):
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def _next_id(self) -> int:
        self._req_id += 1
        return self._req_id

    def _check_range_error(self, msg: str):
        lower = msg.lower()
        # quicknode, alchemy, infura and geth all phrase this slightly differently
        if any(s in lower for s in ["query returned more than", "block range", "limit exceeded", "10000 results", "response size"]):
            raise RangeLimitExceeded(msg)

    def call(self, method: str, params: List[Any]) -> Any:
        payload = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": method,
            "params": params,
        }

        backoff = 0.5
        for attempt in range(self.max_retries):
            try:
                resp = self._client.post(self.endpoint, json=payload)
                # print(f"DEBUG: {resp.status_code} len={len(resp.content)}")

                if resp.status_code == 429:
                    retry_after = resp.headers.get("retry-after")
                    wait = float(retry_after) if retry_after else backoff
                    time.sleep(wait)
                    backoff = min(backoff * 2.0, 15.0)
                    continue

                resp.raise_for_status()
                data = resp.json()

                if "error" in data:
                    err = data["error"]
                    msg = err.get("message", "")
                    self._check_range_error(msg)
                    raise RPCError(err.get("code", -1), msg, err.get("data"))

                return data.get("result")
            except RangeLimitExceeded:
                raise
            except (httpx.TransportError, httpx.TimeoutException):
                if attempt == self.max_retries - 1:
                    raise
                time.sleep(backoff)
                backoff = min(backoff * 1.8, 12.0)

        raise RuntimeError(f"Failed after {self.max_retries} attempts: {method}")

    def batch_call(self, calls: List[Tuple[str, List[Any]]]) -> List[Any]:
        if not calls:
            return []

        payloads = []
        id_map = {}
        for method, params in calls:
            req_id = self._next_id()
            payloads.append({
                "jsonrpc": "2.0",
                "id": req_id,
                "method": method,
                "params": params,
            })
            id_map[req_id] = len(payloads) - 1

        backoff = 0.5
        for attempt in range(self.max_retries):
            try:
                resp = self._client.post(self.endpoint, json=payloads)
                if resp.status_code == 429:
                    time.sleep(backoff)
                    backoff = min(backoff * 2.0, 15.0)
                    continue

                resp.raise_for_status()
                data = resp.json()

                # response can arrive out of order from some providers (e.g. erigon)
                results = [None] * len(payloads)
                for item in data:
                    idx = id_map.get(item.get("id"))
                    if idx is not None:
                        if "error" in item:
                            err = item["error"]
                            results[idx] = RPCError(err.get("code", -1), err.get("message", ""))
                        else:
                            results[idx] = item.get("result")
                return results
            except (httpx.TransportError, httpx.TimeoutException):
                if attempt == self.max_retries - 1:
                    raise
                time.sleep(backoff)
                backoff = min(backoff * 1.8, 12.0)

        raise RuntimeError("Batch request failed")

    def get_block_number(self) -> int:
        res = self.call("eth_blockNumber", [])
        return int(res, 16)

    def get_logs(self, from_block: int, to_block: int, address: Optional[str] = None, topics: Optional[List[Optional[str]]] = None) -> List[Dict[str, Any]]:
        query: Dict[str, Any] = {
            "fromBlock": hex(from_block),
            "toBlock": hex(to_block),
        }
        if address:
            query["address"] = address.lower()
        if topics:
            query["topics"] = topics

        # FIXME: alchemy sometimes sends code -32000 with "exceeded maximum block range", need cleaner regex here
        res = self.call("eth_getLogs", [query])
        return res or []
