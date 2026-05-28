# -*- coding: utf-8 -*-
"""调试图表生成"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import asyncio
from agent import get_agent_response

async def test():
    print("="*60)
    print("测试: 科技投入排名TOP10")
    print("="*60)
    
    response = await get_agent_response("科技投入排名TOP10", "test_user")
    
    print(f"\n--- 响应分析 ---")
    print(f"响应类型: {type(response)}")
    print(f"响应键: {list(response.keys())}")
    
    content = response.get('content', '')
    charts = response.get('charts', [])
    
    print(f"\n内容长度: {len(content)}")
    print(f"图表数量: {len(charts)}")
    
    if content:
        print(f"\n内容摘要: {content[:400]}...")
    
    if charts:
        print(f"\n--- 图表数据 ---")
        for i, chart in enumerate(charts):
            print(f"\n图表{i+1}:")
            print(f"  类型: {type(chart)}")
            print(f"  长度: {len(chart)}")
            print(f"  格式检查: {chart[:50]}...")
            print(f"  是否为base64图片: {chart.startswith('data:image/png;base64,')}")

asyncio.run(test())
