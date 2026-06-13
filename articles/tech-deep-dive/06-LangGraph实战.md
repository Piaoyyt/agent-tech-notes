# LangGraph 实战：用图结构框架搭建生产级 Agent

> 🏗️ **知识地图位置**：第4层 → Agent 系统框架 ｜ 📊 **难度**：进阶
>
> 这是「Agent技术笔记」的第六篇文章。前三篇核心能力模块（决策推理、记忆管理、工具调用）讲完后，很多朋友问：**这些模块我都理解了，但怎么把它们"组装"成一个真正能跑的 Agent？** 这篇就是答案——LangGraph。

---

## 先说结论

LangGraph 解决的核心问题只有一个：

> **复杂 Agent 的状态管理和流程控制，用线性链式调用根本 Hold 不住。**

LangChain 的 LCEL（链式调用）非常适合「输入→处理→输出」的线性场景。但一旦你的 Agent 需要**条件分支**（这一步成功走 A，失败走 B）、**循环迭代**（ReAct 的推理-行动-观察循环）、**并行执行**（同时查多个数据源）、**状态持久化**（支持断点续跑、Human-in-the-Loop），线性链就开始捉襟见肘。

LangGraph 用一个根本性的设计转变解决了这个问题：**把 Agent 的执行流程，建模成一个有向图（Directed Cyclic Graph）。**

---

## 一、为什么是图？从 DAG 到 DCG 的跃迁

先做一个关键对比：

| 框架 | 图结构 | 能力边界 |
|:---|:---|:---|
| **LangChain LCEL** | DAG（有向无环图）| 线性流程、简单链式调用 |
| **LangGraph** | DCG（有向循环图）| 循环迭代、条件分支、并行执行 |

为什么循环（Cyclic）这么重要？

因为 **ReAct 本身就是一个循环**：推理 → 调用工具 → 观察结果 → 再推理 → 再调用工具……直到得出最终答案。用 DAG 表达这个流程，你只能把循环"展开"成固定步数——但你提前不知道 Agent 需要循环几次。

LangGraph 的 DCG 天然支持这种「循环直到条件满足」的语义，这才是它和普通链式调用框架的本质区别。

```
LangChain（DAG）：        LangGraph（DCG）：
A → B → C → D            ┌──────────┐
（不能回头）               │  agent   │◄──┐
                          └────┬─────┘   │
                    有工具调用  │         │
                          ┌────▼─────┐   │
                          │  tools   │───┘
                          └──────────┘
                    无工具调用 → END
```

---

## 二、LangGraph 的三个核心原语

理解 LangGraph，只需要掌握三个概念：**State（状态）、Node（节点）、Edge（边）**。

### 2.1 State：贯穿全程的「共享内存」

State 是整个图执行过程中的**共享数据容器**，你可以理解为 Agent 的「工作台」——所有节点都从这里读数据、往这里写数据。

```python
from typing import TypedDict, List, Annotated
import operator

class AgentState(TypedDict):
    messages: Annotated[List, operator.add]  # 对话历史（追加模式）
    user_query: str                           # 用户输入
    final_answer: str                         # 最终答案
    retry_count: int                          # 重试次数（用于流程控制）
```

> 💡 **两个实用细节**
>
> **① 用 `Annotated[List, operator.add]`** 而不是普通 `List`。这是 LangGraph 的「状态归约器」机制——当多个并行节点同时更新同一个字段时，`operator.add` 会自动合并（追加），而不是互相覆盖。
>
> **② 推荐 TypedDict**，方便 IDE 类型检查；需要运行时数据校验时换 Pydantic BaseModel，两者可以混用。

### 2.2 Node：执行逻辑的「最小单元」

Node 就是一个 Python 函数，接收当前 State，返回需要更新的字段。

