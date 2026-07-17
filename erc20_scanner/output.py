import sys
import csv
import json
from typing import Iterable, TextIO

from erc20_scanner.models import DecodedEvent, TransferEvent, ApprovalEvent


def write_jsonl(events: Iterable[DecodedEvent], stream: TextIO = sys.stdout) -> int:
    count = 0
    for ev in events:
        stream.write(json.dumps(ev.to_dict()) + "\n")
        count += 1
    stream.flush()
    return count


def write_csv(events: Iterable[DecodedEvent], stream: TextIO = sys.stdout) -> int:
    # field list is fixed so header is written even when iterator is empty
    fieldnames = ["event_type", "token_address", "block_number", "tx_hash", "log_index", "from_owner", "to_spender", "value", "timestamp"]
    writer = csv.DictWriter(stream, fieldnames=fieldnames)
    writer.writeheader()

    count = 0
    for ev in events:
        row = ev.to_dict()
        # normalize keys across transfer and approval for uniform csv export
        flat = {
            "event_type": row.get("event_type"),
            "token_address": row.get("token_address"),
            "block_number": row.get("block_number"),
            "tx_hash": row.get("tx_hash"),
            "log_index": row.get("log_index"),
            "from_owner": row.get("from_address") or row.get("owner", ""),
            "to_spender": row.get("to_address") or row.get("spender", ""),
            "value": row.get("value"),
            "timestamp": row.get("timestamp", ""),
        }
        writer.writerow(flat)
        count += 1
    stream.flush()
    return count


def format_table(events: list[DecodedEvent], max_rows: int = 50) -> str:
    """Format a list of decoded events into an aligned terminal string."""
    if not events:
        return "No events found."

    lines = []
    header = f"{'Block':<9} {'Type':<9} {'Token':<12} {'From/Owner':<12} {'To/Spender':<12} {'Value (raw)':<20} {'Tx Hash':<12}"
    lines.append(header)
    lines.append("-" * len(header))

    def _short(addr: str) -> str:
        if not addr or len(addr) <= 10:
            return addr or "-"
        return addr[:5] + ".." + addr[-4:]

    for ev in events[:max_rows]:
        if isinstance(ev, TransferEvent):
            kind = "Transfer"
            src = _short(ev.from_address)
            dst = _short(ev.to_address)
        elif isinstance(ev, ApprovalEvent):
            kind = "Approval"
            src = _short(ev.owner)
            dst = _short(ev.spender)
        else:
            kind = "Other"
            src = "-"
            dst = "-"

        token = _short(ev.token_address)
        tx = _short(ev.tx_hash)
        val_str = str(ev.value)
        if len(val_str) > 18:
            val_str = val_str[:15] + "..."

        lines.append(f"{ev.block_number:<9} {kind:<9} {token:<12} {src:<12} {dst:<12} {val_str:<20} {tx:<12}")

    if len(events) > max_rows:
        lines.append(f"... ({len(events) - max_rows} more rows hidden, use --limit or export to file)")

    return "\n".join(lines)
