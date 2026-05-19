# -*- coding: utf-8 -*-
"""
智能卡片API扩展模块
为app.py添加智能卡片相关的API路由
"""
from flask import Blueprint, request, jsonify
import asyncio

# 导入智能卡片管理器
from smart_card_manager import get_card_manager

# 创建蓝图
smart_cards_bp = Blueprint('smart_cards', __name__, url_prefix='/api')

# 获取卡片管理器
card_manager = get_card_manager()

# 导入Agent响应函数（需要在主app中定义）
from agent import get_agent_response


# ========== 卡片配置API ==========

@smart_cards_bp.route('/cards', methods=['GET'])
def get_cards():
    """获取所有卡片配置"""
    return jsonify({
        'preset_cards': card_manager.get_preset_cards(),
        'custom_cards': card_manager.get_custom_cards(),
        'quick_questions': card_manager.get_quick_questions()
    })


@smart_cards_bp.route('/cards/preset', methods=['GET'])
def get_preset_cards():
    """获取预制卡片"""
    return jsonify({'cards': card_manager.get_preset_cards()})


@smart_cards_bp.route('/cards/custom', methods=['GET'])
def get_custom_cards():
    """获取自定义卡片"""
    return jsonify({'cards': card_manager.get_custom_cards()})


@smart_cards_bp.route('/cards/custom', methods=['POST'])
def add_custom_card():
    """添加自定义卡片"""
    data = request.json
    title = data.get('title', '').strip()
    query = data.get('query', '').strip()
    description = data.get('description', '')
    icon = data.get('icon', '📋')
    tags = data.get('tags', [])
    
    if not title or not query:
        return jsonify({'error': '标题和查询内容不能为空'}), 400
    
    card = card_manager.add_custom_card(
        title=title,
        query=query,
        description=description,
        icon=icon,
        tags=tags
    )
    return jsonify({'success': True, 'card': card})


@smart_cards_bp.route('/cards/custom/<card_id>', methods=['PUT'])
def update_custom_card(card_id):
    """更新自定义卡片"""
    data = request.json
    card = card_manager.update_custom_card(card_id, **data)
    if card:
        return jsonify({'success': True, 'card': card})
    return jsonify({'error': '卡片不存在'}), 404


@smart_cards_bp.route('/cards/custom/<card_id>', methods=['DELETE'])
def delete_custom_card(card_id):
    """删除自定义卡片"""
    if card_manager.delete_custom_card(card_id):
        return jsonify({'success': True})
    return jsonify({'error': '卡片不存在'}), 404


# ========== 快捷提问API ==========

@smart_cards_bp.route('/quick-questions', methods=['GET'])
def get_quick_questions():
    """获取快捷提问列表"""
    return jsonify({'questions': card_manager.get_quick_questions()})


@smart_cards_bp.route('/quick-questions', methods=['POST'])
def add_quick_question():
    """添加快捷提问"""
    data = request.json
    text = data.get('text', '').strip()
    icon = data.get('icon', '💬')
    
    if not text:
        return jsonify({'error': '问题内容不能为空'}), 400
    
    question = card_manager.add_quick_question(text, icon)
    return jsonify({'success': True, 'question': question})


@smart_cards_bp.route('/quick-questions/<question_id>', methods=['DELETE'])
def delete_quick_question(question_id):
    """删除快捷提问"""
    if card_manager.delete_quick_question(question_id):
        return jsonify({'success': True})
    return jsonify({'error': '问题不存在'}), 404


# ========== 智能分析API ==========

