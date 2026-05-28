# -*- coding: utf-8 -*-
"""测试图表生成功能"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agent import generate_analysis_chart, make_bar_chart

# 测试make_bar_chart
print("测试make_bar_chart...")
labels = ['公司A', '公司B', '公司C', '公司D', '公司E']
values = [100, 80, 120, 95, 110]
result = make_bar_chart(labels, values, '测试图表', horizontal=True)
print(f"图表生成结果: {result[:50]}...")
print(f"是否为base64格式: {result.startswith('data:image/png;base64,')}")

# 测试generate_analysis_chart
print("\n测试generate_analysis_chart...")
import json
data_desc = json.dumps({
    'labels': ['公司A', '公司B', '公司C', '公司D', '公司E'],
    'values': [100, 80, 120, 95, 110],
    'title': '测试图表'
})
result2 = generate_analysis_chart('bar', data_desc)
print(f"图表生成结果: {result2[:50]}...")
print(f"是否为base64格式: {result2.startswith('data:image/png;base64,')}")

print("\n图表生成功能测试完成！")
