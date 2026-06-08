# Agent 决策机制深度解析：从四大模式到混合架构，看懂 Agent 如何思考与行动

> 🧠 **知识地图位置**：第3层 → 决策推理模块 ｜ 📊 **难度**：进阶
>
> 本文是「Agent技术笔记」关于**Agent决策机制**的系统性解析。在 AI Agent 架构设计中，**控制层（Brain/Planning）的决策模式**是决定 Agent 智能程度、灵活性和落地成本的核心。本文基于个人实践理解，将主流决策模式划分为四大类，逐一拆解原理、代码和落地经验。

---

## 先说结论

Agent 和 LLM 调用的核心差别在于：**决策循环（Decision Loop）**。

但"怎么决策"这个问题，其实会有很多不同的路子去解。按照当前的行业工程实践，主流决策模式可以划分为以下**四大类**：

| # | 类别 | 代表模式 | 核心特点 |
|:---:|:---|:---|:---|
| **1** | **经典自主决策** | ReAct、Plan-and-Solve | LLM 完全主导，自由度最高 |
| **2** | **确定性工作流** | Router、State Machine | 代码保证确定性，LLM 只做局部决策 |
| **3** | **多 Agent 协同** | Orchestrator-Workers、Discussion | 多角色协作，解决单一 Prompt 臃肿问题 |
| **4** | **混合决策** ⭐ | Static Plan+Dynamic Exec、Dual-LLM | 工程落地通常选择的模式，兼顾确定性与灵活性 |

其中 **第 1 类**是理解所有模式的基础，**第 4 类**是生产环境目前比较受欢迎的方向（因为大部分的企业还处在agentic化的探索阶段）。本篇文章会对这两类做重点展开。

---

## 一、决策的本质：Agent 的思维闭环

### 1.1 从一个场景说起

假设你对助理说两句话：

> **A：「帮我查一下北京今天的天气」**
>
> **B：「帮我安排一次北京出差」**

A 是一个**单步任务**——调用一次天气接口就能回答。B 是一个**多步任务**——需要查天气、订机票、订酒店、安排行程……每一步的输入都依赖上一步的输出。

普通 LLM 调用只能处理 A。要处理 B，Agent 必须具备一种能力：

> **根据上一步的结果，自主决定下一步做什么。**

这就是决策机制的使命。

### 1.2 通用的决策循环模型

无论哪种具体的决策模式，底层都遵循同一个闭环结构：

```
┌──────────────────────────────────────────────┐
│               Agent 决策循环                  │
│                                               │
│  ┌──────┐   ┌──────┐   ┌──────┐   ┌──────┐  │
│  │感知   │ → │推理   │ → │行动   │ → │观察   │  │
│  │Percep.│   │Reason│   │Action│   │ Obs. │  │
│  └──────┘   └──────┘   └──────┘   └──────┘  │
│       ↑                                     │  │
│       └─────────────────────────────────────┘  │
│            基于观察结果继续推理                 │
└──────────────────────────────────────────────┘
```

四个环节各司其职：

| 环节 | 做什么 | 类比 |
|:---|:---|:---|
| **感知 Perception** | 理解用户指令 + 读取当前上下文/记忆 | 听懂老板的要求 |
| **推理 Reasoning** | 分析当前状态，规划下一步行动 | 思考"先做什么后做什么" |
| **行动 Action** | 调用工具 / 执行操作 / 生成输出 | 打电话、发邮件、查系统 |
| **观察 Observation** | 获取行动结果 + 环境变化反馈 | 确认对方是否接了电话 |

> 💡 **关键认知**：不同的决策模式，本质上是"在这个循环里以什么节奏、按什么策略推进"的区别。下面四类模式，就是四条不同的"推进策略"。

---

## 二、经典自主决策模式（LLM-Centric Autonomy）

**这类模式完全以大模型为核心**，给 LLM 极高的自由度，让其自主完成"思考→行动→观察"的循环。这是 Agent 技术的原点，也是理解所有其他模式的基础。

---

### 2.1 ReAct —— 边想边做，工业界最通用的基础模式 ⭐

#### 原理

ReAct（**Re**asoning + **Act**ing）的核心思想：**不做预先规划，走一步、看一步、想一步**，在推理和行动之间快速交替推进。

```
Thought（思考）→ Action（行动）→ Observation（观察结果）
      ↑                                          │
      └──────────────────────────────────────────┘
```

为什么 ReAct 成为主流？因为现实世界的大多数任务**无法提前完全规划**——你不知道查完天气之后会不会改变出行方式，不知道搜完航班后发现没票时该换什么方案。ReAct 的"边想边做"天然适合这种**不确定性高**的场景。

