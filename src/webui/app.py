# WebUI Flask应用
import re
import os
from flask import Flask, render_template, request, jsonify
from loguru import logger
from ..comm import webui_config, save_path
from .models import (
    init_queue_db, add_to_queue, is_duplicate, get_queue_status, get_item_status,
    get_history_page, get_distinct_sources, retry_failed_item,
)
from curl_cffi import requests as cffi_requests


def create_app() -> Flask:
    """Flask应用工厂"""
    template_dir = os.path.join(os.path.dirname(__file__), "templates")
    static_dir = os.path.join(os.path.dirname(__file__), "static")

    app = Flask(
        __name__,
        template_folder=template_dir,
        static_folder=static_dir,
    )
    app.config["SECRET_KEY"] = os.urandom(32).hex()

    # 初始化队列数据库
    init_queue_db()

    # ==================== 路由 ====================

    @app.route("/")
    def index():
        """主页"""
        return render_template(
            "index.html",
            turnstile_site_key=webui_config.get("TurnstileSiteKey", ""),
        )

    @app.route("/api/submit", methods=["POST"])
    def submit():
        """提交下载请求"""
        data = request.get_json(silent=True)
        if not data:
            return jsonify({"success": False, "message": "无效的请求数据"}), 400

        avid = data.get("avid", "").strip()
        turnstile_token = data.get("turnstile_token", "")

        # 1. Turnstile验证
        turnstile_secret = webui_config.get("TurnstileSecretKey", "")
        if turnstile_secret:
            if not turnstile_token:
                return jsonify({"success": False, "message": "请完成人机验证"}), 400

            if not _verify_turnstile(turnstile_token, turnstile_secret):
                return jsonify({"success": False, "message": "人机验证失败，请重试"}), 403

        # 2. 输入验证
        validation = _validate_avid(avid)
        if not validation["valid"]:
            return jsonify({"success": False, "message": validation["message"]}), 400

        avid = validation["avid"]  # 使用规范化后的AVID

        # 3. 检查是否已下载
        if _is_already_downloaded(avid):
            return jsonify({"success": False, "message": f"{avid} 已经下载过了"}), 409

        # 4. 检查队列重复
        if is_duplicate(avid):
            return jsonify({"success": False, "message": f"{avid} 已在队列中"}), 409

        # 5. 添加到队列
        result = add_to_queue(avid)
        status_code = 200 if result["success"] else 409
        return jsonify(result), status_code

    @app.route("/api/queue")
    def queue_status():
        """获取队列状态"""
        status = get_queue_status()
        return jsonify(status)

    @app.route("/api/status/<int:item_id>")
    def item_status(item_id):
        """获取单项状态"""
        status = get_item_status(item_id)
        if status:
            return jsonify(status)
        return jsonify({"error": "未找到"}), 404

    @app.route("/api/history")
    def history():
        """分页获取历史记录，支持筛选"""
        page = request.args.get("page", 1, type=int)
        per_page = request.args.get("per_page", 20, type=int)
        status = request.args.get("status", "")
        source = request.args.get("source", "")
        result = get_history_page(page, per_page, status, source)
        # 附带可用的下载方式列表，供前端筛选下拉框使用
        result["sources"] = get_distinct_sources()
        return jsonify(result)

    @app.route("/api/retry/<int:item_id>", methods=["POST"])
    def retry(item_id):
        """重试失败的下载项"""
        data = request.get_json(silent=True)
        turnstile_token = data.get("turnstile_token", "") if data else ""

        # Turnstile验证
        turnstile_secret = webui_config.get("TurnstileSecretKey", "")
        if turnstile_secret:
            if not turnstile_token:
                return jsonify({"success": False, "message": "请完成人机验证"}), 400
            if not _verify_turnstile(turnstile_token, turnstile_secret):
                return jsonify({"success": False, "message": "人机验证失败，请重试"}), 403

        result = retry_failed_item(item_id)
        status_code = 200 if result["success"] else 400
        return jsonify(result), status_code

    return app


# ==================== 工具函数 ====================

def _validate_avid(avid: str) -> dict:
    """
    验证并规范化AVID输入
    :return: {"valid": bool, "message": str, "avid": str}
    """
    if not avid:
        return {"valid": False, "message": "番号不能为空", "avid": ""}

    # 长度限制
    if len(avid) > 30:
        return {"valid": False, "message": "输入过长", "avid": ""}

    # 仅允许: 字母 数字 空格 连字符
    if not re.match(r'^[A-Za-z0-9\- ]+$', avid):
        return {"valid": False, "message": "仅允许包含字母、数字、空格和连字符", "avid": ""}

    # XSS检查
    xss_patterns = [
        r'<\s*script', r'javascript\s*:', r'on\w+\s*=',
        r'<\s*img', r'<\s*iframe', r'<\s*object',
        r'<\s*embed', r'<\s*link', r'<\s*style',
        r'expression\s*\(', r'vbscript\s*:',
    ]
    avid_lower = avid.lower()
    for pattern in xss_patterns:
        if re.search(pattern, avid_lower):
            return {"valid": False, "message": "包含不允许的内容", "avid": ""}

    # SQL注入检查
    sql_patterns = [
        r'\b(union|select|insert|update|delete|drop|alter|create|exec|execute)\b',
        r'(--|;|/\*|\*/)',
        r'(\'\s*(or|and)\s*\')',
        r'(\"\s*(or|and)\s*\")',
    ]
    for pattern in sql_patterns:
        if re.search(pattern, avid_lower):
            return {"valid": False, "message": "包含不允许的内容", "avid": ""}

    # 转大写
    avid = avid.upper()

    # FC2-PPV 特殊处理: "FC2-PPV 123456" -> "FC2-PPV-123456"
    avid = re.sub(r'^FC2-PPV\s+(\d+)$', r'FC2-PPV-\1', avid)

    # 格式验证
    if not re.match(r'^[A-Z0-9]+(?:-[A-Z0-9]+)*-\d+[A-Z]?$', avid) and not re.match(r'^FC2-PPV-\d+$', avid):
        return {
            "valid": False,
            "message": "格式必须为 字母-数字（如 SONE-217）或 FC2-PPV-数字（如 FC2-PPV-123456）",
            "avid": "",
        }

    return {"valid": True, "message": "", "avid": avid}


def _is_already_downloaded(avid: str) -> bool:
    """检查是否已下载（检查SavePath目录中是否存在对应文件夹和视频文件）"""
    target_dir = os.path.join(save_path, avid)
    mp4_path = os.path.join(target_dir, f"{avid}.mp4")
    return os.path.exists(mp4_path)


def _verify_turnstile(token: str, secret: str) -> bool:
    """验证Cloudflare Turnstile token"""
    try:
        response = cffi_requests.post(
            "https://challenges.cloudflare.com/turnstile/v0/siteverify",
            data={
                "secret": secret,
                "response": token,
            },
            timeout=10,
            impersonate="chrome110",
        )
        result = response.json()
        success = result.get("success", False)
        if not success:
            logger.warning(f"Turnstile验证失败: {result}")
        return success
    except Exception as e:
        logger.error(f"Turnstile验证请求异常: {e}")
        return False
