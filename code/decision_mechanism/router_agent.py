"""
Router / Classifier —— 确定性工作流模式（意图分类 + 固定工作流分发）

对应公众号文章：《Agent 决策机制深度解析》第三章 3.1 节
文章路径：articles/tech-deep-dive/04-Agent决策机制深度解析.md

核心思想：LLM 仅做"分类器"，将任务分流到预先写死的固定工作流
  用户输入 → [LLM Router 判断意图] → 分发到对应 Workflow
  极高确定性，适合业务边界清晰、对准确率要求 100% 的场景

运行方式：
  python3 code/decision_mechanism/router_agent.py
  python3 code/decision_mechanism/router_agent.py --question "帮我查一下去上海的航班"
  python3 code/decision_mechanism/router_agent.py --mode batch

运行环境：Python 3.9+（无第三方依赖）
"""

import argparse


# ============ 工具定义 ============

def get_weather(city: str, date: str) -> dict:
    """模拟天气查询工具"""
    data = {
        ("北京", "today"): {"weather": "晴", "temp": "28°C", "aqi": 65},
        ("上海", "today"): {"weather": "小雨", "temp": "22°C", "aqi": 45},
    }
    return data.get((city, date), {"error": f"未找到 {city} {date} 的数据"})


# ============ 意图分类 Prompt ============

INTENT_ROUTER_PROMPT = """你是一个意图分类器。
根据用户问题，判断它属于哪个类别。只输出类别名称，不要输出其他内容。

类别列表：
- weather   （天气查询）
- flight    （航班相关）
- hotel     （酒店预订）
- unknown   （无法识别）

用户问题：{question}

类别："""


# ============ Router（意图分类器） ============

def route_intent(question: str) -> str:
    """
    调用 LLM 做意图分类

    实际替换为 LLM API 调用，示例：
        import openai
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": INTENT_ROUTER_PROMPT.format(question=question)}],
            temperature=0.0,
        )
        return response.choices[0].message.content.strip().lower()
    """
    # ---- 模拟意图分类（实际使用时删除）----
    if "天气" in question:
        return "weather"
    if "航班" in question or "机票" in question or "飞机" in question:
        return "flight"
    if "酒店" in question or "住宿" in question:
        return "hotel"
    return "unknown"
    # -----------------------------------------


# ============ 固定工作流（各意图对应处理逻辑） ============

def handle_weather(question: str) -> str:
    """天气查询的固定工作流（代码写死）"""
    # 步骤1：提取城市名（可用 LLM 或正则，此处简化）
    city = "北京"
    for candidate in ["北京", "上海", "深圳", "广州"]:
        if candidate in question:
            city = candidate
            break
    # 步骤2：调用工具
    result = get_weather(city, "today")
    return f"{city}今天：{result.get('weather', '未知')} {result.get('temp', '未知')}"


def handle_flight(question: str) -> str:
    """航班查询的固定工作流"""
    return "已为您搜索相关航班（模拟）：CA1234 上海→北京 ¥680，MU5678 上海→北京 ¥520"


def handle_hotel(question: str) -> str:
    """酒店预订的固定工作流"""
    return "酒店预订功能开发中，敬请期待"


def handle_unknown(question: str) -> str:
    """未知意图的兜底处理"""
    return "抱歉，暂不支持该类型问题，您可以试试查询天气、航班或酒店"


# 意图 → 处理函数 映射表
HANDLERS = {
    "weather": handle_weather,
    "flight": handle_flight,
    "hotel": handle_hotel,
    "unknown": handle_unknown,
}


# ============ 主入口 ============

def router_agent(question: str, verbose: bool = True) -> dict:
    """
    运行 Router Agent

    Args:
        question: 用户问题
        verbose: 是否打印中间过程

    Returns:
        {"intent": str, "answer": str}
    """
    if verbose:
        print(f"\n🔀 Router Agent 启动")
        print(f"问题: {question}")
        print("-" * 40)

    # 第一步：意图分类
    intent = route_intent(question)
    if verbose:
        print(f"🔀 路由结果: {intent}")

    # 第二步：分发到对应工作流
    handler = HANDLERS.get(intent, handle_unknown)
    answer = handler(question)

    if verbose:
        print(f"💬 回答: {answer}")

    return {"intent": intent, "answer": answer}


def run_batch(questions: list, verbose: bool = True) -> list:
    """
    批量运行 Router Agent

    Args:
        questions: 问题列表
        verbose: 是否打印中间过程

    Returns:
        结果列表
    """
    results = []
    if verbose:
        print(f"\n🔀 Router Agent 批量模式（{len(questions)} 个问题）")
        print("=" * 60)

    for q in questions:
        result = router_agent(q, verbose=verbose)
        results.append(result)
        if verbose:
            print()

    if verbose:
        print("=" * 60)
        print(f"✅ 批量处理完毕，共 {len(results)} 个问题")

    return results


# ============ 入口 ============

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Router / Classifier 模式（对应文章第 3.1 节）"
    )
    parser.add_argument(
        "--question", "-q",
        type=str,
        default="北京今天天气怎么样？",
        help="用户问题（默认演示问题）",
    )
    parser.add_argument(
        "--mode", "-m",
        type=str,
        choices=["single", "batch"],
        default="single",
        help="运行模式：single（单问题）/ batch（批量演示）",
    )
    args = parser.parse_args()

    if args.mode == "batch":
        demo_questions = [
            "北京今天天气怎么样？",
            "帮我查一下去上海的航班",
            "有没有性价比高的酒店推荐",
            "今天有什么新闻？",
        ]
        run_batch(demo_questions)
    else:
        result = router_agent(args.question)
        print(f"\n📊 运行结果: {result}")
