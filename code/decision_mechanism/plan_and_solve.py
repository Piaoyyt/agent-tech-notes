"""
Plan-and-Solve + Reflection —— 经典自主决策模式（先谋后动 + 动态反思）

对应公众号文章：《Agent 决策机制深度解析》第二章 2.2 节
文章路径：articles/tech-deep-dive/04-Agent决策机制深度解析.md

核心思想：先生成完整计划，执行中动态反思并调整后续步骤
  规划阶段: LLM 生成完整计划（步骤列表）
  执行阶段: 执行 Step → 观察结果 → 反思（是否需要调整？）
                  ↓ 是（重新规划）       ↓ 否（继续执行）

运行方式：
  python3 code/decision_mechanism/plan_and_solve.py
  python3 code/decision_mechanism/plan_and_solve.py --task "帮我安排一次上海出差"
  python3 code/decision_mechanism/plan_and_solve.py --max-rounds 10

运行环境：Python 3.9+（无第三方依赖）
"""

import json
import argparse
from typing import List, Dict


# ============ 工具集（与 ReAct 示例一致） ============

def get_weather(city: str, date: str) -> dict:
    """模拟天气查询工具"""
    data = {
        ("北京", "today"): {"weather": "晴", "temp": "28°C", "aqi": 65},
        ("北京", "tomorrow"): {"weather": "多云", "temp": "25°C", "aqi": 80},
        ("上海", "today"): {"weather": "小雨", "temp": "22°C", "aqi": 45},
        ("上海", "tomorrow"): {"weather": "阴", "temp": "21°C", "aqi": 55},
    }
    return data.get((city, date), {"error": f"未找到 {city} {date} 的数据"})


def search_flight(origin: str, dest: str, date: str) -> dict:
    """模拟航班搜索工具"""
    return {
        "flights": [
            {"flight": "CA1234", "from": origin, "to": dest, "date": date, "price": "¥680"},
            {"flight": "MU5678", "from": origin, "to": dest, "date": date, "price": "¥520"},
        ]
    }


def search_hotel(city: str, checkin: str, nights: int) -> dict:
    """模拟酒店搜索工具"""
    return {
        "hotels": [
            {"name": f"{city}商务酒店", "checkin": checkin, "nights": nights, "price": "¥388/晚"},
            {"name": f"{city}快捷酒店", "checkin": checkin, "nights": nights, "price": "¥228/晚"},
        ]
    }


TOOLS = {
    "check_weather": get_weather,
    "search_flight": search_flight,
    "search_hotel": search_hotel,
}


# ============ Planner（规划器） ============

PLANNER_PROMPT = """你是一个任务规划专家。
给定任务和可用工具，请将任务拆解为执行步骤。

可用工具：
{tool_desc}

请严格按 JSON 格式输出：
{{"plan": [{{"step": 1, "action": "工具名", "params": {{...}}, "purpose": "目的"}}]}}

任务：{task}"""


def planner(task: str) -> List[Dict]:
    """
    调用 LLM 生成执行计划

    实际替换为 LLM API 调用，示例：
        import openai
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": PLANNER_PROMPT.format(...)}],
            temperature=0.2,
        )
        return json.loads(response.choices[0].message.content)["plan"]
    """
    # ---- 模拟 LLM 规划输出（实际使用时删除）----
    if "北京" in task:
        return [
            {"step": 1, "action": "check_weather",
             "params": {"city": "北京", "date": "today"},
             "purpose": "确认出差日天气"},
            {"step": 2, "action": "search_flight",
             "params": {"origin": "上海", "dest": "北京", "date": "2026-06-12"},
             "purpose": "搜索航班"},
            {"step": 3, "action": "search_hotel",
             "params": {"city": "北京", "checkin": "2026-06-12", "nights": 2},
             "purpose": "预订酒店"},
        ]
    else:
        return [
            {"step": 1, "action": "check_weather",
             "params": {"city": "上海", "date": "today"},
             "purpose": "确认出差日天气"},
            {"step": 2, "action": "search_flight",
             "params": {"origin": "北京", "dest": "上海", "date": "2026-06-12"},
             "purpose": "搜索航班"},
            {"step": 3, "action": "search_hotel",
             "params": {"city": "上海", "checkin": "2026-06-12", "nights": 2},
             "purpose": "预订酒店"},
        ]
    # -----------------------------------------


# ============ Reflector（反思器） ============

REFLECTION_PROMPT = """你是审查员。请审视刚执行的步骤是否合理。

任务：{task}
当前步骤：{step_info}
执行结果：{observation}

请判断（输出 JSON）：
{{"need_replan": true/false, "reason": "理由", "adjusted_steps": [修改后剩余步骤]}}"""


