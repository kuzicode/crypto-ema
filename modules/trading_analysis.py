import os
import requests
import logging
import datetime
import numpy as np
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
def get_klines(symbol, interval, limit=1000, start_time=None, end_time=None):
    """
    获取K线数据，单次最多1000条
    """
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
        'limit': min(limit, 1000)  # 币安API单次最多1000条
    }
    
    if start_time:
        params['startTime'] = start_time
    if end_time:
        params['endTime'] = end_time
    
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


def get_klines_extended(symbol, interval, total_limit=4000):
    """
    分页获取更多K线数据，支持获取超过1000条的历史数据
    
    Args:
        symbol: 交易对符号
        interval: K线周期
        total_limit: 总共需要获取的数据条数（默认4000条，4h周期约2年）
    
    Returns:
        list: K线数据列表
    """
    all_klines = []
    end_time = None
    remaining = total_limit
    
    while remaining > 0:
        batch_size = min(remaining, 1000)
        klines = get_klines(symbol, interval, limit=batch_size, end_time=end_time)
        
        if not klines:
            break
            
        # 如果是第一次请求或者有新数据
        if klines:
            # 将数据添加到列表开头（因为我们是从最新往回取）
            all_klines = klines + all_klines
            
            # 获取最早一条数据的开始时间，作为下次请求的结束时间
            earliest_time = klines[0][0]  # 第一条数据的开始时间
            end_time = earliest_time - 1  # 减1毫秒，避免重复
            
            remaining -= len(klines)
            
            # 如果返回的数据少于请求的数量，说明已经没有更多历史数据了
            if len(klines) < batch_size:
                logger.info(f"已获取所有可用的 {symbol} 历史数据")
                break
                
            # 避免请求过于频繁
            time.sleep(0.2)
        else:
            break
    
    # 去重并按时间排序
    if all_klines:
        # 使用开始时间作为key去重
        seen = set()
        unique_klines = []
        for kline in all_klines:
            if kline[0] not in seen:
                seen.add(kline[0])
                unique_klines.append(kline)
        
        # 按开始时间排序
        unique_klines.sort(key=lambda x: x[0])
        logger.info(f"总共获取 {symbol} K线数据 {len(unique_klines)} 条")
        return unique_klines
    
    return all_klines

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
        self.limit = 4400  # 4h周期下，4400条约2年数据
        self.data = self.fetch_data()
        if not self.data.empty:
            self.calculate_macd()
            self.indicators = self.calculate_indicators()
        else:
            self.indicators = pd.DataFrame()

    def fetch_data(self):
        try:
            logger.info(f"正在获取 {self.symbol} 的数据...")
            
            # 使用扩展函数获取更多历史数据
            klines = get_klines_extended(self.symbol, self.interval, self.limit)
            
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
            
            # GMGN.ai PRO Dark Theme 配色
            BG_COLOR = '#0d0d0d'          # 主背景色
            BG_CHART = '#141414'          # 图表背景
            GRID_COLOR = '#2a2a2a'        # 网格线
            TEXT_COLOR = '#9ca3af'        # 文字颜色
            TEXT_PRIMARY = '#e5e5e5'      # 主要文字
            
            # 线条配色 - 专业交易风格
            PRICE_COLOR = '#f59e0b'       # 当前价格 - 橙黄色（醒目）
            MA2_COLOR = '#e5e5e5'         # 中线 - 白色
            MA3_COLOR = '#4ade80'         # 上涨线 - 浅绿
            MA4_COLOR = '#22c55e'         # 强势线 - 深绿
            MA5_COLOR = '#f87171'         # 下跌线 - 浅红
            MA6_COLOR = '#ef4444'         # 超跌线 - 深红
            
            # MACD 配色
            MACD_COLOR = '#3b82f6'        # MACD线 - 蓝色
            SIGNAL_COLOR = '#a855f7'      # 信号线 - 紫色
            HIST_UP = '#22c55e'           # 柱状图上涨 - 绿色
            HIST_DOWN = '#ef4444'         # 柱状图下跌 - 红色
            
            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(18, 8), gridspec_kw={'height_ratios': [3, 1]})
            plt.style.use('dark_background')

            # 绘制MA1到MA6
            ax1.plot(df['MA1'], label='Current Price', color=PRICE_COLOR, linewidth=1)
            ax1.plot(df['MA2'], label='中线', color=MA2_COLOR, linewidth=1)
            ax1.plot(df['MA3'], label='上涨线', color=MA3_COLOR, linewidth=1)
            ax1.plot(df['MA4'], label='强势线', color=MA4_COLOR, linewidth=1)
            ax1.plot(df['MA5'], label='下跌线', color=MA5_COLOR, linestyle='--', linewidth=1)
            ax1.plot(df['MA6'], label='超跌线', color=MA6_COLOR, linestyle='--', linewidth=1)

            # 设置日期格式和刻度
            ax1.set_xticks(df.index[::50])  
            ax1.tick_params(axis='x', rotation=45)
            ax1.tick_params(colors=TEXT_COLOR)
            
            # 尝试使用日期格式化器
            try:
                ax1.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
            except:
                pass
                
            ax1.xaxis.set_visible(False)

            # 添加生成时间到标题
            beijing_time = datetime.datetime.utcnow() + datetime.timedelta(hours=8)
            formatted_time = beijing_time.strftime('%Y-%m-%d %H:%M:%S')
            ax1.set_title(f'{self.symbol} Moving Averages - Last Update: {formatted_time}', color=TEXT_PRIMARY, fontsize=16)
            ax1.set_ylabel('Price', color=TEXT_COLOR)
            
            # 图例样式
            legend1 = ax1.legend(facecolor=BG_CHART, edgecolor=GRID_COLOR, labelcolor=TEXT_COLOR)
            legend1.get_frame().set_alpha(0.9)
            
            # 网格和背景
            ax1.grid(True, linestyle='-', alpha=0.3, color=GRID_COLOR)
            ax1.set_facecolor(BG_CHART)
            
            # 设置边框颜色
            for spine in ax1.spines.values():
                spine.set_color(GRID_COLOR)
            
            # 添加当前价格标注
            current_price = df['Close'].iloc[-1]
            ax1.text(df.index[-1], current_price, f"  {current_price:.2f}", 
                    color=PRICE_COLOR, fontweight='bold', verticalalignment='center')
            
            # 绘制MACD和信号线
            ax2.plot(df.index, df['MACD'], label='MACD', color=MACD_COLOR, linewidth=1)
            ax2.plot(df.index, df['Signal Line'], label='Signal', color=SIGNAL_COLOR, linewidth=1)

            # 绘制MACD柱状图
            colors = [HIST_UP if val >= 0 else HIST_DOWN for val in df['MACD Histogram']]
            ax2.bar(df.index, df['MACD Histogram'], color=colors, width=0.7, alpha=0.8)

            # 设置日期格式和刻度
            ax2.set_xticks(df.index[::50])
            ax2.tick_params(axis='x', rotation=45, colors=TEXT_COLOR)
            ax2.tick_params(axis='y', colors=TEXT_COLOR)
            
            # 尝试使用日期格式化器
            try:
                ax2.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
            except:
                pass
                
            ax2.set_xlabel('Date', color=TEXT_COLOR)
            ax2.set_ylabel('MACD', color=TEXT_COLOR)
            
            # 图例样式
            legend2 = ax2.legend(facecolor=BG_CHART, edgecolor=GRID_COLOR, labelcolor=TEXT_COLOR)
            legend2.get_frame().set_alpha(0.9)
            
            ax2.grid(True, linestyle='-', alpha=0.3, color=GRID_COLOR)
            ax2.set_facecolor(BG_CHART)
            
            # 设置边框颜色
            for spine in ax2.spines.values():
                spine.set_color(GRID_COLOR)

            fig.patch.set_facecolor(BG_COLOR)
            plt.tight_layout()
            
            # 转换为base64编码的图像
            buf = io.BytesIO()
            plt.savefig(buf, format='png', facecolor=BG_COLOR, dpi=100)
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


