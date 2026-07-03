"""
报告生成服务
- 根据 AI 结构化结果生成 AI 分析报告 PDF 和结构化分析报告 PDF
- 使用项目 pdf/ skill 的 ReportLab 路线，直接注册中文字体生成 PDF
"""

import json
import logging
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from src.config import DATA_DIR

logger = logging.getLogger(__name__)
REPORTS_DIR = DATA_DIR / "reports"

# Windows 常见中文字体
CJK_FONT_CANDIDATES = [
    r"C:\Windows\Fonts\simhei.ttf",
    r"C:\Windows\Fonts\msyh.ttc",
    r"C:\Windows\Fonts\simsun.ttc",
]


def _register_cjk_fonts() -> str:
    """注册 CJK 字体并返回使用的字体名。"""
    font_path = None
    for cand in CJK_FONT_CANDIDATES:
        if Path(cand).exists():
            font_path = cand
            break

    if not font_path:
        logger.warning("未找到 CJK 字体，PDF 中的中文可能显示为方框")
        return "Helvetica"

    try:
        pdfmetrics.registerFont(TTFont("CJK", font_path))
        pdfmetrics.registerFont(TTFont("CJK-Bold", font_path))
        logger.info("已注册 CJK 字体: %s", font_path)
        return "CJK"
    except Exception as e:
        logger.warning("注册 CJK 字体失败: %s", e)
        return "Helvetica"


CJK_FONT = _register_cjk_fonts()


def _txt(value: Any) -> str:
    """将字段值格式化为字符串，自动处理枚举类型。"""
    if value is None:
        return "-"
    if isinstance(value, Enum):
        return str(value.value)
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def _p(text: str, style: ParagraphStyle) -> Paragraph:
    """创建 Paragraph，转义 XML 特殊字符并保留换行。"""
    safe = escape(str(text) if text is not None else "").replace("\n", "<br/>")
    return Paragraph(safe, style)


def _make_styles() -> dict[str, ParagraphStyle]:
    """创建报告使用的样式集合。"""
    base = getSampleStyleSheet()
    styles = {
        "title": ParagraphStyle(
            "ReportTitle",
            parent=base["Title"],
            fontName=CJK_FONT + "-Bold" if CJK_FONT != "Helvetica" else "Helvetica-Bold",
            fontSize=18,
            leading=24,
            spaceAfter=16,
            textColor=colors.HexColor("#1a1a1a"),
            wordWrap="CJK",
        ),
        "heading1": ParagraphStyle(
            "ReportH1",
            parent=base["Heading1"],
            fontName=CJK_FONT + "-Bold" if CJK_FONT != "Helvetica" else "Helvetica-Bold",
            fontSize=14,
            leading=20,
            spaceBefore=16,
            spaceAfter=8,
            textColor=colors.HexColor("#1a1a1a"),
            wordWrap="CJK",
        ),
        "heading2": ParagraphStyle(
            "ReportH2",
            parent=base["Heading2"],
            fontName=CJK_FONT + "-Bold" if CJK_FONT != "Helvetica" else "Helvetica-Bold",
            fontSize=12,
            leading=16,
            spaceBefore=12,
            spaceAfter=6,
            textColor=colors.HexColor("#333333"),
            wordWrap="CJK",
        ),
        "normal": ParagraphStyle(
            "ReportNormal",
            parent=base["Normal"],
            fontName=CJK_FONT,
            fontSize=10.5,
            leading=16,
            spaceAfter=6,
            textColor=colors.HexColor("#1a1a1a"),
            wordWrap="CJK",
        ),
        "small": ParagraphStyle(
            "ReportSmall",
            parent=base["Normal"],
            fontName=CJK_FONT,
            fontSize=9,
            leading=13,
            textColor=colors.HexColor("#555555"),
            wordWrap="CJK",
        ),
    }
    return styles


