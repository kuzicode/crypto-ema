#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import time
import os
import logging
import smtplib
import datetime
from modules.trading_analysis import token_trend, KlineBot
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header


# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 配置参数
TOKENS = ["BTC", "ETH", "SOL", "UNI", "AAVE", "PENDLE", "PEPE", "PENGU"]  # 要监控的代币
INTERVAL = "4h"  # K线周期
JSON_FILE = "mail_alerts.json"  # JSON文件路径
CHECK_INTERVAL = 300  # 检查间隔（秒），5分钟

# 邮件配置
def load_email_config():
    """从配置文件加载邮件配置"""
    config_path = ".mail_config"
    default_config = {
        "smtp_server": "smtp.qq.com",
        "smtp_port": 465,
        "username": "",
        "password": "",
        "sender": "",
        "recipients": []
    }
    
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                logger.info(f"已从配置文件加载邮件设置: {config_path}")
                return config
        except Exception as e:
            logger.error(f"加载邮件配置文件时出错: {e}")
    else:
        logger.warning(f"配置文件不存在: {config_path}，创建默认配置")
        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(default_config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"创建配置文件时出错: {e}")
    
    return default_config

# 加载配置
EMAIL_CONFIG = load_email_config()

# 从环境变量获取密码（如果配置文件中没有）
if not EMAIL_CONFIG.get("password") and os.environ.get("QQ_EMAIL_AUTH_CODE"):
    EMAIL_CONFIG["password"] = os.environ.get("QQ_EMAIL_AUTH_CODE")

# EMA状态映射
EMA_STATUS_MAP = {
    "above_ma4": "突破上涨黄线",
    "above_ma3": "突破上涨绿线",
    "between_ma2_ma3": "盘整区上行",
    "between_ma5_ma2": "盘整区下行",
    "below_ma5": "跌破底部绿线",
    "below_ma6": "跌破底部蓝线"
}

def get_token_data():
    """获取代币数据"""
    results = []
    
    for token in TOKENS:
        try:
            # 添加USDT后缀
            symbol = f"{token}USDT"
            
            # 获取代币趋势
            trend_data = token_trend(symbol, INTERVAL)
            
            if trend_data and 'token_trend' in trend_data:
                # 从trading_analysis模块获取价格
                bot = KlineBot(symbol, INTERVAL)
                
                if not bot.indicators.empty:
                    price = bot.indicators['Close'].iloc[-1]
                    
                    # 创建代币数据
                    token_data = {
                        "Token": token,
                        "Price": f"{price:.2f}",
                        "EMA": EMA_STATUS_MAP.get(trend_data['token_trend'], "未知")
                    }
                    
                    results.append(token_data)
                    logger.info(f"获取{token}数据成功: {token_data}")
                else:
                    logger.error(f"获取{token}数据失败: 指标数据为空")
            else:
                logger.error(f"获取{token}趋势失败")
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
    """检查EMA状态是否有变化，返回需要提醒的币种列表（只在突破上涨黄线、突破上涨绿线、跌破底部绿线、跌破底部蓝线时提醒）"""
    # 只关注这四种状态
    notify_ema_status = [
        "突破上涨黄线",
        "突破上涨绿线",
        "跌破底部绿线",
        "跌破底部蓝线"
    ]
    if not previous_data:
        # 如果没有之前的数据，所有币种都视为有变化，但只提醒指定状态
        return [item.get("Token") for item in current_data if "Token" in item and item.get("EMA") in notify_ema_status]
    
    # 创建之前数据的映射 {Token: EMA}
    prev_map = {item["Token"]: item["EMA"] for item in previous_data if "Token" in item and "EMA" in item}
    
    # 检查当前数据是否有变化
    changed_tokens = []
    for item in current_data:
        token = item.get("Token")
        ema = item.get("EMA")
        if token and ema:
            # 只在指定状态变化时提醒
            if (token not in prev_map or prev_map[token] != ema) and ema in notify_ema_status:
                changed_tokens.append(token)
    return changed_tokens

