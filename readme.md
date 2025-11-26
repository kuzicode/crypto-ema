# Crypto EMA App

加密货币技术分析工具，支持 Web 界面查看和 Telegram 消息提醒。

## 功能特点

- 📊 多币种 EMA 趋势分析
- 📈 K线图表可视化
- 🔔 Telegram 实时提醒（突破/跌破关键线位时）
- 📧 邮件提醒支持

## 线位说明

| 线位 | 名称 | 颜色 | 说明 |
|------|------|------|------|
| MA4 | 强势线 | 🌲 深绿 | 价格强势上涨区 |
| MA3 | 上涨线 | 🍀 浅绿 | 价格上涨区 |
| MA2 | 中线 | ⚪ 白色 | 多空分界线 |
| MA5 | 下跌线 | 🔻 浅红 | 价格下跌区 |
| MA6 | 超跌线 | 🔴 深红 | 价格超跌区 |

## 安装

1. 克隆项目并设置虚拟环境：

```bash
sudo apt update && sudo apt upgrade -y
git clone https://github.com/kuzicode/crypto-ema-web
cd crypto-ema-web
sudo apt install python3.12-venv -y
python3 -m venv .venv
source .venv/bin/activate
```

2. 安装依赖：

```bash
pip3 install -r requirements.txt
```

## 运行 Web 服务

```bash
python3 app.py
```

访问 http://localhost:6969

开放防火墙端口（可选）：

```bash
sudo ufw allow 6969
```

## Telegram 提醒配置

1. 创建 `.env` 文件：

```bash
# Telegram Bot 配置
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here
# 话题ID（可选，用于有话题功能的群组）
TELEGRAM_THREAD_ID=
```

2. 获取 Bot Token：在 Telegram 中找 @BotFather 创建机器人

3. 获取 Chat ID：给机器人发消息后访问 `https://api.telegram.org/bot<TOKEN>/getUpdates`

4. 运行提醒脚本：

```bash
python3 telegram_alert.py
```

## 依赖

- Flask: Web 框架
- Pandas: 数据处理
- Matplotlib: 图表生成
- Requests: 访问币安 API
- python-dotenv: 环境变量管理