"""
Static Plan + Dynamic Execution —— 混合决策模式（静态规划 + 动态执行）

对应公众号文章：《Agent 决策机制深度解析》第五章 5.1 节
文章路径：articles/tech-deep-dive/04-Agent决策机制深度解析.md

核心思想：顶层采用硬编码流程图（确定性），特定节点内部封装微型 ReAct 循环（灵活性）
  [接收需求] → [提取字段] → [?? 灵活处理节点 ??] → [汇总结果] → [返回]
                                    ↓
                          内部封装微型 ReAct 循环
                          （LLM 自主决策，但受步数限制）

典型场景（物流场景）：
  1. 接收司机找货请求
  2. 提取司机偏好 → LLM 做信息提取
  3. 搜索匹配货源 → 确定性检索
  4. 个性化排序   → 封装 ReAct 循环，LLM 综合多因素排序
  5. 返回结果

运行方式：
  python3 code/decision_mechanism/hybrid_agent.py
  python3 code/decision_mechanism/hybrid_agent.py --input "我需要找从北京到上海的货源，6.8米高栏车"
  python3 code/decision_mechanism/hybrid_agent.py --max-react-rounds 3

运行环境：Python 3.9+（无第三方依赖）
"""

import json
import argparse
import re
from typing import List, Dict, Any


# ============ 模拟数据 ============

# 司机偏好结构
DRIVER_PROFILES = {
    "default": {
        "vehicle_type": "6.8米高栏",
        "route": "北京→上海",
        "price_expect": "≥200元/吨",
    }
}

# 模拟货源数据库
CARGO_DATABASE = [
    {"id": "C001", "origin": "北京", "dest": "上海", "cargo": "建材", "weight": "20吨",
     "price": "220元/吨", "distance": "1200km", "urgency": "普通"},
    {"id": "C002", "origin": "北京", "dest": "上海", "cargo": "家具", "weight": "15吨",
     "price": "180元/吨", "distance": "1200km", "urgency": "加急"},
    {"id": "C003", "origin": "北京", "dest": "上海", "cargo": "电子产品", "weight": "8吨",
     "price": "350元/吨", "distance": "1200km", "urgency": "普通"},
    {"id": "C004", "origin": "北京", "dest": "南京", "cargo": "食品", "weight": "25吨",
     "price": "160元/吨", "distance": "900km", "urgency": "普通"},
    {"id": "C005", "origin": "天津", "dest": "上海", "cargo": "钢材", "weight": "30吨",
     "price": "190元/吨", "distance": "1100km", "urgency": "加急"},
]


# ============ Step 1: 提取字段（确定性 + LLM 辅助提取） ============

def extract_fields(user_input: str) -> Dict[str, str]:
    """
    从用户输入中提取结构化字段

    实际项目中可用 LLM 做更智能的提取，此处简化为规则匹配

    实际 LLM 调用示例：
        import openai
        response = openai.chat.completions.create(
            model="gpt-4o-mini",  # 小模型即可完成提取
            messages=[{"role": "user", "content": f"提取以下信息：...{user_input}"}],
            temperature=0.0,
        )
    """
    fields = {"origin": "", "dest": "", "vehicle_type": ""}

    # 简单规则提取
    for city in ["北京", "上海", "广州", "深圳", "南京", "天津"]:
        if city in user_input and not fields["origin"]:
            fields["origin"] = city
        elif city in user_input and not fields["dest"]:
            fields["dest"] = city

    for vt in ["高栏", "厢式", "平板", "冷藏", "6.8米", "9.6米", "13米"]:
        if vt in user_input:
            fields["vehicle_type"] = vt
            break

    # 如果没有提取到，使用默认值
    if not fields["origin"]:
        fields["origin"] = "北京"
    if not fields["dest"]:
        fields["dest"] = "上海"
    if not fields["vehicle_type"]:
        fields["vehicle_type"] = "6.8米高栏"

    return fields


# ============ Step 2: 确定性检索 ============

def deterministic_search(fields: Dict[str, str]) -> List[Dict]:
    """
    确定性检索匹配货源（代码实现，不涉及 LLM）
    """
    candidates = []
    for cargo in CARGO_DATABASE:
        # 简单匹配：出发地和目的地
        match_origin = fields["origin"] in cargo["origin"]
        match_dest = fields["dest"] in cargo["dest"]
        if match_origin or match_dest:
            candidates.append(cargo)
    return candidates


# ============ Step 3: 动态排序（封装微型 ReAct 循环） ============

RANKING_PROMPT = """你是一个排序专家。请根据用户需求对以下候选结果进行智能排序。

用户需求：{user_input}
候选列表：{candidates}

请分析每个候选与用户需求的匹配度，输出排序后的结果。
你可以先思考（Thought），然后给出排序（Final Answer）。

Thought: [你的分析]
Final Answer: {{"ranked_ids": ["C001", "C003", ...], "reasons": {{"C001": "原因", ...}}}}
"""


