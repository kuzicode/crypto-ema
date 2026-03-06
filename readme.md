# Crypto EMA Web

加密货币数据分析平台 — 集成链上指标与技术分析工具。

## 功能概览

| 模块 | 说明 |
|------|------|
| **主页仪表盘** | 一页总览所有指标当前状态，卡片式布局 |
| **MA指标查询** | 多币种均线技术分析，支持自定义币种和周期 |
| **MA异动提醒** | 币价突破/跌破关键均线时的历史记录展示 |
| **AHR999** | 比特币定投参考指标，含交互式历史走势图 |
| **MVRV** | 市值与实现价值比率，BTC 周期顶底判断 |

### MA 线位说明

| 线位 | 名称 | 颜色 | 说明 |
|------|------|------|------|
| MA4 | 强势线 | 深绿 | 价格强势上涨区 |
| MA3 | 上涨线 | 浅绿 | 价格上涨区 |
| MA2 | 中线 | 白色 | 多空分界线 |
| MA5 | 下跌线 | 浅红 | 价格下跌区 |
| MA6 | 超跌线 | 深红 | 价格超跌区 |

## 技术栈

- **后端**: Flask, Pandas, NumPy, Matplotlib
- **前端**: Jinja2 模板, Lightweight Charts v4, Font Awesome
- **数据源**: Binance REST API (K线/价格), BGeometrics API (MVRV)

## 部署

```bash
git clone https://github.com/kuzicode/crypto-ema-web
cd crypto-ema-web
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 app.py
```

访问 `http://localhost:6969`

开放端口（生产环境可选）：

```bash
sudo ufw allow 6969
```

## Telegram 提醒

1. 创建 `.env` 文件：

```
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
TELEGRAM_THREAD_ID=          # 可选，话题群组用
```

2. 运行提醒脚本：

```bash
python3 telegram_alert.py
```

## 项目结构

```
├── app.py                  # Flask 入口
├── modules/
│   ├── routes.py           # API 路由
│   └── trading_analysis.py # 计算引擎 (MA/AHR999/MVRV)
├── templates/
│   ├── layout.html         # 页面骨架
│   └── partials/           # 各功能模块模板
├── telegram_alert.py       # Telegram 提醒脚本
├── mail_alert.py           # 邮件提醒脚本
└── requirements.txt
```
