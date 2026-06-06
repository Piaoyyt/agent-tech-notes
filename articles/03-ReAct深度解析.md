# ReAct 深度解析：从原理到手写实现，彻底搞懂 Agent 决策模式

> 这是「Agent技术笔记」的第三篇文章。ReAct 是绝大多数 Agent 系统的决策基石，搞懂它，后续所有框架你都能一眼看穿。

## 引子：一个真实的困惑

我第一次接触 Agent 框架的时候，最大的困惑是：

**"Agent 到底是怎么决定下一步该做什么的？"**

我理解 LLM 能生成文本，理解 Function Calling 能调用工具，但**"推理 → 行动 → 观察 → 再推理"这个循环，具体是怎么运作的？** 是 prompt 工程？是代码逻辑？还是模型训练时就学会了？

这个问题困扰了我好几天，直到我认真读了 ReAct 的论文，并且**手写了一遍实现**，才真正理解。

这篇文章，我会把你带到我理解 ReAct 的那个时刻——从论文思想，到 prompt 设计，再到完整可运行的代码实现。

读完这篇，你应该能回答两个问题：
1. ReAct 的决策循环究竟是怎么工作的？
2. 我能不能自己写一个 ReAct Agent，不依赖任何框架？

答案是：**能。**

---

## 一、ReAct 是什么（用一句话说清楚）

**ReAct = Reasoning（推理）+ Acting（行动）**

核心思想只有一句话：

> **让 LLM 在每一步先"把思考过程写出来"，再基于思考结果"决定调用哪个工具"，然后根据工具返回的结果"决定下一步做什么"。**

这听起来很自然，但在 ReAct 之前，主流做法是分开的：
- **Reasoning-only**：让模型只做推理，不调用工具（比如 Chain-of-Thought）
- **Acting-only**：让模型直接调用工具，不展示推理过程（比如传统的工具调用）

ReAct 的创新在于：**把推理和行动交织在同一个循环里**，并且把推理过程显式地展示出来。

---

## 二、ReAct 的工作循环：一步一步拆解

一个完整的 ReAct 循环包含三个步骤，不断重复：

```
Thought（思考）→ Action（行动）→ Observation（观察）
      ↑                                        |
      |________________________________________|
              根据观察结果，进入下一轮思考
```

### Step 1：Thought（思考）

LLM 根据当前任务描述和历史信息，**用自然语言写出自己的思考过程**。

比如任务是"北京今天天气怎么样，适不适合跑步？"，Thought 可能是：

> Thought: 我需要先查一下北京今天的天气，然后判断适不适合跑步。可以先调用天气查询工具。

关键点：Thought 不是给机器看的，是**给人看的**——它让 Agent 的决策过程变得**可解释、可调试**。

### Step 2：Action（行动）

基于 Thought，LLM **决定调用哪个工具，以及传入什么参数**。

继续上面的例子：

> Action: get_weather(city="北京", date="today")

关键点：Action 是结构化的，通常是一个函数名 + 参数，方便代码解析并执行。

### Step 3：Observation（观察）

系统执行 Action，得到结果，然后把结果**作为新的信息**，追加到 LLM 的上下文中。

> Observation: {"city": "北京", "date": "2026-06-06", "weather": "晴", "temperature": "28°C", "AQI": 65}

然后，LLM 基于这个 Observation，**开始新一轮的 Thought → Action → Observation**...

直到 LLM 认为信息足够，给出最终答案：

> Thought: 我已经拿到了北京的天气信息，今天晴天、28度、空气质量良好，适合跑步。
>
> Final Answer: 北京今天天气不错，晴天、28°C、空气质量良好（AQI 65），非常适合跑步！建议傍晚时段，避开中午的高温。

---

## 三、ReAct 的 Prompt 设计（这是核心）

ReAct 能不能工作好，**90% 取决于 prompt 设计**。

一个标准的 ReAct prompt 需要包含以下几个部分：

### 3.1 角色设定（Role Definition）

```
You are a helpful AI assistant that can use tools to answer questions.
You MUST think step by step before taking any action.
```

### 3.2 工具描述（Tool Descriptions）

这是最关键的部分。**工具描述的质量，直接决定了 LLM 能不能正确选择工具。**

```
You have access to the following tools:

1. get_weather(city: str, date: str) -> dict
   Get weather information for a city on a specific date.
   Example: get_weather("北京", "today")

2. search_web(query: str) -> str
   Search the web for information.
   Example: search_web("2026年端午节放假安排")

3. calculate(expression: str) -> float
   Evaluate a mathematical expression.
   Example: calculate("23 * 45")
```