def _table(data: list[list[str]], col_widths: list[float] | None = None) -> Table:
    """创建三线表风格的表格。"""
    table = Table(data, colWidths=col_widths, hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, 0), CJK_FONT + "-Bold" if CJK_FONT != "Helvetica" else "Helvetica-Bold"),
                ("FONTNAME", (0, 1), (-1, -1), CJK_FONT),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("LINEABOVE", (0, 0), (-1, 0), 1.2, colors.HexColor("#333333")),
                ("LINEBELOW", (0, 0), (-1, 0), 0.75, colors.HexColor("#333333")),
                ("LINEBELOW", (0, -1), (-1, -1), 1.2, colors.HexColor("#333333")),
            ]
        )
    )
    return table


def build_analysis_report(structured: dict[str, Any], output_path: Path) -> None:
    """生成面向读者的 AI 分析报告 PDF。"""
    styles = _make_styles()
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        topMargin=2.5 * cm,
        bottomMargin=2.5 * cm,
        leftMargin=2.8 * cm,
        rightMargin=2.5 * cm,
        title=f"AI 分析报告 - {_txt(structured.get('title'))}",
    )

    story: list[Any] = []
    source = structured.get("source", {}) or {}
    opinion = structured.get("ai_opinion", {}) or {}
    sentiment = structured.get("sentiment", {}) or {}

    story.append(_p(f"AI 分析报告：{_txt(structured.get('title'))}", styles["title"]))
    story.append(_p(f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}", styles["small"]))
    story.append(Spacer(1, 0.4 * cm))

    # 文章信息表
    info_data = [
        ["字段", "内容"],
        ["标题", _txt(structured.get("title"))],
        ["英文标题", _txt(structured.get("title_en"))],
        ["来源", _txt(source.get("name"))],
        ["发布时间", _txt(structured.get("publish_time"))],
        ["原文链接", _txt(source.get("url"))],
        ["语言", _txt(structured.get("language"))],
        ["分类", _txt(structured.get("category"))],
        ["标签", "、".join(structured.get("tags", [])) or "-"],
        ["事件类型", _txt(structured.get("event_type"))],
        ["涉及技术", "、".join(structured.get("technologies", [])) or "-"],
    ]
    story.append(KeepTogether([_p("文章信息", styles["heading1"]), _table(info_data, [4 * cm, 12 * cm])]))
    story.append(Spacer(1, 0.3 * cm))

    # AI 摘要
    story.append(_p("AI 摘要", styles["heading1"]))
    story.append(_p(_txt(structured.get("ai_summary")), styles["normal"]))

    # AI 观点
    story.append(_p("AI 观点", styles["heading1"]))
    story.append(_p(f"核心观点：{_txt(opinion.get('viewpoint'))}", styles["normal"]))
    story.append(_p(f"重要性：{_txt(opinion.get('significance'))}", styles["normal"]))
    story.append(_p(f"影响方向：{_txt(opinion.get('impact_direction'))}", styles["normal"]))

    # 核心要点
    story.append(_p("核心要点", styles["heading1"]))
    for idx, point in enumerate(structured.get("key_points", []), 1):
        story.append(_p(f"{idx}. {_txt(point)}", styles["normal"]))
    if not structured.get("key_points"):
        story.append(_p("暂无核心要点", styles["normal"]))

    # 关键实体
    story.append(_p("关键实体", styles["heading1"]))
    entities = structured.get("entities", [])
    if entities:
        entity_data = [["实体", "类型"]] + [[_txt(e.get("name")), _txt(e.get("type"))] for e in entities]
        story.append(_table(entity_data, [8 * cm, 8 * cm]))
    else:
        story.append(_p("暂无关键实体", styles["normal"]))

    # 情感分析
    story.append(_p("情感分析", styles["heading1"]))
    story.append(_p(f"整体情感：{_txt(sentiment.get('overall'))}（分数：{_txt(sentiment.get('score'))}）", styles["normal"]))
    story.append(_p(f"判断理由：{_txt(sentiment.get('reason'))}", styles["normal"]))

    # 实体关系
    story.append(_p("实体关系", styles["heading1"]))
    relations = structured.get("relations", [])
    if relations:
        rel_data = [["主体", "关系", "客体"]] + [
            [_txt(r.get("subject")), _txt(r.get("predicate")), _txt(r.get("object"))]
            for r in relations
        ]
        story.append(_table(rel_data, [5.3 * cm, 5.3 * cm, 5.3 * cm]))
    else:
        story.append(_p("暂无实体关系", styles["normal"]))

    doc.build(story)


def build_structured_report(structured: dict[str, Any], output_path: Path) -> None:
    """生成面向分析人员的结构化数据报告 PDF。"""
    styles = _make_styles()
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        topMargin=2.5 * cm,
        bottomMargin=2.5 * cm,
        leftMargin=2.8 * cm,
        rightMargin=2.5 * cm,
        title=f"结构化分析报告 - {_txt(structured.get('title'))}",
    )

    story: list[Any] = []
    processing = structured.get("processing", {}) or {}
    source = structured.get("source", {}) or {}

    story.append(_p(f"结构化分析报告：{_txt(structured.get('title'))}", styles["title"]))
    story.append(_p(f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}", styles["small"]))
    story.append(Spacer(1, 0.4 * cm))

    meta_data = [
        ["字段", "值"],
        ["ID", _txt(structured.get("id"))],
        ["标题", _txt(structured.get("title"))],
        ["英文标题", _txt(structured.get("title_en"))],
        ["分类", _txt(structured.get("category"))],
        ["事件类型", _txt(structured.get("event_type"))],
        ["来源", _txt(source.get("name"))],
        ["来源类型", _txt(source.get("type"))],
        ["来源链接", _txt(source.get("url"))],
        ["发布时间", _txt(structured.get("publish_time"))],
        ["语言", _txt(structured.get("language"))],
        ["标签", "、".join(structured.get("tags", [])) or "-"],
        ["涉及技术", "、".join(structured.get("technologies", [])) or "-"],
        ["处理状态", _txt(processing.get("status"))],
        ["使用模型", _txt(processing.get("model"))],
        ["批次 ID", _txt(processing.get("batch_id"))],
        ["抽取时间", _txt(processing.get("extracted_at"))],
        ["重试次数", _txt(processing.get("retry_count"))],
    ]
    story.append(KeepTogether([_p("结构化数据摘要", styles["heading1"]), _table(meta_data, [4 * cm, 12 * cm])]))
    story.append(Spacer(1, 0.3 * cm))

    story.append(_p("完整结构化 JSON", styles["heading1"]))
    json_text = json.dumps(structured, ensure_ascii=False, indent=2, default=lambda o: o.value if isinstance(o, Enum) else str(o))
    story.append(_p(json_text, styles["normal"]))

    doc.build(story)


def generate_reports(
    structured: dict[str, Any],
) -> tuple[str | None, str | None]:
    """
    为结构化结果生成两份 PDF 报告。
    返回：(AI 分析报告路径, 结构化分析报告路径)。
    """
    record_id = structured.get("id")
    if not record_id:
        logger.warning("结构化结果缺少 id，跳过报告生成")
        return None, None

    output_dir = REPORTS_DIR / record_id
    output_dir.mkdir(parents=True, exist_ok=True)

    analysis_pdf_path = output_dir / "analysis_report.pdf"
    structured_pdf_path = output_dir / "structured_report.pdf"
    original_text_path = output_dir / "original_text.txt"

    # 单独保存原文，供下载/预览
    original_text_path.write_text(
        structured.get("original_text", ""), encoding="utf-8"
    )

    build_analysis_report(structured, analysis_pdf_path)
    build_structured_report(structured, structured_pdf_path)

    return str(analysis_pdf_path), str(structured_pdf_path)