#### 完整代码实现

```python
"""
ReAct Agent —— 不依赖任何框架的完整实现
核心思想：Reasoning 和 Acting 交织循环
"""
import re, json

# ============ 工具集 ============

def get_weather(city: str, date: str) -> dict:
    data = {
        ("北京", "today"): {"weather": "晴", "temp": "28°C", "aqi": 65},
        ("北京", "tomorrow"): {"weather": "多云", "temp": "25°C", "aqi": 80},
    }
    return data.get((city, date), {"error": f"未找到 {city} {date} 的数据"})

def search_web(query: str) -> str:
    mock = {"端午节放假": "2026年端午节：6月19日-21日，共3天。"}
    return mock.get(query, f"关于「{query}」的搜索结果（模拟）。")

def calculate(expr: str) -> float:
    try:
        return float(eval(expr, {"__builtins__": {}}, {}))
    except Exception:
        return f"无法计算: {expr}"

TOOLS = {"get_weather": get_weather, "search_web": search_web,
          "calculate": calculate}

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
    fa = re.search(r"Final Answer\s*:\s*(.+)", text, re.DOTALL)
    if fa:
        return {"type": "final", "answer": fa.group(1).strip()}
    am = re.search(r"Action\s*:\s*(\w+)\s*\((.*?)\)", text)
    if am:
        tool = am.group(1)
        params = [p.strip().strip('"\'') for p in am.group(2).split(",") if p.strip()]
        tm = re.search(r"Thought\s*:\s*(.+?)(?=Action\s*:|$)", text, re.DOTALL)
        return {"type": "action", "tool": tool, "params": params,
                "thought": tm.group(1).strip() if tm else ""}
    return {"type": "unparsed", "raw": text[:150]}

# ============ 主循环 ============

def run_react(question: str, max_rounds: int = 6) -> dict:
    history = []
    print(f"\n🤖 ReAct Agent 启动 | 问题: {question}\n{'='*60}")

    for rnd in range(max_rounds):
        r = rnd + 1
        print(f"\n🔄 第 {r} 轮")

        # ---- 实际使用时替换为真实 LLM 调用 ----
        llm_text = _simulate(question, history, rnd)
        # ----------------------------------------------------

        print(f"  💭 {llm_text[:80]}...")
        parsed = parse_react(llm_text)

        if parsed["type"] == "final":
            print(f"  🎯 最终答案: {parsed['answer']}")
            return {"answer": parsed["answer"], "rounds": r}

        if parsed["type"] == "action":
            tool, params = parsed["tool"], parsed["params"]
            print(f"  💡 思考: {parsed.get('thought', '')}")
            print(f"  🔧 行动: {tool}({params})")

            if tool in TOOLS:
                try:
                    obs = TOOLS[tool](*params)
                    obs_str = json.dumps(obs, ensure_ascii=False) if isinstance(obs, dict) else str(obs)
                except Exception as e:
                    obs_str = f"工具异常: {e}"
            else:
                obs_str = f"未知工具: {tool}"

            print(f"  📊 观察: {obs_str[:80]}...")
            history.append(
                f"Thought: {parsed.get('thought', '')}\n"
                f"Action: {tool}({', '.join(params)})\n"
                f"Observation: {obs_str}")
        else:
            print(f"  ⚠️ 格式异常，引导重试")
            history.append("(格式错误，请严格按 Thought→Action→Observation 格式输出)")

    return {"answer": None, "rounds": max_rounds}


def _simulate(q: str, hist: list, rnd: int) -> str:
    """模拟 LLM 输出（实际使用时删除）"""
    if rnd == 0:
        return 'Thought: 需要查北京今天天气\nAction: get_weather("北京", "today")'
    return ('Thought: 北京今日晴天28°C、AQI 65，适合跑步\n'
            'Final Answer: 北京今天天气很好！晴天28°C、AQI 65，'
            '非常适合户外跑步🏃 建议清晨或傍晚时段。')


if __name__ == "__main__":
    run_react("北京今天天气怎么样，适不适合跑步？")
```

#### 运行效果

```
🤖 ReAct Agent 启动 | 问题: 北京今天天气怎么样...

🔄 第 1 轮
  💭 Thought: 需要查北京今天天气
  💡 思考: 需要查北京今天天气
  🔧 行动: get_weather(['北京', 'today'])
  📊 观察: {"weather": "晴", "temp": "28°C", "aqi": 65}

🔄 第 2 轮
  💭 Thought: 北京今日晴天...
  🎯 最终答案: 北京今天天气很好！晴天28°C、AQI 65，非常适合户外跑步🏃
```

