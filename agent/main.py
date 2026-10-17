import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain.agents import create_agent

from agent.tools.k8s_query import (
    get_pods, describe_pod, get_pod_logs, get_events, get_deployments
)
from agent.tools.k8s_action import (
    restart_deployment, scale_deployment, rollback_deployment, delete_pod
)

load_dotenv()

SYSTEM_PROMPT = """你是 K8s 故障自愈专家。

工作流程：
1. 发现异常：用 get_pods / get_events 扫描异常 Pod
2. 诊断根因：用 describe_pod / get_pod_logs 收集证据
3. 选择动作：根据故障类型选择重启 / 扩容 / 回滚 / 删除
4. 执行修复：调用写操作工具
5. 验证结果：再次 get_pods 确认恢复

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
        get_pods, describe_pod, get_pod_logs, get_events, get_deployments,
        restart_deployment, scale_deployment, rollback_deployment, delete_pod
    ]

    return create_agent(
        model=llm,
        tools=tools,
        system_prompt=SYSTEM_PROMPT
    )


def main():
    agent = build_agent()
    print("K8s 故障自愈 Agent 已启动")
    print("输入 'exit' 退出\n")

    while True:
        q = input("巡检需求 > ")
        if q.lower() == "exit":
            break
        for chunk in agent.stream(
            {"messages": [{"role": "user", "content": q}]},
            stream_mode="messages",
        ):
            # chunk 是一个元组 (message_chunk, metadata)
            # message_chunk.content 是本次生成的 token 内容
            if chunk[0].content:
                print(chunk[0].content, end="", flush=True)

        print("\n")

if __name__ == "__main__":
    main()
