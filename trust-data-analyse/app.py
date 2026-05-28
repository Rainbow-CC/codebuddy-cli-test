# -*- coding: utf-8 -*-
"""
信托行业科技建设数据分析智能体 - 主应用
"""
import os
import sys
import asyncio
import json
import re
import threading

# 设置路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask, request, jsonify, Response, stream_with_context, send_from_directory
from flask_cors import CORS
import logging

# 导入Agent模块
from agent import (
    get_agent_response,
    get_agent_streaming_response,
    get_stats_overview,
    get_raw_data,
    get_companies_list,
    get_fields_list,
    get_company_field_value,
    get_suggestions
)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

# 创建Flask应用
static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
app = Flask(__name__, static_folder=static_dir, static_url_path='')

# CORS配置
cors_origins = [
    origin.strip()
    for origin in os.getenv(
        "TRUST_DATA_CORS_ORIGINS",
        "http://127.0.0.1:5000,http://localhost:5000"
    ).split(",")
    if origin.strip()
]
CORS(app, resources={r"/api/*": {"origins": cors_origins}})

# 线程锁
_analysis_lock = threading.RLock()

def _clean_thread_id(thread_id):
    """清理线程ID"""
    thread_id = str(thread_id or 'user_default')
    cleaned = re.sub(r'[^A-Za-z0-9_.:-]', '_', thread_id)[:120]
    return cleaned or 'user_default'

# ========== 静态文件路由 ==========

@app.route('/')
def index():
    """主页"""
    return send_from_directory(static_dir, 'index.html')

@app.route('/<path:path>')
def static_files(path):
    """静态文件"""
    return send_from_directory(static_dir, path)

# ========== Agent聊天API ==========

@app.route('/api/chat-agent', methods=['POST'])
def chat_agent():
    """Agent问答接口（阻塞式）"""
    data = request.get_json(silent=True) or {}
    query = str(data.get('query', ''))
    thread_id = _clean_thread_id(data.get('thread_id', 'user_default'))
    
    if len(query) > 2000:
        return jsonify({'error': '问题长度不能超过2000字符'}), 400
    
    if not query.strip():
        return jsonify({'error': '请输入问题'}), 400
    
    try:
        response = asyncio.run(get_agent_response(query, thread_id))
        return jsonify({'result': response, 'charts': []})
    except Exception as e:
        logging.error(f"Agent响应错误: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/chat-agent/stream', methods=['POST'])
def chat_agent_stream():
    """Agent问答接口（流式SSE）"""
    data = request.get_json(silent=True) or {}
    query = str(data.get('query', ''))
    thread_id = _clean_thread_id(data.get('thread_id', 'user_default'))
    
    if len(query) > 2000:
        return jsonify({'error': '问题长度不能超过2000字符'}), 400
    
    if not query.strip():
        return jsonify({'error': '请输入问题'}), 400
    
    def generate():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        gen = get_agent_streaming_response(query, thread_id)
        try:
            while True:
                try:
                    chunk = loop.run_until_complete(gen.__anext__())
                    if chunk:
                        yield f"data: {json.dumps({'content': chunk})}\n\n"
                except StopAsyncIteration:
                    break
                except Exception as e:
                    yield f"data: {json.dumps({'error': str(e)})}\n\n"
                    break
        finally:
            loop.close()
    
    return Response(stream_with_context(generate()), mimetype='text/event-stream')

# ========== 数据统计API ==========

@app.route('/api/stats/overview', methods=['GET'])
def stats_overview():
    """获取统计概览"""
    return jsonify(get_stats_overview())

@app.route('/api/raw-data', methods=['GET'])
def raw_data():
    """获取原始数据"""
    return jsonify(get_raw_data())

@app.route('/api/companies', methods=['GET'])
def companies_list():
    """获取公司列表"""
    return jsonify(get_companies_list())

@app.route('/api/fields', methods=['GET'])
def fields_list():
    """获取字段列表"""
    return jsonify(get_fields_list())

@app.route('/api/company/field', methods=['GET'])
def company_field():
    """获取指定公司的指定字段值"""
    company = request.args.get('company', '')
    field = request.args.get('field', '')
    return jsonify(get_company_field_value(company, field))

@app.route('/api/suggestions', methods=['GET'])
def suggestions():
    """获取快捷提问建议"""
    return jsonify(get_suggestions())

# ========== 启动配置 ==========

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    debug = os.getenv('FLASK_DEBUG', 'false').lower() == 'true'
    
    print(f"信托行业科技建设数据分析智能体启动...")
    print(f"端口: {port}")
    print(f"调试模式: {debug}")
    print(f"数据库: 61家信托公司")
    
    app.run(host='0.0.0.0', port=port, debug=debug, threaded=True)