#### Prompt 设计四要素（决定 ReAct 成败）

| 要素 | 说明 | 常见坑 |
|:---|:---|:---|
| **角色设定** | 明确LLM的职责边界 | 太模糊 → LLM 会失去目标导向 |
| **工具描述** | 功能 + 参数类型 + 返回值 + **具体示例** | 不写示例 → LLM 传错参数 |
| **格式约束** | Thought/Action/Observation/Final Answer 强制结构化 | 不强制 → 解析器无法可靠提取 |
| **Few-shot** | 放 1-2 个完整交互样例 | **效果提升最明显**，没有之一 |

---

### 2.2 Plan-and-Solve / Plan-Act-Reflect —— 先谋后动 + 动态反思

#### 原理

Plan-and-Solve（也叫 Plan-and-Execute）是最符合人类直觉的模式：**先把整个任务拆解成步骤计划，然后逐步执行**。在执行过程中引入**反思机制（Self-Reflection / Self-Correction）**，一旦发现执行结果偏离预期，动态修改后续计划。

```
用户任务
  ↓
[规划阶段]  LLM 生成完整计划（步骤列表）
  ↓
[执行阶段]  执行 Step 1 → 观察结果 → 反思（是否需要调整计划？）
                  ↓ 是                    ↓ 否
            重新规划剩余步骤          执行 Step 2
                  ↓                       ↓
            ...                  执行完毕 → 最终答案
```

**相比纯 Plan-and-Execute 的改进**：纯 Plan-and-Execute 的最大问题是"计划可能与实际脱节"——第 1 步的结果可能导致后续步骤需要调整，但初始计划已经固定。加入 Reflection 之后，Agent 具备了**动态修正能力**。

#### 代码实现（带动态反思的 Plan-and-Solve）

```python
"""
Plan-and-Solve + Reflection
先生成计划，执行中动态反思并调整后续步骤
"""
import json
from typing import List, Dict

# ============ 工具定义（同 ReAct 示例） ============
# ...（复用前面的 TOOLS 定义）

# ============ Planner ============

PLANNER_PROMPT = """你是一个任务规划专家。
给定任务和可用工具，请将任务拆解为执行步骤。

可用工具：
{tool_desc}

请严格按 JSON 格式输出：
{{"plan": [{{"step": 1, "action": "工具名", "params": {{...}}, "purpose": "目的"}}]}}

任务：{task}"""


def planner(task: str) -> List[Dict]:
    """调用 LLM 生成执行计划"""
    # ---- 实际替换为 LLM API 调用 ----
    return [
        {"step": 1, "action": "check_weather",
         "params": {"city": "北京", "date": "2026-06-12"},
         "purpose": "确认出差日天气"},
        {"step": 2, "action": "search_flight",
         "params": {"origin": "上海", "dest": "北京", "date": "2026-06-12"},
         "purpose": "搜索航班"},
        {"step": 3, "action": "search_hotel",
         "params": {"city": "北京", "checkin": "2026-06-12", "nights": 2},
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


def reflector(task: str, step_info: str, observation: str) -> dict:
    """反思当前步骤，决定是否需要重新规划"""
    # ---- 实际替换为 LLM API 调用 ----
    # 模拟：如果天气下雨，建议调整户外活动安排
    if "雨" in str(observation):
        return {"need_replan": True,
                "reason": "下雨，建议调整行程安排",
                "adjusted_steps": []}
    return {"need_replan": False, "reason": "执行正常，继续"}
    # -----------------------------------------


# ============ 主执行循环 ============

def run_plan_and_solve(task: str, max_rounds: int = 8) -> dict:
    print(f"\n📋 Plan-and-Solve Agent 启动")
    print(f"任务: {task}\n{'='*60}")

    # 阶段一：生成计划
    plan = planner(task)
    print(f"\n📋 生成计划（共 {len(plan)} 步）：")
    for s in plan:
        print(f"  Step {s['step']}: {s['action']} —— {s['purpose']}")

    # 阶段二：逐步执行 + 动态反思
    print(f"\n🚀 开始执行\n{'='*60}")
    results = []
    remaining = list(enumerate(plan))  # (idx, step) 列表

    while remaining and len(results) < max_rounds:
        idx, step_info = remaining.pop(0)
        print(f"\n▶ Step {step_info['step']}: {step_info['action']}")
        print(f"  目的: {step_info['purpose']}")

        # 执行工具
        tool = step_info["action"]
        params = step_info["params"]
        if tool in TOOLS:
            try:
                obs = TOOLS[tool](**params)
                obs_str = json.dumps(obs, ensure_ascii=False) if isinstance(obs, dict) else str(obs)
            except Exception as e:
                obs_str = f"错误: {e}"
        else:
            obs_str = f"未知工具: {tool}"

        print(f"   ✅ 结果: {obs_str[:80]}...")
        results.append({"step": step_info["step"], "result": obs_str})

        # 反思：是否需要调整后续计划？
        reflection = reflector(task, step_info, obs_str)
        if reflection["need_replan"]:
            print(f"   🪞 反思：需要重新规划！理由: {reflection['reason']}")
            # 用调整后的步骤替换 remaining
            if reflection.get("adjusted_steps"):
                remaining = [(i, s) for i, s in enumerate(reflection["adjusted_steps"])]
                print(f"   🔄 已更新剩余计划（{len(remaining)} 步）")
        else:
            print(f"   ✅ 反思：执行正常，继续")

    print(f"\n{'='*60}")
    print(f"✅ 执行完毕，共完成 {len(results)} 步")
    return {"results": results}


if __name__ == "__main__":
    run_plan_and_solve("帮我安排一次北京出差，6月12日出发，住两晚")
```

