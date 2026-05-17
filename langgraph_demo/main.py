import asyncio
import os
import sys

# 将当前目录添加到路径中，确保在某些调试环境下也能找到本地模块
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.checkpoint.memory import MemorySaver
from langchain.agents import create_agent

# 导入本地定义的工具和加载器
from agent_tools import query_academic_sqlite, get_database_schema
from skills_loader import load_local_skills

async def main():
    # 1. 基础配置 (使用 Tongyi 的 OpenAI 兼容模式)
    # 提示：请确保环境变量 DASHSCOPE_API_KEY 已设置
    llm = ChatOpenAI(
        model="qwen3.6-flash", 
        api_key=os.getenv("DASHSCOPE_API_KEY"),
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        temperature=0
    )

    # 2. 动态加载本地 Skills 指令 (模拟 CodeBuddy 行为)
    # 扫描父目录中的技能文件夹
    parent_dir = os.path.join(os.path.dirname(__file__), "..")
    skill_instructions = load_local_skills(parent_dir)

    system_prompt = f"""你是一个高级代码和研究助理，
    你可以使用多种工具来完成任务。

    以下是已加载的本地技能指令：
    {skill_instructions}

    当用户询问学术相关问题时，请务必先调用 get_database_schema 工具。
    """

    # 3. 准备工具
    tools = [query_academic_sqlite, get_database_schema]

    # 4. 创建带状态管理的 Agent
    memory = MemorySaver()
    agent_executor = create_agent(
        llm, 
        tools=tools, 
        checkpointer=memory,
        system_prompt=system_prompt
    )

    print("--- LangGraph Agent  已启动 ---")
    print("输入 'exit' 退出对话。\n")
    
    config = {"configurable": {"thread_id": "user_session_001"}}

    while True:
        try:
            user_input = input("用户: ").strip()
            if not user_input:
                continue
            if user_input.lower() in ["exit", "quit"]:
                break

            # 5. 流式输出处理
            input_data = {"messages": [HumanMessage(content=user_input)]}
            
            async for event in agent_executor.astream(input_data, config, stream_mode="values"):
                last_msg = event["messages"][-1]
                
                # 过滤掉用户自己的消息
                if isinstance(last_msg, HumanMessage):
                    continue
                
                # 打印工具调用详情 (类似 SDK 的 ToolUseBlock)
                if hasattr(last_msg, 'tool_calls') and last_msg.tool_calls:
                    for tc in last_msg.tool_calls:
                        print(f"[工具调用]: {tc['name']} -> {tc['args']}")
                
                # 打印文本回复
                elif last_msg.content:
                    print(f"\nAI: {last_msg.content}\n")
                    
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"发生错误: {e}")

if __name__ == "__main__":
    asyncio.run(main())
