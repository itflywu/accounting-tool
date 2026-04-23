import sqlite3
from datetime import date, datetime
from typing import Dict, List, Tuple

import pandas as pd
import requests
import streamlit as st


DB_PATH = "expenses.db"
CATEGORIES = ["食", "行", "住", "衣", "其他"]


def init_sqlite_db() -> None:
    conn = sqlite3.connect(DB_PATH)
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
    conn.close()


def get_sqlite_conn() -> sqlite3.Connection:
    return sqlite3.connect(DB_PATH)


def has_supabase_config() -> bool:
    return "SUPABASE_URL" in st.secrets and "SUPABASE_KEY" in st.secrets


def get_supabase_config() -> Tuple[str, str] | None:
    if not has_supabase_config():
        return None
    return st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"]


def using_supabase() -> bool:
    return get_supabase_config() is not None


def sqlite_insert_record(record: Dict[str, object]) -> None:
    conn = get_sqlite_conn()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO records (date, category, description, amount) VALUES (?, ?, ?, ?)",
        (
            record["date"],
            record["category"],
            record["description"],
            record["amount"],
        ),
    )
    conn.commit()
    conn.close()


def supabase_request(method: str, params: object = None, payload: object = None) -> requests.Response:
    config = get_supabase_config()
    if config is None:
        raise RuntimeError("Supabase 配置缺失")
    supabase_url, supabase_key = config
    url = f"{supabase_url.rstrip('/')}/rest/v1/records"
    headers = {
        "apikey": supabase_key,
        "Authorization": f"Bearer {supabase_key}",
        "Content-Type": "application/json",
    }
    response = requests.request(method=method, url=url, headers=headers, params=params, json=payload, timeout=20)
    response.raise_for_status()
    return response


def supabase_insert_record(record: Dict[str, object]) -> None:
    supabase_request("POST", payload=record)


def sqlite_load_data(month_prefix: str) -> Tuple[pd.DataFrame, pd.DataFrame]:
    conn = get_sqlite_conn()
    df_month = pd.read_sql_query(
        "SELECT category, amount FROM records WHERE date LIKE ?",
        conn,
        params=(f"{month_prefix}%",),
    )
    df_recent = pd.read_sql_query(
        """
        SELECT
            date AS 日期,
            category AS 分类,
            description AS 明细,
            amount AS 金额
        FROM records
        ORDER BY date DESC, id DESC
        LIMIT 10
        """,
        conn,
    )
    conn.close()
    return df_month, df_recent


def current_month_range() -> Tuple[str, str]:
    today = date.today()
    first_day = today.replace(day=1)
    if first_day.month == 12:
        next_month = first_day.replace(year=first_day.year + 1, month=1)
    else:
        next_month = first_day.replace(month=first_day.month + 1)
    return first_day.strftime("%Y-%m-%d"), next_month.strftime("%Y-%m-%d")


def supabase_load_data() -> Tuple[pd.DataFrame, pd.DataFrame]:
    if not using_supabase():
        return pd.DataFrame(), pd.DataFrame(columns=["日期", "分类", "明细", "金额"])

    start_date, end_date = current_month_range()
    month_resp = supabase_request(
        "GET",
        params=[
            ("select", "category,amount"),
            ("date", f"gte.{start_date}"),
            ("date", f"lt.{end_date}"),
        ],
    )
    month_data: List[Dict[str, object]] = month_resp.json() or []
    df_month = pd.DataFrame(month_data)

    recent_resp = supabase_request(
        "GET",
        params={
            "select": "date,category,description,amount,id",
            "order": "date.desc,id.desc",
            "limit": "10",
        },
    )
    recent_data: List[Dict[str, object]] = recent_resp.json() or []
    df_recent = pd.DataFrame(recent_data)
    if df_recent.empty:
        df_recent = pd.DataFrame(columns=["日期", "分类", "明细", "金额"])
    else:
        df_recent = df_recent.rename(
            columns={
                "date": "日期",
                "category": "分类",
                "description": "明细",
                "amount": "金额",
            }
        )[["日期", "分类", "明细", "金额"]]

    return df_month, df_recent


def save_record(record: Dict[str, object]) -> None:
    if using_supabase():
        supabase_insert_record(record)
    else:
        sqlite_insert_record(record)


def load_dashboard_data() -> Tuple[pd.DataFrame, pd.DataFrame]:
    if using_supabase():
        return supabase_load_data()
    month_prefix = datetime.today().strftime("%Y-%m")
    return sqlite_load_data(month_prefix)


init_sqlite_db()
st.set_page_config(page_title="极简记账", page_icon="📓", layout="centered")
st.title("📓 日常开支")
st.caption("数据源：" + ("Supabase 云端数据库" if using_supabase() else "本地 SQLite"))

with st.container():
    st.subheader("一笔新开支")
    with st.form("add_record_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            date_input = st.date_input("日期", datetime.today())
            category_input = st.selectbox("分类", CATEGORIES)
        with col2:
            amount_input = st.number_input("金额 (元)", min_value=0.01, format="%.2f")
            desc_input = st.text_input("明细 (如：午饭、打车)")

        submitted = st.form_submit_button("保存记录", use_container_width=True)
        if submitted:
            try:
                save_record(
                    {
                        "date": date_input.strftime("%Y-%m-%d"),
                        "category": category_input,
                        "description": (desc_input or "").strip(),
                        "amount": float(amount_input),
                    }
                )
                st.success("记录成功！")
            except Exception as exc:
                st.error(f"保存失败：{exc}")

st.divider()
st.subheader("近期记录与统计")

df_month, df_recent = load_dashboard_data()
current_month = datetime.today().strftime("%Y-%m")

if not df_month.empty and "amount" in df_month:
    total_expense = float(df_month["amount"].sum())
    st.metric(label=f"{current_month} 总支出", value=f"¥ {total_expense:.2f}")
    category_sum = df_month.groupby("category", as_index=False)["amount"].sum()
    st.bar_chart(category_sum, x="category", y="amount")
else:
    st.info("本月暂未记录开支。")

st.dataframe(df_recent, width="stretch", hide_index=True)
