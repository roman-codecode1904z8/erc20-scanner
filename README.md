# erc20-scanner

Simple CLI tool to scrape ERC-20 `Transfer` and `Approval` event logs directly from an EVM node via raw `eth_getLogs`.

I got tired of spinning up local Graph nodes or indexers just to audit token balances and transfer histories. This dumps decoded logs straight into SQLite or JSONL.

## Install

```bash
pip install .
```

Or editable for development:

```bash
pip install -e ".[dev]"
```

## Usage

Scan USDT transfers to SQLite:

```bash
erc20-scan \
  --rpc https://eth.llamarpc.com \
  --token 0xdAC17F958D2ee523a2206206994597C13D831ec7 \
  --from-block 18000000 \
  --to-block 18010000 \
  --db usdt.db
```

Stream all events into JSONL with custom batch size:

```bash
erc20-scan \
  --rpc http://localhost:8545 \
  --token 0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48 \
  --from-block 19000000 \
  --to-block latest \
  --events transfer approval \
  --chunk-size 2000 \
  --format jsonl \
  --out usdc_events.jsonl
```

Public RPCs (Infura, Alchemy, public endpoints) usually limit `eth_getLogs` block range to 2,000 or 10,000 blocks per request. The scanner automatically halves chunk size if the node returns response-size or query-range errors.

<!-- refreshed: 2026-09-12 -->
