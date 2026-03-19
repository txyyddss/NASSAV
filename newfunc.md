# 目标
你需要对现有的项目进行修改 添加功能:
- 基于Python的WebUI界面
- 基于Powlarr索引器的种子搜索作为兜底
- 修改README文件 添加详细的使用说明和功能介绍以及大致代码实现 并移除冗余说明

你需要:
- 确保新添加的功能能够正常运行
- 确保代码高质量(运行效率高 可维护性好 可读性好)
- 网页能够动态适配不同尺寸的设备
- 多线程运行代码 提高效率并避免阻塞
- 仔细阅读现存代码
- 确保有完整的错误处理
- 确保代码安全 不存在安全漏洞
- 现有的代码能够正常运行 非必要的情况下不对现有代码进行修改
- 修改configs.json 确保添加的所有功能均为可选且可配置
- 确保代码的模块化
- 代码复用 减少重复代码
- 确保程序运行时 需要在控制台输出完整的日志
- 添加错误重试逻辑

你无需:
- 在本地进行测试
- 读取Git记录或进行Commit/Push

# 网页界面
网页默认运行于5177端口 无需登入
## 输入验证
当用户提交时 进行以下验证:
- 不能为空
- 不能包含特殊字符
- 不能包含SQL注入语句
- 不能包含XSS攻击代码
- 仅能包含 字母 - 空格 数字
- 格式必须为 字母-数字 FC2-PPV-数字(FC2-PPV[空格]数字自动转换为FC2-PPV-数字)
- 读取config里的SavePath 确保该番号未被下载过
- 集成Cloudflare Turnstile 验证 确保无法被绕过 必须验证通过才能提交
当任一验证失败时 返回错误信息并提示用户重新输入
## 使用队列以及sqlite数据库进行请求排队及历史记录储存
- 确保用户无法重复提交相同请求
- 在sqlite中储存所有需要的信息
## 请求提交
当用户提交请求并验证成功时 将其添加至队列 并返回成功信息 刷新网页
## 显示进度
在网页上显示当前下载队列的状态 包括正在下载的番号 以及等待中的番号 以及历史番号
每个项目显示:
- 番号
- 数据源(仅历史番号)
- 下载状态及进度
- 其他必要的信息
- 标题(如有)

