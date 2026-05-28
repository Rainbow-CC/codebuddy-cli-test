# -*- coding: utf-8 -*-
"""测试Agent图表生成完整流程"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import asyncio
from agent import get_agent_response

# 测试问题，应该触发图表生成
test_queries = [
    "科技投入排名TOP10",
    "综合排名TOP10",
    "画出科技投入排名图表",
    "显示排名前5的公司"
]

async def test_chart_flow():
    for query in test_queries:
        print(f"\n{'='*60}")
        print(f"测试问题: {query}")
        print(f"{'='*60}")
        
        try:
            response = await get_agent_response(query, "test_user")
            print(f"响应内容长度: {len(response.get('content', ''))}")
            print(f"图表数量: {len(response.get('charts', []))}")
            
            if response.get('charts'):
                for i, chart in enumerate(response['charts']):
                    print(f"图表{i+1}格式: {chart[:50]}...")
                    print(f"是否为base64: {chart.startswith('data:image/png;base64,')}")
            else:
                print("未生成图表")
                
            # 打印部分响应内容
            content = response.get('content', '')
            if len(content) > 200:
                print(f"\n响应摘要: {content[:200]}...")
            else:
                print(f"\n响应内容: {content}")
                
        except Exception as e:
            print(f"错误: {str(e)}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_chart_flow())