def send_email_alert(data, changed_tokens):
    """发送邮件提醒"""
    try:
        # 获取SMTP配置
        smtp_server = EMAIL_CONFIG.get("smtp_server")
        smtp_port = EMAIL_CONFIG.get("smtp_port", 465)
        username = EMAIL_CONFIG.get("username")
        password = EMAIL_CONFIG.get("password")
        recipients = EMAIL_CONFIG.get("recipients", [])
        
        # 检查配置是否完整
        if not all([smtp_server, username, password, recipients]):
            logger.error("邮件配置不完整，无法发送邮件")
            return False
        
        # 创建邮件内容
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # 在标题中显示变化的币种
        changed_tokens_str = ", ".join(changed_tokens)
        subject = f"{changed_tokens_str} 币价状态变化提醒 - {timestamp}"
        
        # 构建HTML内容
        html_content = f"""
        <html>
        <head>
            <style>
                table {{
                    border-collapse: collapse;
                    width: 100%;
            <h2></h2>
                }}
                th, td {{
                    border: 1px solid #dddddd;
                    text-align: left;
                    padding: 8px;
                }}
                th {{
                    background-color: #f2f2f2;
                }}
                tr:nth-child(even) {{
                    background-color: #f9f9f9;
                }}
                .highlight {{
                    font-weight: bold;
                    color: #ff0000;
                }}
            </style>
        </head>
        <body>
            <p class="highlight">检测到 {changed_tokens_str} 的EMA状态发生变化</p>
            <p>时间: {timestamp}</p>
            <table>
                <tr>
                    <th>代币</th>
                    <th>价格</th>
                    <th>EMA状态</th>
                </tr>
        """
        
        for item in data:
            token = item.get("Token", "")
            price = item.get("Price", "")
            ema = item.get("EMA", "")
            
            # 为变化的币种添加高亮样式
            if token in changed_tokens:
                html_content += f"""
                <tr class="highlight">
                    <td>{token}</td>
                    <td>{price}</td>
                    <td>{ema}</td>
                </tr>
                """
            else:
                html_content += f"""
                <tr>
                    <td>{token}</td>
                    <td>{price}</td>
                    <td>{ema}</td>
                </tr>
                """
        
        html_content += """
            </table>
            <p>此邮件由自动监控系统发送，无需回复。</p>
            <p>Power by CashMiner</p>
        </body>
        </html>
        """
        
        # 创建HTML邮件
        msg = MIMEText(html_content, 'html', 'utf-8')
        msg['Subject'] = subject
        msg['From'] = username  # 直接使用邮箱地址
        msg['To'] = ", ".join(recipients)
            
        logger.info(f"正在发送邮件到 {', '.join(recipients)}")
        
        # 发送邮件
        server = smtplib.SMTP_SSL(smtp_server, smtp_port)
        server.login(username, password)
        server.sendmail(username, recipients, msg.as_string())
        server.quit()
        
        logger.info("邮件发送成功")
        return True
    except Exception as e:
        logger.error(f"发送邮件失败: {e}")
        return False

def main():
    """主函数"""
    logger.info("开始运行加密货币监控脚本")
    
    try:
        # 获取当前代币数据
        current_data = get_token_data()
        
        if not current_data:
            logger.error("未能获取任何代币数据")
            return
        
        # 加载之前的数据
        previous_data = load_previous_data()
        
        # 检查EMA状态是否有变化
        changed_tokens = has_ema_changed(previous_data, current_data)
        if changed_tokens:
            logger.info(f"检测到EMA状态变化的币种: {', '.join(changed_tokens)}")
            # 保存新数据
            if save_data(current_data):
                send_email_alert(current_data, changed_tokens)
        else:
            logger.info("EMA状态未变化，不更新数据")
    
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


