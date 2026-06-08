# React Agent 模块

本目录包含文章《ReAct 深度解析：从原理到手写实现》的配套代码。

## 文件说明

| 文件 | 说明 |
|------|------|
| `react_agent.py` | ReAct Agent 完整手写实现（无框架依赖） |

## 快速运行

```bash
# 安装依赖
pip install openai

# 配置 API Key
export OPENAI_API_KEY="sk-xxx"

# 修改 call_llm() 函数，替换为真实 API 调用
# 然后运行
python react_agent.py
```

## 核心函数一览

| 函数 | 说明 |
|------|------|
| `build_react_prompt()` | 构建 ReAct 格式 Prompt |
| `parse_llm_output()` | 解析 LLM 输出，提取 Thought/Action/Final Answer |
| `execute_tool()` | 执行工具调用 |
| `run_react_agent()` | ReAct 主循环 |

## 扩展建议

- 替换 `call_llm()` 中的模拟逻辑，接入真实 LLM API
- 在 `AVAILABLE_TOOLS` 中注册自己的工具函数
- 增加输出解析的健壮性（当前为简单正则解析）
- 加入 JSON 格式输出模式（比自由文本更稳定）
