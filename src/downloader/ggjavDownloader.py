import re
import base64
import json
import time
import random
from typing import Optional

from loguru import logger
from curl_cffi import requests

from .downloaderBase import Downloader, AVDownloadInfo

class GGJavDownloader(Downloader):
    def __init__(self, path: str, proxy=None, timeout=15):
        super().__init__(path, proxy, timeout)

    def getDownloaderName(self) -> str:
        return "GGJav"

    def _fetch_with_retry(self, url: str, referer: str = None, max_retries: int = 3) -> Optional[str]:
        """带重试的请求方法"""
        for attempt in range(max_retries):
            try:
                # 添加随机延迟，避免请求过快
                if attempt > 0:
                    delay = random.uniform(2, 5)
                    logger.debug(f"Retry {attempt + 1}/{max_retries}, waiting {delay:.1f}s...")
                    time.sleep(delay)
                
                content = self._fetch_html(url, referer=referer)
                if content:
                    return content
                    
            except Exception as e:
                logger.warning(f"Attempt {attempt + 1} failed: {e}")
                if attempt == max_retries - 1:
                    raise
        
        return None

    def getHTML(self, avid: str) -> Optional[str]:
        '''需要先搜索,获取到详情页url,然后解析页面中的加密视频链接'''
        # 添加小延迟，模拟人类行为
        time.sleep(random.uniform(0.5, 1.5))
        
        searchUrl = f"https://{self.domain}/main/search?string={avid}"
        logger.debug(searchUrl)
        
        try:
            content = self._fetch_with_retry(searchUrl)
        except Exception as e:
            logger.error(f"Failed to fetch search page: {e}")
            return None
            
        if not content: 
            return None

        # 提取视频详情页的ID
        first_id = None
        match = re.search(r'[?&]id=(\d+)', content)
        if match:
            first_id = match.group(1)
            logger.info(f"Found video ID: {first_id}")
        if not first_id:
            logger.error("未找到视频ID")
            return None
        
        # 添加延迟
        time.sleep(random.uniform(1, 2))
        
        # 访问视频详情页
        videoPageUrl = f"https://{self.domain}/main/video?id={first_id}"
        logger.debug(f"Video page URL: {videoPageUrl}")
        
        try:
            videoPageContent = self._fetch_with_retry(
                videoPageUrl, 
                referer=searchUrl
            )
        except Exception as e:
            logger.error(f"Failed to fetch video page: {e}")
            return None
            
        if not videoPageContent:
            logger.error("无法获取视频详情页")
            return None
        
        # 从页面中提取加密的视频链接数据
        match = re.search(r'var\s+l\s*=\s*["\']([^"\']+)["\']', videoPageContent)
        if not match:
            logger.error("未找到加密的视频链接数据")
            return None
        
        encrypted_data = match.group(1)
        logger.debug(f"Found encrypted data (length: {len(encrypted_data)})")
        
        # 解密视频链接
        try:
            # Step 1: Base64 解码得到字节数组
            decoded_bytes = base64.b64decode(encrypted_data)
            logger.debug(f"Decoded bytes length: {len(decoded_bytes)}")
            
            # Step 2: 对每个字节减去 0x58，然后转换为字符
            decrypted = ''
            for byte in decoded_bytes:
                char_code = byte - 0x58
                if char_code < 0:
                    char_code += 256
                decrypted += chr(char_code)
            
            logger.debug(f"Decrypted string length: {len(decrypted)}")
            logger.debug(f"Decrypted string preview: {decrypted[:100]}")
            
            # Step 3: 解析JSON
            links_data = json.loads(decrypted)
            logger.info(f"Successfully decrypted video links")
            logger.debug(f"Available servers: {list(links_data.keys())}")
            
            return json.dumps({
                'links': links_data,
                'video_id': first_id,
                'page_url': videoPageUrl
            })
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON: {e}")
            logger.error(f"Decrypted content: {decrypted[:500]}")
            return None
        except Exception as e:
            logger.error(f"Failed to decrypt video links: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None

    def _resolve_external_embed(self, url: str) -> str:
        """尝试从外部嵌套页面中解析出 .mp4 或 .m3u8 真实地址"""
        try:
            logger.info(f"Attempting to resolve external embed: {url}")
            html = self._fetch_html(url)
            if not html:
                return url
            
            # 优先匹配常见的 source 标签内或者字符串中的裸的 mp4/m3u8
            m3u8_matches = re.findall(r'(https?://[^\s\"\'<>]*?\.m3u8[^\s\"\'<>]*)', html)
            if m3u8_matches:
                return m3u8_matches[0]
                
            mp4_matches = re.findall(r'(https?://[^\s\"\'<>]*?\.mp4[^\s\"\'<>]*)', html)
            if mp4_matches:
                return mp4_matches[0]
                
        except Exception as e:
            logger.warning(f"Failed to resolve external embed URL {url}: {e}")
            
        return url

    def parseHTML(self, html: str) -> Optional[AVDownloadInfo]:
        '''解析解密后的视频链接数据'''
        downloadInfo = AVDownloadInfo()

        try:
            data = json.loads(html)
            links = data.get('links', {})
            
            # 尝试从不同的服务器获取视频URL
            video_url = None
            
            for server in ['ggjav', 'mmsi01', 'mmvh01']:
                if server in links and links[server]:
                    server_links = links[server]
                    if isinstance(server_links, list) and len(server_links) > 0:
                        video_url = server_links[0].strip()
                    elif isinstance(server_links, str):
                        video_url = server_links.strip()
                    
                    if video_url:
                        logger.info(f"Found video URL from server '{server}': {video_url}")
                        break
            
            if not video_url:
                for server, urls in links.items():
                    if urls:
                        if isinstance(urls, list) and len(urls) > 0:
                            video_url = urls[0].strip()
                        elif isinstance(urls, str):
                            video_url = urls.strip()
                        if video_url:
                            logger.info(f"Found video URL from fallback server '{server}': {video_url}")
                            break
            
            if not video_url:
                logger.error(f"No video URL found in decrypted data")
                logger.error(f"Available data: {links}")
                return None
            
            # 清理URL，只保留到 u= 参数，移除 &poster= 等后续参数
            if '&' in video_url and 'u=' in video_url:
                match = re.match(r'(https?://[^?]+\?u=[^&]+)', video_url)
                if match:
                    video_url = match.group(1)
                    logger.debug(f"Cleaned video URL: {video_url}")
                else:
                    parts = video_url.split('&')
                    # 取出包含 u= 的部分并尝试组装，不过直接 split 也能应对一些情况
                    video_url = parts[0]
                    logger.debug(f"Cleaned video URL (fallback): {video_url}")
            
            # 关键步骤：解码u参数获取真实视频地址（GGJav等自带服务器用）
            is_resolved = False
            if 'u=' in video_url:
                u_match = re.search(r'[?&]u=([^&]+)', video_url)
                if u_match:
                    u_param = u_match.group(1)
                    try:
                        # Base64解码u参数得到真实视频URL
                        u_param += '=' * (-len(u_param) % 4)
                        real_video_url = base64.b64decode(u_param).decode('utf-8')
                        logger.info(f"Decoded real video URL from u parameter: {real_video_url}")
                        video_url = real_video_url
                        is_resolved = True
                    except Exception as e:
                        logger.warning(f"Failed to decode u parameter: {e}, using original URL")
            
            # 其他流处理：如果不包含 mp4 且不包含 m3u8，这大概率是个 iframe 或第三方网页
            if not is_resolved and not video_url.endswith('.m3u8') and not video_url.endswith('.mp4'):
                video_url = self._resolve_external_embed(video_url)

            # 再次检查是否是.mp4文件，如果是，有些流返回的是 .mp4，但本质是HLS链接目录
            if video_url.endswith('.mp4') and 'mmsi' in video_url:
                # 将 .mp4 转换为 .mp4/index.m3u8
                video_url = video_url + '/index.m3u8'
                logger.info(f"Converted .mp4 to .m3u8: {video_url}")
            
            downloadInfo.m3u8 = video_url
            logger.info(f"Final video URL: {video_url}")
            return downloadInfo
            
        except Exception as e:
            logger.error(f"Failed to parse decrypted data: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None