```python
from langchain_openai import ChatOpenAI

model = ChatOpenAI(model="gpt-4o", temperature=0).bind_tools(tools)

def call_agent(state: AgentState) -> AgentState:
    """Agent 节点：调用 LLM 进行推理"""
    messages = state["messages"]
    response = model.invoke(messages)
    return {"messages": [response]}  # 只返回需要更新的字段，LangGraph 自动合并
```

> 💡 **节点只需要返回「要更新的部分」**，不需要返回完整状态。LangGraph 会自动把返回值 merge 进当前 State。

### 2.3 Edge：控制流程走向的「路由器」

Edge 分两种：

**① 普通边**：无条件跳转
```python
graph.add_edge("tools", "agent")  # tools 执行完，总是回到 agent
```

**② 条件边**：根据 State 动态路由
```python
def should_continue(state: AgentState) -> str:
    """判断下一步：继续调用工具，还是结束"""
    last_message = state["messages"][-1]
    if last_message.tool_calls:
        return "tools"   # 有工具调用 → 执行工具
    return "end"         # 无工具调用 → 结束

graph.add_conditional_edges("agent", should_continue, {
    "tools": "tools",
    "end": END
})
```

这三个原语组合在一起，就能描述任意复杂的 Agent 执行逻辑。

---

## 三、从零搭一个 ReAct Agent

把三个原语组合起来，用最少的代码实现一个完整的 ReAct Agent：

```python
from langgraph.graph import StateGraph, END, START, MessageState
from langgraph.prebuilt import ToolNode
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool

# ① 定义工具
@tool
def search_cargo(origin: str, destination: str) -> str:
    """搜索从出发地到目的地的货源信息"""
    # 实际调用货源搜索 API
    return f"找到 23 条从{origin}到{destination}的货源，均价 ¥3,200"

tools = [search_cargo]
tool_node = ToolNode(tools)

# ② 初始化 LLM 并绑定工具
model = ChatOpenAI(model="gpt-4o", temperature=0).bind_tools(tools)

# ③ 定义节点
def call_agent(state: MessageState):
    response = model.invoke(state["messages"])
    return {"messages": [response]}

# ④ 定义路由函数
def should_continue(state: MessageState):
    if state["messages"][-1].tool_calls:
        return "tools"
    return END

# ⑤ 构建图
graph_builder = StateGraph(MessageState)
graph_builder.add_node("agent", call_agent)
graph_builder.add_node("tools", tool_node)

graph_builder.set_entry_point("agent")
graph_builder.add_conditional_edges("agent", should_continue)
graph_builder.add_edge("tools", "agent")  # 工具执行完回到 agent

app = graph_builder.compile()

# ⑥ 运行
result = app.invoke({
    "messages": [{"role": "user", "content": "帮我找北京到上海的货源"}]
})
print(result["messages"][-1].content)
```

这 40 行代码实现了一个完整的 ReAct 循环：Agent 推理 → 决定调工具 → ToolNode 执行 → 结果回传 → 再次推理 → 直到不再需要工具为止。

---

## 四、进阶：三个生产级必备能力

基础 ReAct 能跑起来之后，生产环境还需要三个关键能力。

### 4.1 并行执行：扇出与扇入

当一个任务需要同时从多个来源获取信息时，串行调用会白白浪费时间。LangGraph 支持**扇出（一个节点同时触发多个下游）和扇入（多个并行节点汇聚到一个节点）**。

```python
from typing import Annotated
import operator

class ResearchState(TypedDict):
    query: str
    results: Annotated[list, operator.add]  # 归约器：并行结果自动合并

def search_web(state):
    return {"results": [f"网页搜索结果: {state['query']}"]}

def search_knowledge_base(state):
    return {"results": [f"知识库检索结果: {state['query']}"]}

def synthesize(state):
    # 此时 results 已包含两个并行节点的结果
    return {"final": "\n".join(state["results"])}

builder = StateGraph(ResearchState)
builder.add_node("web_search", search_web)
builder.add_node("kb_search", search_knowledge_base)
builder.add_node("synthesize", synthesize)

builder.set_entry_point("web_search")       # 入口
builder.add_edge(START, "web_search")       # 扇出：同时触发两个搜索
builder.add_edge(START, "kb_search")
builder.add_edge("web_search", "synthesize")  # 扇入：两路结果汇聚
builder.add_edge("kb_search", "synthesize")
```

