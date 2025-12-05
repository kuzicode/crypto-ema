from flask import Flask
import logging
from modules.routes import init_routes
import os
import time
from datetime import datetime, timedelta

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 设置环境变量强制使用亚洲/上海时区
os.environ['TZ'] = 'Asia/Shanghai'
try:
    time.tzset()  # 在某些平台上可能不支持
    logger.info(f"系统时区已设置为: {time.tzname}")
except AttributeError:
    logger.info("此平台不支持tzset函数, 时区设置可能无效")

def create_app():
    """创建并配置Flask应用"""
    app = Flask(__name__)
    
    # 输出当前北京时间（不使用timezone类）
    now = datetime.utcnow() + timedelta(hours=8)
    logger.info(f"应用启动时间(北京时间): {now.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 初始化路由
    app = init_routes(app)
    
    return app

if __name__ == "__main__":
    app = create_app()
    app.run(debug=False, host='0.0.0.0', port=6969)