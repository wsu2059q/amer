import uvicorn
import os
import datetime
from utils.config import (server_host, server_port, yh_webhook_path, bot_qq, temp_folder)
from aiocqhttp import CQHttp, Event
from quart import request, jsonify
from utils.log import logger
from amer_adapter.yunhu.handler import handler as YH_handler
from amer_adapter.qq.handler import (
    msg_handler as QQ_msg_handler,
    handle_request as QQ_request_handler,
    handle_notice as QQ_notice_handler
)
from route import register_api_routes

if not os.path.exists(temp_folder):
    os.makedirs(temp_folder)

qqBot = CQHttp(__name__)
app = qqBot.server_app
# QQ - 消息
@qqBot.on_message
async def handle_msg(event: Event):
    await QQ_msg_handler(event, qqBot)

# QQ - 请求
@qqBot.on_request
async def handle_requests(event: Event):
    await QQ_request_handler(event, qqBot)

# QQ - 通知
@qqBot.on_notice
async def handle_notices(event: Event):
    await QQ_notice_handler(event, qqBot)

# 云湖
@app.route(yh_webhook_path, methods=['POST'])
async def webhook():
    data = await request.get_json()
    if data:
        await YH_handler(data, qqBot)
        return jsonify({"status": "success"}), 200
    return jsonify({"status": "error"}), 400

register_api_routes(app, qqBot)
# 服务器 , 启动!
if __name__ == "__main__":
    logger.info(f"启动Webserver,主机: {server_host}, 端口: {server_port}")
    uvicorn.run(
        "main:qqBot.asgi",
        host=server_host,
        port=server_port,
        reload=True
    )