> 💡 **并行分支写同一个状态字段时，必须用归约器（`Annotated[list, operator.add]`），否则后写的会覆盖先写的。**

### 4.2 Human-in-the-Loop：让人类介入决策

生产环境中，有些决策不能完全交给 Agent——比如发送邮件前需要人工确认、高风险操作需要审批。LangGraph 的 **Checkpointer** 机制支持在任意节点暂停，等待人类输入后恢复执行。

```python
from langgraph.checkpoint.memory import MemorySaver

# 使用 MemorySaver 作为 Checkpointer
checkpointer = MemorySaver()
app = graph_builder.compile(
    checkpointer=checkpointer,
    interrupt_before=["send_email"]  # 在执行 send_email 节点前暂停
)

# 第一次运行：执行到 send_email 前暂停
thread_config = {"configurable": {"thread_id": "task-001"}}
result = app.invoke({"messages": [...]}, config=thread_config)

# 此时流程已暂停，人类审查结果...
# 人类批准后，从断点恢复执行
result = app.invoke(None, config=thread_config)
```

这个机制在物流 Agent 场景里非常有价值——Agent 可以自主完成货源搜索和价格评估，但在最终下单之前，司机需要确认一下。

### 4.3 Command：让节点直接控制流程

普通设计里，节点负责更新状态，边负责控制流程——这是"关注点分离"。但有些场景下，**节点自己最清楚下一步该去哪**，这时候用 `Command` 更简洁：

```python
from langgraph.types import Command
from typing import Literal

def process_order(state) -> Command[Literal["success_handler", "error_handler"]]:
    """处理订单，根据结果直接跳转到对应节点"""
    try:
        result = create_order(state["order_info"])
        return Command(
            update={"order_id": result["id"], "status": "created"},
            goto="success_handler"
        )
    except Exception as e:
        return Command(
            update={"error": str(e), "status": "failed"},
            goto="error_handler"
        )
```

> 💡 **Command vs 条件边，怎么选？**
>
> - 跳转逻辑依赖**节点内部计算结果** → 用 Command（结果出来了再决定去哪）
> - 跳转逻辑依赖**状态里的某个字段** → 用条件边（先更新状态，边来路由）
> - **子图跳转到父图** → 只能用 Command，条件边做不到

---

## 五、实践中踩过的坑

### 坑一：工具节点的错误没有被 Agent 感知

**现象**：工具抛出异常，整个图直接崩，不是 Agent 优雅地重试。

**原因**：默认情况下，`ToolNode` 会把工具异常向上抛，而不是把错误信息写入 State 返回给 Agent。

**解法**：在节点里显式捕获异常，把错误信息写成 Observation 返回：

```python
from langgraph.prebuilt import ToolNode

# 使用 handle_tool_errors=True，ToolNode 会捕获异常并把错误作为消息返回
tool_node = ToolNode(tools, handle_tool_errors=True)
```

加上这个参数，工具失败时 Agent 会收到错误消息，可以自主决定重试还是换个思路。

### 坑二：并行分支的状态更新冲突

**现象**：两个并行节点都更新同一个字段，最终只保留了一个节点的结果。

**原因**：没有为并行更新的字段配置归约器，默认是「后写覆盖先写」。

**解法**：所有可能被并行节点同时写入的字段，都加上归约器：

```python
# 错误：普通字段，并行写入会冲突
class State(TypedDict):
    results: list  # ❌

# 正确：加上归约器，并行写入自动合并
class State(TypedDict):
    results: Annotated[list, operator.add]  # ✅
```

### 坑三：递归限制导致 Agent 意外中断

