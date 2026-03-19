#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import time
import os
import logging
import datetime
import requests
from dotenv import load_dotenv
from modules.trading_analysis import token_trend, KlineBot

# 加载 .env 文件
load_dotenv()

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 配置参数
TOKENS = ["BTC", "ETH", "SOL"]  # 要监控的代币
INTERVAL = "4h"  # K线周期
JSON_FILE = "telegram_alert.json"  # JSON文件路径
CHECK_INTERVAL = 300  # 检查间隔（秒），5分钟

# Telegram配置 - 从 .env 文件加载
TELEGRAM_CONFIG = {
    "bot_token": os.environ.get("TELEGRAM_BOT_TOKEN", ""),
    "chat_id": os.environ.get("TELEGRAM_CHAT_ID", ""),
    "message_thread_id": os.environ.get("TELEGRAM_THREAD_ID", "")  # 话题ID（可选，用于群组话题）
}

# 检查配置是否完整
if not TELEGRAM_CONFIG["bot_token"]:
    logger.warning("未配置 TELEGRAM_BOT_TOKEN，请在 .env 文件中设置")
if not TELEGRAM_CONFIG["chat_id"]:
    logger.warning("未配置 TELEGRAM_CHAT_ID，请在 .env 文件中设置")

# EMA状态映射
EMA_STATUS_MAP = {
    "above_ma4": "🌲 突破强势线",
    "above_ma3": "🍀 突破上涨线",
    "between_ma2_ma3": "⬆️ 盘整区上行",
    "between_ma5_ma2": "⬇️ 盘整区下行",
    "below_ma5": "🔻 跌破下跌线",
    "below_ma6": "🔴 跌破超跌线"
}

# EMA状态对应的emoji（用于标题）
EMA_EMOJI_MAP = {
    "above_ma4": "🚀",
    "above_ma3": "📈",
    "between_ma2_ma3": "⬆️",
    "between_ma5_ma2": "⬇️",
    "below_ma5": "📉",
    "below_ma6": "🔴"
}

def get_token_data():
    """获取代币数据"""
    results = []
    
    for token in TOKENS:
        try:
            # 添加USDT后缀
            symbol = f"{token}USDT"
            
            # 直接使用 KlineBot 获取数据（只请求一次API）
            bot = KlineBot(symbol, INTERVAL)
            
            if not bot.indicators.empty:
                # 获取最新数据
                latest = bot.indicators.iloc[-1]
                price = latest['Close']
                
                # 判断趋势类别（复用已有数据，不再调用API）
                ma2 = latest['MA2']
                ma3 = latest['MA3']
                ma4 = latest['MA4']
                ma5 = latest['MA5']
                ma6 = latest['MA6']
                
                if price > ma4:
                    trend_key = 'above_ma4'
                elif price > ma3:
                    trend_key = 'above_ma3'
                elif price > ma2:
                    trend_key = 'between_ma2_ma3'
                elif price > ma5:
                    trend_key = 'between_ma5_ma2'
                elif price > ma6:
                    trend_key = 'below_ma5'
                else:
                    trend_key = 'below_ma6'
                
                # 创建代币数据（包含各线位价格）
                token_data = {
                    "Token": token,
                    "Price": f"{price:.2f}",
                    "EMA": EMA_STATUS_MAP.get(trend_key, "未知"),
                    "EMA_Key": trend_key,
                    "MA6": f"{ma6:.2f}",  # 超跌线（深红）
                    "MA5": f"{ma5:.2f}",  # 下跌线（浅红）
                    "MA2": f"{ma2:.2f}",  # MA趋势线（白）
                    "MA3": f"{ma3:.2f}",  # 上涨线（浅绿）
                    "MA4": f"{ma4:.2f}"   # 强势线（深绿）
                }
                
                results.append(token_data)
                logger.info(f"获取{token}数据成功: {token_data}")
            else:
                logger.error(f"获取{token}数据失败: 指标数据为空")
                
            # 添加请求间隔，避免触发频率限制
            time.sleep(0.5)
            
        except Exception as e:
            logger.error(f"处理{token}时出错: {e}")
    
    return results