@smart_cards_bp.route('/cards/<card_id>/analyze', methods=['POST'])
def analyze_card(card_id):
    """
    分析卡片内容
    如果缓存存在则返回缓存，否则调用Agent生成
    """
    # 查找卡片
    card = None
    for c in card_manager.get_all_cards():
        if c['id'] == card_id:
            card = c
            break
    
    if not card:
        return jsonify({'error': '卡片不存在'}), 404
    
    query = card['query']
    
    # 检查是否有强制刷新参数
    force_refresh = request.json.get('force_refresh', False)
    
    # 尝试获取缓存
    if not force_refresh:
        cached = card_manager.get_cached_response(query, card_id)
        if cached:
            return jsonify({
                'success': True,
                'result': cached['result'],
                'charts': cached['charts'],
                'cached': True,
                'cached_at': cached['cached_at'],
                'card_id': card_id,
                'card_title': card['title']
            })
    
    # 调用Agent生成响应
    try:
        response = asyncio.run(get_agent_response(query, f"card_{card_id}"))
        
        # 缓存响应
        card_manager.cache_response(
            query=query,
            result=response,
            charts=[],
            card_id=card_id
        )
        
        return jsonify({
            'success': True,
            'result': response,
            'charts': [],
            'cached': False,
            'card_id': card_id,
            'card_title': card['title']
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@smart_cards_bp.route('/cards/<card_id>/regenerate', methods=['POST'])
def regenerate_card(card_id):
    """重新生成卡片分析（强制刷新缓存）"""
    def agent_func(query):
        return asyncio.run(get_agent_response(query, f"card_{card_id}_regen"))
    
    result = card_manager.regenerate_card_response(card_id, agent_func)
    
    if result is None:
        return jsonify({'error': '卡片不存在'}), 404
    
    if 'error' in result:
        return jsonify({'error': result['error']}), 500
    
    return jsonify({
        'success': True,
        'result': result['result'],
        'charts': result['charts'],
        'cached': False,
        'card_id': card_id
    })


@smart_cards_bp.route('/quick-questions/<question_id>/analyze', methods=['POST'])
def analyze_quick_question(question_id):
    """分析快捷提问"""
    # 查找问题
    question = None
    for q in card_manager.get_quick_questions():
        if q['id'] == question_id:
            question = q
            break
    
    if not question:
        return jsonify({'error': '问题不存在'}), 404
    
    query = question['text']
    
    # 检查缓存
    cached = card_manager.get_cached_response(query, question_id)
    if cached:
        return jsonify({
            'success': True,
            'result': cached['result'],
            'charts': cached['charts'],
            'cached': True,
            'cached_at': cached['cached_at'],
            'question_id': question_id
        })
    
    # 调用Agent
    try:
        response = asyncio.run(get_agent_response(query, f"qq_{question_id}"))
        
        # 缓存
        card_manager.cache_response(
            query=query,
            result=response,
            charts=[],
            card_id=question_id
        )
        
        return jsonify({
            'success': True,
            'result': response,
            'charts': [],
            'cached': False,
            'question_id': question_id
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ========== 缓存管理API ==========

@smart_cards_bp.route('/cache/stats', methods=['GET'])
def get_cache_stats():
    """获取缓存统计"""
    return jsonify(card_manager.get_cache_stats())


@smart_cards_bp.route('/cache/clear', methods=['POST'])
def clear_cache():
    """清除缓存"""
    data = request.json or {}
    card_id = data.get('card_id')
    
    if card_id:
        card_manager.clear_card_cache(card_id)
        return jsonify({'success': True, 'message': f'已清除卡片 {card_id} 的缓存'})
    else:
        card_manager.clear_all_cache()
        return jsonify({'success': True, 'message': '已清除所有缓存'})


# ========== 批量初始化API ==========

@smart_cards_bp.route('/cards/init-cache', methods=['POST'])
def init_cards_cache():
    """
    批量初始化所有卡片的缓存
    用于首次部署时预生成所有卡片分析
    """
    results = []
    errors = []
    
    # 获取所有卡片
    all_cards = card_manager.get_all_cards()
    
    for card in all_cards:
        try:
            query = card['query']
            card_id = card['id']
            
            # 检查是否已有缓存
            if card_manager.get_cached_response(query, card_id):
                results.append({
                    'card_id': card_id,
                    'title': card['title'],
                    'status': 'skipped',
                    'message': '已有缓存'
                })
                continue
            
            # 调用Agent
            response = asyncio.run(get_agent_response(query, f"card_{card_id}"))
            
            # 缓存
            card_manager.cache_response(
                query=query,
                result=response,
                charts=[],
                card_id=card_id
            )
            
            results.append({
                'card_id': card_id,
                'title': card['title'],
                'status': 'success'
            })
        except Exception as e:
            errors.append({
                'card_id': card['id'],
                'title': card['title'],
                'error': str(e)
            })
    
    return jsonify({
        'success': True,
        'total': len(all_cards),
        'successful': len([r for r in results if r['status'] == 'success']),
        'skipped': len([r for r in results if r['status'] == 'skipped']),
        'failed': len(errors),
        'results': results,
        'errors': errors
    })


# 用于在主app中注册蓝图的函数
def register_smart_cards_blueprint(app):
    """注册智能卡片蓝图到Flask应用"""
    app.register_blueprint(smart_cards_bp)
    print("✅ 智能卡片API已注册")
