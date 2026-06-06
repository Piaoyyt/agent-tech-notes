"""
ReAct Agent 手写实现（无框架依赖）

对应公众号文章：《ReAct 深度解析：从原理到手写实现》
文章链接：待补充

运行环境：
  Python 3.9+
  pip install openai   # 或其它 LLM SDK

使用前请修改 LLM 调用部分，替换为真实的 API 调用。
"""

import re
import json
import os
from typing import Any, Callable, Dict, List, Optional, Tuple

# ============================================================
# 1. 工具定义（Tool Definitions）
# ============================================================

def get_weather(city: str, date: str) -> dict:
    """
    模拟天气查询工具。
    实际使用时替换为真实天气 API（如和风天气、OpenWeather 等）。
    """
    mock_data = {
        ("北京", "today"):   {"weather": "晴", "temperature": "28°C", "AQI": 65},
        ("北京", "tomorrow"): {"weather": "多云", "temperature": "25°C", "AQI": 80},
        ("上海", "today"):    {"weather": "小雨", "temperature": "22°C", "AQI": 45},
        ("上海", "tomorrow"): {"weather": "阴",   "temperature": "21°C", "AQI": 55},
        ("深圳", "today"):    {"weather": "阵雨", "temperature": "30°C", "AQI": 40},
    }
    key = (city, date)
    if key in mock_data:
        return mock_data[key]
    return {"error": f"未找到 {city} {date} 的天气数据"}


def search_web(query: str) -> str:
    """
    模拟网络搜索工具。
    实际使用时替换为真实搜索 API（如 SerpAPI、Bing Search 等）。
    """
    return f'[模拟搜索结果] 关于"{query}"的相关信息：这是一条模拟的搜索结果，实际使用时请接入真实搜索 API。'


def calculate(expression: str) -> str:
    """
    安全的数学表达式计算器。
    仅允许基础算术运算，禁止 __import__ 等危险操作。
    """
    allowed_chars = set("0123456789.+-*/() ")
    if not all(c in allowed_chars for c in expression):
        return f"计算错误：表达式包含不支持的字符"
    try:
        result = eval(expression, {"__builtins__": {}}, {})
        return str(float(result))
    except Exception as e:
        return f"计算错误：{e}"


# 注册所有可用工具
AVAILABLE_TOOLS: Dict[str, Callable] = {
    "get_weather": get_weather,
    "search_web": search_web,
    "calculate": calculate,
}

TOOL_DESCRIPTIONS: str = """
- get_weather(city: str, date: str) -> dict
  查询某城市某天的天气。date 可以是 "today" 或 "tomorrow"。
  示例: get_weather("北京", "today")

- search_web(query: str) -> str
  搜索网络信息。
  示例: search_web("2026年端午节放假安排")

- calculate(expression: str) -> str
  计算数学表达式（仅支持 + - * / 和括号）。
  示例: calculate("23 * 45")
""".strip()


# ============================================================
# 2. Prompt 构建
# ============================================================

FEW_SHOT_EXAMPLES: str = """
Here is an example of how to use the tools correctly:

Question: 上海明天天气怎么样，适合穿什么？

Thought: 我需要查询上海明天的天气情况，然后根据温度和天气给出穿衣建议。
Action: get_weather("上海", "tomorrow")
Observation: {"city": "上海", "date": "2026-06-07", "weather": "小雨", "temperature": "22°C"}

Thought: 上海明天下雨，温度22度，需要带伞，建议穿长袖外套。
Final Answer: 上海明天有小雨，气温22°C，建议穿长袖外套，记得带伞。

Remember: You MUST follow the format exactly. Do NOT include extra text outside the format.
""".strip()


def build_react_prompt(question: str, history: str = "") -> str:
    """
    构建完整的 ReAct Prompt。

    Args:
        question: 用户原始问题
        history:  历史对话（Thought/Action/Observation 循环记录）

    Returns:
        完整的 prompt 字符串
    """
    prompt = f"""You are a helpful AI assistant that can use tools to answer questions.

You have access to the following tools:
{TOOL_DESCRIPTIONS}

To answer the user's question, you MUST follow this format EXACTLY:

Thought: [your reasoning about what to do next]
Action: tool_name("param1", "param2")
Observation: [will be filled by system]

(This Thought/Action/Observation cycle can repeat multiple times)

Thought: [your reasoning that you now have enough information]
Final Answer: [your final answer to the user's question]

{FEW_SHOT_EXAMPLES}

Now, answer the following question. Use tools when needed.

Question: {question}

{history}""".strip()
    return prompt


