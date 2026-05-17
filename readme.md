# AI Agent 测试项目

本仓库用于测试本地数据处理类的 AI Agent 的构建方式

## 项目概览

本项目包含两个主要的测试场景：

1.  **CodeBuddy 官方 SDK 集成 (`codebuddy-test.py`)**: 演示如何使用 `codebuddy-agent-sdk` 与 CodeBuddy Agent 进行流式对话，并加载本地技能（Skills）。
2.  **LangGraph 自定义 Agent (`langgraph_demo/`)**: 模拟 CodeBuddy 的技能加载机制，利用 LangGraph 和 LangChain 构建一个具备状态管理和工具调用能力的自定义学术研究助手。

## 快速开始

### 前置条件

*   Python 3.10+
*   已安装依赖：
    ```bash
    pip install codebuddy-agent-sdk langchain langchain-openai langgraph
    ```
*   环境变量配置：
    *   `DASHSCOPE_API_KEY`: 使用 LangGraph 演示时需要（对接通义千问 API）。

### 1. CodeBuddy Python SDK 集成测试

运行 `codebuddy-test.py` 可以启动一个交互式命令行客户端，它会连接到 CodeBuddy 后端。

```bash
python codebuddy-test.py
```

**关键特性：**
*   **流式输出**：实时接收并打印 AI 的文本回复和工具调用过程。
*   **技能加载**：通过配置 `setting_sources=["user", "project"]` 自动加载项目根目录下的 `.codebuddy/skills` 或其他定义的技能。
*   **自动授权**：设置 `permission_mode="bypassPermissions"` 以便在测试环境下自动允许工具调用。

### 2. LangGraph 自定义 Agent 测试

进入 `langgraph_demo` 目录并运行 `main.py`。该演示模拟了一个学术研究场景。

```bash
cd langgraph_demo
python main.py
```

**关键特性：**
*   **动态技能加载**：模仿 CodeBuddy 扫描项目中的 `SKILL.md` 文件并将其指令注入 System Prompt。
*   **工具调用**：内置了查询 SQLite 数据库和获取 Schema 的工具。
*   **状态管理**：使用 LangGraph 的 `MemorySaver` 实现多轮对话的上下文记忆。
*   **学术研究技能**：结合 `academic-researcher` 目录下的数据，回答关于论文、作者和引用关系的问题。

## 项目结构

*   `codebuddy-test.py`: 官方 SDK 集成入口。
*   `langgraph_demo/`: LangGraph 自定义 Agent 的完整实现。
    *   `main.py`: Agent 逻辑与交互入口。
    *   `agent_tools.py`: 定义 Agent 可使用的工具（如 SQL 查询）。
    *   `skills_loader.py`: 负责从项目中动态扫描并加载技能指令。
*   `academic-researcher/`: 包含学术研究相关的 SQL 数据库 (`academic.sqlite`) 和技能说明 (`SKILL.md`)。
*   `spider_data/`: (可选) 包含 Spider 数据集，用于更复杂的 SQL 生成测试。
*   `.codebuddy/`: CodeBuddy 配置文件存放目录。

## 开发参考

*   [CodeBuddy 官方文档](https://github.com/google/codebuddy)
*   [LangGraph 文档](https://langchain-ai.github.io/langgraph/)
*   [通义千问 OpenAI 兼容接口](https://help.aliyun.com/zh/dashscope/developer-reference/openai-compatible-interface)
