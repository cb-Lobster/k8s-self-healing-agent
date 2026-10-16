import subprocess
from langchain_core.tools import tool


def _kubectl(args: str, timeout: int = 30) -> str:
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
def get_pods(namespace: str = "default") -> str:
    """获取指定 namespace 下所有 Pod 的状态、重启次数、运行时长"""
    return _kubectl(f"get pods -n {namespace} -o wide")


@tool
def describe_pod(pod_name: str, namespace: str = "default") -> str:
    """查看 Pod 详细信息，包括 Events、状态、重启原因"""
    return _kubectl(f"describe pod {pod_name} -n {namespace}")


@tool
def get_pod_logs(pod_name: str, namespace: str = "default", tail: int = 100) -> str:
    """获取 Pod 最近 N 行日志，用于定位崩溃原因"""
    return _kubectl(f"logs {pod_name} -n {namespace} --tail={tail}")


@tool
def get_events(namespace: str = "default") -> str:
    """获取 namespace 下最近的所有事件，按时间排序"""
    return _kubectl(f"get events -n {namespace} --sort-by=.lastTimestamp")


@tool
def get_deployments(namespace: str = "default") -> str:
    """获取 namespace 下所有 Deployment 的副本数和状态"""
    return _kubectl(f"get deployments -n {namespace} -o wide")
