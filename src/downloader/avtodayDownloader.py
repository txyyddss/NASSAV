from .downloaderBase import *
import re
import json

class AvTodayDownloader(Downloader):
    def getDownloaderName(self) -> str:
        return "AvToday"

    def getHTML(self, avid: str) -> Optional[str]:
        '''需要实现的方法：根据avid，构造url并请求，获取html, 返回字符串'''
        # 尝试通过搜索获取
        searchUrl = f"https://{self.domain}/search?keyword={avid}".lower()
        logger.debug(searchUrl)
        content = self._fetch_html(searchUrl)
        if not content: return None

        pageUrl = None
        # 匹配搜索结果中的视频链接，可能如 /video/FC2PPV-xxxx 或类似于 /v/xxxx
        match = re.search(r'href="(/video/[^"]+)"', content, re.IGNORECASE)
        if match:
            pageUrl = f"https://{self.domain}{match.group(1)}"
        else:
            # 备用方案，尝试直接访问
            pageUrl = f"https://{self.domain}/video/{avid}".lower()
            
        logger.info(pageUrl)
        content = self._fetch_html(pageUrl)
        if content: return content
        return None

    def parseHTML(self, html: str) -> Optional[AVDownloadInfo]:
        '''需要实现的方法：根据html，解析出元数据，返回AVDownloadInfo'''
        downloadInfo = AVDownloadInfo()

        # 1. 尝试提取视频链接或iframe中的源
        # 寻找 m3u8
        m3u8_match = re.search(r'(https?://[^"\'\s]+\.m3u8)', html)
        if m3u8_match:
            downloadInfo.m3u8 = m3u8_match.group(1)
            logger.info(f"Found m3u8: {downloadInfo.m3u8}")
        else:
            # 寻找播放器iframe或者js变量作为备选（框架提供支持，具体可能需后续补全）
            iframe_match = re.search(r'<iframe[^>]+src="([^"]+)"', html)
            if iframe_match:
                # 若需要进一步请求 iframe 提取，则在此处理
                iframe_src = iframe_match.group(1)
                if iframe_src.startswith('/'):
                    iframe_src = f"https://{self.domain}{iframe_src}"
                logger.info(f"Found iframe src, might need further parsing: {iframe_src}")
                iframe_html = self._fetch_html(iframe_src, referer=f"https://{self.domain}/")
                if iframe_html:
                    iframe_m3u8 = re.search(r'(https?://[^"\'\s]+\.m3u8)', iframe_html)
                    if iframe_m3u8:
                        downloadInfo.m3u8 = iframe_m3u8.group(1)
                        logger.info(f"Found m3u8 in iframe: {downloadInfo.m3u8}")
                    else:
                        logger.error("未在 iframe 中找到 m3u8")
                        return None
            else:
                logger.error("未找到 m3u8 或可用 iframe")
                return None

        # 2. 提取基本信息
        self._extract_metadata(html, downloadInfo)
        
        return downloadInfo

    @staticmethod
    def _extract_metadata(html: str, metadata: AVDownloadInfo) -> bool:
        try:
            # 提取OG标签标题
            og_title = re.search(r'<meta property="og:title" content="([^"]+)"', html)
            if og_title: 
                title_content = og_title.group(1)
                # 尝试分离番号
                if code_match := re.search(r'([A-Z]+(?:-[A-Z]+)*-\d+)', title_content):
                    metadata.avid = code_match.group(1)
                    metadata.title = title_content.replace(metadata.avid, '').strip()
                else:
                    metadata.title = title_content.strip()
        except Exception as e:
            logger.error(f"元数据解析异常: {str(e)}")
            return False
        return True
