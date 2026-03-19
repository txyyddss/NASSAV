from src import downloaderMgr
from src.comm import *
from src import data
import sys
import argparse
from metadata import *

def append_if_not_duplicate(filename, new_content):
    new_content = new_content.strip()
    try:
        with open(filename, 'r', encoding='utf-8') as file:
            existing_lines = [line.strip() for line in file.readlines()]
    except FileNotFoundError:
        existing_lines = []
    
    if new_content not in existing_lines:
        with open(filename, 'a', encoding='utf-8') as file:
            file.write(new_content + '\n')
        return True
    else:
        return False


def run_webui():
    """启动WebUI模式"""
    from src.webui.app import create_app
    from src.queue_worker import QueueWorker

    port = webui_config.get("Port", 5177)

    # 启动队列工作线程
    worker = QueueWorker()
    worker.start()

    # 启动Flask
    logger.info(f"启动WebUI，端口: {port}")
    app = create_app()

    try:
        app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
    except KeyboardInterrupt:
        logger.info("收到停止信号")
    finally:
        worker.stop()


def run_cli(args):
    """CLI模式（保留原有逻辑）"""
    data.initialize_db(downloaded_path, "MissAV")

    avid = args.target.upper()

    if not args.force:
        if data.find_in_db(avid, downloaded_path, "MissAV"):
            logger.info(f"{avid} 已在小姐姐数据库中")
            exit(0)
            
    logger.info(f"开始执行 车牌号: {avid}")

    import os
    if os.path.exists("work"):
        with open("work", "r") as f:
            content = f.read().strip()
        if content == "1":
            logger.info(f"A download task is running, save {avid} to download queue")
            with open(queue_path, 'a') as f: # 记录到queue中，等待下载
                    f.write(f'{avid}\n')
            exit(0)

    with open("work", "w") as f:
        f.write("1")
    
    mgr = downloaderMgr.DownloaderMgr()
    try:
        # 按照配置好的下载器顺序，依次尝试
        if len(sorted_downloaders) == 0:
            raise ValueError(f"cfg没有配置下载器：{sorted_downloaders}")
        
        count = 0
        download_success = False
        for it in sorted_downloaders:
            count += 1
            downloader = mgr.GetDownloader(it["downloaderName"])
            if not downloader.setDomain(it["domain"]): # 设置成配置中的域名
                logger.error(f"下载器 {downloader.getDownloaderName()} 的域名没有配置")
                continue
            if downloader is None:
                logger.error(f"下载器{it['downloaderName']} 没有找到")
                raise ValueError(f"下载器{it['downloaderName']} 没有找到")
            logger.info(f"尝试使用Downloader: {downloader.getDownloaderName()} 下载")

            # 下载失败使用下一个downloader
            info = downloader.downloadInfo(avid)
            if not info:
                logger.error(f"{avid} 下载元数据失败")
                if count >= len(sorted_downloaders):
                    break
                continue
            logger.info(info)
            if not downloader.downloadM3u8(info.m3u8, avid):
                logger.error(f"{info.m3u8} 下载视频失败")
                if count >= len(sorted_downloaders):
                    break
                continue
            download_success = True
            break

        # Prowlarr兜底
        if not download_success and prowlarr_config.get("Enabled", False):
            logger.info("所有下载器均失败，尝试Prowlarr兜底...")
            from src.prowlarr import ProwlarrClient
            client = ProwlarrClient()
            if client.full_flow(avid):
                download_success = True
                logger.info(f"Prowlarr兜底成功: {avid}")

        if not download_success:
            raise ValueError(f"{avid} 所有下载方式均失败")
        
        # 元数据刮削（可选）
        if scraper_enabled:
            gen_nfo()
        else:
            logger.info("刮削器已禁用，跳过元数据刮削")
            
    except ValueError as e:
        logger.error(e)
        if append_if_not_duplicate(queue_path, avid):
            logger.info(f"'{avid}' 已成功添加到下载队列。")
        else:
            logger.info(f"'{avid}' 已存在下载队列中。")

    finally: # 一定要执行
        with open("work", "w") as f:
            f.write("0")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="NASSAV 下载管理器")
    
    parser.add_argument('-f', '--force', action='store_true', help='跳过DB检查，强制执行')
    parser.add_argument('-t', '--target', type=str, help='指定车牌号')
    parser.add_argument('--webui', action='store_true', help='启动WebUI模式')
    
    args, unknown = parser.parse_known_args()

    # WebUI模式
    if args.webui:
        run_webui()
        sys.exit(0)

    # CLI模式
    if unknown:
        logger.error(f"Error: Unknown arguments are not allowed: {unknown}")
        sys.exit(1)
    
    # 获取位置参数
    positional_args = [arg for arg in sys.argv[1:] if not arg.startswith('-')]
    
    if len(positional_args) == 1:
        args.target = positional_args[0]
    elif args.target is None:
        logger.error("需要提供车牌号")
        sys.exit(1)
    
    logger.info(f"Force: {args.force}")
    logger.info(f"Target: {args.target}")

    run_cli(args)