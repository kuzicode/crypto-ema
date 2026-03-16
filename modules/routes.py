from flask import render_template, jsonify, request
import logging
import math
import concurrent.futures
from datetime import datetime, timedelta
from modules.trading_analysis import KlineBot, token_trend, calculate_ahr999, fetch_mvrv_data, fetch_btc_dominance

logger = logging.getLogger(__name__)

# 存储活跃的交易机器人实例
active_bots = {}

def init_routes(app):
    """初始化所有路由"""
    
    @app.route('/')
    def index():
        """渲染主页"""
        return render_template('layout.html')
        
    @app.route('/get_chart', methods=['POST'])
    def get_chart():
        """获取图表数据"""
        try:
            # 从表单数据中获取参数，而不是JSON
            symbol = request.form.get('symbol', 'BTC').upper().strip()
            if not symbol.endswith('USDT'):
                symbol = symbol + 'USDT'
            
            interval = request.form.get('interval', '4h')  # 默认使用4小时
            
            # 生成唯一键
            bot_key = f"{symbol}_{interval}"
            
            # 强制重新创建bot实例，确保每次获取最新数据
            bot = KlineBot(symbol, interval)
            active_bots[bot_key] = bot
            
            if bot.indicators.empty:
                return jsonify({'success': False, 'error': '无法获取数据'})

            # 获取市场分析
            market_analysis = bot.generate_market_analysis()

            # 获取当前最新价格和MA线值
            latest = bot.indicators.iloc[-1]
            market_info = {
                "price": float(latest['Close']),
                "ma2": float(latest['MA2']),
                "ma3": float(latest['MA3']),
                "ma4": float(latest['MA4']),
                "ma5": float(latest['MA5']),
                "ma6": float(latest['MA6'])
            }

            # 构建交互式图表数据
            chart_data = []
            for _, row in bot.indicators.iterrows():
                if math.isnan(row.get('MA6', float('nan'))):
                    continue
                chart_data.append({
                    'time': int(row['Time']),
                    'close': float(row['Close']),
                    'ma2': float(row['MA2']),
                    'ma3': float(row['MA3']),
                    'ma4': float(row['MA4']),
                    'ma5': float(row['MA5']),
                    'ma6': float(row['MA6']),
                    'macd': float(row['MACD']),
                    'signal': float(row['Signal Line']),
                    'hist': float(row['MACD Histogram'])
                })

            # 添加当前服务器时间(北京时间)
            current_time = (datetime.utcnow() + timedelta(hours=8)).strftime('%Y-%m-%d %H:%M:%S')

            logger.info(f"获取了 {symbol} 的最新数据，时间: {current_time}，共 {len(chart_data)} 条")

            return jsonify({
                'success': True,
                'chart_data': chart_data,
                'market_info': market_info,
                'analysis': market_analysis,
                'timestamp': current_time
            })
        except Exception as e:
            logger.error(f"获取图表时出错: {e}")
            return jsonify({'success': False, 'error': str(e)})
    
    @app.route('/get_market_trends', methods=['POST'])
    def get_market_trends():
        """获取盘面趋势"""
        try:
            # 获取请求数据
            data = request.json
            symbols = data.get('symbols', [])
            interval = data.get('interval', '4h')  # 默认使用4小时周期
            
            # 确保所有币种都以USDT结尾
            symbols = [symbol.upper() + 'USDT' if not symbol.upper().endswith('USDT') else symbol.upper() for symbol in symbols]
            
            logger.info(f"获取多币种趋势: {symbols}, 周期: {interval}")
            
            # 定义趋势分类
            trends = {
                'above_ma4': [],    # 突破强势线（深绿）
                'above_ma3': [],    # 突破上涨线（浅绿）
                'between_ma2_ma3': [],  # 盘整区上行
                'between_ma5_ma2': [],  # 盘整区下行
                'below_ma5': [],    # 跌破下跌线（浅红）
                'below_ma6': []     # 跌破超跌线（深红）
            }
            
            # 使用线程池并行获取数据
            with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                # 提交任务到线程池并保存 Future 对象
                future_to_symbol = {executor.submit(token_trend, symbol, interval): symbol.replace('USDT', '') for symbol in symbols}
                
                # 处理结果
                for future in concurrent.futures.as_completed(future_to_symbol):
                    symbol = future_to_symbol[future]
                    try:
                        result = future.result()
                        if result:
                            # 根据结果将币种放入相应的趋势类别
                            category = result['token_trend']
                            if category in trends:
                                trends[category].append(symbol)
                    except Exception as e:
                        logger.error(f"处理 {symbol} 趋势时出错: {e}")
            
            return jsonify({
                'success': True,
                'trends': trends
            })
        except Exception as e:
            logger.error(f"获取盘面趋势时出错: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            })
            
    @app.route('/get_dashboard', methods=['GET'])
    def get_dashboard():
        """获取仪表盘摘要数据"""
        result = {}
        try:
            ahr = calculate_ahr999()
            result['ahr999'] = ahr['current'] if ahr else None
        except Exception as e:
            logger.error(f"Dashboard 获取 AHR999 出错: {e}")
            result['ahr999'] = None
        try:
            mvrv = fetch_mvrv_data()
            result['mvrv'] = mvrv['current'] if mvrv else None
        except Exception as e:
            logger.error(f"Dashboard 获取 MVRV 出错: {e}")
            result['mvrv'] = None
        try:
            btcd = fetch_btc_dominance()
            result['btc_dominance'] = btcd['current'] if btcd else None
        except Exception as e:
            logger.error(f"Dashboard 获取 BTC Dominance 出错: {e}")
            result['btc_dominance'] = None
        return jsonify({'success': True, **result})

    @app.route('/get_ahr999', methods=['GET'])
    def get_ahr999():
        """获取 AHR999 指标数据"""
        try:
            result = calculate_ahr999()
            if result is None:
                return jsonify({'success': False, 'error': '无法计算 AHR999 指标'})
            
            return jsonify({
                'success': True,
                'current': result['current'],
                'history': result['history']
            })
        except Exception as e:
            logger.error(f"获取 AHR999 数据时出错: {e}")
            return jsonify({'success': False, 'error': str(e)})
    
    @app.route('/get_mvrv', methods=['GET'])
    def get_mvrv():
        """获取 MVRV 指标数据"""
        try:
            result = fetch_mvrv_data()
            if result is None:
                return jsonify({'success': False, 'error': '无法获取 MVRV 指标数据'})
            
            return jsonify({
                'success': True,
                'current': result['current'],
                'history': result['history']
            })
        except Exception as e:
            logger.error(f"获取 MVRV 数据时出错: {e}")
            return jsonify({'success': False, 'error': str(e)})
    
    @app.route('/get_btc_dominance', methods=['GET'])
    def get_btc_dominance_route():
        """获取 BTC Dominance 指标数据"""
        try:
            result = fetch_btc_dominance()
            if result is None:
                return jsonify({'success': False, 'error': '无法获取 BTC Dominance 数据'})
            return jsonify({
                'success': True,
                'current': result['current'],
                'history': result['history']
            })
        except Exception as e:
            logger.error(f"获取 BTC Dominance 数据时出错: {e}")
            return jsonify({'success': False, 'error': str(e)})

    @app.route('/get_price_alerts', methods=['GET'])
    def get_price_alerts():
        """获取币价变动提醒记录（从 telegram_alert.json 读取）"""
        try:
            import os
            import json
            
            # 定义JSON文件路径（改用 telegram_alert.json）
            json_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'telegram_alert.json')
            
            # 检查文件是否存在
            if not os.path.exists(json_file):
                logger.warning(f"提醒记录文件不存在: {json_file}")
                return jsonify({
                    'success': True,
                    'alerts': []
                })
            
            # 读取JSON文件内容
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    alerts = json.load(f)
                    
                logger.info(f"成功加载提醒记录，共 {len(alerts)} 条")
                return jsonify({
                    'success': True,
                    'alerts': alerts
                })
            except json.JSONDecodeError as e:
                logger.error(f"JSON解析错误: {e}")
                return jsonify({
                    'success': False,
                    'error': f"无法解析JSON文件: {str(e)}"
                })
            except Exception as e:
                logger.error(f"读取文件时出错: {e}")
                return jsonify({
                    'success': False,
                    'error': f"读取文件时出错: {str(e)}"
                })
        except Exception as e:
            logger.error(f"获取币价提醒记录时出错: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            })
            
    return app 