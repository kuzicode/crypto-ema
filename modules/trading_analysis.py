import requests
import logging
import datetime
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import base64
import io
import time

# 配置中文字体支持
plt.rcParams['font.sans-serif'] = ['Arial Unicode MS', 'SimHei', 'DejaVu Sans', 'Heiti TC', 'PingFang SC']
plt.rcParams['axes.unicode_minus'] = False  # 解决负号显示问题

logger = logging.getLogger(__name__)

# REST API: 币安 API K-line数据 
def get_klines(symbol, interval, limit=1000):
    # 使用备用域名列表
    api_urls = [
        "https://api1.binance.com/api/v3/klines",
        "https://api2.binance.com/api/v3/klines",
        "https://api3.binance.com/api/v3/klines",
        "https://api4.binance.com/api/v3/klines"
    ]
    
    params = {
        'symbol': symbol,
        'interval': interval,
        'limit': limit
    }
    
    for url in api_urls:
        try:
            # 设置15秒超时，避免长时间阻塞
            logger.info(f"正在通过 {url} 获取 {symbol} {interval} K线数据...")
            response = requests.get(url, params=params, timeout=15)
            
            # 检查HTTP状态码
            if response.status_code == 200:
                data = response.json()
                if not data:
                    logger.error(f"获取 {symbol} K线数据返回空列表")
                    continue
                logger.info(f"成功获取 {symbol} K线数据，获取到 {len(data)} 条记录")
                return data
            elif response.status_code == 429:
                logger.error(f"API请求频率限制: {response.text}")
                # 如果是频率限制，等待一分钟后重试
                time.sleep(60)
                continue
            else:
                logger.error(f"通过 {url} 获取K线数据失败: HTTP {response.status_code}, {response.text}")
                continue
        except requests.exceptions.Timeout:
            logger.error(f"通过 {url} 获取 {symbol} K线数据超时")
            continue
        except requests.exceptions.ConnectionError:
            logger.error(f"连接 {url} 失败，尝试下一个域名")
            continue
        except Exception as e:
            logger.error(f"通过 {url} 获取K线数据时出现异常: {e}")
            continue
    
    logger.error(f"所有API域名都无法访问，请检查网络连接或使用代理")
    return []

# 辅助函数 - 解析币安K线数据的格式
def parser_klines(kline):
    return {
        "Open_time": kline[0],
        "Open": kline[1],
        "High": kline[2],
        "Low": kline[3],
        "Close": kline[4],
        "Volume": kline[5],
        "Close_time": kline[6],
        "Quote_asset_volume": kline[7],
        "Number_of_trades": kline[8],
        "Taker_buy_base_asset_volume": kline[9],
        "Taker_buy_quote_asset_volume": kline[10],
        "Ignore": kline[11]
    }

# 时间格式化函数
def get_alltime(time):
    try:
        formatted_time = datetime.datetime.fromtimestamp(time / 1000)
        return formatted_time.strftime('%Y-%m-%d %H:%M:%S')
    except Exception as e:
        logger.error(f"时间格式化错误: {e}")
        return str(time)

