<div align="center">
<img style="max-width:50%;" src="pic/logo.png" alt="NASSAV" />
<br>
</div>

<div align="center">
  <img src="https://img.shields.io/github/stars/Satoing/NASSAV?style=for-the-badge&color=FF69B4" alt="Stars">
  <img src="https://img.shields.io/github/forks/Satoing/NASSAV?style=for-the-badge&color=FF69B4" alt="Forks">
  <img src="https://img.shields.io/github/issues/Satoing/NASSAV?style=for-the-badge&color=FF69B4" alt="Issues">
  <img src="https://img.shields.io/github/license/Satoing/NASSAV?style=for-the-badge&color=FF69B4" alt="License">
</div>

## 项目简介

TX媒体库AV求片 是一个基于 Python 开发的多源影视资源下载管理工具，支持从多个数据源自动下载、整理和刮削影视资源。

项目采用模块化设计，支持自定义下载器、WebUI 管理界面、Prowlarr 种子搜索兜底，并提供完整的元数据管理功能。

## 核心特性

- 🎥 **多源下载**：支持 MissAV、Jable、HohoJ、Memo、KanAV 等多个数据源，权重优先级排序
- 🌐 **WebUI 管理界面**：基于 Flask + Waitress WSGI 的响应式网页，支持提交下载请求、队列管理和进度查看
- 🔍 **Prowlarr 兜底**：所有爬虫源失败时，自动通过 Prowlarr 索引器搜索种子并使用 AI 选择最优资源
- 🤖 **AI 选种**：集成 DeepSeek API，智能选择最佳种子（文件大小、做种人数、标题匹配度）
- 📝 **智能元数据**：从 JavBus 自动获取影片信息、封面、海报等，生成 NFO 文件
- 🔄 **队列管理**：SQLite 数据库驱动，支持去重、状态跟踪、历史记录
- 🔒 **安全验证**：Cloudflare Turnstile 人机验证 + 服务端输入验证（防 XSS / SQL 注入）
- 🎨 **媒体服务器兼容**：自动生成 Jellyfin/Emby 兼容的 NFO 和海报

## Jellyfin 预览

![](pic/1.png)

## 系统架构

```
main.py                     # 入口：CLI模式 / WebUI模式（Waitress WSGI）
├── src/
│   ├── comm.py             # 配置加载 & 全局变量
│   ├── data.py             # SQLite 已下载数据库
│   ├── download_task.py    # 核心下载逻辑（可复用，支持进度回调）
│   ├── queue_worker.py     # 后台队列工作线程
│   ├── prowlarr.py         # Prowlarr API + DeepSeek AI 选种
│   ├── scraper.py          # JavBus 元数据刮削器
│   ├── downloaderMgr.py    # 下载器管理器
│   ├── downloader/         # 各数据源下载器实现
│   │   ├── downloaderBase.py
│   │   ├── missAVDownloader.py
│   │   ├── jableDownloder.py
│   │   ├── hohoJDownloader.py
│   │   ├── memoDownloader.py
│   │   └── KanAVDownloader.py
│   └── webui/              # WebUI 模块
│       ├── app.py          # Flask 路由 & 验证
│       ├── models.py       # 队列数据库模型
│       ├── templates/      # HTML 模板
│       └── static/         # CSS 样式
├── cfg/configs.json        # 配置文件
├── db/                     # 数据库文件
└── tools/                  # 外部工具（ffmpeg, m3u8下载器）
```

## 系统要求

- Python 3.11+
- FFmpeg
- 稳定的网络连接和代理服务

## 安装指南

1. 克隆项目并安装依赖：
```bash
git clone https://github.com/Satoing/NASSAV.git
cd NASSAV
pip3 install -r requirements.txt
```

2. 安装 FFmpeg：
```bash
# Linux
sudo apt install ffmpeg
# Windows：将 ffmpeg.exe 放入 tools/ 目录（已包含）
```

3. 配置 `cfg/configs.json`（详见下方配置说明）

## 使用方法

### WebUI 模式（推荐）

启动 WebUI 管理界面（使用 Waitress 生产级 WSGI 服务器）：
```bash
python main.py --webui
```

访问 `http://localhost:5177`，在网页上提交番号即可自动下载。

**功能**：
- 输入番号提交下载请求（支持格式：`SONE-217`、`FC2-PPV-123456`）
- 实时查看下载进度、等待队列、历史记录
- Cloudflare Turnstile 人机验证（需配置 Site Key 和 Secret Key）
- 自动去重检查（队列 + 已下载目录）

### CLI 模式

下载单个资源：
```bash
python main.py <车牌号>
```

强制下载（跳过已下载检查）：
```bash
python main.py <车牌号> -f
```

### 批量下载

1. 将车牌号逐行添加到 `db/download_queue.txt`
2. 设置定时任务：
```bash
20 * * * * cd /path/to/NASSAV && bash cron_task.sh
```

### Docker 下载

```bash
# 构建（首次）
docker build -t nassav .
# 运行
docker run --rm -v "<本地存片位置>:<configs.json中SavePath>" nassav <车牌号>
```

## 配置说明

编辑 `cfg/configs.json`：

