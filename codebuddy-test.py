import asyncio
import os
from codebuddy_agent_sdk import (
    CodeBuddySDKClient,
    CodeBuddyAgentOptions,
    SystemMessage,
    AssistantMessage,
    ResultMessage,
    TextBlock,
    ToolUseBlock,
    ToolResultBlock
)


async def handle_messages(client):
    """
    流式接收并解析当前轮次 Agent 返回的消息
    """
    async for message in client.receive_response():
        if isinstance(message, SystemMessage):
            print(f"[系统] 会话初始化成功，会话 ID: {message.data.get('session_id')}")
            print(f"[系统] 可用工具列表: {message.data.get('tools')}")

        elif isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    # 打印 AI 的文本回复
                    print(block.text, end="", flush=True)
                elif isinstance(block, ToolUseBlock):
                    # 打印 Agent 决定调用的工具或技能
                    print(f"\n[工具/技能调用] 名称: {block.name}, 输入参数: {block.input}")
                elif isinstance(block, ToolResultBlock):
                    # 打印工具执行后的返回结果
                    print(f"\n[工具/技能结果] 内容: {block.content}")

        elif isinstance(message, ResultMessage):
            if message.subtype == "success":
                print(f"\n[执行完成] 本轮对话流结束，耗时: {message.duration_ms} ms\n")
            else:
                print("\n[执行错误] 任务执行出现异常\n")


async def main():
    # 关键配置说明：
    # 1. SDK 默认处于环境隔离状态，不会主动加载本地的技能（Skills）配置。
    #    必须通过 setting_sources 显式指定 ['user', 'project'] 才能加载对应的技能文件。
    # 2. permission_mode 设置为 'bypassPermissions' 可以在自动化测试时绕过人工权限确认弹窗。
    options = CodeBuddyAgentOptions(
        model="deepseek-v3.1",
        setting_sources=["user", "project"],  # 必须配置此项以加载并测试本地 Skills
        permission_mode="bypassPermissions",  # 自动允许工具与技能调用
        cwd=os.getcwd()  # 设置 Agent 的执行工作目录
    )

    print("启动 CodeBuddy 多轮对话与 Skill 测试客户端...\n")

    # 使用 CodeBuddySDKClient 维持多轮对话上下文
    async with CodeBuddySDKClient(options=options) as client:
        while True:
            # 获取用户输入
            print("-" * 50)
            user_prompt = input("用户 (输入 'exit' 或 'quit' 退出): ").strip()

            if not user_prompt:
                continue

            if user_prompt.lower() in ["exit", "quit"]:
                print("退出会话。")
                break

            print("\nAI 正在思考并执行任务...\n")
            await client.query(user_prompt)
            await handle_messages(client)


if __name__ == "__main__":
    # 运行异步主函数（要求 Python >= 3.10）
    asyncio.run(main())
