import argparse
import sqlite3
from typing import Dict, List

import requests


def read_sqlite_records(db_path: str) -> List[Dict[str, object]]:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    rows = cursor.execute(
        """
        SELECT date, category, description, amount
        FROM records
        ORDER BY id ASC
        """
    ).fetchall()
    conn.close()

    return [
        {
            "date": row[0],
            "category": row[1],
            "description": row[2] or "",
            "amount": float(row[3]),
        }
        for row in rows
    ]


def chunked(data: List[Dict[str, object]], size: int) -> List[List[Dict[str, object]]]:
    return [data[i : i + size] for i in range(0, len(data), size)]


def main() -> None:
    parser = argparse.ArgumentParser(description="将本地 SQLite 记录迁移到 Supabase")
    parser.add_argument("--db-path", default="expenses.db", help="本地 SQLite 数据库路径")
    parser.add_argument("--supabase-url", required=True, help="Supabase project URL")
    parser.add_argument(
        "--supabase-key",
        required=True,
        help="Supabase key（建议使用 service role key，仅本地脚本使用，勿提交到仓库）",
    )
    parser.add_argument("--batch-size", type=int, default=500, help="批量写入条数")
    args = parser.parse_args()

    records = read_sqlite_records(args.db_path)
    if not records:
        print("本地数据库没有可迁移记录。")
        return

    endpoint = f"{args.supabase_url.rstrip('/')}/rest/v1/records"
    headers = {
        "apikey": args.supabase_key,
        "Authorization": f"Bearer {args.supabase_key}",
        "Content-Type": "application/json",
    }

    total = 0
    for batch in chunked(records, args.batch_size):
        response = requests.post(endpoint, headers=headers, json=batch, timeout=30)
        response.raise_for_status()
        total += len(batch)
        print(f"已迁移 {total}/{len(records)} 条")

    print(f"迁移完成，共 {len(records)} 条。")


if __name__ == "__main__":
    main()
