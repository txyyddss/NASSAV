from .downloader.downloaderBase import Downloader
from .downloader.jableDownloder import JableDownloader
from .downloader.missAVDownloader import MissAVDownloader
from .downloader.hohoJDownloader import HohoJDownloader
from .downloader.memoDownloader import MemoDownloader
from .downloader.KanAVDownloader import KanAVDownloader
from .downloader.avtodayDownloader import AvTodayDownloader
from .downloader.netFlavDownloader import NetFlavDownloader
from .downloader.ggjavDownloader import GGJavDownloader
from .comm import *
from typing import Optional

class DownloaderMgr:

    def __init__(self):
        self.downloaders = {}
        # 手动注册handler
        downloader = MissAVDownloader(save_path, myproxy)
        self.downloaders[downloader.getDownloaderName()] = downloader

        downloader = JableDownloader(save_path, myproxy)
        self.downloaders[downloader.getDownloaderName()] = downloader

        downloader = HohoJDownloader(save_path, myproxy)
        self.downloaders[downloader.getDownloaderName()] = downloader

        downloader = MemoDownloader(save_path, myproxy)
        self.downloaders[downloader.getDownloaderName()] = downloader
        
        downloader = KanAVDownloader(save_path, myproxy)
        self.downloaders[downloader.getDownloaderName()] = downloader

        downloader = AvTodayDownloader(save_path, myproxy)
        self.downloaders[downloader.getDownloaderName()] = downloader

        downloader = NetFlavDownloader(save_path, myproxy)
        self.downloaders[downloader.getDownloaderName()] = downloader

        downloader = GGJavDownloader(save_path, myproxy)
        self.downloaders[downloader.getDownloaderName()] = downloader
    
    def GetDownloader(self, downloaderName: str) -> Optional[Downloader]:
        return self.downloaders.get(downloaderName)
