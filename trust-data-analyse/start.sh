#!/bin/bash
# 信托行业科技建设数据分析智能体启动脚本

cd /workspace

# 检查环境变量
if [ -z "$DASHSCOPE_API_KEY" ]; then
    echo "警告: DASHSCOPE_API_KEY 未设置，Agent功能可能无法正常工作"
    echo "请设置: export DASHSCOPE_API_KEY=your_api_key"
fi

# 检查数据库
if [ ! -f "trust-survey-sql-expert/trust_survey.db" ]; then
    echo "错误: 数据库文件不存在"
    exit 1
fi

# 检查公司数量
COMPANY_COUNT=$(sqlite3 trust-survey-sql-expert/trust_survey.db "SELECT COUNT(*) FROM survey_data")
echo "数据库包含 $COMPANY_COUNT 家信托公司"

# 启动服务
echo "启动服务..."
python app.py