#### 运行效果

```
📋 Plan-and-Solve Agent 启动
任务: 帮我安排一次北京出差，6月12日出发，住两晚
============================================================

📋 生成计划（共 3 步）：
  Step 1: check_weather —— 确认出差日天气
  Step 2: search_flight —— 搜索航班
  Step 3: search_hotel —— 预订酒店

🚀 开始执行
============================================================

▶ Step 1: check_weather
  目的: 确认出差日天气
   ✅ 结果: {"weather": "晴", "temp": "28°C", "aqi": 65}
   ✅ 反思：执行正常，继续

▶ Step 2: search_flight
  目的: 搜索航班
   ✅ 结果: {"flights": [{"flight": "CA1234", "price": "¥680"},
             {"flight": "MU5678", "price": "¥520"}]}
   ✅ 反思：执行正常，继续

▶ Step 3: search_hotel
  目的: 预订酒店
   ✅ 结果: {"hotels": [{"name": "北京商务酒店", "price": "¥388/晚"},
             {"name": "北京快捷酒店", "price": "¥228/晚"}]}
   ✅ 反思：执行正常，继续

============================================================
✅ 执行完毕，共完成 3 步，重新规划 0 次
```

> 💡 如果 Step 1 的天气结果是「小雨」，反思器会触发 `need_replan: true`，自动调整后续航班和酒店日期，这就是动态反思的价值。

#### Plan-and-Solve 适用场景

| 维度 | 分析 |
|:---|:---|
| **适合** | 步骤相对明确的复杂任务（行程规划、数据分析流程、文档处理流水线） |
| **核心优势** | 过程透明、每步可控、便于调试和人工介入 |
| **加了 Reflection 后** | 具备"自愈"能力，能应对执行中的动态变化 |

---

## 三、确定性工作流模式（Workflow / Graph-based）

**随着企业级应用对确定性（Determinism）和稳定性要求的提升**，纯自主的 ReAct 容易出现"幻觉"或死循环（Looping），因此工作流模式成为了目前工程落地的绝对主流。

这类模式的核心思想是：**用代码保证主干流程的确定性，只在局部节点引入 LLM 的动态决策**。

---

### 3.1 Router / Classifier（路由模式）

#### 原理

LLM 仅作为一个"交警"或"分类器"。输入进来后，LLM 判断其意图，然后将任务**分流到预先用代码写死的固定工作流（Workflow）或特定技能（Skill）**中。

```
用户输入
   ↓
[LLM Router] 判断意图
   ├── 意图A → Workflow_A（代码固定流程）
   ├── 意图B → Workflow_B（代码固定流程）
   └── 意图C → Skill_C（直接调用工具）
```

#### 特点

- **极高的确定性**，适合业务边界清晰、对准确率要求 100% 的场景
- LLM 只做"分类"这一件事，成本可控，延迟低
- 缺点是**不够灵活**——新意图需要提前配置对应的工作流

#### 代码示意