```json
{
    "LogPath": "./logs",
    "SavePath": "/vol2/1000/MissAV",
    "DBPath": "./db/downloaded.db",
    "QueuePath": "./db/download_queue.txt",
    "Proxy": "http://127.0.0.1:7897",
    "IsNeedVideoProxy": false,
    "ScraperEnabled": true,
    "ScraperDomain": ["www.javbus.com", "www.busdmm.ink"],
    "Downloader": [...],
    "WebUI": {
        "Enabled": true,
        "Port": 5177,
        "TurnstileSiteKey": "你的Turnstile Site Key",
        "TurnstileSecretKey": "你的Turnstile Secret Key"
    },
    "Prowlarr": {
        "Enabled": true,
        "URL": "http://localhost:9696",
        "APIKey": "你的Prowlarr API Key",
        "Timeout": 30
    },
    "DeepSeek": {
        "APIKey": "你的DeepSeek API Key",
        "Model": "deepseek-reasoner",
        "BaseURL": "https://api.deepseek.com"
    }
}
```

### 基础配置

| 字段 | 说明 |
|------|------|
| `SavePath` | 视频保存路径 |
| `Proxy` | HTTP 代理地址，留空不使用代理 |
| `IsNeedVideoProxy` | 下载视频是否优先使用代理 |
| `ScraperEnabled` | 是否启用元数据刮削（JavBus） |

### 下载器配置

| 字段 | 说明 |
|------|------|
| `downloaderName` | 下载器名称 |
| `domain` | 数据源域名 |
| `weight` | 权重，值越大优先级越高，设为 0 禁用 |

### WebUI 配置

| 字段 | 说明 |
|------|------|
| `Enabled` | 是否启用 WebUI |
| `Port` | WebUI 端口（默认 5177） |
| `TurnstileSiteKey` | Cloudflare Turnstile Site Key（留空跳过验证） |
| `TurnstileSecretKey` | Cloudflare Turnstile Secret Key |

### Prowlarr 配置

| 字段 | 说明 |
|------|------|
| `Enabled` | 是否启用 Prowlarr 兜底搜索 |
| `URL` | Prowlarr 服务地址 |
| `APIKey` | Prowlarr API Key |
| `Timeout` | 搜索超时时间（秒） |

### DeepSeek 配置

| 字段 | 说明 |
|------|------|
| `APIKey` | DeepSeek API Key（留空使用备选策略：按文件大小+做种数排序） |
| `Model` | 使用的模型（默认 `deepseek-reasoner`） |
| `BaseURL` | API 基础 URL |

## 数据源说明

| 数据源 | 优点 | 缺点 |
|--------|------|------|
| **MissAV** | 资源全面，反爬限制较少 | 清晰度一般（720p-1080p） |
| **Jable** | 中文字幕多，清晰度高（1080p） | 反爬限制较严格 |
| **HohoJ** | 清晰度高（1080p），基本无反爬 | 中文字幕资源较少 |
| **Memo** | 资源较新，更新及时 | 部分资源需要会员 |
| **Prowlarr** | 种子资源兜底，自动AI选种 | 需要额外部署 Prowlarr 服务 |

## 下载流程

```
提交番号 → 遍历配置的下载器（按权重降序）
  ├── 下载成功 → 元数据刮削（可选）→ 完成
  └── 全部失败 → Prowlarr兜底（可选）
       ├── 搜索种子 → AI选择最佳 → 添加下载 → 成功
       └── 搜索失败 → 加入重试队列
```

## 开发指南

### 添加新的下载器

1. 在 `src/downloader/` 下创建新文件
2. 继承 `Downloader` 基类，实现 `getDownloaderName()`、`getHTML()`、`parseHTML()`
3. 在 `DownloaderMgr.__init__` 中注册
4. 在 `configs.json` 的 `Downloader` 数组中添加配置

```python
class NewDownloader(Downloader):
    def getDownloaderName(self) -> str:
        return "NewDownloader"

    def getHTML(self, avid: str) -> Optional[str]:
        # 获取HTML
        pass

    def parseHTML(self, html: str) -> Optional[AVDownloadInfo]:
        # 解析出m3u8链接
        pass
```

## Debian/Ubuntu 系统服务部署

项目提供 `install_service.sh` 脚本，可一键将 WebUI 注册为 systemd 系统服务，实现开机自启。

### 安装服务

```bash
sudo bash install_service.sh install
```

脚本会自动检测 Python 路径和项目目录，创建 `nassav-webui.service` 并立即启动。

### 常用命令

```bash
# 查看服务状态
systemctl status nassav-webui

# 查看实时日志
journalctl -u nassav-webui -f

# 重启服务
sudo systemctl restart nassav-webui

# 停止服务
sudo systemctl stop nassav-webui
```

### 卸载服务

```bash
sudo bash install_service.sh uninstall
```

## 注意事项

- 使用本项目需要稳定的代理服务
- 请遵守相关法律法规，合理使用本工具
- 建议定期备份数据库文件
- 下载频率不要过高，避免触发 Cloudflare 防护
- 日志文件保留 3 天，到期后由 loguru 自动清理

## Reference

1. m3u8-Downloader-Go: https://github.com/Greyh4t/m3u8-Downloader-Go
2. mrjet: https://github.com/cailurus/mrjet

## 许可证

本项目采用 MIT 许可证。详见 [LICENSE](LICENSE) 文件。