import random
import string
from quart import request, jsonify, render_template_string, send_from_directory
from utils import logger
from amer_adapter import MessageManager, BindingManager , yhtools, qqtools
import datetime
from utils.config import redis_client
from captcha.image import ImageCaptcha
import base64
from io import BytesIO

# 速率限制头
RATE_LIMIT_KEY_PREFIX = "rate_limit:"
MAX_REQUESTS_PER_MINUTE = 2

async def base_error_page(title, message):
    return await render_template_string(
        """
        <!DOCTYPE html>
        <html lang="zh">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>{{ title }}</title>
            <style>
                body { 
                    font-family: Arial, sans-serif; 
                    background: #f5f5f5; 
                    color: #333; 
                    margin: 0;
                    padding: 0;
                }
                .container { 
                    max-width: 500px; 
                    margin: 50px auto; 
                    padding: 20px; 
                    background: #fff; 
                    border-radius: 8px; 
                    box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1); 
                    text-align: center; 
                }
                h1 { 
                    color: #f00;
                    font-size: 1.8em; 
                    margin-bottom: 10px; 
                }
                p { 
                    font-size: 1em; 
                    color: #555; 
                    margin-bottom: 20px; 
                }
                a { 
                    display: inline-block; 
                    padding: 10px 20px; 
                    background: #000; 
                    color: #fff; 
                    text-decoration: none; 
                    border-radius: 5px; 
                    font-weight: bold; 
                }
                a:hover { 
                    background: #333; 
                }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>{{ title }}</h1>
                <p>{{ message }}</p>
                <a href="javascript:history.back();">返回</a>
            </div>
        </body>
        </html>
        """,
        title=title,
        message=message
    )

async def base_success_page(title, message):
    return await render_template_string(
        """
        <!DOCTYPE html>
        <html lang="zh">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>{{ title }}</title>
            <style>
                body { 
                    font-family: Arial, sans-serif; 
                    background: #f5f5f5; 
                    color: #333; 
                    margin: 0;
                    padding: 0;
                }
                .container { 
                    max-width: 500px; 
                    margin: 50px auto; 
                    padding: 20px; 
                    background: #fff; 
                    border-radius: 8px; 
                    box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1); 
                    text-align: center; 
                }
                h1 { 
                    color: #000;
                    font-size: 1.8em; 
                    margin-bottom: 10px; 
                }
                p { 
                    font-size: 1em; 
                    color: #555; 
                    margin-bottom: 20px; 
                }
                a { 
                    display: inline-block; 
                    padding: 10px 20px; 
                    background: #000; 
                    color: #fff; 
                    text-decoration: none; 
                    border-radius: 5px; 
                    font-weight: bold; 
                }
                a:hover { 
                    background: #333; 
                }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>{{ title }}</h1>
                <p>{{ message }}</p>
                <a href="javascript:history.back();">返回</a>
            </div>
        </body>
        </html>
        """,
        title=title,
        message=message
    )

def generate_captcha():
    # 随机生成4位字符的验证码（仅包含小写字母和数字）
    captcha_text = ''.join(random.choices(string.ascii_lowercase + string.digits, k=4))
    # 使用ImageCaptcha生成验证码图片
    image = ImageCaptcha()
    data = image.generate(captcha_text)
    # 将验证码图片转换为Base64格式，方便嵌入HTML
    buffered = BytesIO()
    image.write(captcha_text, buffered)
    img_base64 = base64.b64encode(buffered.getvalue()).decode("utf-8")
    return captcha_text, img_base64