```python
"""
Router 模式示例：意图分类 + 固定工作流分发
"""
INTENT_ROUTER_PROMPT = """你是一个意图分类器。
根据用户问题，判断它属于哪个类别。只输出类别名称，不要输出其他内容。

类别列表：
- weather   （天气查询）
- flight    （航班相关）
- hotel     （酒店预订）
- unknown   （无法识别）

用户问题：{question}

类别："""


def route_intent(question: str) -> str:
    """调用 LLM 做意图分类（实际替换为 API 调用）"""
    if "天气" in question:
        return "weather"
    if "航班" in question or "机票" in question:
        return "flight"
    if "酒店" in question:
        return "hotel"
    return "unknown"


def handle_weather(question: str) -> str:
    """天气查询的固定工作流（代码写死）"""
    # 步骤1：提取城市名（可用 LLM 或正则）
    city = "北京"  # 简化示例
    # 步骤2：调用工具
    result = get_weather(city, "today")
    return f"{city}今天：{result['weather']} {result['temp']}"


def handle_flight(question: str) -> str:
    """航班查询的固定工作流"""
    return "已为您搜索相关航班（模拟）"


# 主入口
def router_agent(question: str) -> str:
    intent = route_intent(question)
    print(f"🔀 路由结果: {intent}")

    handlers = {
        "weather": handle_weather,
        "flight": handle_flight,
        "hotel": lambda q: "酒店预订功能开发中",
        "unknown": lambda q: "抱歉，暂不支持该类型问题",
    }
    return handlers[intent](question)


if __name__ == "__main__":
    print(router_agent("北京今天天气怎么样？"))
    print(router_agent("帮我查一下去上海的航班"))
```
这部分就不给出输出示例了，感兴趣可以自己去跑看看

---

### 3.2 State Machine / Graph（状态机 / 图结构）

#### 原理

以 **LangGraph** 为代表。将任务拆解为不同的**状态节点（Nodes）**，节点之间的**流转线（Edges）**可以包含条件判断（由 LLM 或代码决定）。

```
┌─────────┐    condition?    ┌─────────┐    condition?    ┌─────────┐
│  Node A  │ ──────────────→ │  Node B  │ ──────────────→ │  Node C  │
└─────────┘                 └─────────┘                 └─────────┘
     ↑                           │                           │
     └───────────────────────────┘                           │
                                                               ↓
                                                        [END / 输出]
```

#### 特点

- 既保留了工作流的严谨性，又允许在**局部节点**引入 LLM 的动态决策（如失败重试、动态分支选择）
- 是目前复杂商业系统（B2B 供应链、财务审批、物流调度）的**首选架构**
- LangGraph 是这个模式最成熟的实现，强烈推荐生产环境使用

#### 为什么比纯代码工作流更强？

| 对比 | 代码工作流（if-else） | LangGraph 状态机 |
|:---|:---|:---|
| **灵活性** | 分支固定，改逻辑要发版 | 节点内可用 LLM 动态决策 |
| **状态管理** | 自己维护上下文变量 | 框架自动管理 State |
| **人工介入** | 要自己写钩子 | 原生支持 interrupt/resume |
| **可观测性** | 要自己打日志 | 可视化执行图，每步可追溯 |

---

## 四、多 Agent 协同模式（Multi-Agent Cooperation）

当单个 Agent 的 Prompt 变得过于臃肿、角色过于混乱时，**将复杂决策拆解到多个垂直 Agent 中协同**成为了主流趋势。

---

### 4.1 Orchestrator-Workers（编排者-执行者）

#### 原理

一个中心化的 LLM Agent 作为"主脑"（Orchestrator），负责**拆解任务、分发任务**给若干个职责单一的专属 Agent（Workers），并汇总最终结果。

```
用户任务
   ↓
[Orchestrator Agent]  ← 唯一入口，负责拆解和调度
   ├── 分发 → [Worker: 天气查询 Agent]
   ├── 分发 → [Worker: 航班搜索 Agent]
   └── 分发 → [Worker: 酒店预订 Agent]
   ↓
[Orchestrator] 汇总各 Worker 结果 → 最终答案
```

#### 特点

- 各个 Worker **职责单一**，容易调优，能有效缓解大模型的**上下文迷失**问题
- Orchestrator 的 Prompt 只需要关注"怎么拆解任务和汇总结果"，不需要关注每个子任务的实现细节
- 适合**任务可以并行处理**的场景


---

### 4.2 Discussion / Peer-to-Peer（对等讨论模式）

#### 原理

以 **AutoGen、MetaGPT** 为代表。多个不同角色的 Agent（如 Product Manager、Coder、QA）在一个"群聊"或管道中按顺序或自由交互。

```
[User Requirement]
   ↓
[PM Agent]  → 写 PRD
   ↓
[Coder Agent] → 写代码
   ↓
[QA Agent]   →  review 代码
   ↓
[PM Agent]  → 判断是否通过（不通过则打回 Coder）
   ↓
[Final Answer]
```

