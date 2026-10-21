import logging

from langchain_core.tools import tool

from agent.rag import DEFAULT_TOP_K, search

logger = logging.getLogger(__name__)


@tool
def search_knowledge_base(keyword: str, top_k: int = DEFAULT_TOP_K) -> str:
    """检索 K8s 运维 SOP 知识库。

    当遇到不确定原因、未知或罕见的故障现象时，先调用本工具查阅标准操作手册，
    再决定执行什么修复动作。输入故障现象、报错信息或关键词（如
    CrashLoopBackOff、OOMKilled、ImagePullBackOff、探针失败），
    返回知识库中相关章节的原文片段及来源。
    """
    try:
        return search(keyword, top_k=top_k)
    except Exception as exc:
        logger.exception("search_knowledge_base 调用失败")
        return f"ERROR: 知识库检索失败：{exc}"
