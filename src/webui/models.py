# WebUI队列数据库模型
import sqlite3
import os
from datetime import datetime
from typing import Optional, List, Dict, Any
from loguru import logger
from ..comm import project_root


# 队列数据库路径（与现有downloaded.db分开）
QUEUE_DB_PATH = os.path.join(project_root, "db", "webui_queue.db")


def _get_conn() -> sqlite3.Connection:
    """获取数据库连接"""
    os.makedirs(os.path.dirname(QUEUE_DB_PATH), exist_ok=True)
    conn = sqlite3.connect(QUEUE_DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")  # 提高并发性能
    return conn


def init_queue_db():
    """初始化队列数据库表"""
    conn = _get_conn()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS download_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                avid TEXT UNIQUE NOT NULL,
                status TEXT NOT NULL DEFAULT 'waiting',
                progress TEXT DEFAULT '',
                source TEXT DEFAULT '',
                title TEXT DEFAULT '',
                error_msg TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_queue_status ON download_queue(status)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_queue_created ON download_queue(created_at)
        """)
        conn.commit()
        logger.info("队列数据库初始化完成")
    except sqlite3.Error as e:
        logger.error(f"队列数据库初始化失败: {e}")
    finally:
        conn.close()


def add_to_queue(avid: str) -> Dict[str, Any]:
    """
    添加AVID到下载队列
    :return: {"success": bool, "message": str}
    """
    conn = _get_conn()
    try:
        conn.execute(
            "INSERT INTO download_queue (avid, status, created_at, updated_at) VALUES (?, 'waiting', ?, ?)",
            (avid, datetime.now().isoformat(), datetime.now().isoformat()),
        )
        conn.commit()
        logger.info(f"已添加到队列: {avid}")
        return {"success": True, "message": f"{avid} 已添加到下载队列"}
    except sqlite3.IntegrityError:
        return {"success": False, "message": f"{avid} 已在队列中"}
    except sqlite3.Error as e:
        logger.error(f"添加队列失败: {e}")
        return {"success": False, "message": f"数据库错误: {e}"}
    finally:
        conn.close()


def is_duplicate(avid: str) -> bool:
    """检查AVID是否已在队列中"""
    conn = _get_conn()
    try:
        row = conn.execute(
            "SELECT 1 FROM download_queue WHERE avid = ? LIMIT 1", (avid,)
        ).fetchone()
        return row is not None
    except sqlite3.Error as e:
        logger.error(f"查重失败: {e}")
        return False
    finally:
        conn.close()


def update_status(avid: str, status: str, progress: str = "",
                  source: str = "", title: str = "", error_msg: str = ""):
    """更新队列项状态"""
    conn = _get_conn()
    try:
        fields = ["status = ?", "updated_at = ?"]
        values: list = [status, datetime.now().isoformat()]

        if progress:
            fields.append("progress = ?")
            values.append(progress)
        if source:
            fields.append("source = ?")
            values.append(source)
        if title:
            fields.append("title = ?")
            values.append(title)
        if error_msg:
            fields.append("error_msg = ?")
            values.append(error_msg)

        values.append(avid)
        conn.execute(
            f"UPDATE download_queue SET {', '.join(fields)} WHERE avid = ?",
            values,
        )
        conn.commit()
    except sqlite3.Error as e:
        logger.error(f"更新状态失败: {e}")
    finally:
        conn.close()


def get_next_waiting() -> Optional[Dict[str, Any]]:
    """获取下一个等待中的任务（按创建时间排序）"""
    conn = _get_conn()
    try:
        row = conn.execute(
            "SELECT * FROM download_queue WHERE status = 'waiting' ORDER BY created_at ASC LIMIT 1"
        ).fetchone()
        return dict(row) if row else None
    except sqlite3.Error as e:
        logger.error(f"获取等待任务失败: {e}")
        return None
    finally:
        conn.close()


def get_queue_status() -> Dict[str, List[Dict[str, Any]]]:
    """获取完整队列状态，分类返回（历史仅返回最近10条，完整历史使用get_history_page）"""
    conn = _get_conn()
    try:
        def fetch_rows(query: str) -> List[Dict[str, Any]]:
            return [dict(r) for r in conn.execute(query).fetchall()]

        current = fetch_rows(
            "SELECT * FROM download_queue WHERE status IN ('downloading', 'searching', 'scraping', 'prowlarr_search') "
            "ORDER BY updated_at DESC"
        )
        waiting = fetch_rows(
            "SELECT * FROM download_queue WHERE status = 'waiting' ORDER BY created_at ASC"
        )
        history = fetch_rows(
            "SELECT * FROM download_queue WHERE status IN ('completed', 'failed') "
            "ORDER BY updated_at DESC LIMIT 10"
        )

        return {
            "current": current,
            "waiting": waiting,
            "history": history,
        }
    except sqlite3.Error as e:
        logger.error(f"获取队列状态失败: {e}")
        return {"current": [], "waiting": [], "history": []}
    finally:
        conn.close()


def get_item_status(item_id: int) -> Optional[Dict[str, Any]]:
    """获取单个队列项状态"""
    conn = _get_conn()
    try:
        row = conn.execute(
            "SELECT * FROM download_queue WHERE id = ?", (item_id,)
        ).fetchone()
        return dict(row) if row else None
    except sqlite3.Error as e:
        logger.error(f"获取项目状态失败: {e}")
        return None
    finally:
        conn.close()


def get_history_page(page: int = 1, per_page: int = 20,
                     status: str = "", source: str = "") -> Dict[str, Any]:
    """
    分页获取历史记录，支持按状态和下载方式筛选
    :param page: 页码（从1开始）
    :param per_page: 每页条数
    :param status: 筛选状态（completed / failed），为空则返回所有
    :param source: 筛选下载方式（下载器名称），为空则返回所有
    :return: { items, total, page, per_page, total_pages }
    """
    conn = _get_conn()
    try:
        # 构建动态WHERE子句
        conditions = ["status IN ('completed', 'failed')"]
        params: list = []

        if status in ("completed", "failed"):
            conditions.append("status = ?")
            params.append(status)

        if source:
            conditions.append("source = ?")
            params.append(source)

        where_clause = " AND ".join(conditions)

        # 查询总数
        count_sql = f"SELECT COUNT(*) FROM download_queue WHERE {where_clause}"
        total = conn.execute(count_sql, params).fetchone()[0]

        # 计算分页
        page = max(1, page)
        per_page = max(1, min(per_page, 100))  # 限制最大100条/页
        total_pages = max(1, (total + per_page - 1) // per_page)
        page = min(page, total_pages)
        offset = (page - 1) * per_page

        # 查询数据
        data_sql = (
            f"SELECT * FROM download_queue WHERE {where_clause} "
            f"ORDER BY updated_at DESC LIMIT ? OFFSET ?"
        )
        rows = conn.execute(data_sql, params + [per_page, offset]).fetchall()
        items = [dict(r) for r in rows]

        return {
            "items": items,
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": total_pages,
        }
    except sqlite3.Error as e:
        logger.error(f"获取历史分页失败: {e}")
        return {"items": [], "total": 0, "page": 1, "per_page": per_page, "total_pages": 1}
    finally:
        conn.close()


def get_distinct_sources() -> List[str]:
    """获取所有不同的下载方式（source值），用于筛选下拉框"""
    conn = _get_conn()
    try:
        rows = conn.execute(
            "SELECT DISTINCT source FROM download_queue "
            "WHERE source IS NOT NULL AND source != '' ORDER BY source"
        ).fetchall()
        return [r[0] for r in rows]
    except sqlite3.Error as e:
        logger.error(f"获取下载方式列表失败: {e}")
        return []
    finally:
        conn.close()


def retry_failed_item(item_id: int) -> Dict[str, Any]:
    """
    重试失败的队列项：将状态重置为waiting，保留created_at不变（不改变位置）。
    :return: {"success": bool, "message": str}
    """
    conn = _get_conn()
    try:
        row = conn.execute(
            "SELECT id, avid, status FROM download_queue WHERE id = ?", (item_id,)
        ).fetchone()
        if not row:
            return {"success": False, "message": "未找到该记录"}

        if row["status"] != "failed":
            return {"success": False, "message": "只能重试失败的项目"}

        conn.execute(
            "UPDATE download_queue SET status = 'waiting', progress = '', "
            "error_msg = '', source = '', title = '', updated_at = ? WHERE id = ?",
            (datetime.now().isoformat(), item_id),
        )
        conn.commit()
        logger.info(f"已重试失败项目: {row['avid']} (id={item_id})")
        return {"success": True, "message": f"{row['avid']} 已重新加入队列"}
    except sqlite3.Error as e:
        logger.error(f"重试失败项目异常: {e}")
        return {"success": False, "message": f"数据库错误: {e}"}
    finally:
        conn.close()