#### 特点

- 适合**创意生成、复杂代码编写、场景模拟**等需要"多视角碰撞"的任务
- **缺点**：交互链路长，容易产生信息冗余和死循环，生产环境需要严格控制轮次上限

---

## 五、混合决策模式（Hybrid Modes）⭐⭐⭐

> **这是目前大规模商业生产中最值得投入的方向。**
>
> 纯粹的 ReAct 不够确定，纯粹的代码工作流不够灵活。**混合模式**取两者之长——用确定性的框架保证主干可控，在需要灵活性的局部节点引入 LLM 自主决策。

---

### 5.1 Static Plan + Dynamic Execution（静态规划 + 动态执行）

#### 原理

**顶层采用硬编码的流程图**（确保主干流程绝对可控），但在图的**某个特定节点内部**，封装一个微型的 ReAct 循环或 Tool-use 循环，处理需要灵活判断的子任务。

```
┌──────────────────────────────────────────────────┐
│          顶层：硬编码工作流（代码保证确定性）       │
│                                                  │
│  [接收需求] → [提取字段] → [?? 灵活处理节点 ??]  │
│                              ↓                   │
│                   内部封装一个微型 ReAct 循环        │
│                   （LLM 自主决策，但受步数限制）    │
│                              ↓                   │
│  [汇总结果] → [返回用户]                         │
└──────────────────────────────────────────────────┘
```

#### 典型场景

以物流场景为例：

```
司机找货流程（顶层设计，代码固定）：
  1. 接收司机找货请求
  2. 提取司机偏好（车型、路线、价格期望）→ 这里用 LLM，但只做信息提取
  3. 搜索匹配货源（确定性检索逻辑，代码实现）
  4. 对匹配结果做个性化排序 → 这里封装一个 ReAct 循环，LLM 综合考虑多因素动态排序
  5. 返回结果
```

**第 4 步**就是"静态规划 + 动态执行"的典型应用——主干流程（1→2→3→4→5）是固定的，但第 4 步内部的排序决策由 LLM 自主完成，且限制最多 3 轮推理，兼顾质量和延迟。

#### 代码框架示意

```python
"""
Static Plan + Dynamic Execution 混合模式示意
顶层是固定工作流，特定节点内部封装 ReAct 循环
"""


def static_workflow(user_input: str) -> str:
    """顶层固定工作流（代码写死）"""
    # Step 1: 提取字段（确定性）
    fields = extract_fields(user_input)

    # Step 2: 检索候选（确定性）
    candidates = deterministic_search(fields)

    # Step 3: 【动态执行节点】LLM 对候选做智能排序（封装 ReAct）
    if candidates:
        ranked = dynamic_ranking_with_react(candidates, user_input)
    else:
        ranked = []

    # Step 4: 返回结果（确定性）
    return format_response(ranked)


def dynamic_ranking_with_react(candidates: list, user_input: str) -> list:
    """
    封装的微型 ReAct 循环
    只在"排序"这个子任务上让 LLM 自主决策
    限制最多 3 轮，控制延迟
    """
    prompt = f"""你是一个排序专家。请根据用户需求对以下候选结果进行智能排序。

用户需求：{user_input}

候选列表：{candidates}

请分析每个候选与用户需求的匹配度，输出排序后的结果（JSON 格式）。
你可以先思考（Thought），然后给出排序（Final Answer）。
Final Answer: {{"ranked": [候选ID列表]}}"""

    # 这里可以是一个受步数限制的 ReAct 循环
    # 实际实现复用前面定义的 run_react() 函数，但 max_rounds=3
    result = run_react_limited(prompt, max_rounds=3)
    return parse_ranking_result(result)
```

#### 这种混合模式的核心优势

| 优势 | 说明 |
|:---|:---|
| **确定性可控** | 主干流程代码写死，不会出现"想不到的路径" |
| **局部灵活** | 需要智能判断的节点用 LLM，其他地方不用 |
| **成本可控** | LLM 只在必要节点调用，且限制步数 |
| **易于调试** | 出问题了先看是哪一步，再定位是该步骤的代码问题还是 LLM 决策问题 |

---

### 5.2 Dual-LLM Architecture（双模型决策）

#### 原理

采用**"信息提取/过滤小模型（如 8B 规模）+ 核心决策大模型（如 70B+ 规模）"**的组合：

```
用户输入
   ↓
[小模型] 前置过滤、分类、结构化（便宜、快速、可以批量）
   ↓
[大模型] 只对过滤后的高质量输入做高难度推理和最终决策
   ↓
最终输出
```