# 下载器
已经存在的代码已经能够实现完整的下载器&爬虫功能 我需要你在此基础上修改/添加功能
## 下载逻辑
- 每次仅同时下载一个番号 其他请求进入等待队列
- 动态回报下载进度 以便在网页上显示
## 修改现存的scraper
- 修改为可选运行 在configs.json中配置
- 失败不计为error 仅记录日志并继续运行
## Powlarr兜底
当现有的爬虫无法找到番号时 使用Powlarr索引器进行搜索
## 接口
http://localhost:9696
API KEY: 18dc49893ca540a8900c9c9194a71962
## 搜索资源
当触发Powlarr兜底时 使用API进行搜索 及 下载
设定Timeout为30秒
如果搜索结果为空 则视为失败 只有seeders大于0的资源才视为有效资源
### 请求示例
```
fetch("https://xxx/api/v1/search?query=番号&categories=6000&type=search&limit=100&offset=0&apikey=", {
  "method": "GET",
});
```
### 响应示例
```
[
  {
    "guid": "https://16mag.net/!in4s",
    "age": 0,
    "ageHours": 0.0007435605277777777,
    "ageMinutes": 0.044613635,
    "size": 8439610880,
    "indexerId": 1,
    "indexer": "0Magnet",
    "title": "SONE-217",
    "sortTitle": "sone 217",
    "imdbId": 0,
    "tmdbId": 0,
    "tvdbId": 0,
    "tvMazeId": 0,
    "publishDate": "2026-03-19T07:43:09Z",
    "downloadUrl": "https://powlarr.1391399.xyz/1/download?apikey=18dc49893ca540a8900c9c9194a71962&link=SE1zOHlpdSt3N3pFRjZWY1JOdVZJQW9pd3UyZXc5djYxM2k0aGJFT1g4cVR4U3R0c01jQnJKVXpSWE9aRlA1Uw&file=SONE-217",
    "infoUrl": "https://16mag.net/!in4s",
    "indexerFlags": [
      "freeleech"
    ],
    "categories": [
      {
        "id": 6000,
        "name": "XXX",
        "subCategories": [
          {
            "id": 6010,
            "name": "XXX/DVD",
            "subCategories": []
          },
          {
            "id": 6020,
            "name": "XXX/WMV",
            "subCategories": []
          },
          {
            "id": 6030,
            "name": "XXX/XviD",
            "subCategories": []
          },
          {
            "id": 6040,
            "name": "XXX/x264",
            "subCategories": []
          },
          {
            "id": 6045,
            "name": "XXX/UHD",
            "subCategories": []
          },
          {
            "id": 6050,
            "name": "XXX/Pack",
            "subCategories": []
          },
          {
            "id": 6060,
            "name": "XXX/ImageSet",
            "subCategories": []
          },
          {
            "id": 6070,
            "name": "XXX/Other",
            "subCategories": []
          },
          {
            "id": 6080,
            "name": "XXX/SD",
            "subCategories": []
          },
          {
            "id": 6090,
            "name": "XXX/WEB-DL",
            "subCategories": []
          }
        ]
      }
    ],
    "seeders": 1,
    "leechers": 1,
    "protocol": "torrent",
    "fileName": "SONE-217.torrent"
  },
  {
    "guid": "https://16mag.net/!in6s",
    "age": 0,
    "ageHours": 0.0007442375555555556,
    "ageMinutes": 0.044654255,
    "size": 6990059520,
    "indexerId": 1,
    "indexer": "0Magnet",
    "title": "sone-217",
    "sortTitle": "sone 217",
    "imdbId": 0,
    "tmdbId": 0,
    "tvdbId": 0,
    "tvMazeId": 0,
    "publishDate": "2026-03-19T07:43:09Z",
    "downloadUrl": "https://powlarr.1391399.xyz/1/download?apikey=18dc49893ca540a8900c9c9194a71962&link=SGxMRmY5RjJIL2oxcm9XcjNXRythQktaZEZpbHdJUFpMT3VXNDl3dVNFU1dIZEVzYWthQk1jZDE3bW5lQkRwRw&file=sone-217",
    "infoUrl": "https://16mag.net/!in6s",
    "indexerFlags": [
      "freeleech"
    ],
    "categories": [
      {
        "id": 6000,
        "name": "XXX",
        "subCategories": [
          {
            "id": 6010,
            "name": "XXX/DVD",
            "subCategories": []
          },
          {
            "id": 6020,
            "name": "XXX/WMV",
            "subCategories": []
          },
          {
            "id": 6030,
            "name": "XXX/XviD",
            "subCategories": []
          },
          {
            "id": 6040,
            "name": "XXX/x264",
            "subCategories": []
          },
          {
            "id": 6045,
            "name": "XXX/UHD",
            "subCategories": []
          },
          {
            "id": 6050,
            "name": "XXX/Pack",
            "subCategories": []
          },
          {
            "id": 6060,
            "name": "XXX/ImageSet",
            "subCategories": []
          },
          {
            "id": 6070,
            "name": "XXX/Other",
            "subCategories": []
          },
          {
            "id": 6080,
            "name": "XXX/SD",
            "subCategories": []
          },
          {
            "id": 6090,
            "name": "XXX/WEB-DL",
            "subCategories": []
          }
        ]
      }
    ],
    "seeders": 1,
    "leechers": 1,
    "protocol": "torrent",
    "fileName": "sone-217.torrent"
  }
]
```
## 选择资源
当搜索结果返回时 处理结果并请求AI 
为每个项目添加"ID"字段
让AI选择最佳的种子并仅返回ID 你需要发送:
- seeders&leechers数量
- size
- title & shortTitle
- 其他必要的信息

你需要编写提示词 让AI能够根据这些信息选择最佳的种子 你需要确保AI能够理解这些信息的含义 以及如何根据这些信息做出选择
调用Deepseek API 进行选择 禁用流式输出 APIkey应在config.json中配置 示例代码(仅供参考):
```
# Please install OpenAI SDK first: `pip3 install openai`
curl https://api.deepseek.com/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${DEEPSEEK_API_KEY}" \
  -d '{
        "model": "deepseek-chat",
        "messages": [
          {"role": "system", "content": "You are a helpful assistant."},
          {"role": "user", "content": "Hello!"}
        ],
        "stream": false
      }'
```
默认模型: deepseek-reasoner

## 添加下载

根据AI返回的结果 匹配到对应的资源 然后根据guid及indexerId请求API添加下载
一旦请求成功 该番号则视为获取成功

### 示例请求

```
fetch("https://powlarr.1391399.xyz/api/v1/search?&apikey=", {
  "referrer": "https://powlarr.1391399.xyz/search",
  "body": "{\"guid\":\"https://16mag.net/!in6s\",\"indexerId\":1}",
  "method": "POST",
});
```
### 示例响应
```
{
  "guid": "https://16mag.net/!in6s",
  "age": 0,
  "ageHours": 0,
  "ageMinutes": 0,
  "size": 0,
  "indexerId": 1,
  "imdbId": 0,
  "tmdbId": 0,
  "tvdbId": 0,
  "tvMazeId": 0,
  "publishDate": "0001-01-01T00:00:00Z",
  "protocol": "unknown",
  "fileName": ""
}
```