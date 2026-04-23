import sqlite3
from datetime import datetime

import pandas as pd
import streamlit as st


DB_PATH = "expenses.db"
CATEGORIES = ["食", "行", "住", "衣", "其他"]


def init_db() -> None:
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


def get_conn() -> sqlite3.Connection:
    return sqlite3.connect(DB_PATH)


init_db()
st.set_page_config(page_title="极简记账", page_icon="📓", layout="centered")
st.title("📓 日常开支")

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
            conn = get_conn()
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO records (date, category, description, amount) VALUES (?, ?, ?, ?)",
                (
                    date_input.strftime("%Y-%m-%d"),
                    category_input,
                    (desc_input or "").strip(),
                    float(amount_input),
                ),
            )
            conn.commit()
            conn.close()
            st.success("记录成功！")

st.divider()
st.subheader("近期记录与统计")

conn = get_conn()
current_month = datetime.today().strftime("%Y-%m")
df_month = pd.read_sql_query(
    "SELECT category, amount FROM records WHERE date LIKE ?",
    conn,
    params=(f"{current_month}%",),
)

if not df_month.empty:
    total_expense = float(df_month["amount"].sum())
    st.metric(label=f"{current_month} 总支出", value=f"¥ {total_expense:.2f}")
    category_sum = df_month.groupby("category", as_index=False)["amount"].sum()
    st.bar_chart(category_sum, x="category", y="amount")
else:
    st.info("本月暂未记录开支。")

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
st.dataframe(df_recent, use_container_width=True, hide_index=True)
conn.close()