**工具描述的最佳实践：**
- 写明函数的**功能**、**参数类型**、**返回值**
- 给出**具体示例**，LLM 对示例的学习效果远好于纯文字描述
- 如果工具有使用限制，一定要写清楚

### 3.3 输出格式要求（Output Format）

这是 ReAct 最精妙的设计——**用格式约束，让 LLM 的输出可被代码解析。**

```
To answer the user's question, you MUST follow this format:

Thought: [your reasoning about what to do next]
Action: [tool_name]([param1], [param2], ...)
Observation: [the result of the action]

... (this Thought/Action/Observation cycle can repeat N times) ...

Thought: [your reasoning that you now have enough information]
Final Answer: [your final answer to the user's question]
```

### 3.4 Few-shot 示例（这是秘密武器）

在 prompt 里放 1-2 个完整的 ReAct 对话示例，**效果远超千言万语的说明。**

```
Here is an example of how to use the tools:

Question: 上海明天天气怎么样，适合穿什么？

Thought: 我需要查询上海明天的天气情况，然后给出穿衣建议。
Action: get_weather("上海", "tomorrow")
Observation: {"city": "上海", "date": "2026-06-07", "weather": "小雨", "temperature": "22°C"}

Thought: 上海明天下雨，温度22度，需要带伞，穿长袖外套比较合适。
Final Answer: 上海明天有小雨，气温22°C，建议穿长袖外套，记得带伞。

Now, answer the following question:

Question: 北京今天天气怎么样，适不适合跑步？
```

---

## 四、手写一个 ReAct Agent（不依赖任何框架）

理解原理之后，最直接的学习方式就是**自己写一遍**。

下面这段代码，不依赖 LangChain 或任何 Agent 框架，只用 Python + OpenAI API，完整实现 ReAct 循环。

