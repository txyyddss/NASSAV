from .downloaderBase import *
import re
import json

class NetFlavDownloader(Downloader):
    def getDownloaderName(self) -> str:
        return "NetFlav"

    def getHTML(self, avid: str) -> Optional[str]:
        '''需要实现的方法：根据avid，构造url并请求，获取html, 返回字符串'''
        url = f"https://{self.domain}/video?id={avid}"
        logger.debug(url)
        content = self._fetch_html(url)
        if content: return content
        return None

    def parseHTML(self, html: str) -> Optional[AVDownloadInfo]:
        '''需要实现的方法：根据html，解析出元数据，返回AVDownloadInfo'''
        downloadInfo = AVDownloadInfo()

        # NetFlav 使用 Next.js，数据通常在 __NEXT_DATA__ 中
        match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.+?)</script>', html)
        if match:
            try:
                data = json.loads(match.group(1))
                initialState = data.get('props', {}).get('initialState', {})
                video_data = initialState.get('video', {}).get('data', {})
                
                if not video_data:
                    logger.error("NetFlav: 视频数据未找到，可能车牌号不正确或无源")
                    return None
                
                # 获取标题
                downloadInfo.title = video_data.get('title', '')
                downloadInfo.avid = video_data.get('videoId', '')
                
                # 获取视频源
                srcs = video_data.get('srcs', [])
                if srcs:
                    # 尝试找到 m3u8 格式的，否则拿第一个
                    m3u8_src = next((s for s in srcs if 'm3u8' in s), srcs[0])
                    downloadInfo.m3u8 = m3u8_src
                    logger.info(f"Found video src: {downloadInfo.m3u8}")
                else:
                    logger.error("NetFlav: 视频 srcs 为空")
                    return None
                    
            except Exception as e:
                logger.error(f"NetFlav JSON解析异常: {str(e)}")
                return None
        else:
            # 备用正则匹配
            m3u8_match = re.search(r'(https?://[^"\'\s]+\.m3u8)', html)
            if m3u8_match:
                downloadInfo.m3u8 = m3u8_match.group(1)
            else:
                logger.error("NetFlav: 未找到 __NEXT_DATA__ 或 m3u8")
                return None

        # 兜底截取番号（如未从json获取成功）
        if not downloadInfo.avid:
            if code_match := re.search(r'([A-Z]+(?:-[A-Z]+)*-\d+)', downloadInfo.title):
                downloadInfo.avid = code_match.group(1)
                
        return downloadInfo