def register_routes(app, qqBot):
    @app.route('/favicon.ico')
    async def favicon():
        """
        返回网站图标文件
        """
        return await send_from_directory('route/icon', 'amer.jpeg', mimetype='image/jpeg')
    @app.route("/report", methods=['GET', 'POST'])
    async def report():
        try:
            client_ip = request.remote_addr
            rate_limit_key = f"{RATE_LIMIT_KEY_PREFIX}{client_ip}"
            current_requests = redis_client.get(rate_limit_key)

            if current_requests and int(current_requests) >= MAX_REQUESTS_PER_MINUTE:
                return await base_error_page("请求过于频繁", "您短时间内发送的请求过多，请稍后再试。"), 429

            if request.method == 'GET':
                if request.args.get("userid") is not None:
                    return await base_error_page("无法举报", "过期的消息"), 400
                msg_id = request.args.get("msgId")
                if not msg_id:
                    return await base_error_page("举报失败", "缺少必要参数，请检查您的请求。"), 400

                captcha_text, img_base64 = generate_captcha()
                captcha_key = f"captcha:{client_ip}"
                redis_client.set(captcha_key, captcha_text, ex=300)

                return await render_template_string(
                    """
                    <!DOCTYPE html>
                    <html lang="zh">
                    <head>
                        <meta charset="UTF-8">
                        <meta name="viewport" content="width=device-width, initial-scale=1.0">
                        <title>举报验证</title>
                        <style>
                            body { 
                                font-family: Arial, sans-serif; 
                                background: #f5f5f5;
                                color: #333;
                                margin: 0;
                                padding: 0;
                            }
                            .container { 
                                max-width: 500px; 
                                margin: 50px auto; 
                                padding: 20px; 
                                background: #fff;
                                border-radius: 8px; 
                                box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
                            }
                            h1 { 
                                text-align: center; 
                                color: #000;
                                font-weight: bold;
                            }
                            form { 
                                display: flex; 
                                flex-direction: column; 
                                gap: 15px; 
                            }
                            label { 
                                font-weight: bold; 
                                color: #333;
                            }
                            input[type="text"] { 
                                padding: 10px; 
                                border: 1px solid #ddd;
                                border-radius: 5px; 
                                background: #fff;
                                color: #333;
                            }
                            button { 
                                padding: 10px; 
                                border: none; 
                                border-radius: 5px; 
                                background: #000;
                                color: #fff;
                                cursor: pointer; 
                                font-weight: bold;
                            }
                            button:hover { 
                                background: #333;
                            }
                            img { 
                                max-width: 100%; 
                                height: auto; 
                                border: 1px solid #ddd;
                                border-radius: 5px; 
                                cursor: pointer; 
                            }
                            .error { 
                                color: #f00;
                                font-size: 0.9em; 
                            }
                        </style>
                    </head>
                    <body>
                        <div class="container">
                            <form method="POST">
                                <input type="hidden" id="msgId" name="msgId" value="{{ msg_id }}">
                                <label for="captcha">请输入验证码:</label>
                                <img src="data:image/png;base64,{{ img_base64 }}" alt="验证码">
                                <input type="text" id="captcha" name="captcha" placeholder="验证码" required>
                                <button type="submit">提交举报</button>
                            </form>
                        </div>
                    </body>
                    </html>
                    """,
                    msg_id=msg_id,
                    img_base64=img_base64
                )

            elif request.method == 'POST':
                # 获取表单数据
                msg_id = (await request.form).get("msgId")
                user_captcha = (await request.form).get("captcha")

                # 验证验证码
                captcha_key = f"captcha:{client_ip}"
                correct_captcha = redis_client.get(captcha_key)
                if not correct_captcha or user_captcha.upper() != correct_captcha.decode("utf-8").upper():
                    return await base_error_page("验证码错误", "请输入正确的验证码。"), 400

                # 删除已使用的验证码
                redis_client.delete(captcha_key)

                if not msg_id:
                    return await base_error_page("举报失败", "缺少必要参数，请检查您的请求。"), 400

                # 解析消息信息
                try:
                    from amer_adapter.ToolManager import BaseTools
                    basetools = BaseTools()
                    messages = await basetools.get_messages_by_msgid(msg_id)
                    if not messages:
                        return await base_error_page("举报失败", "未找到指定的消息ID，请检查您的请求。"), 404
                    message_info = messages[0]
                except Exception as e:
                    logger.error(f"解析消息信息失败: {e}")
                    return await base_error_page("解析失败", "无法解析消息信息，请稍后再试。"), 400

                # 更新 Redis 请求计数
                if not redis_client.exists(rate_limit_key):
                    redis_client.set(rate_limit_key, 1, ex=60)
                else:
                    redis_client.incr(rate_limit_key)
                
                # 获取被举报的用户ID
                reported_user_id = message_info.get('sender_id')
                if not reported_user_id:
                    return await base_error_page("举报失败", "无法获取被举报用户的ID，请稍后再试。"), 400

                # 记录举报次数
                report_count_key = f"report_count:{reported_user_id}"
                report_count = redis_client.get(report_count_key)
                if report_count:
                    report_count = int(report_count) + 1
                else:
                    report_count = 1
                redis_client.set(report_count_key, report_count, ex=86400)

                # 检查举报次数
                if report_count >= 3:
                    # 计算封禁时长
                    ban_duration = 1800 + (report_count - 3) * 600  # 第三次开始，每次增加10分钟

                    # 封禁用户
                    ban_reason = "被多次举报"
                    ban_status = await basetools.add_to_blacklist(reported_user_id, ban_reason, ban_duration)
                    if ban_status:
                        # 生成解封链接
                        unban_token = ''.join(random.choices(string.ascii_letters + string.digits, k=32))
                        unban_link = f"https://amer.bot.anran.xyz/unban?msgId={msg_id}&token={unban_token}"
                        unban_token_key = f"unban_token:{unban_token}"
                        redis_client.set(unban_token_key, reported_user_id, ex=86400)

                        # 获取用户名
                        platform = message_info.get('platform_from')
                        if platform == "QQ" or platform == "qq":
                            user_name = await qqtools.get_user_nickname(reported_user_id)
                        elif platform == "YH" or platform == "yh":
                            user_name = await yhtools.get_user_nickname(reported_user_id)
                        else:
                            user_name = reported_user_id

                        notify_message_text = (
                            f"【ฅ喵呜·封禁通知ฅ】\n"
                            f"✦{user_name} (ID: {reported_user_id}) 的小鱼干被没收啦~\n"
                            f"从现在起不会同步这个用户的消息了喵！\n"
                            f"✦封禁原因：{ban_reason}\n"
                            f"✦持续时间：{'直到吃完'+str(ban_duration//10)+'个猫罐头的时间(大概'+str(ban_duration)+'秒)喵~' if ban_duration >0 else '永久的喵~ (小爪爪盖上红印)'}\n"
                            f"✦自助解封链接：{unban_link}"
                        )

                        notify_message_html = (
                            # 消息容器：封禁通知内容
                            f'<div style="background-color: #f9f9f9; padding: 5px; border-radius: 5px;">{user_name} (ID: {reported_user_id}) 的小鱼干被没收啦~'
                            f'<p style="font-size: 12px; color: #8b0000; margin: 5px 0;">'
                            f'从现在起不会同步这个用户的消息了喵！'
                            f'</p>'
                            f'<p style="font-size: 12px; color: #333; margin: 5px 0;">'
                            f'✦封禁原因：{ban_reason}'
                            f'</p>'
                            f'<p style="font-size: 12px; color: #333; margin: 5px 0;">'
                            f'✦持续时间：{"直到吃完"+str(ban_duration//10)+"个猫罐头的时间(大概"+str(ban_duration)+"秒)喵~" if ban_duration > 0 else "永久的喵~ (小爪爪盖上红印)"}'
                            f'</p>'
                            f'<p style="font-size: 12px; color: #333; margin: 5px 0;">'
                            f'✦<a href="{unban_link}" target="_blank">自助解封</a>'
                            f'</p>'
                            f'</div>'
                        )

                        group_id = message_info.get('id_from')
                        if platform == "QQ" or platform == "qq":
                            await qqBot.send_group_msg(group_id=group_id, message=notify_message_text)
                            await MessageManager.send_to_all_bindings(
                                "QQ",
                                group_id,
                                "html",
                                notify_message_html,
                                0,
                                "Amer"
                            )

                        elif platform == "YH" or platform == "yh":
                            await yhtools.send(recvId=group_id, recvType="group", contentType="html", content=notify_message_html)
                            await MessageManager.send_to_all_bindings(
                                "YH",
                                group_id,
                                "text",
                                notify_message_text,
                                0,
                                "Amer"
                            )
                        else:
                            await qqBot.send_group_msg(group_id=message_data.group_id, message=f"未知平台: {platform}")

                report_message = (
                    "【举报通知】\n"
                    f"平台: {message_info.get('platform_from')}\n"
                    f"群号: {message_info.get('id_from')}\n"
                    f"时间: {message_info.get('timestamp')}\n"
                    f"消息ID: {message_info.get('msg_id')}\n\n"
                    f"发送者ID: {message_info.get('sender_id')}\n"
                    f"发送者昵称: {message_info.get('sender_nickname')}\n\n"
                    f"消息内容: {message_info.get('message_content')}\n"
                )

                # 发送给开发者
                await qqBot.send_private_msg(user_id=2694611137, message=report_message)

                # 记录日志
                logger.info(f"收到举报: {report_message}")

                # 返回成功页面
                return await base_success_page("举报成功", "感谢您的反馈！我们会尽快处理。"), 200

        except Exception as e:
            logger.error(f"处理举报时发生错误: {e}")
            return await base_error_page("服务器错误", "抱歉，处理您的请求时发生了错误，请稍后再试。"), 500

    @app.route("/unban", methods=['GET'])
    async def unban():
        try:
            msg_id = request.args.get("msgId")
            token = request.args.get("token")
            if not msg_id or not token:
                return await base_error_page("参数错误", "缺少必要参数，请检查您的请求。"), 400

            from amer_adapter.ToolManager import BaseTools
            basetools = BaseTools()
            messages = await basetools.get_messages_by_msgid(msg_id)
            if not messages:
                return await base_error_page("解封失败", "未找到指定的消息ID，请检查您的请求。"), 404
            message_info = messages[0]

            # 获取被举报的用户ID
            user_id = message_info.get('sender_id')
            if not user_id:
                return await base_error_page("解封失败", "无法获取用户的ID，请稍后再试。"), 400

            # 验证解封令牌
            unban_token_key = f"unban_token:{token}"
            stored_user_id = redis_client.get(unban_token_key)
            if not stored_user_id or stored_user_id.decode("utf-8") != user_id:
                return await base_error_page("解封失败", "无效的解封令牌，请检查您的链接。"), 400

            # 检查当天解封次数
            unban_count_key = f"unban_count:{user_id}"
            unban_count = redis_client.get(unban_count_key)
            if unban_count and int(unban_count) >= 3:
                return await base_error_page("解封次数限制", "您今天已经解封了3次，请明天再试。"), 400

            # 增加解封次数
            if unban_count:
                unban_count = int(unban_count) + 1
            else:
                unban_count = 1
            redis_client.set(unban_count_key, unban_count, ex=86400)

            # 移除解封令牌
            redis_client.delete(unban_token_key)

            # 解封用户
            unban_status = await basetools.remove_from_blacklist(user_id)
            if unban_status:
                return await base_success_page("解封成功", "您已成功解封，请注意遵守社区规则。"), 200
            else:
                return await base_error_page("解封失败", "解封过程中发生错误，请稍后再试。"), 500

        except Exception as e:
            logger.error(f"处理解封时发生错误: {e}")
            return await base_error_page("服务器错误", "抱歉，处理您的请求时发生了错误，请稍后再试。"), 500