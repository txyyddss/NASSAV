# Prowlarr API 兜底搜索模块
import json
from loguru import logger
from typing import Optional, List, Dict, Any
from .comm import prowlarr_config, deepseek_config, myproxy
from curl_cffi import requests as cffi_requests
import time


class ProwlarrClient:
    """Prowlarr索引器API客户端，用于兜底种子搜索"""

    def __init__(self):
        self.base_url = prowlarr_config["URL"].rstrip("/")
        self.api_key = prowlarr_config["APIKey"]
        self.timeout = prowlarr_config["Timeout"]
        self.enabled = prowlarr_config["Enabled"]
        self.max_retries = 3
        self.retry_delay = 2

    def search(self, avid: str) -> Optional[List[Dict[str, Any]]]:
        """
        搜索Prowlarr索引器
        :param avid: 车牌号
        :return: 有效结果列表(seeders > 0)，失败返回None
        """
        if not self.enabled:
            logger.warning("Prowlarr未启用")
            return None

        if not self.api_key:
            logger.error("Prowlarr API Key未配置")
            return None

        url = (
            f"{self.base_url}/api/v1/search"
            f"?query={avid}&categories=6000&type=search"
            f"&limit=100&offset=0&apikey={self.api_key}"
        )

        for attempt in range(1, self.max_retries + 1):
            try:
                logger.info(f"Prowlarr搜索 '{avid}' (尝试 {attempt}/{self.max_retries})")
                response = cffi_requests.get(
                    url,
                    timeout=self.timeout,
                    impersonate="chrome110",
                )
                response.raise_for_status()
                results = response.json()

                if not isinstance(results, list):
                    logger.error(f"Prowlarr返回非预期格式: {type(results)}")
                    return None

                # 过滤: 仅保留seeders > 0的结果
                valid_results = [r for r in results if r.get("seeders", 0) > 0]
                logger.info(f"Prowlarr搜索到 {len(results)} 个结果, {len(valid_results)} 个有效(seeders>0)")

                if not valid_results:
                    logger.warning(f"Prowlarr未找到有效种子: {avid}")
                    return None

                # 为每个结果添加ID字段
                for idx, item in enumerate(valid_results):
                    item["ID"] = idx + 1

                return valid_results

            except Exception as e:
                logger.error(f"Prowlarr搜索失败 (尝试 {attempt}/{self.max_retries}): {e}")
                if attempt < self.max_retries:
                    wait = self.retry_delay * attempt
                    logger.info(f"等待 {wait}s 后重试...")
                    time.sleep(wait)

        return None

    def select_best_torrent(self, results: List[Dict[str, Any]], avid: str) -> Optional[Dict[str, Any]]:
        """
        调用DeepSeek API选择最佳种子
        :param results: Prowlarr搜索结果列表(已含ID字段)
        :param avid: 车牌号
        :return: 选中的资源dict，失败返回None
        """
        if not deepseek_config.get("APIKey"):
            logger.error("DeepSeek API Key未配置，使用默认选择策略")
            return self._fallback_select(results, avid)

        try:
            from openai import OpenAI

            client = OpenAI(
                api_key=deepseek_config["APIKey"],
                base_url=deepseek_config["BaseURL"],
            )

            # 构造发送给AI的信息
            items_info = []
            for item in results:
                items_info.append({
                    "ID": item["ID"],
                    "title": item.get("title", ""),
                    "sortTitle": item.get("sortTitle", ""),
                    "size": item.get("size", 0),
                    "size_gb": round(item.get("size", 0) / (1024**3), 2),
                    "seeders": item.get("seeders", 0),
                    "leechers": item.get("leechers", 0),
                    "indexer": item.get("indexer", ""),
                    "age_hours": round(item.get("ageHours", 0), 1),
                })

            system_prompt = (
                "你是一个种子资源选择助手。用户会给你一组种子搜索结果，"
                "你需要根据以下规则选择最佳的一个种子并仅返回其ID数字：\n"
                "1. 优先选择title与搜索番号完全匹配或最接近的资源\n"
                "2. 在匹配度相近时，优先选择文件最大的（通常画质更好）\n"
                "3. seeders越多越好，确保能够下载\n"
                "4. 忽略明显无关的结果（如合集/pack）\n"
                "5. 如果所有结果都与搜索番号明显不相关，则返回None\n"
                "6. 仅返回一个数字ID或None，不要返回任何其他内容"
            )

            user_prompt = (
                f"搜索番号: {avid}\n\n"
                f"搜索结果:\n{json.dumps(items_info, ensure_ascii=False, indent=2)}\n\n"
                "请选择最佳种子，仅返回ID数字。如果没有合适的种子请返回None。"
            )

            logger.info("调用DeepSeek API选择最佳种子...")
            response = client.chat.completions.create(
                model=deepseek_config["Model"],
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                stream=False,
            )

            answer = response.choices[0].message.content.strip()
            logger.info(f"DeepSeek返回: {answer}")

            # 检查AI是否返回了None（表示没有合适的种子）
            if answer.lower() == "none":
                logger.warning(f"AI判断没有合适的种子: {avid}")
                return None

            # 提取ID数字
            selected_id = None
            for part in answer.split():
                try:
                    selected_id = int(part)
                    break
                except ValueError:
                    continue

            if selected_id is None:
                # 尝试从整个字符串提取
                import re
                match = re.search(r'\d+', answer)
                if match:
                    selected_id = int(match.group())

            if selected_id is None:
                logger.error(f"无法从AI响应中提取ID: {answer}")
                return self._fallback_select(results, avid)

            # 查找对应资源
            for item in results:
                if item["ID"] == selected_id:
                    logger.info(f"AI选择: ID={selected_id}, title={item.get('title', '')}, "
                                f"size={round(item.get('size', 0) / (1024**3), 2)}GB")
                    return item

            logger.error(f"AI返回的ID {selected_id} 不在结果中")
            return self._fallback_select(results, avid)

        except Exception as e:
            logger.error(f"DeepSeek API调用失败: {e}")
            return self._fallback_select(results, avid)

    @staticmethod
    def _fallback_select(results: List[Dict[str, Any]], avid: str) -> Optional[Dict[str, Any]]:
        """
        备选选择策略：当AI不可用时，按size最大 + seeders最多排序
        """
        if not results:
            return None

        logger.info("使用备选策略选择种子（按大小+seeders排序）")

        # 优先匹配标题
        avid_upper = avid.upper()
        exact_matches = [
            r for r in results
            if r.get("title", "").upper().strip() == avid_upper
        ]
        pool = exact_matches if exact_matches else results

        # 按 size 降序, seeders 降序
        pool.sort(key=lambda x: (x.get("size", 0), x.get("seeders", 0)), reverse=True)
        selected = pool[0]
        logger.info(f"备选选择: title={selected.get('title', '')}, "
                     f"size={round(selected.get('size', 0) / (1024**3), 2)}GB, "
                     f"seeders={selected.get('seeders', 0)}")
        return selected

    def add_download(self, guid: str, indexer_id: int) -> bool:
        """
        向Prowlarr添加下载任务
        :param guid: 资源的guid
        :param indexer_id: 索引器ID
        :return: 是否成功
        """
        url = f"{self.base_url}/api/v1/search?apikey={self.api_key}"
        payload = {"guid": guid, "indexerId": indexer_id}

        for attempt in range(1, self.max_retries + 1):
            try:
                logger.info(f"Prowlarr添加下载 (尝试 {attempt}/{self.max_retries}): guid={guid}")
                response = cffi_requests.post(
                    url,
                    json=payload,
                    timeout=self.timeout,
                    impersonate="chrome110",
                    headers={"Content-Type": "application/json"},
                )
                response.raise_for_status()
                logger.info(f"Prowlarr下载添加成功: {response.text[:200]}")
                return True

            except Exception as e:
                logger.error(f"Prowlarr添加下载失败 (尝试 {attempt}/{self.max_retries}): {e}")
                if attempt < self.max_retries:
                    wait = self.retry_delay * attempt
                    logger.info(f"等待 {wait}s 后重试...")
                    time.sleep(wait)

        return False

    def full_flow(self, avid: str) -> bool:
        """
        完整的Prowlarr兜底流程: 搜索 -> AI选择 -> 添加下载
        :param avid: 车牌号
        :return: 是否成功
        """
        logger.info(f"===== 开始Prowlarr兜底流程: {avid} =====")

        # 1. 搜索
        results = self.search(avid)
        if not results:
            logger.error(f"Prowlarr搜索无结果: {avid}")
            return False

        # 2. AI选择
        selected = self.select_best_torrent(results, avid)
        if not selected:
            logger.error(f"无法选择种子: {avid}")
            return False

        # 3. 添加下载
        guid = selected.get("guid", "")
        indexer_id = selected.get("indexerId", 0)
        if not guid or not indexer_id:
            logger.error(f"资源信息不完整: guid={guid}, indexerId={indexer_id}")
            return False

        success = self.add_download(guid, indexer_id)
        if success:
            logger.info(f"===== Prowlarr兜底成功: {avid} =====")
        else:
            logger.error(f"===== Prowlarr兜底失败: {avid} =====")

        return success