**现象**：Agent 在处理复杂任务时，突然抛出 `GraphRecursionError`，任务中断。

**原因**：LangGraph 默认递归限制是 25 步（Superstep），复杂任务可能超限。

**解法**：根据任务复杂度调整递归限制，同时加异常处理：

```python
from langgraph.errors import GraphRecursionError

try:
    result = app.invoke(
        initial_state,
        config={"recursion_limit": 50}  # 根据任务调整上限
    )
except GraphRecursionError:
    # 超限时的降级处理
    result = {"error": "任务过于复杂，请拆分后重试"}
```

---

## 六、LangGraph 在业务中实际的应用

把上面的能力结合起来，在一个典型的资源匹配 Agent 场景中，我们曾用 LangGraph 搭建了一个「智能推荐 Agent」，架构大致如下：

```
用户输入（用户需求）
       ↓
 [意图理解节点]
       ↓（条件边）
  ┌────┴────┐
  ↓         ↓
[资源搜索]  [偏好分析]   ← 并行执行
  ↓         ↓
  └────┬────┘（扇入汇聚）
       ↓
 [结果排序节点]
       ↓（条件边）
  ┌────┴────────────┐
  ↓                 ↓
[直接推荐]    [需要协商？]
                    ↓
              [协商谈判节点]
                    ↓（interrupt_before）
              ⏸️ 等待用户确认
                    ↓
              [执行节点]
```

简单介绍一下这套结构里面几个设计trick：

**① 资源搜索和偏好分析并行执行**，总延迟从 6s 降到 3.5s。

**② 在执行前加 `interrupt_before`**，用户必须确认才能真正提交——Agent 能自主决策，但关键操作需要人类兜底。

**③ 用 `RetryPolicy` 为关键节点配置重试**：搜索节点最多重试 3 次，遇到网络超时自动重试，无需外层逻辑手动处理。

```python
from langgraph.types import RetryPolicy

builder.add_node(
    "resource_search",
    resource_search_func,
    retry=RetryPolicy(
        max_attempts=3,
        retry_on=TimeoutError  # 只对超时异常重试
    )
)
```
其实langraph本身的运用没有想象中那么复杂，**在实际工业落地场景里面，业务逻辑的梳理比框架本身更关键！**

---

## 总结

LangGraph 解决的不是「Agent 怎么推理」的问题，而是「Agent 的执行流程怎么工程化」的问题。

| 能力 | LangGraph 的解法 |
|:---|:---|
| **循环迭代**（ReAct 循环）| 有向循环图（DCG）天然支持 |
| **条件分支**（成功/失败走不同路径）| 条件边 + 路由函数 |
| **并行执行**（多路信息同时获取）| 扇出/扇入 + 状态归约器 |
| **Human-in-the-Loop** | Checkpointer + interrupt_before |
| **节点级重试** | RetryPolicy |
| **状态持久化**（断点续跑）| Checkpointer |

一句话概括：**如果你的 Agent 需要「不止一个 if-else」的控制流，就该用 LangGraph 了。**

前面几篇文章讲了 Agent 「怎么想」（决策推理）、「记什么」（记忆管理）、「能做什么」（工具调用），LangGraph 解决的是「**怎么把这些能力组装成一个跑得起来的系统**」——这才是从原型到生产的最后一公里。

---

## 📖 下一步阅读建议

- **回顾同层**：《Agent 技术全景图》——LangGraph 在第4层（框架层）的位置（第02篇）
- **向下夯实**：《工具调用模块深度解析》——LangGraph 里 ToolNode 背后的设计逻辑（第05篇）
- **向上延伸**：《业务 Agent 深度开发》——在 LangGraph 之上，如何设计子 Agent 和 Skill 的分层架构

**下一篇预告：《Agent Skill 层设计：让能力像乐高一样可复用》**

---

*如果这篇文章对你有帮助，欢迎转发给正在研究 Agent 工程化的朋友。有任何问题或踩坑经历，随时后台留言 💬*