# ============================================================
# 3. LLM 调用（替换为真实 API）
# ============================================================

def call_llm(prompt: str) -> str:
    """
    调用大语言模型。

    当前为模拟实现，实际使用时请替换为真实 LLM API 调用。
    支持：OpenAI GPT、Anthropic Claude、Qwen、GLM 等。

    示例（OpenAI）：
        import openai
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
        )
        return response.choices[0].message.content
    """
    # ---- 模拟 LLM 输出（实际使用时删除此段）----
    # 这里仅用于演示运行流程，真实场景下注释掉下面的模拟逻辑
    if "北京" in prompt and "天气" in prompt and "Action:" not in prompt.split("Question:")[-1]:
        return '''Thought: 我需要查询北京今天的天气情况，判断适不适合跑步。
Action: get_weather("北京", "today")'''
    elif "Observation:" in prompt and "28" in prompt:
        return '''Thought: 北京今天晴天、28度、空气质量良好（AQI 65），非常适合跑步。不过28度有点热，建议傍晚时段跑步，避开中午的高温。
Final Answer: 北京今天天气不错，晴天、28°C、空气质量良好（AQI 65），非常适合跑步！建议选择傍晚时段，避开中午的高温。'''
    # ---- 模拟结束，以下是真实调用示例 ----

    # TODO: 替换为你的 LLM 调用
    # import openai
    # api_key = os.getenv("OPENAI_API_KEY")
    # if not api_key:
    #     raise ValueError("请设置 OPENAI_API_KEY 环境变量")
    # response = openai.chat.completions.create(
    #     model="gpt-4o",
    #     messages=[{"role": "user", "content": prompt}],
    #     temperature=0.2,
    # )
    # return response.choices[0].message.content

    raise NotImplementedError(
        "call_llm() 当前为模拟模式。请替换为真实的 LLM API 调用，或取消上面模拟代码的注释以测试运行流程。"
    )


# ============================================================
# 4. 解析 LLM 输出
# ============================================================

def parse_llm_output(output: str) -> Dict[str, Any]:
    """
    解析 LLM 输出，判断是 Final Answer 还是 Action。

    Returns:
        字典，包含 type 字段：
        - {"type": "final_answer", "content": "..."}
        - {"type": "action", "thought": "...", "tool_name": "...", "params": [...]}
        - {"type": "thought_only", "content": "..."}
    """
    # 去除可能的代码块包裹
    output = re.sub(r"^```[\w]*\n?", "", output).strip()
    output = re.sub(r"\n?```$", "", output).strip()

    # 尝试提取 Final Answer（优先）
    final_match = re.search(r"Final Answer:\s*(.+)", output, re.DOTALL | re.IGNORECASE)
    if final_match:
        content = final_match.group(1).strip()
        # 去掉可能跟随的多余内容
        content = re.split(r"\n\s*(Thought:|Action:)", content)[0].strip()
        return {"type": "final_answer", "content": content}

    # 尝试提取 Action（工具调用）
    # 支持多种格式：Action: tool("param") 或 Action: tool(param)
    action_match = re.search(
        r"Action:\s*(\w+)\s*\(\s*(.+?)\s*\)",
        output,
        re.DOTALL
    )
    thought_match = re.search(
        r"Thought:\s*(.+?)(?=Action:|Final Answer:|$)",
        output,
        re.DOTALL | re.IGNORECASE
    )

    if action_match:
        tool_name = action_match.group(1).strip()
        params_str = action_match.group(2).strip()

        # 解析参数（处理带引号和不带引号的情况）
        params = _parse_params(params_str)

        thought = thought_match.group(1).strip() if thought_match else ""
        return {
            "type": "action",
            "thought": thought,
            "tool_name": tool_name,
            "params": params,
        }

    # 都没有：只有 Thought，或格式不正确
    return {"type": "thought_only", "content": output.strip()}


