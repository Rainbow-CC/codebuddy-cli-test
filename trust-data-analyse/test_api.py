# -*- coding: utf-8 -*-
"""测试API接口"""
import requests
import json

url = "http://127.0.0.1:5000/api/chat-agent"

data = {
    "query": "科技投入排名TOP10",
    "thread_id": "test_user"
}

print("发送请求到:", url)
print("请求数据:", data)
print()

try:
    response = requests.post(url, json=data)
    print(f"响应状态码: {response.status_code}")
    
    if response.status_code == 200:
        result = response.json()
        print(f"\n响应键: {list(result.keys())}")
        print(f"结果长度: {len(result.get('result', ''))}")
        print(f"图表数量: {len(result.get('charts', []))}")
        
        if result.get('charts'):
            for i, chart in enumerate(result['charts']):
                print(f"\n图表{i+1}:")
                print(f"  长度: {len(chart)}")
                print(f"  是否为base64: {chart.startswith('data:image/png;base64,')}")
                
        # 打印部分结果
        content = result.get('result', '')
        if content:
            print(f"\n结果摘要: {content[:300]}...")
    else:
        print(f"错误: {response.text}")
        
except Exception as e:
    print(f"请求失败: {str(e)}")