# BTC 创世区块日期
BTC_GENESIS_DATE = datetime.date(2009, 1, 3)

# 幂律回归参数（经典拟合）
AHR999_FIT_A = 5.84
AHR999_FIT_B = -17.01


_ahr999_cache = {"data": None, "timestamp": 0}
AHR999_CACHE_TTL = 3600  # 秒


def calculate_ahr999():
    """
    计算 AHR999 指标。
    拉取 BTCUSDT 日线数据，计算 200 日定投成本、币龄拟合价格和 AHR999 值。
    
    Returns:
        dict: {
            "current": { "ahr999", "price", "cost_200d", "fitted_price", "suggestion" },
            "history": [ { "date", "ahr999", "price", "cost_200d", "fitted_price" }, ... ]
        }
        None: 计算失败时返回
    """
    try:
        now = time.time()
        if _ahr999_cache["data"] and (now - _ahr999_cache["timestamp"]) < AHR999_CACHE_TTL:
            logger.info("AHR999: 使用缓存数据")
            return _ahr999_cache["data"]
        klines = get_klines_extended("BTCUSDT", "1d", total_limit=2000)
        if not klines:
            logger.error("AHR999: 无法获取 BTC 日线数据")
            return None

        dates = []
        closes = []
        for kline in klines:
            ts = datetime.datetime.fromtimestamp(kline[0] / 1000).date()
            dates.append(ts)
            closes.append(float(kline[4]))

        df = pd.DataFrame({"date": dates, "close": closes})
        df = df.drop_duplicates(subset="date").sort_values("date").reset_index(drop=True)

        df["cost_200d"] = df["close"].rolling(window=200).mean()

        df["coin_age_days"] = df["date"].apply(lambda d: (d - BTC_GENESIS_DATE).days)

        df["fitted_price"] = df["coin_age_days"].apply(
            lambda days: 10 ** (AHR999_FIT_A * np.log10(days) + AHR999_FIT_B) if days > 0 else np.nan
        )

        df["ahr999"] = (df["close"] / df["cost_200d"]) * (df["close"] / df["fitted_price"])

        df_valid = df.dropna(subset=["ahr999"]).copy()
        if df_valid.empty:
            logger.error("AHR999: 计算结果为空（数据量不足200天）")
            return None

        latest = df_valid.iloc[-1]
        ahr999_val = float(latest["ahr999"])

        if ahr999_val < 0.45:
            suggestion = "抄底区"
        elif ahr999_val <= 1.2:
            suggestion = "定投区"
        else:
            suggestion = "观望区"

        current = {
            "ahr999": round(ahr999_val, 4),
            "price": round(float(latest["close"]), 2),
            "cost_200d": round(float(latest["cost_200d"]), 2),
            "fitted_price": round(float(latest["fitted_price"]), 2),
            "suggestion": suggestion
        }

        history = []
        for _, row in df_valid.iterrows():
            history.append({
                "date": row["date"].strftime("%Y-%m-%d"),
                "ahr999": round(float(row["ahr999"]), 4),
                "price": round(float(row["close"]), 2),
                "cost_200d": round(float(row["cost_200d"]), 2),
                "fitted_price": round(float(row["fitted_price"]), 2)
            })

        logger.info(f"AHR999 计算完成: 当前值={current['ahr999']}, 建议={suggestion}, 历史数据点={len(history)}")
        result = {"current": current, "history": history}
        _ahr999_cache["data"] = result
        _ahr999_cache["timestamp"] = time.time()
        return result

    except Exception as e:
        logger.error(f"计算 AHR999 时出错: {e}")
        return None


