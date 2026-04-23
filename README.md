# 极简记账（Streamlit + SQLite）

这是一个轻量记账工具，支持：

- 快速录入：`日期 / 分类 / 明细 / 金额`
- 当月统计：总支出 + 分类柱状图
- 历史导入：把你的 Excel/CSV 宽表账本转换为标准记录并入库
- 多设备访问：浏览器打开同一个网址即可

---

## 1. 本地运行

### 1) 安装依赖

```bash
pip install -r requirements.txt
```

### 2) 导入历史数据

把历史文件（支持 `csv/xlsx/xls`）放到一个目录，例如：

- `C:\Users\你的用户名\Desktop\日常开支`

运行导入：

```bash
python import_history.py --data-dir "C:\Users\你的用户名\Desktop\日常开支"
```

如需指定数据库路径：

```bash
python import_history.py --data-dir "./csv_data" --db-path "./expenses.db"
```

### 3) 启动应用

```bash
streamlit run app.py
```

打开浏览器访问终端中显示的地址（通常是 `http://localhost:8501`）。

---

## 2. 部署到 Streamlit Community Cloud（免费）

> 适合快速上线、随时可访问。

### 1) 准备仓库

把以下文件推送到 GitHub 仓库根目录：

- `app.py`
- `import_history.py`
- `requirements.txt`
- `README.md`

### 2) 创建应用

1. 打开 [Streamlit Community Cloud](https://share.streamlit.io/)
2. 使用 GitHub 账号登录
3. 选择你的仓库和分支
4. Main file path 填 `app.py`
5. 点击 **Deploy**

部署成功后会得到一个公网地址，例如：

- `https://your-expense-app.streamlit.app`

---

## 3. 关于数据持久化（很重要）

当前项目使用本地 SQLite 文件 `expenses.db`。

- 在本地运行时：数据稳定保存在你本机
- 在云端运行时：平台重启后，容器本地文件可能被重置

如果你希望“长期稳定保存云端数据”，建议下一步把数据库切换到托管数据库（如 Supabase Postgres / Turso）。

---

## 4. 常见问题

### Q1: 导入后没有数据？

- 检查你的日期是否在每行第一列
- 检查宽表列顺序是否为：`日期, 衣明细, 衣金额, 食明细, 食金额, ...`
- 重新执行导入命令并观察导入条数输出

### Q2: 页面打不开或外网 502？

- 本机先验证：`http://localhost:8501`
- 局域网访问使用 `Network URL`
- 如果要稳定外网访问，优先用 Streamlit Cloud 部署地址

---

## 5. 项目结构

```text
accounting-tool/
  app.py                # Streamlit 记账应用
  import_history.py     # 历史账本导入脚本（csv/xlsx/xls）
  requirements.txt      # Python 依赖
  expenses.db           # SQLite 数据库（运行后生成）
```

