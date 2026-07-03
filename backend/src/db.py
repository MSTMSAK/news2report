"""
AI舆情分析日报系统 - SQLite 持久化层
用于保存上传记录、结构化结果和生成的报告路径。
"""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.config import DATA_DIR

DB_PATH = DATA_DIR / "news2report.db"


def _get_connection() -> sqlite3.Connection:
    """获取 SQLite 连接，返回字典风格的行。"""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """初始化数据库表。"""
    with _get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS upload_records (
                id TEXT PRIMARY KEY,
                upload_type TEXT NOT NULL,
                title TEXT,
                source TEXT,
                url TEXT,
                language TEXT,
                published_at TEXT,
                content TEXT,
                structured_json TEXT,
                report_pdf_path TEXT,
                structured_pdf_path TEXT,
                pdf_pages INTEGER,
                created_at TEXT,
                updated_at TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_upload_records_created_at
            ON upload_records (created_at)
            """
        )
        conn.commit()


def insert_upload_record(
    record_id: str,
    upload_type: str,
    title: str,
    source: str,
    url: str,
    language: str,
    published_at: str,
    content: str,
    structured: dict[str, Any],
    report_pdf_path: str | None = None,
    structured_pdf_path: str | None = None,
    pdf_pages: int | None = None,
) -> None:
    """插入或替换一条上传记录。"""
    now = datetime.now(timezone.utc).isoformat()
    with _get_connection() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO upload_records (
                id, upload_type, title, source, url, language, published_at,
                content, structured_json, report_pdf_path, structured_pdf_path,
                pdf_pages, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, COALESCE(
                (SELECT created_at FROM upload_records WHERE id = ?
            ), ?), ?)
            """,
            (
                record_id,
                upload_type,
                title,
                source,
                url,
                language,
                published_at,
                content,
                json.dumps(structured, ensure_ascii=False),
                report_pdf_path,
                structured_pdf_path,
                pdf_pages,
                record_id,
                now,
                now,
            ),
        )
        conn.commit()


def get_upload_record(record_id: str) -> dict[str, Any] | None:
    """根据 ID 查询上传记录。"""
    with _get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM upload_records WHERE id = ?", (record_id,)
        ).fetchone()
    if row is None:
        return None
    return dict(row)