def _simulate_ranking_llm(candidates: list, user_input: str, rnd: int) -> str:
    """模拟排序 LLM 输出"""
    if rnd == 0:
        ids = [c["id"] for c in candidates]
        reasons = {c["id"]: f"价格{c['price']}，{'加急' if c['urgency'] == '加急' else '普通'}优先级" for c in candidates}
        ranking_result = {"ranked_ids": ids, "reasons": reasons}
        return (
            f'Thought: 综合考虑价格、紧急程度和匹配度进行排序\n'
            f'Final Answer: {json.dumps(ranking_result, ensure_ascii=False)}'
        )
    return 'Final Answer: {"ranked_ids": [], "reasons": {}}'


def _parse_ranking(text: str) -> Dict[str, Any]:
    """解析排序结果"""
    fa = re.search(r"Final Answer\s*:\s*(.+)", text, re.DOTALL)
    if fa:
        try:
            result = json.loads(fa.group(1).strip())
            return result
        except json.JSONDecodeError:
            pass
    return {"ranked_ids": [], "reasons": {}}


def dynamic_ranking_with_react(
    candidates: List[Dict], user_input: str, max_rounds: int = 3
) -> List[Dict]:
    """
    封装的微型 ReAct 循环
    只在"排序"这个子任务上让 LLM 自主决策
    限制最多 max_rounds 轮，控制延迟
    """
    if not candidates:
        return []

    print(f"\n   🔄 动态排序节点（ReAct 循环，最多 {max_rounds} 轮）")

    for rnd in range(max_rounds):
        r = rnd + 1
        print(f"     第 {r} 轮推理...")

        # ---- 实际使用时替换为真实 LLM 调用 ----
        llm_text = _simulate_ranking_llm(candidates, user_input, rnd)
        # -----------------------------------------

        parsed = _parse_ranking(llm_text)
        if parsed.get("ranked_ids"):
            # 按 LLM 排序结果重排候选列表
            id_order = {cid: i for i, cid in enumerate(parsed["ranked_ids"])}
            ranked = sorted(
                candidates,
                key=lambda c: id_order.get(c["id"], 999),
            )
            if parsed.get("reasons"):
                print(f"     排序原因:")
                for cid, reason in parsed["reasons"].items():
                    print(f"       {cid}: {reason}")
            return ranked

    # 超出轮数，返回原始顺序
    print(f"     ⚠️ 达到最大轮数，返回原始顺序")
    return candidates


# ============ Step 4: 格式化输出 ============

def format_response(ranked: List[Dict]) -> str:
    """格式化最终返回结果"""
    if not ranked:
        return "未找到匹配的货源，请稍后再试。"

    lines = ["为您推荐以下货源：\n"]
    for i, cargo in enumerate(ranked, 1):
        lines.append(
            f"  {i}. 【{cargo['id']}】{cargo['origin']}→{cargo['dest']} "
            f"| {cargo['cargo']} {cargo['weight']} "
            f"| {cargo['price']} "
            f"| {'🔴加急' if cargo['urgency'] == '加急' else '普通'}"
        )
    return "\n".join(lines)


# ============ 顶层固定工作流 ============

def static_workflow(user_input: str, max_react_rounds: int = 3, verbose: bool = True) -> dict:
    """
    顶层固定工作流（代码写死）

    Args:
        user_input: 用户输入
        max_react_rounds: 动态排序节点的最大 ReAct 轮数
        verbose: 是否打印中间过程

    Returns:
        {"fields": dict, "candidates_count": int, "response": str}
    """
    if verbose:
        print(f"\n🏗️ Static Plan + Dynamic Execution 混合模式")
        print(f"用户输入: {user_input}")
        print("=" * 60)

    # Step 1: 提取字段（确定性 + LLM 辅助）
    if verbose:
        print("\n📌 Step 1: 提取字段")
    fields = extract_fields(user_input)
    if verbose:
        print(f"   提取结果: {fields}")

    # Step 2: 检索候选（确定性）
    if verbose:
        print("\n📌 Step 2: 确定性检索匹配货源")
    candidates = deterministic_search(fields)
    if verbose:
        print(f"   匹配到 {len(candidates)} 条候选货源")

    # Step 3: 【动态执行节点】LLM 对候选做智能排序（封装 ReAct）
    if verbose:
        print("\n📌 Step 3: 动态排序（LLM 智能决策）")
    if candidates:
        ranked = dynamic_ranking_with_react(candidates, user_input, max_react_rounds)
    else:
        ranked = []

    # Step 4: 返回结果（确定性）
    if verbose:
        print("\n📌 Step 4: 格式化输出")
    response = format_response(ranked)
    if verbose:
        print(f"   {response}")

    if verbose:
        print(f"\n{'=' * 60}")
        print("✅ 混合模式执行完毕")

    return {
        "fields": fields,
        "candidates_count": len(candidates),
        "response": response,
    }


# ============ 入口 ============

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Static Plan + Dynamic Execution 混合模式（对应文章第 5.1 节）"
    )
    parser.add_argument(
        "--input", "-i",
        type=str,
        default="我需要找从北京到上海的货源，6.8米高栏车",
        help="用户输入（默认演示输入）",
    )
    parser.add_argument(
        "--max-react-rounds",
        type=int,
        default=3,
        help="动态排序节点的最大 ReAct 轮数（默认 3）",
    )
    args = parser.parse_args()

    result = static_workflow(args.input, args.max_react_rounds)
    print(f"\n📊 运行结果: {json.dumps(result, ensure_ascii=False, indent=2)}")
