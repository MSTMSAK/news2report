"""
AI 领域日报生成服务
基于 news-daily-report skill 从结构化新闻数据生成日报 Markdown/HTML 报告。
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import markdown2
from openai import OpenAI

from src.config import DATA_DIR, OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_MODEL

logger = logging.getLogger(__name__)

OUTPUT_DIR = DATA_DIR / "output"

SYSTEM_PROMPT = """你是一位资深的 AI 产业分析师。请基于用户提供的结构化新闻数据，生成一份专业的《AI领域日报》分析报告。

报告必须严格按照以下结构输出 Markdown：

```markdown
# AI领域日报 —— [日期]

## 今日主要热点

### 热点1：[事件标题（不超过20字）]
一句话核心概述（不超过40字）。

### 热点2：[事件标题]
一句话核心概述。

### 热点3：[事件标题]
一句话核心概述。

（可选热点4、热点5）

---

## 重要事件深度分析

### 1. [事件标题]

**事件概述**
2-3句话概括事件核心事实，明确主体、时间、关键动作和关键数字。

**背景与动因**
解释为什么这个事件现在发生。涉及的行业背景、公司战略、技术演进路径或市场环境变化。

**直接影响**
分点说明对各方的影响——直接受影响的公司/产品、用户群体、竞争对手、相关产业链。每个影响点用一句话+数据/事实支撑。

**深层含义**
分析事件可能引发的连锁反应或范式转变。可以适当引入前瞻判断，但必须标注判断依据。

（对每个热点事件重复上述结构，热点数量 = 深度分析事件数量，不允许遗漏）

---

## 趋势判断

### 技术趋势
基于今日事件综合判断。说明观察到的方向变化、支撑事件、可能的演进路径。

### 应用趋势
AI技术在实际应用/商业落地方面的趋势变化。

### 政策趋势
监管、合规、政策导向方面的趋势。

### 资本趋势
投融资、估值、并购等资本层面的趋势。

---

## 风险与机会提示

### 风险提示
- **风险标题（确定性：高/中/低 | 时间窗口：短期/中期/长期）**：简述风险内容 + 支撑逻辑（为什么这是个风险）

### 机会提示
- **机会标题（确定性：高/中/低 | 时间窗口：短期/中期/长期）**：简述机会内容 + 支撑逻辑

---

*数据来源：[来源列表] | 报告生成时间：[时间戳]*
```

写作要求：
1. 热点事件 3-5 个，必须至少包含 1 条技术类事件。
2. 每个热点事件必须在"重要事件深度分析"中逐一分析，禁止遗漏。
3. 每个事件的"背景与动因"+"直接影响"+"深层含义"合计不少于 150 字。
4. 每个论点必须有因果逻辑链（因为 X，所以 Y，可能导致 Z），禁止纯描述。
5. 使用具体数据/事实支撑论点；无数据支撑的观点标注 [待验证]。
6. 禁止空洞表述："意义重大""值得关注""影响深远"等。
7. 区分已验证事实与合理推断，不确定信息标注 [待验证]。
8. 禁止使用 emoji/表情符号；加粗仅用于小标题和关键术语，禁止整段加粗。
9. 趋势判断每个方向至少引用 2 个具体事件/数据支撑。
10. 风险/机会提示必须包含确定性评级和时间窗口，以及明确逻辑链。