BGEOMETRICS_MVRV_URL = "https://bitcoin-data.com/v1/mvrv"
BGEOMETRICS_PRICE_URL = "https://bitcoin-data.com/v1/btc-price"

# MVRV 缓存：日级数据无需频繁刷新，缓存 1 小时节省 API 配额
_mvrv_cache = {"data": None, "timestamp": 0}
MVRV_CACHE_TTL = 3600  # 秒


def fetch_mvrv_data():
    """
    获取 MVRV 指标数据。
    数据源: BGeometrics (bitcoin-data.com) 免费 API，无需认证。
    
    Returns:
        dict: {
            "current": { "mvrv", "price", "status", "percentile" },
            "history": [ { "date", "mvrv", "price" }, ... ]
        }
        None: 获取失败时返回
    """
    try:
        now = time.time()
        if _mvrv_cache["data"] and (now - _mvrv_cache["timestamp"]) < MVRV_CACHE_TTL:
            logger.info("MVRV: 使用缓存数据")
            return _mvrv_cache["data"]

        mvrv_resp = requests.get(BGEOMETRICS_MVRV_URL, timeout=60)
        mvrv_resp.raise_for_status()
        mvrv_list = mvrv_resp.json()

        if not mvrv_list:
            logger.error("MVRV: BGeometrics 返回空数据")
            return None

        price_map = {}
        try:
            price_resp = requests.get(BGEOMETRICS_PRICE_URL, timeout=60)
            price_resp.raise_for_status()
            price_list = price_resp.json()
            if price_list:
                price_map = {item["d"]: float(item["btcPrice"]) for item in price_list if float(item.get("btcPrice", 0)) > 0}
        except Exception as e:
            logger.warning(f"MVRV: 价格数据获取失败，将使用币安补充: {e}")

        all_mvrv_vals = [float(item["mvrv"]) for item in mvrv_list if item.get("mvrv") is not None]

        latest = mvrv_list[-1]
        latest_mvrv = float(latest["mvrv"])
        latest_date = latest["d"]

        if latest_mvrv < 1.0:
            status_text = "低估区"
        elif latest_mvrv <= 3.0:
            status_text = "合理区"
        else:
            status_text = "高估区"

        percentile = 0
        if all_mvrv_vals:
            below_count = sum(1 for v in all_mvrv_vals if v <= latest_mvrv)
            percentile = round(below_count / len(all_mvrv_vals) * 100, 1)

        latest_price = price_map.get(latest_date)
        if latest_price is None:
            klines = get_klines("BTCUSDT", "1d", limit=1)
            if klines:
                latest_price = float(klines[-1][4])
            else:
                latest_price = 0

        current = {
            "mvrv": round(latest_mvrv, 4),
            "price": round(float(latest_price), 2),
            "status": status_text,
            "percentile": percentile
        }

        history = []
        for item in mvrv_list:
            date = item.get("d")
            mvrv_val = item.get("mvrv")
            if date and mvrv_val is not None:
                entry = {"date": date, "mvrv": round(float(mvrv_val), 4)}
                price = price_map.get(date)
                if price is not None:
                    entry["price"] = round(price, 2)
                history.append(entry)

        result = {"current": current, "history": history}

        _mvrv_cache["data"] = result
        _mvrv_cache["timestamp"] = time.time()

        logger.info(f"MVRV 数据获取完成: 当前值={current['mvrv']}, 状态={status_text}, 分位={percentile}%, 历史数据点={len(history)}")
        return result

    except Exception as e:
        logger.error(f"获取 MVRV 数据时出错: {e}")
        return None


