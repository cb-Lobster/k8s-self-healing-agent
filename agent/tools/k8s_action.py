import subprocess
from langchain_core.tools import tool


def _kubectl(args: str, timeout: int = 60) -> str:
    """执行 kubectl 命令并返回输出"""
    try:
        r = subprocess.run(
            f"kubectl {args}",
            shell=True, capture_output=True, text=True, timeout=timeout
        )
        return r.stdout if r.returncode == 0 else f"ERROR: {r.stderr}"
    except subprocess.TimeoutExpired:
        return "ERROR: kubectl 命令超时"


@tool
def restart_deployment(deployment: str, namespace: str = "default") -> str:
    """滚动重启 Deployment，用于修复 CrashLoopBackOff 或配置更新"""
    return _kubectl(f"rollout restart deployment/{deployment} -n {namespace}")


@tool
def scale_deployment(deployment: str, replicas: int, namespace: str = "default") -> str:
    """扩缩容 Deployment，用于应对高负载或释放资源。replicas 是目标副本数"""
    return _kubectl(f"scale deployment/{deployment} --replicas={replicas} -n {namespace}")


@tool
def rollback_deployment(deployment: str, namespace: str = "default") -> str:
    """回滚 Deployment 到上一个版本，用于新版本发布故障"""
    return _kubectl(f"rollout undo deployment/{deployment} -n {namespace}")


@tool
def delete_pod(pod_name: str, namespace: str = "default") -> str:
    """删除 Pod，触发重建，用于 Pod 卡死或状态异常。这是最后手段，优先用重启/扩容/回滚"""
    return _kubectl(f"delete pod {pod_name} -n {namespace}")
