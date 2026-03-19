# 后台队列工作线程
import threading
import time
from loguru import logger
from .webui.models import (
    get_next_waiting, update_status, init_queue_db,
)
from .download_task import DownloadTask
from . import data
from .comm import downloaded_path


class QueueWorker:
    """
    后台下载队列工作线程
    - 每次处理一个任务
    - 自动从队列取下一个等待项
    - 通过进度回调更新数据库状态
    """

    def __init__(self):
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._poll_interval = 5  # 秒, 轮询间隔

    def start(self):
        """启动工作线程"""
        if self._thread and self._thread.is_alive():
            logger.warning("队列工作线程已在运行")
            return

        init_queue_db()
        data.initialize_db(downloaded_path, "MissAV")

        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True, name="QueueWorker")
        self._thread.start()
        logger.info("队列工作线程已启动")

    def stop(self):
        """停止工作线程"""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=10)
        logger.info("队列工作线程已停止")

    def _run(self):
        """主循环"""
        logger.info("队列工作线程开始运行...")
        while not self._stop_event.is_set():
            try:
                task_item = get_next_waiting()
                if task_item is None:
                    # 无等待任务，等待后再检查
                    self._stop_event.wait(self._poll_interval)
                    continue

                avid = task_item["avid"]
                logger.info(f"开始处理队列任务: {avid}")

                # 创建进度回调，更新数据库
                def progress_callback(av: str, status: str, msg: str):
                    update_status(av, status=status, progress=msg)

                # 标记为下载中
                update_status(avid, status="downloading", progress="开始处理...")

                try:
                    # 执行下载
                    dl_task = DownloadTask(progress_callback=progress_callback)
                    result = dl_task.execute(avid)

                    # 更新最终状态
                    if result["success"]:
                        update_status(
                            avid,
                            status="completed",
                            progress="下载完成",
                            source=result.get("source", ""),
                        )
                        # 记录到已下载数据库
                        try:
                            data.batch_insert_bvids([avid], downloaded_path, "MissAV")
                        except Exception as e:
                            logger.error(f"记录已下载失败: {e}")
                    else:
                        update_status(
                            avid,
                            status="failed",
                            progress="下载失败",
                            error_msg=result.get("error", "未知错误"),
                        )

                    logger.info(f"任务完成: {avid}, 结果: {'成功' if result['success'] else '失败'}")
                except Exception as task_e:
                    logger.error(f"处理任务 {avid} 异常: {task_e}")
                    update_status(
                        avid,
                        status="failed",
                        progress="下载异常",
                        error_msg=str(task_e),
                    )

            except Exception as e:
                logger.error(f"队列工作线程异常: {e}")
                time.sleep(5)  # 异常后等待后重试

        logger.info("队列工作线程退出")