# ==================== BTC Dominance ====================

COINGECKO_GLOBAL_URL = "https://api.coingecko.com/api/v3/global"
COINGECKO_COIN_CHART_URL = "https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart"
CRYPTOCOMPARE_HISTO_URL = "https://min-api.cryptocompare.com/data/v2/histoday"

# BTC+ETH 近似流通量（用于历史市值估算）
_BTC_SUPPLY = 19_500_000
_ETH_SUPPLY = 120_000_000

def _coingecko_headers():
    """返回 CoinGecko 请求头，有 API key 时自动携带。"""
    key = os.environ.get("COINGECKO_API_KEY", "").strip()
    if key:
        return {"x-cg-demo-api-key": key}
    logger.warning("CoinGecko: 未找到 COINGECKO_API_KEY，请求可能被拒绝（401）")
    return {}

_btcd_cache = {"data": None, "timestamp": 0}
BTCD_CACHE_TTL = 3600

# 启动时输出 key 状态（只显示前8位，保护隐私）
_cg_key_check = os.environ.get("COINGECKO_API_KEY", "").strip()
if _cg_key_check:
    logger.info(f"CoinGecko API key 已加载: {_cg_key_check[:8]}... (长度={len(_cg_key_check)})")
else:
    logger.warning("CoinGecko API key 未找到，BTC Dominance 请求将使用无密钥模式")

