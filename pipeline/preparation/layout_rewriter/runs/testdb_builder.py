#!/usr/bin/env python3
"""Build a larger SQLite database for cold-start benchmarking.

Defaults reproduce the 600k-row / ~102 MiB reference DB. Use --rows / --out to
build other sizes (≈180 bytes/row incl. the two indexes, so 6,000,000 rows ≈ 1 GiB).
"""

import argparse
import os
import sqlite3

DEFAULT_ROWS = 600000
DEFAULT_OUT = "test.db"


def build(out: str, rows: int) -> None:
    if os.path.exists(out):
        os.remove(out)

    conn = sqlite3.connect(out)
    cur = conn.cursor()
    cur.executescript(
        f"""
        PRAGMA journal_mode=OFF;
        PRAGMA synchronous=OFF;
        PRAGMA temp_store=MEMORY;

        CREATE TABLE items (
          id INTEGER PRIMARY KEY,
          k1 TEXT NOT NULL,
          k2 TEXT NOT NULL,
          payload BLOB NOT NULL
        );

        CREATE INDEX idx_items_k1 ON items(k1);
        CREATE INDEX idx_items_k2 ON items(k2);

        WITH RECURSIVE cnt(x) AS (
          SELECT 1
          UNION ALL
          SELECT x + 1 FROM cnt WHERE x < {int(rows)}
        )
        INSERT INTO items(k1, k2, payload)
        SELECT
          printf('group_%04d', x % 1000),
          printf('tag_%06d', x),
          randomblob(100)
        FROM cnt;
        """
    )
    conn.commit()
    conn.close()

    size = os.path.getsize(out)
    print(f"built {out}: {size} bytes ({size / 1024 / 1024:.2f} MiB, "
          f"{size / 1024**3:.3f} GiB) from {rows:,} rows")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--rows", type=int, default=DEFAULT_ROWS,
                    help=f"number of rows (default {DEFAULT_ROWS}; 6,000,000 ≈ 1 GiB)")
    ap.add_argument("--out", default=DEFAULT_OUT,
                    help=f"output DB path (default {DEFAULT_OUT})")
    args = ap.parse_args()
    build(args.out, args.rows)


if __name__ == "__main__":
    main()