def reflector(task: str, step_info: dict, observation: str) -> dict:
    """
    反思当前步骤，决定是否需要重新规划

    实际替换为 LLM API 调用，示例：
        import openai
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": REFLECTION_PROMPT.format(...)}],
            temperature=0.2,
        )
        return json.loads(response.choices[0].message.content)
    """
    # ---- 模拟反思逻辑（实际使用时删除）----
    # 如果天气下雨，建议调整户外活动安排
    if "雨" in str(observation):
        return {
            "need_replan": True,
            "reason": "下雨，建议调整行程安排",
            "adjusted_steps": [
                {"step": 2, "action": "search_flight",
                 "params": {"origin": "北京", "dest": "上海", "date": "2026-06-13"},
                 "purpose": "改签至次日航班（避开雨天）"},
                {"step": 3, "action": "search_hotel",
                 "params": {"city": "上海", "checkin": "2026-06-13", "nights": 2},
                 "purpose": "预订酒店（日期顺延一天）"},
            ],
        }
    return {"need_replan": False, "reason": "执行正常，继续"}
    # -----------------------------------------


# ============ 主执行循环 ============

def run_plan_and_solve(task: str, max_rounds: int = 8, verbose: bool = True) -> dict:
    """
    运行 Plan-and-Solve + Reflection 决策循环

    Args:
        task: 用户任务
        max_rounds: 最大执行轮数
        verbose: 是否打印中间过程

    Returns:
        {"results": list, "total_steps": int, "replan_count": int}
    """
    if verbose:
        print(f"\n📋 Plan-and-Solve Agent 启动")
        print(f"任务: {task}")
        print("=" * 60)

    # 阶段一：生成计划
    plan = planner(task)
    if verbose:
        print(f"\n📋 生成计划（共 {len(plan)} 步）：")
        for s in plan:
            print(f"  Step {s['step']}: {s['action']} —— {s['purpose']}")

    # 阶段二：逐步执行 + 动态反思
    if verbose:
        print(f"\n🚀 开始执行")
        print("=" * 60)
    results = []
    remaining = list(enumerate(plan))  # (idx, step) 列表
    replan_count = 0

    while remaining and len(results) < max_rounds:
        idx, step_info = remaining.pop(0)
        if verbose:
            print(f"\n▶ Step {step_info['step']}: {step_info['action']}")
            print(f"  目的: {step_info['purpose']}")

        # 执行工具
        tool = step_info["action"]
        params = step_info["params"]
        if tool in TOOLS:
            try:
                obs = TOOLS[tool](**params)
                obs_str = (
                    json.dumps(obs, ensure_ascii=False)
                    if isinstance(obs, dict)
                    else str(obs)
                )
            except Exception as e:
                obs_str = f"错误: {e}"
        else:
            obs_str = f"未知工具: {tool}"

        if verbose:
            print(f"   ✅ 结果: {obs_str[:80]}...")
        results.append({"step": step_info["step"], "result": obs_str})

        # 反思：是否需要调整后续计划？
        reflection = reflector(task, step_info, obs_str)
        if reflection["need_replan"]:
            replan_count += 1
            if verbose:
                print(f"   🪞 反思：需要重新规划！理由: {reflection['reason']}")
            # 用调整后的步骤替换 remaining
            if reflection.get("adjusted_steps"):
                remaining = [
                    (i, s) for i, s in enumerate(reflection["adjusted_steps"])
                ]
                if verbose:
                    print(f"   🔄 已更新剩余计划（{len(remaining)} 步）")
        else:
            if verbose:
                print("   ✅ 反思：执行正常，继续")

    if verbose:
        print(f"\n{'=' * 60}")
        print(f"✅ 执行完毕，共完成 {len(results)} 步，重新规划 {replan_count} 次")

    return {
        "results": results,
        "total_steps": len(results),
        "replan_count": replan_count,
    }


# ============ 入口 ============

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Plan-and-Solve + Reflection（对应文章第 2.2 节）"
    )
    parser.add_argument(
        "--task", "-t",
        type=str,
        default="帮我安排一次北京出差，6月12日出发，住两晚",
        help="用户任务（默认演示任务）",
    )
    parser.add_argument(
        "--max-rounds",
        type=int,
        default=8,
        help="最大执行轮数（默认 8）",
    )
    args = parser.parse_args()

    result = run_plan_and_solve(args.task, args.max_rounds)
    print(f"\n📊 运行结果: {json.dumps(result, ensure_ascii=False, indent=2)}")
