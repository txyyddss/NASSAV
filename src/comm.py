import json
import random
from loguru import logger
import os
import platform

# 获取项目目录
current_file_path = os.path.abspath(__file__)
project_root = os.path.dirname(os.path.dirname(current_file_path))

# 获取配置
with open(project_root+'/cfg/configs.json', 'r', encoding='utf-8') as file:
    configs = json.load(file)
logger.info(configs)

# 初始化日志
logger.add(
    configs["LogPath"]+"/{time:YYYY-MM-DD}.log",
    rotation="00:00",            
    retention="3 days", 
    enqueue=False,
    level="DEBUG",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}"
)

# 存储到变量中
save_path = configs["SavePath"]
downloaded_path = configs["DBPath"]
queue_path = configs["QueuePath"]
myproxy = configs["Proxy"]
isNeedVideoProxy = configs["IsNeedVideoProxy"]
if myproxy == "":
    myproxy = None
sorted_downloaders = sorted(
    [downloader for downloader in configs["Downloader"] if downloader["weight"] != 0],
    key=lambda x: x["weight"],
    reverse=True  # 降序排序
)
print(sorted_downloaders)
missAVDomain = ""
for downloader in configs["Downloader"]:
    if downloader["downloaderName"] == "MissAV":
        missAVDomain = downloader["domain"]
        break
logger.info(f"missav domain: {missAVDomain}")

scraperDomain = random.choice(configs["ScraperDomain"])
logger.info(f"scraper domain: {scraperDomain}")

# 新功能配置（向后兼容，缺失字段使用默认值）
scraper_enabled = configs.get("ScraperEnabled", True)

webui_config = configs.get("WebUI", {})
webui_config.setdefault("Enabled", False)
webui_config.setdefault("Port", 5177)
webui_config.setdefault("TurnstileSiteKey", "")
webui_config.setdefault("TurnstileSecretKey", "")

prowlarr_config = configs.get("Prowlarr", {})
prowlarr_config.setdefault("Enabled", False)
prowlarr_config.setdefault("URL", "http://localhost:9696")
prowlarr_config.setdefault("APIKey", "")
prowlarr_config.setdefault("Timeout", 30)

deepseek_config = configs.get("DeepSeek", {})
deepseek_config.setdefault("APIKey", "")
deepseek_config.setdefault("Model", "deepseek-reasoner")
deepseek_config.setdefault("BaseURL", "https://api.deepseek.com")

flaresolverr_config = configs.get("Flaresolverr", {})
flaresolverr_config.setdefault("Enabled", False)
flaresolverr_config.setdefault("URL", "http://localhost:8191")
flaresolverr_config.setdefault("Timeout", 60)


# 初始化下载器
download_tool = f"'{project_root}/tools/m3u8-Downloader-Go'"
ffmpeg_tool = f"'ffmpeg'"
if platform.system() == 'Windows':
    print("platform: Windows")
    download_tool = rf'"{project_root}\tools\m3u8-Downloader-Go.exe"'
    ffmpeg_tool = rf'"{project_root}\tools\ffmpeg.exe"'