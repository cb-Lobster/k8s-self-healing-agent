"""轻量级 K8s SOP 知识库。

纯 Python 实现，不依赖向量数据库或 embedding 模型：
启动时读取 knowledge/ 下的 Markdown，按 ``##`` 标题切分，
检索时用关键词匹配返回相关故障段落。
"""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_KNOWLEDGE_DIR = PROJECT_ROOT / "knowledge"
DEFAULT_TOP_K = 3
MAX_RESULTS = 10

# 过泛的词会让无关段落命中，不参与匹配
_STOPWORDS = {
    "集群", "容器", "故障", "问题", "现象", "服务", "应用", "日志",
    "一直", "反复", "出现", "可能", "原因", "排查", "修复", "处理",
    "确认", "异常", "情况", "这个", "那个",
}

_sections: list[dict[str, str]] = []
_cache_key: tuple[tuple[str, int, int], ...] | None = None


def _knowledge_dir() -> Path:
    raw = os.getenv("KNOWLEDGE_DIR", "").strip()
    return Path(raw).expanduser().resolve() if raw else DEFAULT_KNOWLEDGE_DIR


def _split_markdown(text: str, source: str, fallback_title: str) -> list[dict[str, str]]:
    """按二级标题 ``##`` 切分 Markdown，每个故障现象成为独立段落。"""
    parts = re.split(r"(?m)^(?=##\s+)", text)
    sections: list[dict[str, str]] = []

    for part in parts:
        content = part.strip()
        if not content:
            continue

        first_line = content.splitlines()[0].strip()
        if first_line.startswith("##"):
            title = first_line.lstrip("#").strip() or fallback_title
        else:
            title = fallback_title
            # 纯文档标题（没有正文）不单独作为可检索段落
            if all(not line.strip() or line.lstrip().startswith("#") for line in content.splitlines()):
                continue

        sections.append({"source": source, "title": title, "content": content})

    return sections


def _load_sections() -> list[dict[str, str]]:
    knowledge_dir = _knowledge_dir()
    if not knowledge_dir.exists():
        logger.warning("知识库目录不存在: %s", knowledge_dir)
        return []

    files = sorted(knowledge_dir.rglob("*.md"))
    if not files:
        logger.warning("知识库目录中没有 Markdown 文件: %s", knowledge_dir)
        return []

    result: list[dict[str, str]] = []
    for path in files:
        try:
            source = path.relative_to(PROJECT_ROOT).as_posix()
        except ValueError:
            source = path.as_posix()
        text = path.read_text(encoding="utf-8")
        result.extend(_split_markdown(text, source, path.stem))
    return result


def _get_sections() -> list[dict[str, str]]:
    """返回知识库段落；知识文件变化时自动重新加载。"""
    global _sections, _cache_key

    knowledge_dir = _knowledge_dir()
    files = sorted(knowledge_dir.rglob("*.md")) if knowledge_dir.exists() else []
    key = tuple((str(path), path.stat().st_mtime_ns, path.stat().st_size) for path in files)

    if _cache_key != key:
        _sections = _load_sections()
        _cache_key = key
        logger.info("已加载 SOP 知识库：%d 个段落", len(_sections))
    return _sections


def _keywords(query: str) -> list[str]:
    """从自然语言查询中提取英文关键词和中文 2-4 字片段。"""
    keywords: list[str] = []

    for token in re.findall(r"[a-zA-Z0-9][a-zA-Z0-9_.\-]*", query):
        if len(token) >= 2:
            keywords.append(token.casefold())

    for sequence in re.findall(r"[\u4e00-\u9fff]+", query):
        if len(sequence) <= 4:
            keywords.append(sequence)
            continue
        for size in (4, 3, 2):
            keywords.extend(
                sequence[start : start + size]
                for start in range(len(sequence) - size + 1)
            )

    # 去重、过滤泛词并保持顺序
    return [keyword for keyword in dict.fromkeys(keywords) if keyword not in _STOPWORDS]


def _score(section: dict[str, str], query: str, keywords: list[str]) -> int:
    content = section["content"].casefold()
    title = section["title"].casefold()
    score = 0

    if query.casefold() in content:
        score += 100
    if query.casefold() in title:
        score += 50

    for keyword in keywords:
        if keyword in title:
            score += len(keyword) * 3
        elif keyword in content:
            score += len(keyword)

    return score


def search_knowledge_base(keyword: str, top_k: int = DEFAULT_TOP_K) -> str:
    """关键词检索 SOP，返回命中的故障段落。"""
    query = (keyword or "").strip()
    if not query:
        return "ERROR: 检索关键词不能为空"

    sections = _get_sections()
    if not sections:
        return f"知识库为空：{_knowledge_dir()} 下没有可检索的 Markdown 文档"

    keywords = _keywords(query)
    matched: list[tuple[dict[str, str], int]] = []
    for section in sections:
        score = _score(section, query, keywords)
        if score > 0:
            matched.append((section, score))

    if not matched:
        return f"知识库中未找到与“{query}”相关的 SOP 段落，请人工确认故障原因。"

    try:
        limit = max(1, min(int(top_k), MAX_RESULTS))
    except (TypeError, ValueError):
        limit = DEFAULT_TOP_K

    matched.sort(key=lambda item: (-item[1], item[0]["title"]))
    matched = matched[:limit]

    lines = [f"知识库检索结果（关键词：{query}，共 {len(matched)} 条）："]
    for index, (section, _) in enumerate(matched, start=1):
        lines.append(
            f"\n【{index}】来源：{section['source']}｜章节：{section['title']}\n"
            f"{section['content']}"
        )
    return "\n".join(lines)


# 兼容现有工具封装中的 search(keyword, top_k=...)
search = search_knowledge_base

# 启动时加载一次知识库
try:
    _get_sections()
except Exception:
    logger.exception("启动加载 SOP 知识库失败")
