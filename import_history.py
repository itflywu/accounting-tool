import argparse
import os
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Tuple

import pandas as pd


DB_PATH = "expenses.db"
CATEGORIES = ["衣", "食", "住", "行", "其他"]


def init_db(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            category TEXT NOT NULL,
            description TEXT DEFAULT '',
            amount REAL NOT NULL
        )
        """
    )
    conn.commit()
    return conn


def parse_date(value: object) -> str:
    if pd.isna(value):
        return ""
    text = str(value).strip()
    if not text:
        return ""

    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(text, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue

    try:
        dt = pd.to_datetime(text, errors="raise")
        return dt.strftime("%Y-%m-%d")
    except Exception:
        return ""


def parse_amount(value: object) -> float | None:
    if pd.isna(value):
        return None
    text = str(value).strip().replace(",", "")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def extract_records_from_dataframe(df: pd.DataFrame) -> List[Tuple[str, str, str, float]]:
    records: List[Tuple[str, str, str, float]] = []
    if df.empty:
        return records

    for _, row in df.iterrows():
        date = parse_date(row.iloc[0] if len(row) > 0 else "")
        if not date:
            continue

        for i, category in enumerate(CATEGORIES):
            item_col = 1 + i * 2
            amount_col = 2 + i * 2
            if amount_col >= len(row):
                continue

            desc_raw = row.iloc[item_col] if item_col < len(row) else ""
            amount = parse_amount(row.iloc[amount_col])
            if amount is None:
                continue

            desc = str(desc_raw).strip() if pd.notna(desc_raw) else ""
            if not desc:
                desc = "无"

            records.append((date, category, desc, amount))

    return records


def extract_records_from_file(file_path: Path) -> List[Tuple[str, str, str, float]]:
    suffix = file_path.suffix.lower()
    all_records: List[Tuple[str, str, str, float]] = []

    if suffix == ".csv":
        df = pd.read_csv(file_path)
        return extract_records_from_dataframe(df)

    if suffix in {".xlsx", ".xls"}:
        workbook = pd.read_excel(file_path, sheet_name=None)
        for _, df in workbook.items():
            all_records.extend(extract_records_from_dataframe(df))
        return all_records

    return all_records


def process_and_import_data(folder_path: str, conn: sqlite3.Connection) -> int:
    folder = Path(folder_path)
    source_files = sorted(
        [
            p
            for p in folder.iterdir()
            if p.is_file() and p.suffix.lower() in {".csv", ".xlsx", ".xls"}
        ]
    )
    all_records: List[Tuple[str, str, str, float]] = []

    for source_file in source_files:
        try:
            all_records.extend(extract_records_from_file(source_file))
        except Exception as exc:
            print(f"[WARN] 处理文件失败: {source_file} -> {exc}")

    if not all_records:
        return 0

    cursor = conn.cursor()
    cursor.executemany(
        "INSERT INTO records (date, category, description, amount) VALUES (?, ?, ?, ?)",
        all_records,
    )
    conn.commit()
    return len(all_records)


def main() -> None:
    parser = argparse.ArgumentParser(description="将宽表历史账单（CSV/Excel）导入 SQLite 数据库")
    parser.add_argument(
        "--data-dir",
        "--csv-dir",
        dest="data_dir",
        default="./csv_data",
        help="数据目录（支持 csv/xlsx/xls），默认 ./csv_data",
    )
    parser.add_argument(
        "--db-path",
        default=DB_PATH,
        help="SQLite 数据库文件路径，默认 expenses.db",
    )
    args = parser.parse_args()

    if not os.path.isdir(args.data_dir):
        raise FileNotFoundError(f"数据目录不存在: {args.data_dir}")

    conn = init_db(args.db_path)
    imported_count = process_and_import_data(args.data_dir, conn)
    conn.close()
    print(f"导入完成，共写入 {imported_count} 条记录。")


if __name__ == "__main__":
    main()
