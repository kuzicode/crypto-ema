import os
from dotenv import load_dotenv
load_dotenv()  # 必须在所有业务模块导入之前执行

from flask import Flask
import logging
import threading
from modules.routes import init_routes
from modules.trading_analysis import calculate_ahr999, fetch_mvrv_data, fetch_btc_dominance
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

def _cache_refresh_loop():
    """后台守护线程：启动时立即预热缓存，之后每小时刷新一次。"""
    while True:
        try:
            logger.info("后台缓存刷新开始 (AHR999 / MVRV / BTCDOM)...")
            calculate_ahr999()
            fetch_mvrv_data()
            fetch_btc_dominance()
            logger.info("后台缓存刷新完成")
        except Exception as e:
            logger.error(f"后台缓存刷新出错: {e}")
        time.sleep(3600)


def create_app():
    """创建并配置Flask应用"""
    app = Flask(__name__)

    # 输出当前北京时间（不使用timezone类）
    now = datetime.utcnow() + timedelta(hours=8)
    logger.info(f"应用启动时间(北京时间): {now.strftime('%Y-%m-%d %H:%M:%S')}")

    # 初始化路由
    app = init_routes(app)

    # 启动后台缓存预热线程（daemon=True 确保进程退出时自动终止）
    t = threading.Thread(target=_cache_refresh_loop, daemon=True, name='cache-refresh')
    t.start()
    logger.info("后台缓存刷新线程已启动")

    return app

if __name__ == "__main__":
    app = create_app()
    app.run(debug=False, host='0.0.0.0', port=6969)