class KlineBot:
    def __init__(self, symbol, interval="4h"):
        self.symbol = symbol
        self.interval = interval
        self.limit = 5000  # 固定为5000，以获取更多的数据点
        self.data = self.fetch_data()
        if not self.data.empty:
            self.calculate_macd()
            self.indicators = self.calculate_indicators()
        else:
            self.indicators = pd.DataFrame()

    def fetch_data(self):
        try:
            logger.info(f"正在获取 {self.symbol} 的数据...")
            
            # Get Data
            klines = get_klines(self.symbol, self.interval, self.limit)
            
            if not klines:
                logger.error(f"获取 {self.symbol} 的K线数据失败")
                return pd.DataFrame()
                
            data = {
                "Open": [], "High": [], "Low": [], "Close": [],
                "Time": [], "Volume": [], "Open_time": [], "Close_time": []
            }

            for kline in klines:
                data["Open_time"].append(get_alltime(kline[0]))
                data["Close_time"].append(get_alltime(kline[6]))
                data["Open"].append(float(kline[1]))
                data["High"].append(float(kline[2]))
                data["Low"].append(float(kline[3]))
                data["Close"].append(float(kline[4]))
                data["Volume"].append(float(kline[5]))
                data["Time"].append(float(kline[0]) / 1000)

            # 转换时间戳到pandas datetime
            timestamp = pd.to_datetime(data["Time"], unit='s')
            
            # 创建DataFrame并设置索引
            new_data = pd.DataFrame(data, columns=['Open', 'High', 'Low', 'Close', 'Volume', 'Time', 'Open_time', 'Close_time'])
            
            # 尝试将时间戳设置为索引，同时处理时区
            try:
                utc_timestamp = timestamp.tz_localize('UTC')
                utc_plus_8_timestamp = utc_timestamp.tz_convert('Asia/Shanghai')
                new_data.index = utc_plus_8_timestamp
            except:
                # 如果时区转换失败，使用原始时间戳作为索引
                new_data.index = timestamp

            return new_data
        except Exception as e:
            logger.error(f"Get {self.symbol} data error: {e}")
            return pd.DataFrame()

    def calculate_indicators(self):
        try:
            df = self.data
            df['MA1'] = df['Close']
            df['MA30'] = df['Close'].rolling(window=30).mean()
            df['MA72'] = df['Close'].rolling(window=72).mean()
            df['MA2'] = (df['MA30'] + df['MA72']) / 2
            df['MA3'] = df['MA2'] * 1.1
            df['MA4'] = df['MA2'] * 1.2
            df['MA5'] = df['MA2'] * 0.9
            df['MA6'] = df['MA2'] * 0.8
            return df
        except Exception as e:
            logger.error(f"计算 {self.symbol} 指标时出错: {e}")
            return pd.DataFrame()

    def calculate_macd(self, short_window=12, long_window=26, signal_window=9):
        try:
            # 计算短期和长期的EMA
            self.data['EMA12'] = self.data['Close'].ewm(span=short_window, adjust=False).mean()
            self.data['EMA26'] = self.data['Close'].ewm(span=long_window, adjust=False).mean()

            # 计算MACD线
            self.data['MACD'] = self.data['EMA12'] - self.data['EMA26']

            # 计算信号线
            self.data['Signal Line'] = self.data['MACD'].ewm(span=signal_window, adjust=False).mean()

            # 计算MACD柱
            self.data['MACD Histogram'] = self.data['MACD'] - self.data['Signal Line']

            return self.data
        except Exception as e:
            logger.error(f"计算 {self.symbol} MACD时出错: {e}")
            return self.data
            
    def generate_market_analysis(self):
        """生成市场分析和买入建议（仅中文）"""
        try:
            if self.indicators.empty:
                return None
                
            df = self.indicators
            # 获取最近的数据点
            latest = df.iloc[-1]
            prev = df.iloc[-2]
            prev5 = df.iloc[-5] if len(df) >= 5 else prev
            
            # 市场分析
            analysis = {
                "latest_close": latest["Close"],
                "latest_time": latest.name.strftime('%Y-%m-%d %H:%M') if hasattr(latest.name, 'strftime') else "最新",
                "ma30": latest["MA30"],
                "ma72": latest["MA72"],
                "ma2": latest["MA2"],
                "macd": latest["MACD"],
                "signal": latest["Signal Line"],
                "histogram": latest["MACD Histogram"],
                "prev_histogram": prev["MACD Histogram"],
                "trend": "",
                "signal_type": "",
                "risk_level": "",
                "trading_advice": ""  # 操作建议
            }
            
            # 趋势判断
            if latest["Close"] > latest["MA2"]:
                if latest["Close"] > latest["MA3"]:
                    analysis["trend"] = "强势上升"
                else:
                    analysis["trend"] = "上升"
            elif latest["Close"] < latest["MA2"]:
                if latest["Close"] < latest["MA5"]:
                    analysis["trend"] = "强势下降"
                else:
                    analysis["trend"] = "下降"
            else:
                analysis["trend"] = "横盘整理"
            
            # MACD信号类型
            if latest["MACD"] > latest["Signal Line"]:
                if latest["MACD Histogram"] > prev["MACD Histogram"]:
                    analysis["signal_type"] = "金叉后动能增强"
                else:
                    analysis["signal_type"] = "金叉"
            else:
                if latest["MACD Histogram"] < prev["MACD Histogram"]:
                    analysis["signal_type"] = "死叉后动能增强"
                else:
                    analysis["signal_type"] = "死叉"
            
            # 风险水平
            price_volatility = (latest["High"] - latest["Low"]) / latest["Close"] * 100
            if price_volatility > 5:
                analysis["risk_level"] = "高"
            elif price_volatility > 2:
                analysis["risk_level"] = "中"
            else:
                analysis["risk_level"] = "低"
            
            # 添加支撑和阻力位
            last_50 = df.iloc[-50:]
            support = last_50["Low"].min()
            resistance = last_50["High"].max()
            
            analysis["support"] = support
            analysis["resistance"] = resistance
            
            # 技术分析综合评估
            # 1. 价格动量
            price_momentum = (latest["Close"] - prev5["Close"]) / prev5["Close"] * 100
            
            # 2. MACD趋势强度
            macd_strength = abs(latest["MACD"]) / latest["Close"] * 100
            
            # 3. 价格与MA的距离
            ma_distance = (latest["Close"] - latest["MA2"]) / latest["MA2"] * 100
            
            # 4. 价格是否接近支撑/阻力位
            near_support = (latest["Close"] - support) / support * 100 < 3
            near_resistance = (resistance - latest["Close"]) / latest["Close"] * 100 < 3
            
            # 5. 柱状图反转信号
            histogram_reversal = (latest["MACD Histogram"] * prev["MACD Histogram"] < 0)
            
            # 综合分析生成操作建议
            if analysis["trend"] == "强势上升" and analysis["signal_type"] == "金叉后动能增强":
                if near_resistance:
                    analysis["trading_advice"] = "接近阻力位，谨慎追高"
                else:
                    analysis["trading_advice"] = "强势上涨趋势，可考虑买入"
            elif analysis["trend"] == "上升" and analysis["signal_type"] == "金叉":
                analysis["trading_advice"] = "上升趋势形成，可分批买入"
            elif analysis["trend"] == "下降" and analysis["signal_type"] == "死叉":
                if near_support:
                    analysis["trading_advice"] = "接近支撑位，可能反弹"
                else:
                    analysis["trading_advice"] = "下跌趋势，建议观望或减仓"
            elif analysis["trend"] == "强势下降" and analysis["signal_type"] == "死叉后动能增强":
                analysis["trading_advice"] = "强势下跌，建议观望"
            elif histogram_reversal and latest["MACD Histogram"] > 0:
                analysis["trading_advice"] = "MACD柱状图转正，可能是买入信号"
            elif histogram_reversal and latest["MACD Histogram"] < 0:
                analysis["trading_advice"] = "MACD柱状图转负，可能是卖出信号"
            elif near_support and analysis["risk_level"] != "高":
                analysis["trading_advice"] = "接近支撑位，可考虑小仓位试探"
            elif near_resistance:
                analysis["trading_advice"] = "接近阻力位，注意可能回调"
            elif abs(ma_distance) < 0.5:
                analysis["trading_advice"] = "价格接近均线，等待方向确认"
            else:
                analysis["trading_advice"] = "市场信号不明确，建议观望"
            
            return analysis
            
        except Exception as e:
            logger.error(f"生成市场分析时出错: {e}")
            return None

    def generate_plot(self):
        try:
            if self.indicators.empty:
                return None, f"No data available for {self.symbol}. Please check if this symbol exists on Binance."
                
            df = self.indicators
            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(13, 8), gridspec_kw={'height_ratios': [3, 1]})
            plt.style.use('dark_background')  # 使用暗色主题，更符合加密货币风格

            # 绘制MA1到MA6
            ax1.plot(df['MA1'], label='Current Price', color='#00FFFF', linewidth=2)  # 青色-当前价格
            ax1.plot(df['MA2'], label='中线', color='#FFFFFF')              # 白色-中线
            ax1.plot(df['MA3'], label='上涨线', color='#90EE90')            # 浅绿-上涨线（浅）
            ax1.plot(df['MA4'], label='强势线', color='#228B22')            # 深绿-强势线（深）
            ax1.plot(df['MA5'], label='下跌线', color='#FF6B6B', linestyle='--')  # 浅红-下跌线（浅）
            ax1.plot(df['MA6'], label='超跌线', color='#DC143C', linestyle='--')  # 深红-超跌线（深）

            # 设置日期格式和刻度
            # 调整为每50个点取一个刻度，避免过多刻度导致的显示问题
            ax1.set_xticks(df.index[::50])  
            ax1.tick_params(axis='x', rotation=45)
            ax1.tick_params(colors='#00FF00')  # 绿色坐标轴文字
            
            # 尝试使用日期格式化器，如果索引是日期时间类型
            try:
                ax1.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
            except:
                pass
                
            ax1.xaxis.set_visible(False)

            # 添加生成时间到标题，使用UTC+8小时作为北京时间
            beijing_time = datetime.datetime.utcnow() + datetime.timedelta(hours=8)
            formatted_time = beijing_time.strftime('%Y-%m-%d %H:%M:%S')
            ax1.set_title(f'{self.symbol} Moving Averages - Last Update: {formatted_time}', color='#00FF00', fontsize=16)
            ax1.set_ylabel('Price', color='#00FF00')
            ax1.legend()
            
            # 像素风格化：网格和背景
            ax1.grid(True, linestyle='--', alpha=0.3, color='#4B0082')
            ax1.set_facecolor('#000033')  # 深蓝背景
            
            # 添加当前价格标注
            current_price = df['Close'].iloc[-1]
            ax1.text(df.index[-1], current_price, f"  {current_price:.2f}", 
                    color='#00FFFF', fontweight='bold', verticalalignment='center')
            
            # 绘制MACD和信号线
            ax2.plot(df.index, df['MACD'], label='MACD', color='#00FFFF', linewidth=1.5)
            ax2.plot(df.index, df['Signal Line'], label='Signal', color='#FF00FF', linewidth=1.5)

            # 绘制MACD柱状图
            colors = ['#00FF00' if val >= 0 else '#FF0000' for val in df['MACD Histogram']]
            ax2.bar(df.index, df['MACD Histogram'], color=colors, width=0.7, alpha=0.7)

            # 设置日期格式和刻度
            ax2.set_xticks(df.index[::50])
            ax2.tick_params(axis='x', rotation=45, colors='#00FF00')
            
            # 尝试使用日期格式化器，如果索引是日期时间类型
            try:
                ax2.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
            except:
                pass
                
            ax2.set_xlabel('Date', color='#00FF00')
            ax2.set_ylabel('MACD', color='#00FF00')
            ax2.legend(facecolor='#000033', edgecolor='#32CD32')
            ax2.grid(True, linestyle='--', alpha=0.3, color='#4B0082')
            ax2.set_facecolor('#000033')

            fig.patch.set_facecolor('#000033')
            plt.tight_layout()
            
            # 转换为base64编码的图像
            buf = io.BytesIO()
            plt.savefig(buf, format='png', facecolor='#000033', dpi=100)
            buf.seek(0)
            img_str = base64.b64encode(buf.read()).decode('utf-8')
            plt.close(fig)
            
            return img_str, None
        except Exception as e:
            logger.error(f"生成{self.symbol}图表时出错: {e}")
            return None, str(e) 

