# 下载任务核心逻辑（从main.py抽取）
from loguru import logger
from typing import Optional, Callable
from . import downloaderMgr
from .comm import (
    save_path, downloaded_path, myproxy, sorted_downloaders,
    scraper_enabled, prowlarr_config,
)
from . import data
from .prowlarr import ProwlarrClient
import time
import os


# 进度回调类型: callback(avid, status, progress_msg)
ProgressCallback = Optional[Callable[[str, str, str], None]]


class DownloadTask:
    """
    可复用的下载任务，支持进度回调
    status 枚举: searching / downloading / scraping / prowlarr_search / completed / failed
    """

    def __init__(self, progress_callback: ProgressCallback = None, max_retries: int = 2):
        self.progress_callback = progress_callback
        self.max_retries = max_retries
        self.mgr = downloaderMgr.DownloaderMgr()

    def _report(self, avid: str, status: str, msg: str):
        """报告进度"""
        logger.info(f"[{avid}] {status}: {msg}")
        if self.progress_callback:
            try:
                self.progress_callback(avid, status, msg)
            except Exception as e:
                logger.error(f"进度回调异常: {e}")

    def execute(self, avid: str, force: bool = False) -> dict:
        """
        执行完整的下载流程
        :param avid: 车牌号
        :param force: 是否跳过DB检查
        :return: {"success": bool, "source": str, "error": str}
        """
        avid = avid.upper()

        # 检查是否已下载
        if not force:
            data.initialize_db(downloaded_path, "MissAV")
            if data.find_in_db(avid, downloaded_path, "MissAV"):
                self._report(avid, "completed", "已在数据库中，跳过下载")
                return {"success": True, "source": "already_downloaded", "error": ""}

        self._report(avid, "searching", "开始搜索下载源...")

        # 检查是否已存在于SavePath中
        target_dir = os.path.join(save_path, avid)
        mp4_path = os.path.join(target_dir, f"{avid}.mp4")
        if os.path.exists(mp4_path) and not force:
            self._report(avid, "completed", "视频文件已存在")
            return {"success": True, "source": "already_exists", "error": ""}

        # 阶段1: 尝试所有配置的下载器
        downloader_result = self._try_downloaders(avid)
        if downloader_result["success"]:
            # 阶段2: 元数据刮削(可选)
            if scraper_enabled:
                self._run_scraper(avid)
            return downloader_result

        # 阶段3: Prowlarr兜底
        if prowlarr_config.get("Enabled", False):
            prowlarr_result = self._try_prowlarr(avid)
            if prowlarr_result["success"]:
                return prowlarr_result

        self._report(avid, "failed", "所有下载方式均失败")
        return {"success": False, "source": "", "error": "所有下载方式均失败"}

    def _try_downloaders(self, avid: str) -> dict:
        """尝试使用配置的下载器下载"""
        if not sorted_downloaders:
            logger.error("cfg没有配置下载器")
            return {"success": False, "source": "", "error": "cfg没有配置下载器"}

        for attempt in range(1, self.max_retries + 1):
            count = 0
            for it in sorted_downloaders:
                count += 1
                downloader_name = it["downloaderName"]
                try:
                    downloader = self.mgr.GetDownloader(downloader_name)
                    if downloader is None:
                        logger.error(f"下载器 {downloader_name} 没有找到")
                        continue

                    if not downloader.setDomain(it["domain"]):
                        logger.error(f"下载器 {downloader_name} 的域名没有配置")
                        continue

                    self._report(avid, "searching", f"尝试 {downloader_name} ({count}/{len(sorted_downloaders)})")

                    # 获取下载信息
                    info = downloader.downloadInfo(avid)
                    if not info:
                        logger.error(f"{avid} 通过 {downloader_name} 下载元数据失败")
                        continue

                    logger.info(info)
                    self._report(avid, "downloading", f"通过 {downloader_name} 下载中...")

                    # 下载视频
                    if not downloader.downloadM3u8(info.m3u8, avid):
                        logger.error(f"{info.m3u8} 通过 {downloader_name} 下载视频失败")
                        continue

                    self._report(avid, "completed", f"通过 {downloader_name} 下载成功")
                    return {"success": True, "source": downloader_name, "error": ""}

                except Exception as e:
                    logger.error(f"下载器 {downloader_name} 异常: {e}")
                    continue

            if attempt < self.max_retries:
                wait = 5 * attempt
                logger.info(f"所有下载器尝试失败，等待 {wait}s 后重试 (尝试 {attempt}/{self.max_retries})")
                self._report(avid, "searching", f"所有下载器失败，等待重试 ({attempt}/{self.max_retries})...")
                time.sleep(wait)

        return {"success": False, "source": "", "error": "所有下载器均失败"}

    def _try_prowlarr(self, avid: str) -> dict:
        """Prowlarr兜底"""
        self._report(avid, "prowlarr_search", "触发Prowlarr兜底搜索...")
        try:
            client = ProwlarrClient()
            success = client.full_flow(avid)
            if success:
                self._report(avid, "completed", "通过Prowlarr兜底成功")
                return {"success": True, "source": "Prowlarr", "error": ""}
            else:
                return {"success": False, "source": "", "error": "Prowlarr兜底失败"}
        except Exception as e:
            logger.error(f"Prowlarr兜底异常: {e}")
            return {"success": False, "source": "", "error": f"Prowlarr兜底异常: {e}"}

    def _run_scraper(self, avid: str):
        """运行元数据刮削器（可选）"""
        try:
            self._report(avid, "scraping", "正在刮削元数据...")
            from .scraper import Sracper
            scraper = Sracper(save_path, myproxy)
            result = scraper.scrape(avid)
            if result:
                logger.info(f"{avid} 刮削成功")
            else:
                logger.warning(f"{avid} 刮削失败（不影响下载结果）")
        except Exception as e:
            logger.warning(f"{avid} 刮削异常（不影响下载结果）: {e}")