```python
import re
import json
import openai  # 也可以用 any LLM SDK，逻辑完全一样

# ============ 1. 定义工具 ============

def get_weather(city: str, date: str) -> dict:
    """模拟天气查询工具"""
    mock_data = {
        ("北京", "today"): {"weather": "晴", "temperature": "28°C", "AQI": 65},
        ("北京", "tomorrow"): {"weather": "多云", "temperature": "25°C", "AQI": 80},
        ("上海", "today"): {"weather": "小雨", "temperature": "22°C", "AQI": 45},
    }
    return mock_data.get((city, date), {"error": "未找到天气数据"})

def search_web(query: str) -> str:
    """模拟网络搜索工具"""
    return f"关于'{query}'的搜索结果：这是一条模拟的搜索结果。"

def calculate(expression: str) -> float:
    """计算器工具（仅用于演示，生产环境请使用 ast.literal_eval 或专用解析库）"""
    try:
        # 注意：eval 即使限制 __builtins__ 也不够安全，此处仅为教学演示
        result = eval(expression, {"__builtins__": {}}, {})
        return float(result)
    except Exception as e:
        return f"计算错误: {e}"

AVAILABLE_TOOLS = {
    "get_weather": get_weather,
    "search_web": search_web,
    "calculate": calculate,
}

# ============ 2. 构建 ReAct Prompt ============

def build_react_prompt(question: str, tool_descriptions: str, history: str) -> str:
    prompt = f"""
You are a helpful AI assistant that can use tools to answer questions.

You have access to the following tools:
{tool_descriptions}

To answer the user's question, you MUST follow this format EXACTLY:

Thought: [your reasoning about what to do next]
Action: tool_name("param1", "param2")
Observation: [will be filled by system]

(This cycle repeats until you have enough information)
Thought: [your final reasoning]
Final Answer: [your final answer to the user]

Question: {question}

{history}
""".strip()
    return prompt

# ============ 3. 解析 LLM 的输出 ============

def parse_llm_output(output: str):
    """解析 LLM 输出，提取 Thought、Action、Final Answer"""
    # 尝试提取 Final Answer
    final_answer_match = re.search(r"Final Answer:\s*(.+)", output, re.DOTALL)
    if final_answer_match:
        return {"type": "final_answer", "content": final_answer_match.group(1).strip()}

    # 尝试提取 Action
    action_match = re.search(r"Action:\s*(\w+)\((.*?)\)", output)
    thought_match = re.search(r"Thought:\s*(.+?)(?=Action:|Final Answer:|$)", output, re.DOTALL)

    if action_match:
        tool_name = action_match.group(1)
        # 简单解析参数（生产环境需要更健壮的解析）
        params_str = action_match.group(2)
        params = [p.strip().strip('"\'') for p in params_str.split(",")]
        thought = thought_match.group(1).strip() if thought_match else ""
        return {
            "type": "action",
            "thought": thought,
            "tool_name": tool_name,
            "params": params
        }

    # 如果没有 Action 也没有 Final Answer，可能是 LLM 在思考中
    return {"type": "thought_only", "content": output}

# ============ 4. ReAct 主循环 ============

def run_react_agent(question: str, max_steps: int = 5):
    """运行 ReAct Agent"""

    # 工具描述
    tool_descriptions = """
- get_weather(city: str, date: str) -> dict
  查询某城市某天的天气。date 可以是 "today" 或 "tomorrow"。
  示例: get_weather("北京", "today")

- search_web(query: str) -> str
  搜索网络信息。
  示例: search_web("2026年端午节放假安排")

- calculate(expression: str) -> float
  计算数学表达式。
  示例: calculate("23 * 45")
""".strip()

    history = ""
    conversation = []

    for step in range(max_steps):
        print(f"\n{'='*50}")
        print(f"Step {step + 1}")
        print(f"{'='*50}")

        # 构建 prompt
        prompt = build_react_prompt(question, tool_descriptions, history)

        # 调用 LLM（这里用伪代码，实际替换成你的 LLM 调用）
        # response = openai.chat.completions.create(
        #     model="gpt-4o",
        #     messages=[{"role": "user", "content": prompt}]
        # )
        # llm_output = response.choices[0].message.content

        # ---- 模拟 LLM 输出（实际使用时删除这段，换成真实 LLM 调用）----
        if step == 0:
            llm_output = """Thought: 我需要查询北京今天的天气，判断适不适合跑步。
Action: get_weather("北京", "today")"""
        elif step == 1:
            llm_output = """Thought: 北京今天晴天、28度、空气质量良好，非常适合跑步。不过28度有点热，建议傍晚跑。
Final Answer: 北京今天天气不错，晴天、28°C、空气质量良好（AQI 65），非常适合跑步！建议傍晚时段，避开中午的高温。"""
        # -------------------------------------------------------------------------

        print(f"LLM 输出:\n{llm_output}\n")

        # 解析输出
        parsed = parse_llm_output(llm_output)
        conversation.append({"step": step + 1, "output": llm_output, **parsed})

        # 如果是最终答案，结束循环
        if parsed["type"] == "final_answer":
            print(f"✅ 最终答案: {parsed['content']}")
            break

        # 如果是 Action，执行工具
        elif parsed["type"] == "action":
            tool_name = parsed["tool_name"]
            params = parsed["params"]

            if tool_name not in AVAILABLE_TOOLS:
                observation = f"错误: 工具 '{tool_name}' 不存在。"
            else:
                try:
                    tool_func = AVAILABLE_TOOLS[tool_name]
                    observation = tool_func(*params)
                except Exception as e:
                    observation = f"工具执行错误: {e}"

            print(f"🔧 调用工具: {tool_name}{params}")
            print(f"📊 观察结果: {observation}\n")

            # 把结果追加到 history 中，供下一轮使用
            history += f"\n{llm_output}\nObservation: {observation}\n\n"

        else:
            # LLM 没有按格式输出，需要引导它
            history += f"\n{llm_output}\n\nPlease follow the format: Thought → Action → Observation or Thought → Final Answer.\n"
            print("⚠️ LLM 输出格式不正确，已引导重新输出\n")

    return conversation

# ============ 5. 运行示例 ============

if __name__ == "__main__":
    question = "北京今天天气怎么样，适不适合跑步？"
    print(f"问题: {question}\n")
    run_react_agent(question)
```

### 这段代码的核心逻辑

1. **`build_react_prompt`**：每次循环都重新构建完整的 prompt，包含原始问题、工具描述和历史对话
2. **`parse_llm_output`**：用正则解析 LLM 的输出，判断是"需要调用工具"还是"已经得出最终答案"
3. **主循环**：调用 LLM → 解析输出 → 执行工具（如有）→ 把结果加回上下文 → 再次调用 LLM...
4. **终止条件**：LLM 输出 `Final Answer`，或者达到最大步数

### 运行效果（终端输出）