# 分析单个币种的趋势类别
def token_trend(symbol, interval):
    """
    分析单个币种的趋势类别
    
    Args:
        symbol (str): 交易对符号，如BTCUSDT
        interval (str): K线周期，如1h, 4h, 1d
        
    Returns:
        dict: 包含趋势类别的字典，如 {'token_trend': 'above_ma4'}
        None: 如果分析失败
    """
    try:
        bot = KlineBot(symbol=symbol, interval=interval)
        
        # 检查数据是否有效
        if bot.indicators.empty:
            return None
            
        # 获取最新的数据点
        latest = bot.indicators.iloc[-1]
        
        # 分析当前价格与各MA线的关系
        price = latest['MA1']  # MA1是当前价格
        ma2 = latest['MA2']    # 中线（白色）
        ma3 = latest['MA3']    # 上涨线（黄色）
        ma4 = latest['MA4']    # 强势线（橙色）
        ma5 = latest['MA5']    # 下跌线（绿色）
        ma6 = latest['MA6']    # 超跌线（红色）
        
        # 判断趋势类别
        if price > ma4:
            return {'token_trend': 'above_ma4'}
        elif price > ma3:
            return {'token_trend': 'above_ma3'}
        elif price > ma2 and price < ma3:
            return {'token_trend': 'between_ma2_ma3'}  # 盘整区上行
        elif price < ma2 and price > ma5:
            return {'token_trend': 'between_ma5_ma2'}  # 盘整区下行
        elif price > ma6:
            return {'token_trend': 'below_ma5'}
        else:
            return {'token_trend': 'below_ma6'}
            
    except Exception as e:
        logger.error(f"分析 {symbol} 趋势时出错: {e}")
        return None 