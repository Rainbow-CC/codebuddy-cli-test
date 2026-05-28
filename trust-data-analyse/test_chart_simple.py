# -*- coding: utf-8 -*-
"""简单测试图表生成"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import asyncio
from agent import get_agent_response, analyze_ranking_for_chart

# 测试1: 直接调用analyze_ranking_for_chart
print("测试1: 直接调用analyze_ranking_for_chart")
print("="*50)
result = analyze_ranking_for_chart("科技投入排名TOP10")
print(f"排名数据: {result['ranking'][:3]}...")
print(f"图表数据是否存在: {result['chart_data'] is not None}")
print(f"图表数据长度: {len(result['chart_data']) if result['chart_data'] else 0}")
print(f"是否为base64格式: {result['chart_data'].startswith('data:image/png;base64,') if result['chart_data'] else False}")

# 测试2: 通过Agent调用
print("\n\n测试2: 通过Agent调用")
print("="*50)
async def test():
    response = await get_agent_response("科技投入排名TOP10", "test_user")
    print(f"响应内容长度: {len(response.get('content', ''))}")
    print(f"图表数量: {len(response.get('charts', []))}")
    
    if response.get('charts'):
        for i, chart in enumerate(response['charts']):
            print(f"\n图表{i+1}:")
            print(f"  格式检查: {chart[:50]}...")
            print(f"  是否为base64: {chart.startswith('data:image/png;base64,')}")
    
    # 打印响应内容
    content = response.get('content', '')
    print(f"\n响应内容摘要: {content[:300]}...")

asyncio.run(test())
