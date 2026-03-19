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
    """获取完整队列状态，分类返回"""
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
            "ORDER BY updated_at DESC LIMIT 100"
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
