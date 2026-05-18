import os
from langchain_openai import ChatOpenAI
from langchain.agents import create_agent
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import MemorySaver
from agent_tools import query_survey_db, get_survey_metadata, get_db_schema
from pathlib import Path

def load_skill_instructions(skill_path: str):
    """加载指定的 Skill 指令"""
    try:
        with open(os.path.join(skill_path, "SKILL.md"), "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        print(f"警告: 无法读取技能文件: {e}")
        return ""

def create_survey_agent():
    # 1. 基础配置
    llm = ChatOpenAI(
        model="qwen-plus", # 或者用户指定的模型
        api_key=os.getenv("DASHSCOPE_API_KEY"),
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        temperature=0
    )

    # 2. 加载 Trust Survey SQL Expert 技能
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    skill_path = os.path.join(BASE_DIR, "..", "trust-survey-sql-expert")
    skill_instructions = load_skill_instructions(skill_path)

    system_prompt = f"""你是一个专业的信托行业调研数据分析专家。
    你可以使用 SQL 工具来查询 trust_survey.db 数据库中的数据。

    以下是你的核心技能指令：
    {skill_instructions}

    重要：在执行任何针对 survey_data 表的 SQL 查询之前，请务必先使用 get_survey_metadata 查找正确的字段名。
    """

    # 3. 准备工具
    tools = [query_survey_db, get_survey_metadata, get_db_schema]

    # 4. 创建带状态管理的 Agent
    memory = MemorySaver()
    agent = create_agent(
        llm, 
        tools=tools, 
        checkpointer=memory,
        system_prompt=system_prompt
    )
    
    return agent

# 单例模式或全局变量
_agent = None

async def get_agent_response(query: str, thread_id: str = "default_user"):
    global _agent
    if _agent is None:
        _agent = create_survey_agent()
    
    config = {"configurable": {"thread_id": thread_id}}
    input_data = {"messages": [HumanMessage(content=query)]}
    
    response_content = ""
    async for event in _agent.astream(input_data, config, stream_mode="values"):
        last_msg = event["messages"][-1]
        
        # 过滤掉用户自己的消息，并获取 AI 的最后一条文本回复
        if hasattr(last_msg, "content") and last_msg.content and last_msg.type == "ai":
            response_content = last_msg.content
            
    return response_content
