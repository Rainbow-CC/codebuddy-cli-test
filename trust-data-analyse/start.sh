#!/bin/bash
# 信托行业科技建设数据分析智能体 - 启动脚本
# 使用方法: bash start.sh

echo "======================================"
echo "  信托行业科技建设数据分析智能体"
echo "  基于65家信托公司调研数据"
echo "======================================"
echo ""

cd "$(dirname "$0")"

# 检查依赖
python3 -c "import flask, pandas, matplotlib, numpy" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "正在安装依赖..."
    pip install flask flask-cors pandas matplotlib numpy --break-system-packages --quiet
fi

# 启动服务
echo "启动数据分析服务..."
echo "请在浏览器中打开: http://localhost:5000"
echo ""
python3 app.py