def _fetch_cc_prices(symbol, limit=1460):
    """从 CryptoCompare 获取历史日收盘价（免费，无需 API key，最多约 2000 天）。"""
    try:
        resp = requests.get(CRYPTOCOMPARE_HISTO_URL,
                            params={"fsym": symbol, "tsym": "USD", "limit": limit},
                            timeout=30)
        if resp.status_code == 200:
            data = resp.json().get("Data", {}).get("Data", [])
            return {
                datetime.datetime.utcfromtimestamp(item["time"]).strftime("%Y-%m-%d"): item["close"]
                for item in data if item.get("close", 0) > 0
            }
        logger.warning(f"CryptoCompare {symbol} 价格获取失败: HTTP {resp.status_code}")
    except Exception as e:
        logger.warning(f"CryptoCompare {symbol} 请求异常: {e}")
    return {}


def _fetch_coin_market_chart(coin_id, days=365):
    """获取指定币种的历史市值数据，返回 {day_key: market_cap} 字典。"""
    url = COINGECKO_COIN_CHART_URL.format(coin_id=coin_id)
    try:
        resp = requests.get(url, params={"vs_currency": "usd", "days": str(days)},
                            headers=_coingecko_headers(), timeout=60)
        if resp.status_code == 200:
            data = resp.json()
            mcap_map = {}
            for item in data.get("market_caps", []):
                day_key = datetime.datetime.utcfromtimestamp(item[0] / 1000).strftime("%Y-%m-%d")
                mcap_map[day_key] = item[1]
            logger.info(f"BTC Dominance: 获取 {coin_id} 市值历史成功, {len(mcap_map)} 天")
            return mcap_map, data.get("prices", [])
        else:
            try:
                err = resp.json()
            except Exception:
                err = resp.text[:200]
            logger.warning(f"BTC Dominance: {coin_id} 市值历史失败 HTTP {resp.status_code} | {err}")
            return {}, []
    except Exception as e:
        logger.warning(f"BTC Dominance: {coin_id} 市值历史请求异常: {e}")
        return {}, []


