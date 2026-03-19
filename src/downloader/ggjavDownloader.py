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
        """尝试从外部嵌套页面中解析出 .mp4 或 .m3u8 真实地址，支持多种第三方播放器"""
        try:
            logger.info(f"Attempting to resolve external embed: {url}")
            html = self._fetch_html(url)
            if not html:
                return url
            
            # 1. 优先匹配 <source> 标签中的 src
            source_match = re.search(r'<source[^>]+src=["\']([^"\']+)["\']', html)
            if source_match:
                src = source_match.group(1)
                if '.m3u8' in src or '.mp4' in src:
                    logger.info(f"Resolved from <source> tag: {src}")
                    return src

            # 2. 匹配裸的 m3u8/mp4 URL
            m3u8_matches = re.findall(r'(https?://[^\s\"\'\<\>]*?\.m3u8[^\s\"\'\<\>]*)', html)
            if m3u8_matches:
                logger.info(f"Resolved m3u8 URL: {m3u8_matches[0]}")
                return m3u8_matches[0]
                
            mp4_matches = re.findall(r'(https?://[^\s\"\'\<\>]*?\.mp4[^\s\"\'\<\>]*)', html)
            if mp4_matches:
                logger.info(f"Resolved mp4 URL: {mp4_matches[0]}")
                return mp4_matches[0]
            
            # 3. 匹配 JS 变量赋值: file: "...", source: "..."
            js_patterns = [
                r'(?:file|source|video_url|videoUrl|src)\s*[:=]\s*["\']([^"\']+\.(?:m3u8|mp4)[^"\']*)["\']',
                r'(?:file|source)\s*:\s*["\']([^"\']+)["\']',
            ]
            for pattern in js_patterns:
                js_match = re.search(pattern, html, re.IGNORECASE)
                if js_match:
                    resolved = js_match.group(1)
                    if resolved.startswith('http'):
                        logger.info(f"Resolved from JS variable: {resolved}")
                        return resolved

            # 4. StreamTape 支持: 拼接 token URL
            if 'streamtape' in url.lower():
                st_match = re.search(r"document\.getElementById\('robotlink'\)\.innerHTML\s*=\s*'([^']+)'\s*\+\s*\('([^']+)'\)", html)
                if st_match:
                    resolved = 'https:' + st_match.group(1) + st_match.group(2)
                    logger.info(f"Resolved StreamTape URL: {resolved}")
                    return resolved

            # 5. DoodStream 支持
            if 'dood' in url.lower():
                dood_match = re.search(r"(https?://[^\s'\"]+/pass_md5/[^\s'\"]+)", html)
                if dood_match:
                    logger.info(f"Found DoodStream pass_md5 URL: {dood_match.group(1)}")
                    return dood_match.group(1)

            # 6. FileMoon / Filemoon 支持
            if 'filemoon' in url.lower() or 'fmoon' in url.lower():
                fm_match = re.search(r'sources:\s*\[\s*\{\s*file:\s*["\']([^"\']+)["\']', html)
                if fm_match:
                    logger.info(f"Resolved FileMoon URL: {fm_match.group(1)}")
                    return fm_match.group(1)

            # 7. 嵌套 iframe — 递归一层
            iframe_match = re.search(r'<iframe[^>]+src=["\']([^"\']+)["\']', html)
            if iframe_match:
                iframe_src = iframe_match.group(1)
                if iframe_src.startswith('//'):
                    iframe_src = 'https:' + iframe_src
                elif iframe_src.startswith('/'):
                    from urllib.parse import urlparse
                    parsed = urlparse(url)
                    iframe_src = f"{parsed.scheme}://{parsed.netloc}{iframe_src}"
                logger.info(f"Found nested iframe, resolving: {iframe_src}")
                return self._resolve_external_embed_inner(iframe_src)
                
        except Exception as e:
            logger.warning(f"Failed to resolve external embed URL {url}: {e}")
            
        return url

    def _resolve_external_embed_inner(self, url: str) -> str:
        """内层 iframe 解析，避免无限递归"""
        try:
            html = self._fetch_html(url)
            if not html:
                return url

            m3u8_matches = re.findall(r'(https?://[^\s\"\'\<\>]*?\.m3u8[^\s\"\'\<\>]*)', html)
            if m3u8_matches:
                return m3u8_matches[0]
            mp4_matches = re.findall(r'(https?://[^\s\"\'\<\>]*?\.mp4[^\s\"\'\<\>]*)', html)
            if mp4_matches:
                return mp4_matches[0]

            js_match = re.search(
                r'(?:file|source|video_url|videoUrl|src)\s*[:=]\s*["\']([^"\']+\.(?:m3u8|mp4)[^"\']*)["\']',
                html, re.IGNORECASE
            )
            if js_match and js_match.group(1).startswith('http'):
                return js_match.group(1)

        except Exception as e:
            logger.warning(f"Failed to resolve inner iframe {url}: {e}")
        return url

    def _resolve_video_url(self, raw_url: str, server_name: str) -> Optional[str]:
        """将原始服务器 URL 解析为可下载的真实视频 URL"""
        video_url = raw_url.strip()
        if not video_url:
            return None

        # 清理URL，只保留到 u= 参数，移除 &poster= 等后续参数
        if '&' in video_url and 'u=' in video_url:
            match = re.match(r'(https?://[^?]+\?u=[^&]+)', video_url)
            if match:
                video_url = match.group(1)
            else:
                video_url = video_url.split('&')[0]

        # 解码u参数获取真实视频地址
        is_resolved = False
        if 'u=' in video_url:
            u_match = re.search(r'[?&]u=([^&]+)', video_url)
            if u_match:
                u_param = u_match.group(1)
                try:
                    u_param += '=' * (-len(u_param) % 4)
                    real_video_url = base64.b64decode(u_param).decode('utf-8')
                    logger.debug(f"[{server_name}] Decoded real URL: {real_video_url}")
                    video_url = real_video_url
                    is_resolved = True
                except Exception as e:
                    logger.warning(f"[{server_name}] Failed to decode u parameter: {e}")

        # 第三方 embed 页面解析
        if not is_resolved and not video_url.endswith('.m3u8') and not video_url.endswith('.mp4'):
            video_url = self._resolve_external_embed(video_url)

        # mmsi 服务器的 .mp4 实际是 HLS
        if video_url.endswith('.mp4') and 'mmsi' in video_url:
            video_url = video_url + '/index.m3u8'
            logger.debug(f"[{server_name}] Converted .mp4 to .m3u8: {video_url}")

        return video_url

    def parseHTML(self, html: str) -> Optional[AVDownloadInfo]:
        '''解析解密后的视频链接数据，提取所有可用源（主源 + 备用源）'''
        downloadInfo = AVDownloadInfo()

        try:
            data = json.loads(html)
            links = data.get('links', {})

            if not links:
                logger.error("No links data found in decrypted content")
                return None

            # 定义优先级顺序
            priority_servers = ['ggjav', 'mmsi01', 'mmvh01']
            # 构建有序的遍历列表：优先服务器在前，其他在后
            ordered_servers = []
            for s in priority_servers:
                if s in links and links[s]:
                    ordered_servers.append(s)
            for s in links:
                if s not in ordered_servers and links[s]:
                    ordered_servers.append(s)

            logger.info(f"Available servers (ordered): {ordered_servers}")

            # 收集所有源的解析后 URL
            all_urls = []
            for server in ordered_servers:
                server_links = links[server]
                raw_url = None
                if isinstance(server_links, list) and len(server_links) > 0:
                    raw_url = server_links[0]
                elif isinstance(server_links, str):
                    raw_url = server_links

                if not raw_url:
                    continue

                try:
                    resolved = self._resolve_video_url(raw_url, server)
                    if resolved:
                        logger.info(f"[{server}] Resolved URL: {resolved}")
                        all_urls.append(resolved)
                    else:
                        logger.warning(f"[{server}] Failed to resolve URL")
                except Exception as e:
                    logger.warning(f"[{server}] Error resolving URL: {e}")
                    continue

            if not all_urls:
                logger.error(f"No video URL resolved from any server. Raw data: {links}")
                return None

            # 第一个作为主源，其余作为备用源
            downloadInfo.m3u8 = all_urls[0]
            downloadInfo.fallback_urls = all_urls[1:]
            
            logger.info(f"Primary URL: {downloadInfo.m3u8}")
            if downloadInfo.fallback_urls:
                logger.info(f"Fallback URLs ({len(downloadInfo.fallback_urls)}): {downloadInfo.fallback_urls}")

            return downloadInfo
            
        except Exception as e:
            logger.error(f"Failed to parse decrypted data: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None
