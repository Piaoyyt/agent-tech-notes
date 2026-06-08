"""
ReAct Agent —— 经典自主决策模式（不依赖任何框架的完整实现）

对应公众号文章：《Agent 决策机制深度解析》第二章 2.1 节
文章路径：articles/tech-deep-dive/04-Agent决策机制深度解析.md

核心思想：Reasoning 和 Acting 交织循环
  Thought → Action → Observation → Thought → ... → Final Answer

运行方式：
  python3 code/decision_mechanism/react_agent.py
  python3 code/decision_mechanism/react_agent.py --question "上海明天天气怎么样？"
  python3 code/decision_mechanism/react_agent.py --max-rounds 5

运行环境：Python 3.9+（无第三方依赖）
"""

import re
import json
import argparse


# ============ 工具集 ============

def get_weather(city: str, date: str) -> dict:
    """模拟天气查询工具"""
    data = {
        ("北京", "today"): {"weather": "晴", "temp": "28°C", "aqi": 65},
        ("北京", "tomorrow"): {"weather": "多云", "temp": "25°C", "aqi": 80},
        ("上海", "today"): {"weather": "小雨", "temp": "22°C", "aqi": 45},
        ("上海", "tomorrow"): {"weather": "阴", "temp": "21°C", "aqi": 55},
    }
    return data.get((city, date), {"error": f"未找到 {city} {date} 的数据"})


def search_web(query: str) -> str:
    """模拟网络搜索工具"""
    mock = {"端午节放假": "2026年端午节：6月19日-21日，共3天。"}
    return mock.get(query, f"关于「{query}」的搜索结果（模拟）。")


def calculate(expr: str) -> float:
    """安全的数学表达式计算器"""
    allowed_chars = set("0123456789.+-*/() ")
    if not all(c in allowed_chars for c in expr):
        return f"计算错误：表达式包含不支持的字符"
    try:
        return float(eval(expr, {"__builtins__": {}}, {}))
    except Exception:
        return f"无法计算: {expr}"


TOOLS = {
    "get_weather": get_weather,
    "search_web": search_web,
    "calculate": calculate,
}


# ============ Prompt 模板 ============

REACT_PROMPT = """你是一个智能助手，可以使用工具回答问题。

## 可用工具
{tool_desc}

## 回答格式（严格遵守）
Thought: [你的分析和下一步思考]
Action: 工具名("参数1", "参数2")
Observation: [系统自动填入]

（Thought→Action→Observation 可重复多次）

Thought: [最终思考]
Final Answer: [最终答案]

## 规则
- 每次只能执行一个 Action
- 必须基于 Observation 继续思考，不要猜测
- 信息充足时必须给出 Final Answer"""

TOOL_DESC = """
1. get_weather(city, date) -> dict
   查询天气。示例: get_weather("北京", "today")
2. search_web(query) -> str
   搜索信息。示例: search_web("端午节放假")
3. calculate(expression) -> float
   计算表达式。示例: calculate("23 * 45")""".strip()


# ============ 输出解析器 ============

def parse_react(text: str) -> dict:
    """解析 LLM 输出，提取 Final Answer 或 Action"""
    fa = re.search(r"Final Answer\s*:\s*(.+)", text, re.DOTALL)
    if fa:
        return {"type": "final", "answer": fa.group(1).strip()}
    am = re.search(r"Action\s*:\s*(\w+)\s*\((.*?)\)", text)
    if am:
        tool = am.group(1)
        params = [p.strip().strip('"\'') for p in am.group(2).split(",") if p.strip()]
        tm = re.search(r"Thought\s*:\s*(.+?)(?=Action\s*:|$)", text, re.DOTALL)
        return {
            "type": "action",
            "tool": tool,
            "params": params,
            "thought": tm.group(1).strip() if tm else "",
        }
    return {"type": "unparsed", "raw": text[:150]}


# ============ 模拟 LLM ============

def simulate_llm(question: str, history: list, rnd: int) -> str:
    """
    模拟 LLM 输出（实际使用时替换为真实 API 调用）

    示例替换代码：
        import openai
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
        )
        return response.choices[0].message.content
    """
    if rnd == 0:
        return 'Thought: 需要查北京今天天气\nAction: get_weather("北京", "today")'
    return (
        "Thought: 北京今日晴天28°C、AQI 65，适合跑步\n"
        "Final Answer: 北京今天天气很好！晴天28°C、AQI 65，"
        "非常适合户外跑步🏃 建议清晨或傍晚时段。"
    )


# ============ 主循环 ============

def run_react(question: str, max_rounds: int = 6, verbose: bool = True) -> dict:
    """
    运行 ReAct 决策循环

    Args:
        question: 用户问题
        max_rounds: 最大推理轮数
        verbose: 是否打印中间过程

    Returns:
        {"answer": str, "rounds": int}
    """
    history = []
    if verbose:
        print(f"\n🤖 ReAct Agent 启动 | 问题: {question}")
        print("=" * 60)

    for rnd in range(max_rounds):
        r = rnd + 1
        if verbose:
            print(f"\n🔄 第 {r} 轮")

        # ---- 实际使用时替换为真实 LLM 调用 ----
        llm_text = simulate_llm(question, history, rnd)
        # -----------------------------------------

        if verbose:
            print(f"  💭 {llm_text[:80]}...")
        parsed = parse_react(llm_text)

        if parsed["type"] == "final":
            if verbose:
                print(f"  🎯 最终答案: {parsed['answer']}")
            return {"answer": parsed["answer"], "rounds": r}

        if parsed["type"] == "action":
            tool, params = parsed["tool"], parsed["params"]
            if verbose:
                print(f"  💡 思考: {parsed.get('thought', '')}")
                print(f"  🔧 行动: {tool}({params})")

            if tool in TOOLS:
                try:
                    obs = TOOLS[tool](*params)
                    obs_str = (
                        json.dumps(obs, ensure_ascii=False)
                        if isinstance(obs, dict)
                        else str(obs)
                    )
                except Exception as e:
                    obs_str = f"工具异常: {e}"
            else:
                obs_str = f"未知工具: {tool}"

            if verbose:
                print(f"  📊 观察: {obs_str[:80]}...")
            history.append(
                f"Thought: {parsed.get('thought', '')}\n"
                f"Action: {tool}({', '.join(params)})\n"
                f"Observation: {obs_str}"
            )
        else:
            if verbose:
                print("  ⚠️ 格式异常，引导重试")
            history.append(
                "(格式错误，请严格按 Thought→Action→Observation 格式输出)"
            )

    return {"answer": None, "rounds": max_rounds}


# ============ 入口 ============

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="ReAct Agent —— 经典自主决策模式（对应文章第 2.1 节）"
    )
    parser.add_argument(
        "--question", "-q",
        type=str,
        default="北京今天天气怎么样，适不适合跑步？",
        help="用户问题（默认演示问题）",
    )
    parser.add_argument(
        "--max-rounds",
        type=int,
        default=6,
        help="最大推理轮数（默认 6）",
    )
    args = parser.parse_args()

    result = run_react(args.question, args.max_rounds)
    print(f"\n{'=' * 60}")
    print(f"📊 运行结果: {result}")