def fetch_btc_dominance():
    """
    获取 BTCDOM 数据（4年日线）。

    数据来源合并策略：
    - 近 365 天：CoinGecko Demo API（BTC+ETH 实际市值 → 精确 dominance）
    - 1~4 年前：CryptoCompare 免费价格数据（BTC+ETH 价格×近似供应量 → 估算 dominance）

    两段数据在 365 天边界做均值归一化，保证趋势连续。

    Returns:
        dict: {
            "current": { "dominance", "price", "status", "market_cap", "total_market_cap" },
            "history": [ { "date", "dominance", "price" }, ... ]
        }
        None: 获取失败时返回
    """
    try:
        now_ts = time.time()
        if _btcd_cache["data"] and (now_ts - _btcd_cache["timestamp"]) < BTCD_CACHE_TTL:
            logger.info("BTCDOM: 使用缓存数据")
            return _btcd_cache["data"]

        # ── 1. 当前全局数据 ────────────────────────────────────────────
        global_resp = requests.get(COINGECKO_GLOBAL_URL, headers=_coingecko_headers(), timeout=30)
        if global_resp.status_code != 200:
            try:
                err_body = global_resp.json()
            except Exception:
                err_body = global_resp.text[:200]
            logger.error(f"BTCDOM: /global 请求失败 HTTP {global_resp.status_code} | {err_body}")
            return None
        global_data = global_resp.json()["data"]
        btc_dominance = global_data["market_cap_percentage"]["btc"]
        eth_dominance = global_data["market_cap_percentage"].get("eth", 0)
        total_market_cap = global_data["total_market_cap"]["usd"]
        combined_dom = btc_dominance + eth_dominance  # ≈ 65~70%

        # ── 2. CoinGecko 近 365 天（精确市值） ────────────────────────
        btc_mcap_map, btc_prices_raw = _fetch_coin_market_chart("bitcoin", days=365)
        eth_mcap_map, _ = _fetch_coin_market_chart("ethereum", days=365)

        cg_price_map = {
            datetime.datetime.utcfromtimestamp(item[0] / 1000).strftime("%Y-%m-%d"): item[1]
            for item in btc_prices_raw
        }

        cg_dom_map = {}  # date → dominance（CoinGecko 精确值）
        for day_key in btc_mcap_map:
            btc_m = btc_mcap_map[day_key]
            if btc_m <= 0:
                continue
            eth_m = eth_mcap_map.get(day_key, 0)
            if eth_m > 0 and combined_dom > 0:
                total_est = (btc_m + eth_m) / (combined_dom / 100)
            elif btc_dominance > 0:
                total_est = btc_m / (btc_dominance / 100)
            else:
                continue
            cg_dom_map[day_key] = round((btc_m / total_est) * 100, 2)

        if not cg_dom_map:
            logger.error("BTCDOM: CoinGecko 无法获取市值数据")
            return None

        # ── 3. CryptoCompare 4 年历史价格（免费估算） ──────────────────
        cc_btc = _fetch_cc_prices("BTC", limit=1460)
        cc_eth = _fetch_cc_prices("ETH", limit=1460)

        cc_dom_map = {}  # date → dominance（估算值）
        for day_key, btc_p in cc_btc.items():
            eth_p = cc_eth.get(day_key, 0)
            if btc_p <= 0:
                continue
            btc_m = btc_p * _BTC_SUPPLY
            eth_m = eth_p * _ETH_SUPPLY if eth_p > 0 else 0
            if eth_m > 0 and combined_dom > 0:
                total_est = (btc_m + eth_m) / (combined_dom / 100)
            elif btc_dominance > 0:
                total_est = btc_m / (btc_dominance / 100)
            else:
                continue
            cc_dom_map[day_key] = round((btc_m / total_est) * 100, 2)

        # ── 4. 归一化：用重叠期均值修正 CC 偏差 ───────────────────────
        overlap = sorted(set(cg_dom_map) & set(cc_dom_map))
        if len(overlap) >= 7:
            cg_avg = sum(cg_dom_map[d] for d in overlap) / len(overlap)
            cc_avg = sum(cc_dom_map[d] for d in overlap) / len(overlap)
            bias = cg_avg - cc_avg  # CC 系统性偏差修正量
        else:
            bias = 0.0

        # ── 5. 合并数据：CC 填历史，CG 覆盖近期 ─────────────────────
        all_dates = sorted(set(cc_dom_map) | set(cg_dom_map))
        history = []
        for day_key in all_dates:
            if day_key in cg_dom_map:
                dom = cg_dom_map[day_key]
            elif day_key in cc_dom_map:
                dom = round(cc_dom_map[day_key] + bias, 2)
            else:
                continue
            entry = {"date": day_key, "dominance": dom}
            price = cg_price_map.get(day_key) or cc_btc.get(day_key)
            if price:
                entry["price"] = round(price, 2)
            history.append(entry)

        if not history:
            logger.error("BTCDOM: 合并后数据为空")
            return None

        # 最后一条修正为实时值
        history[-1]["dominance"] = round(btc_dominance, 2)

        if btc_dominance > 60:
            status_text = "BTC主导"
        elif btc_dominance >= 40:
            status_text = "均衡"
        else:
            status_text = "山寨季"

        latest_price = history[-1].get("price", 0)
        current = {
            "dominance": round(btc_dominance, 2),
            "price": round(latest_price, 2),
            "status": status_text,
            "market_cap": round(total_market_cap * btc_dominance / 100, 0),
            "total_market_cap": round(total_market_cap, 0)
        }

        result = {"current": current, "history": history}
        _btcd_cache["data"] = result
        _btcd_cache["timestamp"] = time.time()

        dom_vals = [h["dominance"] for h in history]
        logger.info(
            f"BTCDOM 获取完成: 当前={current['dominance']}%, "
            f"历史范围={min(dom_vals):.2f}%~{max(dom_vals):.2f}%, "
            f"数据点={len(history)} (CC偏差修正={bias:+.2f}%)"
        )
        return result

    except Exception as e:
        logger.error(f"获取 BTCDOM 数据时出错: {e}")
        return None