```
==================================================
Step 1
==================================================
LLM 输出:
Thought: 我需要查询北京今天的天气，判断适不适合跑步。
Action: get_weather("北京", "today")

🔧 调用工具: get_weather['北京', 'today']
📊 观察结果: {'weather': '晴', 'temperature': '28°C', 'AQI': 65}

==================================================
Step 2
==================================================
LLM 输出:
Thought: 北京今天晴天、28度、空气质量良好，非常适合跑步。
Final Answer: 北京今天天气不错，晴天、28°C、空气质量良好（AQI 65），非常适合跑步！

✅ 最终答案: 北京今天天气不错，晴天、28°C、空气质量良好（AQI 65），非常适合跑步！
```

---

## 五、ReAct 的局限性与改进方向

ReAct 很强大，但不是万能的。在实际工程中，我遇到过以下几个典型问题：

### 问题1：LLM 输出格式不稳定

LLM 有时会不按 `Thought → Action → Observation` 的格式输出，导致解析失败。

**解决方案：**
- 在 prompt 里加更多 few-shot 示例
- 用 JSON 格式代替自由文本格式（更易于解析）
- 解析失败时，把错误信息喂回给 LLM，让它重新输出

### 问题2：循环次数失控

LLM 可能陷入死循环——不断调用工具，但永远不给出 Final Answer。

**解决方案：**
- 设置 `max_steps` 上限（通常 5-10 步足够）
- 在 prompt 里强调"不要重复调用相同的工具"
- 记录已调用的工具历史，检测循环模式

### 问题3：工具选择错误

当工具很多时，LLM 可能选错工具，或者传错参数。

**解决方案：**
- 精简工具描述，只保留当前任务相关的工具
- 给工具加更详细的参数说明和示例
- 实现工具选择的前置过滤（根据任务描述，先用 LLM 筛选相关工具）

### 问题4：复杂任务需要多步规划

ReAct 是"走一步看一步"的模式，对于需要提前规划的任务（比如"帮我规划一个3天2晚的北京旅行"），效果不好。

**解决方案：**
- 用 **Plan-and-Execute** 模式：先让 LLM 制定完整计划，再逐步执行
- 或者用 **ReWOO**（Reason Without Observations）：先制定完整计划，再批量执行工具调用

---

## 六、从 ReAct 到生产级 Agent

看完上面的手写实现，你可能有一个疑问：

**"我知道 ReAct 怎么工作了，但生产环境里，我需要用 LangChain 或 LangGraph 吗？还是可以继续用自己写的循环？"**

我的建议是：

**学习阶段：自己写。** 手写一遍 ReAct 循环，你会理解 Agent 的所有核心机制——prompt 设计、输出解析、工具调用、上下文管理。这个理解，是你未来用任何框架的基础。

**原型阶段：用 LangChain。** 它的 `create_react_agent` 已经帮你处理好了格式解析、工具绑定、错误处理。快速验证想法时，不需要重复造轮子。

**生产阶段：LangGraph 或自研。** 当你的业务逻辑复杂到需要条件分支、循环、人工介入、状态持久化时，LangChain 的抽象可能不够用。这时候 LangGraph 的图结构会更清晰，或者你可以基于对 ReAct 手写实现的理解，设计一个更适合自己业务的框架。

**关键认知：** 框架是工具，不是魔法。理解了 ReAct 的原理，你看任何 Agent 框架的源码，都能一眼看懂它在干什么。

---

## 总结

这篇文章，我们从"Agent 怎么决策"这个疑问出发，完整走了一遍 ReAct 的：

1. **核心思想**：推理和行动交织循环
2. **工作步骤**：Thought → Action → Observation，不断重复
3. **Prompt 设计**：角色设定 + 工具描述 + 输出格式 + few-shot 示例
4. **代码实现**：不依赖任何框架，纯手写 ReAct 循环
5. **局限性**：格式不稳定、循环失控、工具选择错误、复杂任务规划能力不足

ReAct 是 Agent 技术的基石，但它不是终点。下一篇文章，我们会在这个基础上，加入 **Memory 模块**——让 Agent 能够记住过去的信息，而不只是"当下聪明"。

---

**思考题（欢迎在评论区讨论）：**

> 你在用 ReAct 或任何 Agent 框架时，遇到过 LLM 输出格式不稳定的问题吗？你是怎么解决的？

---

*如果这篇文章对你有帮助，欢迎转发。下一篇预告：《Memory 模块设计实录：如何让 Agent 记住3个月前的对话》*
