import sqlite3
from pathlib import Path
from typing import List, Optional
from erc20_scanner.models import LogEntry


SCHEMA = """
CREATE TABLE IF NOT EXISTS transfers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    token_address TEXT NOT NULL,
    from_address TEXT NOT NULL,
    to_address TEXT NOT NULL,
    amount TEXT NOT NULL,
    block_number INTEGER NOT NULL,
    tx_hash TEXT NOT NULL,
    log_index INTEGER NOT NULL,
    UNIQUE(tx_hash, log_index)
);

CREATE TABLE IF NOT EXISTS approvals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    token_address TEXT NOT NULL,
    owner TEXT NOT NULL,
    spender TEXT NOT NULL,
    amount TEXT NOT NULL,
    block_number INTEGER NOT NULL,
    tx_hash TEXT NOT NULL,
    log_index INTEGER NOT NULL,
    UNIQUE(tx_hash, log_index)
);

CREATE TABLE IF NOT EXISTS sync_state (
    key TEXT PRIMARY KEY,
    last_block INTEGER NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


class Database:
    def __init__(self, path: Union[str, Path] = "scanner.db"):
        self.path = str(path)
        self.conn = sqlite3.connect(self.path)
        self.conn.execute("PRAGMA journal_mode=WAL;")
        self.conn.execute("PRAGMA synchronous=NORMAL;")
        self._init_db()

    def _init_db(self):
        with self.conn:
            self.conn.executescript(SCHEMA)

    def close(self):
        self.conn.close()

    def get_last_synced_block(self, key: str = "default") -> Optional[int]:
        cur = self.conn.cursor()
        cur.execute("SELECT last_block FROM sync_state WHERE key = ?", (key,))
        row = cur.fetchone()
        return row[0] if row else None

    def save_checkpoint(self, last_block: int, key: str = "default"):
        with self.conn:
            self.conn.execute(
                "INSERT INTO sync_state(key, last_block, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP) "
                "ON CONFLICT(key) DO UPDATE SET last_block = excluded.last_block, updated_at = CURRENT_TIMESTAMP",
                (key, last_block)
            )

    def insert_transfers(self, transfers: List[LogEntry]):
        if not transfers:
            return
        rows = [
            (t.contract_address, t.args["from"], t.args["to"], str(t.args["value"]), t.block_number, t.tx_hash, t.log_index)
            for t in transfers
        ]
        with self.conn:
            self.conn.executemany(
                "INSERT OR IGNORE INTO transfers (token_address, from_address, to_address, amount, block_number, tx_hash, log_index) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                rows
            )
