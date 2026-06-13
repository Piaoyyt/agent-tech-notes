项目 LangGraph 使用总结
一、项目中的 LangGraph Agent 一览
Agent	文件	图拓扑复杂度	角色
货主主Agent	shipper_agent.py	高（15节点+多层条件路由）	货主侧总编排
司机主Agent	driver_agent.py	高（12节点+多层条件路由）	司机侧总编排
群组货主Agent	group_shipper_agent.py	低（2节点线性）	群聊货主回复
RTC司机Agent	rtc_driver_agent.py	中（5节点+条件路由）	实时语音司机
RTC货主Agent	rtc_shipper_agent.py	低（1节点线性+流式）	实时语音货主
司机记忆Agent	driver_memory_agent.py	低（2节点条件分支）	短期/长期记忆
司机横评Agent	rerank_drivers_agent.py	低（1节点线性）	司机重排
知识提取Agent	knowledge_extract_agent.py	中（3节点+条件路由）	隐私号知识提取
司机交互子图	drivers_interaction_node.py	中（子图模式）	司货沟通编排
二、LangGraph 核心特性使用分析
1. StateGraph + TypedDict 状态管理
所有 Agent 均使用 TypedDict 定义 State，与 LangGraph 的 StateGraph 深度集成：
# shipper_state.py
class ShipperAgentState(TypedDict):
    messages: List[ChatMessage]
    next_node: str
    response: str
    tool_actions: Optional[List[ToolCall]]
    ab_params: Dict
    ...
2. Annotated[List, operator.add] 消息累积
DriverAgentState 使用了 LangGraph 的状态注解机制实现消息自动追加：
class DriverAgentState(TypedDict):
    message: Annotated[List[DriverChatMessage], operator.add]
    result_message: Annotated[List[DriverChatMessage], operator.add]
3. 条件路由（add_conditional_edges）
项目中大量使用条件路由，形成了多层级路由架构：
第一层路由：意图识别 → 分发到业务节点
第二层路由：业务节点后判断 → 工具校验 / 建议回复
第三层路由：工具处理结果 → 后续节点
4. MemorySaver + 流式输出
rtc_shipper_agent.py 使用了 MemorySaver checkpointer 配合流式输出：
from langgraph.checkpoint.memory import MemorySaver
5. StreamWriter 实时推送
rtc_driver_nodes.py 使用 StreamWriter 实现语音通话的实时流式输出：
from langgraph.types import StreamWriter

async def rtc_driver_base(state: RTCDriverState, writer: StreamWriter):
    writer({"stream_message": [...]})  # 实时推送
6. yield from 生成器节点
rtc_shipper_agent.py 使用了 LangGraph 的生成器节点模式：
def shipper_chat_node_wrapper(state: RTCShipperState):
    yield from rtc_shipper_chat_sub_agent.run(state=state, ...)
三、优秀设计模式点评
1. Router-Worker 编排模式 — 最佳实践
shipper_agent.py 的图结构采用了经典的 Router-Worker 模式：
START → node_router ──→ node_check
                  ├──→ node_bargain
                  ├──→ node_chat
                  ├──→ node_report
                  └──→ ...
优点：
路由节点（shipper_orchestrator）采用 规则 → 正则 → LLM 三级降级策略，先快后准
新增业务意图只需增加一个 Worker 节点和路由映射，无需改动路由框架
路由与业务完全解耦，职责清晰
2. Hub-and-Spoke 收敛模式 — 统一后处理
所有业务节点执行后统一汇入 node_judge_tool 判断节点：
node_chat ──────┐
node_check ─────┤
node_bargain ───┤──→ node_judge_tool ──→ node_suggestion
node_report ────┤                  └──→ node_tool_validate
node_knowledge ─┘
优点：
避免每个节点都写工具校验逻辑，DRY 原则
统一了"是否需要建议回复"的判断出口
便于后续增加后处理环节（如内容审核、打标等）
3. State 携带 AB 实验参数 — 运行时动态路由
State 中内置 ab_params 字典，所有节点通过读取 ab_params 实现运行时实验分流：
# 节点内部根据 AB 参数选择不同逻辑
if correction_mode == "skill":
    result, skill_info = engine.run(...)
else:
    llm_response = correction_sub_agent.run(...)