def load_previous_data():
    """加载之前的数据"""
    if os.path.exists(JSON_FILE):
        try:
            with open(JSON_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if data and isinstance(data, list) and len(data) > 0:
                    return data[-1].get('data', [])
        except Exception as e:
            logger.error(f"加载之前的数据时出错: {e}")
    
    return []

def save_data(data):
    """保存数据到JSON文件"""
    try:
        # 创建带时间戳的记录
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        record = {
            "timestamp": timestamp,
            "data": data
        }
        
        # 加载现有数据
        existing_data = []
        if os.path.exists(JSON_FILE):
            try:
                with open(JSON_FILE, 'r', encoding='utf-8') as f:
                    existing_data = json.load(f)
            except:
                existing_data = []
        
        # 确保existing_data是列表
        if not isinstance(existing_data, list):
            existing_data = []
        
        # 添加新记录
        existing_data.append(record)
        
        # 保存到文件
        with open(JSON_FILE, 'w', encoding='utf-8') as f:
            json.dump(existing_data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"数据已保存到{JSON_FILE}")
        return True
    except Exception as e:
        logger.error(f"保存数据时出错: {e}")
        return False

def has_ema_changed(previous_data, current_data):
    """检查EMA状态是否有变化，返回需要提醒的币种列表（只在突破强势线、突破上涨线、跌破下跌线、跌破超跌线时提醒）"""
    # 只关注这四种状态的key
    notify_ema_keys = [
        "above_ma4",     # 突破强势线（深绿）
        "above_ma3",     # 突破上涨线（浅绿）
        "below_ma5",     # 跌破下跌线（浅红）
        "below_ma6"      # 跌破超跌线（深红）
    ]
    
    if not previous_data:
        # 如果没有之前的数据，所有币种都视为有变化，但只提醒指定状态
        return [item.get("Token") for item in current_data 
                if "Token" in item and item.get("EMA_Key") in notify_ema_keys]
    
    # 创建之前数据的映射 {Token: EMA_Key}
    prev_map = {item["Token"]: item.get("EMA_Key", "") for item in previous_data if "Token" in item}
    
    # 检查当前数据是否有变化
    changed_tokens = []
    for item in current_data:
        token = item.get("Token")
        ema_key = item.get("EMA_Key")
        if token and ema_key:
            # 只在指定状态变化时提醒
            if (token not in prev_map or prev_map[token] != ema_key) and ema_key in notify_ema_keys:
                changed_tokens.append(token)
    return changed_tokens

def send_telegram_alert(data, changed_tokens):
    """发送Telegram提醒"""
    try:
        # 获取Telegram配置
        bot_token = TELEGRAM_CONFIG.get("bot_token")
        chat_id = TELEGRAM_CONFIG.get("chat_id")
        
        # 检查配置是否完整
        if not all([bot_token, chat_id]):
            logger.error("Telegram配置不完整，无法发送消息")
            return False
        
        # 创建消息内容
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # 构建消息
        changed_tokens_str = ", ".join(changed_tokens)
        
        # 获取变化币种的emoji
        changed_emojis = []
        for item in data:
            if item.get("Token") in changed_tokens:
                ema_key = item.get("EMA_Key", "")
                emoji = EMA_EMOJI_MAP.get(ema_key, "⚡")
                changed_emojis.append(emoji)
        
        emoji_str = "".join(changed_emojis) if changed_emojis else "⚡"
        
        message = f"""{emoji_str} *币价状态变化提醒*
⏰ `{timestamp}`

"""
        
        # 添加各币种详情
        for item in data:
            token = item.get("Token", "")
            price = item.get("Price", "")
            ema = item.get("EMA", "")
            ma6 = item.get("MA6", "")  # 超跌线（深红）
            ma5 = item.get("MA5", "")  # 下跌线（浅红）
            ma2 = item.get("MA2", "")  # MA趋势线（白）
            ma3 = item.get("MA3", "")  # 上涨线（浅绿）
            ma4 = item.get("MA4", "")  # 强势线（深绿）
            
            # 为变化的币种添加标记（状态也加粗）
            if token in changed_tokens:
                message += f"🔔 *{token}* ${price} *{ema}*\n"
            else:
                message += f"▫️ {token} ${price} {ema}\n"
            
            # 各线位价格（简洁列表）
            # 🔴超跌线(深红) 🔻下跌线(浅红) ⚪中线 🍀上涨线(浅绿) 🌲强势线(深绿)
            message += f"🔴{ma6} 🔻{ma5} ⚪{ma2} 🍀{ma3} 🌲{ma4}\n\n"
        
        # 发送消息
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "Markdown"
        }
        
        # 如果配置了话题ID，添加到payload
        message_thread_id = TELEGRAM_CONFIG.get("message_thread_id")
        if message_thread_id:
            payload["message_thread_id"] = int(message_thread_id)
            logger.info(f"正在发送Telegram消息到 {chat_id} 话题 {message_thread_id}")
        else:
            logger.info(f"正在发送Telegram消息到 {chat_id}")
        
        response = requests.post(url, json=payload, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            if result.get("ok"):
                logger.info("Telegram消息发送成功")
                return True
            else:
                logger.error(f"Telegram API返回错误: {result}")
                return False
        else:
            logger.error(f"发送Telegram消息失败: HTTP {response.status_code}, {response.text}")
            return False
            
    except Exception as e:
        logger.error(f"发送Telegram消息失败: {e}")
        return False

# 测试模式开关 - 设为 True 时每次运行都发送消息
TEST_MODE = False

def main():
    """主函数"""
    logger.info("开始运行加密货币Telegram监控脚本")
    
    try:
        # 获取当前代币数据
        current_data = get_token_data()
        
        if not current_data:
            logger.error("未能获取任何代币数据")
            return
        
        # 测试模式：每次都发送消息
        if TEST_MODE:
            logger.info("【测试模式】强制发送消息")
            all_tokens = [item.get("Token") for item in current_data if "Token" in item]
            send_telegram_alert(current_data, all_tokens)
            return
        
        # 加载之前的数据
        previous_data = load_previous_data()
        
        # 首次运行时初始化数据（无论什么状态都保存）
        if not previous_data:
            logger.info("首次运行，初始化数据...")
            save_data(current_data)
            return
        
        # 检查EMA状态是否有变化
        changed_tokens = has_ema_changed(previous_data, current_data)

        # 每次都保存当前状态，确保中间经过的非通知状态也被记录
        # 否则 A→B（不通知）→A 时，因为上次保存的仍是 A，会错误地认为无变化
        save_data(current_data)

        if changed_tokens:
            logger.info(f"检测到EMA状态变化的币种: {', '.join(changed_tokens)}")
            send_telegram_alert(current_data, changed_tokens)
        else:
            logger.info("EMA状态未变化，无需提醒")
    
    except Exception as e:
        logger.error(f"运行脚本时出错: {e}")

if __name__ == "__main__":
    # 单次运行
    main()
    
    # 定时运行
    while True:
        try:
            time.sleep(CHECK_INTERVAL)
            main()
        except Exception as e:
            logger.error(f"主循环出错: {e}")
            time.sleep(60)  # 出错后等待1分钟再重试
        
        logger.info(f"等待{CHECK_INTERVAL}秒后再次检查...")