def _parse_params(params_str: str) -> List[str]:
    """
    简单参数解析器。
    支持："param1", "param2"  和  param1, param2  两种格式。
    """
    params = []
    current = ""
    in_quotes = False
    quote_char = None
    i = 0
    while i < len(params_str):
        c = params_str[i]
        if not in_quotes and c in ('"', "'"):
            in_quotes = True
            quote_char = c
        elif in_quotes and c == quote_char:
            in_quotes = False
        elif not in_quotes and c == ",":
            params.append(current.strip())
            current = ""
        else:
            current += c
        i += 1
    if current.strip():
        params.append(current.strip())
    # 去除参数两端的引号
    cleaned = []
    for p in params:
        p = p.strip()
        if (p.startswith('"') and p.endswith('"')) or (p.startswith("'") and p.endswith("'")):
            p = p[1:-1]
        cleaned.append(p)
    return cleaned


# ============================================================
# 5. 执行工具调用
# ============================================================

def execute_tool(tool_name: str, params: List[str]) -> Any:
    """
    执行工具调用，返回观察结果。

    Args:
        tool_name: 工具名称
        params:    参数列表（字符串）

    Returns:
        工具返回结果（任意类型）
    """
    if tool_name not in AVAILABLE_TOOLS:
        return f"❌ 错误：工具 '{tool_name}' 不存在。可用工具：{list(AVAILABLE_TOOLS.keys())}"

    try:
        tool_func = AVAILABLE_TOOLS[tool_name]
        result = tool_func(*params)
        return result
    except Exception as e:
        return f"❌ 工具执行错误：{type(e).__name__}: {e}"


# ============================================================
# 6. ReAct 主循环
# ============================================================

def run_react_agent(question: str, max_steps: int = 8, verbose: bool = True) -> str:
    """
    运行 ReAct Agent，返回最终答案。

    Args:
        question:  用户问题
        max_steps: 最大推理步数（防止死循环）
        verbose:   是否打印中间过程

    Returns:
        最终答案字符串
    """
    history = ""
   .    if verbose:
        print(f"\n{'='*60}")
        print(f"📝 问题：{question}")
        print(f"{'='*60}\n")

    for step in range(max_steps):
        if verbose:
            print(f"\n--- Step {step + 1} ---")

        # 构建 prompt 并调用 LLM
        prompt = build_react_prompt(question, history)
        try:
            llm_output = call_llm(prompt)
        except NotImplementedError:
            print("⚠️  LLM 调用未配置，当前为模拟模式。请查看 call_llm() 函数。")
            break

        if verbose:
            print(f"🤖 LLM 输出：\n{llm_output}\n")

        # 解析输出
        parsed = parse_llm_output(llm_output)

        # 最终答案 → 结束
        if parsed["type"] == "final_answer":
            if verbose:
                print(f"✅ 最终答案：\n{parsed['content']}\n")
            return parsed["content"]

        # 调用工具 → 执行并追加 Observation
        if parsed["type"] == "action":
            tool_name = parsed["tool_name"]
            params = parsed["params"]

            if verbose:
                print(f"🧠 Thought：{parsed.get('thought', '')}")
                print(f"🔧 调用工具：{tool_name}{params}")

            observation = execute_tool(tool_name, params)

            if verbose:
                print(f"👀 Observation：{observation}\n")

            # 追加到历史，供下一轮使用
            history += f"\n{llm_output}\nObservation: {observation}\n"

        # 格式不正确 → 引导修正
        else:
            if verbose:
                print(f"⚠️  LLM 输出格式不正确，引导重新输出...")
            history += f"\n{llm_output}\n\nPlease follow the exact format:\nThought: ...\nAction: tool_name(params)\nor\nThought: ...\nFinal Answer: ...\n"

    # 达到最大步数仍未得出答案
    error_msg = f"⚠️  已达到最大步数（{max_steps}），仍未得出最终答案。请检查工具定义或 LLM 输出格式。"
    if verbose:
        print(error_msg)
    return error_msg


# ============================================================
# 7. 运行入口
# ============================================================

if __name__ == "__main__":
    # 测试用例 1：天气查询 + 判断
    question_1 = "北京今天天气怎么样，适不适合跑步？"
    answer_1 = run_react_agent(question_1, max_steps=5)
    print(f"\n📊 最终回答：{answer_1}")

    # 测试用例 2：数学计算
    # question_2 = "23乘以45等于多少？"
    # answer_2 = run_react_agent(question_2)
    # print(f"\n📊 最终回答：{answer_2}")

    # 测试用例 3：需要搜索 + 计算组合
    # question_3 = "搜索一下2026年端午节放假几天，然后计算如果每天跑5公里，整个假期能跑多少公里？"
    # answer_3 = run_react_agent(question_3, max_steps=8)
    # print(f"\n📊 最终回答：{answer_3}")