优点：
无需部署多套代码即可实现实验对比
Prompt 版本、模型选择、功能开关全部通过 ab_params 控制
与 Lion 配置中心联动，热更新无需重启
4. SkillEngine ReAct 模式 — SOP 驱动的工具调用
SkillEngine 没有使用 LangGraph 内置的 ReAct Agent，而是自研了 SOP 约束的 ReAct 引擎：
L1/L2 两级技能层级：L1 编排决策，L2 执行子技能
load_skill / invoke_tool / task_complete 三种 action kind
双消息上下文隔离（skill_messages / action_messages）
从 Lion 平台动态加载技能定义（含 YAML front matter 的 inputs 声明）
优点：
比通用 ReAct Agent 更可控，SOP 约束了 LLM 的行为边界
技能定义与代码分离，运营可独立配置
子技能生命周期管理清晰
5. build_graph() 工厂函数 — 延迟编译
rtc_driver_agent.py 和 rtc_shipper_agent.py 使用工厂函数构建图：
@observe(name="build_graph")
def build_graph():
    workflow = StateGraph(RTCDriverState)
    ...
    return workflow.compile()

rtc_driver_agent_graph = build_graph()
优点：
避免模块导入时立即编译，支持延迟初始化
便于测试时传入不同配置
每次调用可以构建全新的图实例，避免状态污染
6. 全链路 Langfuse 追踪 — 可观测性
每个节点函数都加了 @observe() 装饰器，结合 Langfuse 实现全链路追踪：
@observe()
async def node_chat(state: ShipperAgentState) -> ShipperAgentState:
    ...

@observe()
def llm_response_tool_process(state):
    ...
优点：
每个节点的输入输出、执行时长都可追溯
线上问题排查效率极高
SkillEngine 还做了 Langfuse trace context 绑定策略，处理了 LangGraph pregel 运行时破坏 contextvars 的问题
7. 动态 Prompt + 模型配置 — Lion 平台热更新
BaseAgent 的 _load_config 方法实现了 Prompt 和 LLM 的运行时动态加载：
def _load_config(self, prompt_version="default", exp_group=None):
    if self.agent_name:
        self.llm = get_llm_by_agent_name(self.agent_name, exp_group=exp_group)
    if self.prompt_lion_key:
        self.prompt = fetch_lion_params(self.prompt_lion_key)
优点：
Prompt 修改不需要重新部署
模型切换可以通过 Lion 平台即时生效
不同实验组可使用不同的模型和 Prompt 版本
四、可改进之处
State 定义过于松散：ShipperAgentState 有近 30 个字段，部分字段如 next_node 既是输入也是输出，容易产生状态耦合。建议将路由状态与业务状态分离。
节点函数过于臃肿：driver_agent.py 中 bargain_agent、common_response_agent 等函数超过 60 行，混合了业务逻辑和状态更新。建议将业务逻辑抽到 BaseAgent 子类中（类似 drivers_interaction_node.py 的 ShipperInteractionSubAgent 模式）。
模块级图编译：部分 Agent 在模块顶层直接 workflow.compile()，导入了即触发全量初始化。建议统一采用 build_graph() 工厂模式。
缺少图的可视化自动化：虽然有 draw_mermaid() 调试代码，但只在 __main__ 中手动使用。可以增加自动化图文档生成流程。
五、架构全景
                    ┌─────────────────────────────────┐
                    │         API Layer (FastAPI)      │
                    └──────────┬──────────────────────┘
                               │
          ┌────────────────────┼────────────────────┐
          ▼                    ▼                     ▼
   ShipperAgent          DriverAgent          KnowledgeExtract
   (Router-Worker        (Router-Worker        (Router + Cond)
    + Hub-Spoke)          + Tool-Process)
          │                    │
          ├── GroupShipper     ├── RTCDriver
          │   (Skill/Workflow) │   (StreamWriter+Cond)
          ├── RTCShipper       ├── DriverMemory
          │   (Generator+Stream)│   (Cond Branch)
          ├── Rerank           └── SkillEngine
          │   (Linear)              (ReAct+SOP)
          └── DriversInteraction
              (Sub-Agent Pipeline)
总体而言，这个项目在 LangGraph 的使用上展现了生产级 Agent 系统的成熟实践：Router-Worker 编排、Hub-Spoke 收敛、AB 实验集成、SOP 驱动的 ReAct 引擎、全链路可观测性等设计都值得借鉴。