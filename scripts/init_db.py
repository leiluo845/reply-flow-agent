from __future__ import annotations

import argparse
from pathlib import Path

from replyflow.config import load_settings
from replyflow.db import connect_db, initialize_schema, seed_database


def main() -> int:
    parser = argparse.ArgumentParser(description="Initialize the local ReplyFlow SQLite database.")
    parser.add_argument("--db", type=Path, default=None, help="Optional database path override")
    args = parser.parse_args()

    settings = load_settings()
    db_path = args.db or settings.replyflow_db_path
    connection = connect_db(db_path)
    try:
        initialize_schema(connection)
        counts = seed_database(connection)
    finally:
        connection.close()

    print(f"ReplyFlow database initialized: {db_path}")
    print("Seeded: " + ", ".join(f"{key}={value}" for key, value in counts.items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
