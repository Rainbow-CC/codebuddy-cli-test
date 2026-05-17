根据参考文档，以下是使用 CodeBuddy Python SDK 测试技能（Skills）使用和多轮对话的完整 Python 脚本示例。

### 准备工作

在使用脚本前，请确保已安装依赖包：

```bash
pip install codebuddy-agent-sdk

```

同时请确保你已经通过命令行完成了 `codebuddy login` 认证，或者在环境变量中设置了 `CODEBUDDY_API_KEY`。

### Python 脚本示例

```python
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
        permission_mode="bypassPermissions", # 自动允许工具与技能调用
        cwd=os.getcwd()                      # 设置 Agent 的执行工作目录
    )

    print("启动 CodeBuddy 多轮对话与 Skill 测试客户端...\n")
    
    # 使用 CodeBuddySDKClient 维持多轮对话上下文
    async with CodeBuddySDKClient(options=options) as client:
        
        # 第一轮对话：尝试触发或询问技能
        print("==================== 第一轮对话 ====================")
        first_prompt = "请帮我检查当前目录的文件结构，并看看是否能够触发我们配置的自定义 Skill 来分析项目？"
        print(f"用户: {first_prompt}\n")
        
        await client.query(first_prompt)
        await handle_messages(client)
        
        # 第二轮对话：基于第一轮的上下文继续交互
        print("==================== 第二轮对话 ====================")
        second_prompt = "根据刚才的分析结果，请进一步调用关联的工具或 Skill，为我生成一份优化建议。"
        print(f"用户: {second_prompt}\n")
        
        await client.query(second_prompt)
        await handle_messages(client)

if __name__ == "__main__":
    # 运行异步主函数（要求 Python >= 3.10）
    asyncio.run(main())

```

### 核心要点解析

1. **技能加载（setting_sources）**：文档强调 SDK 默认为了保证行为可预测性，采用了环境隔离机制（不加载任何 Skills、MCP、Rules）。脚本中通过 `setting_sources=["user", "project"]` 显式打破隔离，从而能正常读取 `~/.codebuddy/skills/` 或当前项目 `.codebuddy/skills/` 下的 AI 自动调用技能。
2. **多轮上下文维持（CodeBuddySDKClient）**：普通的 `query()` 函数是单次调用，而使用 `async with CodeBuddySDKClient` 上下文管理器可以创建一个持久会话，多次调用 `client.query()` 会自动承接上一轮的对话记忆与状态。
3. **消息类型处理**：通过判断 `AssistantMessage` 内部的 `ToolUseBlock` 与 `ToolResultBlock`，可以清晰地捕捉到 Agent 何时触发了 Skill 以及 Skill 返回了什么数据。