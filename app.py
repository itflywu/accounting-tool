import sqlite3
from datetime import date, datetime, timedelta
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


def sqlite_load_all_records() -> pd.DataFrame:
    conn = get_sqlite_conn()
    df_records = pd.read_sql_query(
        """
        SELECT
            date,
            category,
            description,
            amount,
            id
        FROM records
        ORDER BY date DESC, id DESC
        """,
        conn,
    )
    conn.close()
    return df_records


def supabase_load_all_records(page_size: int = 1000) -> pd.DataFrame:
    if not using_supabase():
        return pd.DataFrame(columns=["date", "category", "description", "amount", "id"])

    offset = 0
    all_rows: List[Dict[str, object]] = []
    while True:
        resp = supabase_request(
            "GET",
            params={
                "select": "date,category,description,amount,id",
                "order": "date.desc,id.desc",
                "limit": str(page_size),
                "offset": str(offset),
            },
        )
        rows: List[Dict[str, object]] = resp.json() or []
        all_rows.extend(rows)
        if len(rows) < page_size:
            break
        offset += page_size

    return pd.DataFrame(all_rows)


def save_record(record: Dict[str, object]) -> None:
    if using_supabase():
        supabase_insert_record(record)
    else:
        sqlite_insert_record(record)


def load_all_records() -> pd.DataFrame:
    if using_supabase():
        return supabase_load_all_records()
    return sqlite_load_all_records()


def normalize_records_df(df_raw: pd.DataFrame) -> pd.DataFrame:
    if df_raw.empty:
        return pd.DataFrame(columns=["日期", "分类", "明细", "金额"])

    df = df_raw.copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"])
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
    df = df.dropna(subset=["amount"])
    df = df.rename(
        columns={
            "date": "日期",
            "category": "分类",
            "description": "明细",
            "amount": "金额",
        }
    )
    df["日期"] = df["日期"].dt.strftime("%Y-%m-%d")
    return df[["日期", "分类", "明细", "金额"]]


def filter_date_range(df: pd.DataFrame, start_date: date, end_date: date) -> pd.DataFrame:
    if df.empty:
        return df
    d = pd.to_datetime(df["日期"], errors="coerce")
    mask = (d.dt.date >= start_date) & (d.dt.date <= end_date)
    return df.loc[mask].copy()


def style_amount(val: object) -> str:
    try:
        amount = float(val)
    except Exception:
        return ""
    if amount >= 300:
        return "background-color: #ffe4e6; color: #9f1239; font-weight: 600;"
    if amount >= 100:
        return "background-color: #fff7ed; color: #9a3412; font-weight: 600;"
    return "background-color: #ecfdf5; color: #166534;"


def summarize_totals(df: pd.DataFrame) -> Tuple[float, float, float]:
    today = date.today()
    week_start = today - timedelta(days=today.weekday())
    month_start = today.replace(day=1)
    year_start = today.replace(month=1, day=1)

    df_week = filter_date_range(df, week_start, today)
    df_month = filter_date_range(df, month_start, today)
    df_year = filter_date_range(df, year_start, today)
    return (
        float(df_week["金额"].sum()) if not df_week.empty else 0.0,
        float(df_month["金额"].sum()) if not df_month.empty else 0.0,
        float(df_year["金额"].sum()) if not df_year.empty else 0.0,
    )


def aggregate_by_period(df: pd.DataFrame, period_mode: str) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["周期", "总金额"])
    d = pd.to_datetime(df["日期"], errors="coerce")
    if period_mode == "按周":
        key = d.dt.strftime("%G-W%V")
    elif period_mode == "按月":
        key = d.dt.strftime("%Y-%m")
    else:
        key = d.dt.strftime("%Y")
    out = (
        pd.DataFrame({"周期": key, "金额": df["金额"]})
        .groupby("周期", as_index=False)["金额"]
        .sum()
        .rename(columns={"金额": "总金额"})
        .sort_values("周期", ascending=False)
    )
    return out


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

        submitted = st.form_submit_button("保存记录", width="stretch")
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
st.subheader("统计与明细")

df_all = normalize_records_df(load_all_records())
if df_all.empty:
    st.info("暂无记录。你可以先新增一笔开支。")
else:
    week_total, month_total, year_total = summarize_totals(df_all)
    c1, c2, c3 = st.columns(3)
    c1.metric("本周总支出", f"¥ {week_total:.2f}")
    c2.metric("本月总支出", f"¥ {month_total:.2f}")
    c3.metric("本年总支出", f"¥ {year_total:.2f}")

    st.markdown("### 按周 / 月 / 年汇总")
    period_mode = st.selectbox("汇总维度", ["按周", "按月", "按年"], index=1)
    df_period = aggregate_by_period(df_all, period_mode)
    st.bar_chart(df_period.head(24), x="周期", y="总金额")
    st.dataframe(df_period, width="stretch", hide_index=True)

    st.markdown("### 全部记录（可筛选）")
    min_day = pd.to_datetime(df_all["日期"]).min().date()
    max_day = pd.to_datetime(df_all["日期"]).max().date()
    fc1, fc2, fc3 = st.columns([1.3, 1, 1])
    with fc1:
        date_range = st.date_input("日期范围", value=(min_day, max_day), min_value=min_day, max_value=max_day)
    with fc2:
        category_options = ["全部"] + CATEGORIES
        category_filter = st.selectbox("分类筛选", category_options)
    with fc3:
        search_text = st.text_input("明细关键词", "")

    if isinstance(date_range, tuple) and len(date_range) == 2:
        start_date, end_date = date_range
    else:
        start_date = end_date = min_day

    df_display = filter_date_range(df_all, start_date, end_date)
    if category_filter != "全部":
        df_display = df_display[df_display["分类"] == category_filter]
    if search_text.strip():
        df_display = df_display[df_display["明细"].astype(str).str.contains(search_text.strip(), case=False, na=False)]

    df_display = df_display.sort_values("日期", ascending=False)
    styled = df_display.style.format({"金额": "¥ {:.2f}"}).applymap(style_amount, subset=["金额"])
    st.caption(f"共 {len(df_display)} 条记录")
    st.dataframe(styled, width="stretch", hide_index=True)