输出必须是纯 Markdown，不要包含代码块包裹，不要添加任何额外说明。
"""


def _map_impact_level(significance: str) -> str:
    """将重要性映射为 high/medium/low。"""
    mapping = {
        "重大": "high",
        "重要": "medium",
        "一般": "low",
        "轻微": "low",
    }
    return mapping.get(significance, "medium")


def _read_structured_news() -> list[dict[str, Any]]:
    """读取结构化新闻数据。"""
    structured_file = DATA_DIR / "structured_news.json"
    if not structured_file.exists():
        return []
    with structured_file.open("r", encoding="utf-8") as f:
        return json.load(f)


def _get_target_date(news_list: list[dict[str, Any]], date_str: str | None) -> str:
    """确定目标日期。"""
    if date_str:
        return date_str
    if not news_list:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")
    # 取最新 publish_time 的日期部分
    publish_times = [n.get("publish_time", "") for n in news_list]
    latest = sorted(publish_times, reverse=True)[0]
    return latest.split("T")[0] if "T" in latest else latest[:10]


def _filter_news_by_date(news_list: list[dict[str, Any]], date_str: str) -> list[dict[str, Any]]:
    """按日期筛选新闻（允许前后各一天，确保内容充足）。"""
    filtered = []
    for news in news_list:
        publish_time = news.get("publish_time", "")
        news_date = publish_time.split("T")[0] if "T" in publish_time else publish_time[:10]
        if news_date == date_str:
            filtered.append(news)
    return filtered


def _prepare_news_items(news_list: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """将内部结构化数据转换为 skill 要求的格式。"""
    items = []
    for news in news_list:
        source = news.get("source", {}) or {}
        opinion = news.get("ai_opinion", {}) or {}
        entities = news.get("entities", []) or []
        item = {
            "title": news.get("title", ""),
            "summary": news.get("ai_summary", ""),
            "source": source.get("name", "未知来源"),
            "publish_time": news.get("publish_time", ""),
            "category": news.get("category", "其他"),
            "tags": news.get("tags", []),
            "entities": [e.get("name") for e in entities if e.get("name")],
            "impact_level": _map_impact_level(opinion.get("significance", "")),
            "key_points": news.get("key_points", []),
        }
        items.append(item)
    return items


def _get_report_paths(date_str: str) -> tuple[Path, Path]:
    """获取报告文件路径。"""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    md_path = OUTPUT_DIR / f"daily_report_{date_str}.md"
    html_path = OUTPUT_DIR / f"daily_report_{date_str}.html"
    return md_path, html_path


def _markdown_to_html(markdown_text: str) -> str:
    """将 Markdown 转换为 HTML。"""
    extras = ["tables", "fenced-code-blocks", "header-ids", "strike", "cuddled-lists"]
    return markdown2.markdown(markdown_text, extras=extras)


def generate_daily_report(
    date_str: str | None = None,
    force: bool = False,
) -> dict[str, Any]:
    """生成日报报告。返回包含 markdown、html、date、generated_at、path 的字典。"""
    if not OPENAI_API_KEY:
        raise RuntimeError("未配置 OPENAI_API_KEY")

    news_list = _read_structured_news()
    target_date = _get_target_date(news_list, date_str)
    md_path, html_path = _get_report_paths(target_date)

    if not force and md_path.exists() and html_path.exists():
        logger.info("日报已存在，直接返回: %s", md_path)
        markdown_text = md_path.read_text(encoding="utf-8")
        html_text = html_path.read_text(encoding="utf-8")
        return {
            "status": "ok",
            "date": target_date,
            "markdown": markdown_text,
            "html": html_text,
            "generated_at": datetime.fromtimestamp(md_path.stat().st_mtime, tz=timezone.utc).isoformat(),
            "path": str(md_path),
        }

    # 按目标日期筛选新闻
    filtered_news = _filter_news_by_date(news_list, target_date)
    if not filtered_news:
        # 如果目标日期没有新闻，尝试使用全部新闻（避免空报告）
        filtered_news = news_list

    if not filtered_news:
        raise RuntimeError("没有可用的结构化新闻数据，无法生成日报")

    news_items = _prepare_news_items(filtered_news)

    client = OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL)
    temperature = 1.0 if OPENAI_MODEL == "kimi-for-coding" else 0.5

    logger.info("正在生成 %s 的 AI 日报，使用 %d 条新闻", target_date, len(news_items))

    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"请根据以下结构化新闻数据生成 {target_date} 的 AI 领域日报。\n\n```json\n{json.dumps(news_items, ensure_ascii=False, indent=2)}\n```",
            },
        ],
        temperature=temperature,
        max_tokens=8000,
    )

    markdown_text = response.choices[0].message.content or ""
    markdown_text = markdown_text.strip()
    if markdown_text.startswith("```markdown"):
        markdown_text = markdown_text[len("```markdown"):].strip()
    if markdown_text.endswith("```"):
        markdown_text = markdown_text[:-3].strip()

    html_text = _markdown_to_html(markdown_text)

    generated_at = datetime.now(timezone.utc).isoformat()
    md_path.write_text(markdown_text, encoding="utf-8")
    html_path.write_text(html_text, encoding="utf-8")

    logger.info("日报生成完成: %s", md_path)
    return {
        "status": "ok",
        "date": target_date,
        "markdown": markdown_text,
        "html": html_text,
        "generated_at": generated_at,
        "path": str(md_path),
    }


def get_latest_report() -> dict[str, Any] | None:
    """获取最新的已生成日报（不触发重新生成）。"""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    report_files = sorted(OUTPUT_DIR.glob("daily_report_*.md"), reverse=True)
    if not report_files:
        return None
    latest_md = report_files[0]
    date_str = latest_md.stem.replace("daily_report_", "")
    _, html_path = _get_report_paths(date_str)
    if not html_path.exists():
        html_path.write_text(_markdown_to_html(latest_md.read_text(encoding="utf-8")), encoding="utf-8")
    return {
        "status": "ok",
        "date": date_str,
        "markdown": latest_md.read_text(encoding="utf-8"),
        "html": html_path.read_text(encoding="utf-8"),
        "generated_at": datetime.fromtimestamp(latest_md.stat().st_mtime, tz=timezone.utc).isoformat(),
        "path": str(latest_md),
    }