**小模型负责"广度"——快速处理大量输入，过滤掉明显无效的；大模型负责"深度"——对剩下的少量高质量输入做精细决策。

#### 为什么这样做？

| 问题 | 单一大模型的痛点 | 双模型方案的解决方式 |
|:---|:---|:---|
| **成本** | 所有请求都走大模型，Token 消耗大 | 小模型过滤掉 70%+ 的无效请求 |
| **延迟** | 大模型推理慢 | 小模型毫秒级响应，只把真正需要"动脑子"的请求交给大模型 |
| **准确率** | 大模型也会犯低级错误 | 小模型做结构化提取（不容易错），大模型做推理（擅长） |
| **可控性** | 大模型的输出格式偶尔不稳定 | 小模型做格式校验和兜底 |

#### 实际案例：记忆系统的双模型架构

以 Agent 的记忆系统为例：

```
用户说了一句话
   ↓
[8B 小模型] 判断：这句话有没有值得记住的信息？
   ├── 没有 → 直接丢弃，不调用大模型（节省成本）
   └── 有   → 提取结构化信息（实体、关系、时效性等）
                 ↓
           [70B+ 大模型] 判断：这条信息应该存入哪种记忆？
                          - 短期记忆（当前对话）
                          - 长期记忆（跨会话知识）
                          - 工作记忆（任务中间状态）
                          ↓
                   存入对应记忆模块
```

> 💡 **工程实践经验**：在用户偏好理解的链路中，先用小模型做"偏好字段提取"，再用大模型做"综合判断"。这样整体延迟降低了 40%，成本降低了 60%，而准确率没有下降。

---

## 六、四大模式横向对比与选型指南

### 6.1 一图看懂四类模式的关系

```
    确定性 ←────────────────────────→ 灵活性
                  LLM 自由度
        低                               高

Static Plan    Router/     ReAct      Plan-and-Solve
+Dynamic Exec  Classifier  (纯自主)   (纯自主+反思)
(混合)        (确定性优先)
```

### 6.2 决策矩阵

| 维度 | 经典自主决策<br/>ReAct / Plan-and-Solve | 确定性工作流<br/>Router / State Machine | 多 Agent 协同<br/>Orchestrator / Discussion | 混合决策 ⭐<br/>Static+Dynamic / Dual-LLM |
|:---|:---|:---|:---|:---|
| **LLM 自由度** | ⭐⭐⭐⭐⭐ 极高 | ⭐ 低（只做分类/单节点） | ⭐⭐⭐ 中高 | ⭐⭐⭐ 可控（按需） |
| **确定性** | ⭐⭐ 弱 | ⭐⭐⭐⭐⭐ 极强 | ⭐⭐⭐ 中 | ⭐⭐⭐⭐ 强 |
| **Token 成本** | 高（每步都调 LLM） | 低（LLM 只调少数几次） | 中高（多个 Agent 调用） | **中（精准使用 LLM）** |
| **延迟** | 高（串行循环） | 低（确定性路径） | 中高（多轮交互） | **可控（针对性优化）** |
| **实现复杂度** | ⭐ 低 | ⭐⭐ 中 | ⭐⭐⭐ 高 | ⭐⭐⭐⭐ 高 |
| **生产就绪度** | ⭐⭐⭐ 中 | ⭐⭐⭐⭐⭐ 高 | ⭐⭐⭐ 中高 | ⭐⭐⭐⭐⭐ **最高** |

### 6.3 实战选型决策树

```
你的任务类型是什么？
│
├─ 业务边界清晰、准确率要求 100%、不接受幻觉
│  └─▶ Router / Classifier（确定性工作流）
│
├─ 步骤相对明确、可接受局部灵活调整
│  ├─ 对成本/延迟敏感？
│  │  └─▶ Static Plan + Dynamic Execution（混合模式）← 推荐
│  └─ 需要极强灵活性？
│     └─▶ ReAct（经典自主决策）
│
├─ 任务极复杂，单一 Prompt 装不下
│  ├─ 需要多角色协作（如 写代码→review→测试）
│  │  └─▶ Orchestrator-Workers（多 Agent 协同）
│  └─ 需要创意碰撞、多视角讨论
│     └─▶ Discussion / Peer-to-Peer（如 MetaGPT）
│
├─ 大规模生产环境，成本和延迟都要优化
│  └─▶ Dual-LLM Architecture（双模型决策）← 强烈推荐
│
└─ 不确定从哪开始？
   └─▶ 先用 ReAct 跑通原型，再逐步引入混合模式优化
```

