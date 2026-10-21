import os
import time
import traceback

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain.agents import create_agent

from agent.tools.k8s_query import (
    get_pods, describe_pod, get_pod_logs, get_events, get_deployments
)
from agent.tools.k8s_action import (
    restart_deployment, scale_deployment, rollback_deployment, delete_pod
)
from agent.tools.rag_tool import search_knowledge_base

load_dotenv()

SYSTEM_PROMPT = """你是 K8s 故障自愈专家。

工作流程：
1. 发现异常：用 get_pods / get_events 扫描异常 Pod
2. 诊断根因：用 describe_pod / get_pod_logs 收集证据
3. 查阅 SOP：遇到未知的故障现象时，必须先调用 search_knowledge_base 查阅 SOP 手册
4. 选择动作：根据故障类型选择重启 / 扩容 / 回滚 / 删除
5. 执行修复：调用写操作工具
6. 验证结果：再次 get_pods 确认恢复

故障类型与修复动作对照（必须严格遵守）：

| 故障类型 | 典型特征 | 推荐动作 |
|---|---|---|
| CrashLoopBackOff（配置错误） | 容器主动 exit，日志显示命令错误 | rollback_deployment |
| CrashLoopBackOff（依赖缺失） | 连不上 DB/Redis 等外部服务 | 通知人工，不自动修复 |
| ImagePullBackOff | 镜像拉取失败 | 通知人工，不自动修复 |
| OOMKilled | 内存超限被杀 | scale_deployment 或通知 |
| PodPending | 资源不足/调度失败 | 通知人工 |
| 无就绪探针 | readiness probe 失败 | restart_deployment |

安全规则（必须遵守）：
- 遇到未知的故障现象时，必须优先调用 search_knowledge_base 工具查阅 SOP 手册，再决定执行什么修复动作
- 执行写操作前，先说明理由
- ImagePullBackOff 不自动修复，只通知（镜像问题需人工）
- 不确定的操作，先输出建议，不要执行
- 每次只修复一个问题，修复后必须验证
- 删 Pod 是最后手段，优先重启/扩容/回滚
"""


def build_agent():
    llm = ChatOpenAI(
        model="deepseek-chat",
        api_key=os.getenv("DEEPSEEK_API_KEY"),
        base_url=os.getenv("DEEPSEEK_BASE_URL"),
        temperature=0
    )

    tools = [
        search_knowledge_base,
        get_pods, describe_pod, get_pod_logs, get_events, get_deployments,
        restart_deployment, scale_deployment, rollback_deployment, delete_pod
    ]

    return create_agent(
        model=llm,
        tools=tools,
        system_prompt=SYSTEM_PROMPT
    )


def _get_interval() -> int:
    raw = os.getenv("AGENT_INTERVAL", "300").strip()
    try:
        value = int(raw)
    except ValueError:
        print(f"AGENT_INTERVAL 非法: {raw!r}，回退为 300 秒", flush=True)
        return 300
    return value if value > 0 else 300


def run_once(agent, task: str) -> None:
    for chunk in agent.stream(
        {"messages": [{"role": "user", "content": task}]},
        stream_mode="messages",
    ):
        # chunk 是一个元组 (message_chunk, metadata)
        # message_chunk.content 是本次生成的 token 内容
        if chunk[0].content:
            print(chunk[0].content, end="", flush=True)
    print("\n", flush=True)


def main():
    print("K8s 故障自愈 Agent 已启动", flush=True)

    task = os.getenv("AGENT_TASK", "").strip()
    if not task:
        print("未设置 AGENT_TASK，跳过巡检，进入常驻休眠", flush=True)
        while True:
            time.sleep(3600)

    interval = _get_interval()
    print(f"巡检任务: {task}", flush=True)
    print(f"巡检间隔: {interval} 秒", flush=True)

    while True:
        print(
            f"\n===== 开始巡检 [{time.strftime('%Y-%m-%d %H:%M:%S')}] =====",
            flush=True,
        )
        try:
            agent = build_agent()
            run_once(agent, task)
            print("本轮巡检完成", flush=True)
        except Exception:
            # 单轮失败不能退出容器，等待下一轮重试
            traceback.print_exc()
            print("本轮巡检失败，等待下一轮", flush=True)

        time.sleep(interval)

if __name__ == "__main__":
    main()