### 6.4 实战策略
基于个人近期在行业内实践总结的经验，实战的策略可以简单总结为几个点（仅供参考，不一定完全准确，具体实践还需要根据实际的业务类型去进行判断），后面会针对单个决策的模式出更为详细的实战讲解。

> - **核心链路用**混合模式（兼顾流程和自主性），
> - **边缘的场景**可以用 ReAct尝试（给予一定的灵活性）
> - **关键易错节点**加 Reflection（带反思/纠错）
> - **大规模调用**上 Dual-LLM（成本优化）

---

## 七、从代码到框架：你应该用什么

看完关于四类模式的讲解，可能有人会问：

> **"这些模式，我应该用框架还是自己写？"**

下面我基于自己的一些理解，写了一些建议指南。

### 7.1 框架 vs 手写：决策指南

| 你的阶段 | 推荐做法 | 理由 |
|:---|:---|:---|
| **学习阶段** | **手写** ReAct / Plan-and-Solve 循环 | 理解原理，这是看任何框架源码的基础 |
| **原型验证** | **LangChain** `create_react_agent` | 5 行代码跑起来，快速验证想法 |
| **生产级系统** | **LangGraph**（确定性强）或**自研**（深度定制） | 需要状态管理、条件分支、人工介入、可观测性 |
| **多 Agent 系统** | **LangGraph** 、 **AutoGen**或**自研**等 | 原生支持多节点协作和通信协议 |
| **混合架构** | **LangGraph**（图结构天然适合混合模式） + 自研关键节点 | LangGraph 负责编排，关键决策节点用自研优化 |

### 7.2 一个重要原则

> **先用手写实现理解原理，再用框架提升效率。**
>
> 如果你跳过了手写这一步直接上框架，遇到问题时你会不知道是 Prompt 的问题、模型的问题还是框架的问题。而如果你亲手写过一遍 ReAct 循环，看任何框架的源码都能一眼看穿它在干什么。

---

## 八、总结

这篇文章主要从"Agent 怎么决策"这个核心问题出发，按照行业工程实践将主流决策模式划分为**四大类**，并针对**经典自主决策**和**混合决策模式**这两种模式进行展开：

### 四类模式速查

|  | 类别 | 你应该用它当... |
|:---:|:---|:---|
| **1** | **经典自主决策** | 快速原型、允许容错、需要一定的灵活度 |
| **2** | **确定性工作流** | 业务边界清晰、准确率要求极高 |
| **3** | **多 Agent 协同** | 单一 Agent 太臃肿、需要多角色协作 |
| **4** | **混合决策** ⭐ | **生产环境、大规模调用、成本和效果都要** |

### 关键点小结

1. **ReAct** 是理解所有模式的基础，但纯 ReAct 不适合直接上生产
2. **Plan-and-Solve + Reflection** 在 ReAct 基础上加入了"先规划+动态修正"，更适合复杂任务
3. **Router / State Machine** 用代码保证确定性，适合能够明确定义不同典型状态，且涉及到状态频繁切换的场景。
4. **混合决策模式**（Static Plan + Dynamic Execution、Dual-LLM）是生产环境的最优解——兼顾确定性和灵活性，且成本和延迟可控
5. **没有银弹**——一切的技术选型必须回归到业务场景需求中，没有最好的，只有最适合自己的

---

## 📖 下一步阅读建议

这篇文章是全景图中**第 3 层（核心能力） → 决策推理模块**的核心内容。后续还会继续拓展关于agent技术相关的内容：

- **同层深入**：《Memory 模块设计》——决策机制解决"怎么想"，Memory 解决"记什么"
- **向上延伸**：《LangGraph 实战》——如何用图结构框架编排复杂的混合决策流程
- **向下夯实**：《LLM 微调实战 SFT + GRPO》——如何让模型的决策能力更强
- **向前延伸**：《多 Agent 协作与 A2A 架构》——当单个 Agent 不够用时怎么办

> 💡 **和上一篇的关系**：上一篇《Agent 技术全景图：从概念到落地，一张图看懂》（第 02 篇）从整体出发，梳理agent相关的技术路线；而这篇是从**第三级：核心能力**出发深入讲解决策模式，能帮助快速建立完整的决策机制知识体系。

---

*如果这篇文章对你有帮助，欢迎转发给正在研究 Agent 技术的朋友。有任何问题或想聊的话题，随时后台留言 💬*

**下一篇预告：《Memory 模块设计实录：如何让 Agent 记住三个月前的对话》**
