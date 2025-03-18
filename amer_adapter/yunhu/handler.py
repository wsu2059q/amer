import json
import re
from .. import BindingManager, MessageManager
from utils import logger
import uuid
import markdown
import imgkit
from typing import Dict, Any
from utils.config import(temp_folder, message_yh, message_yh_followed, bot_qq, replace_blocked_words)
import os

from .. import qqtools, yhtools

async def handler(data: Dict[str, Any], qqBot):
    message_data = MessageManager.YunhuMessageData(data)
    message_data.qqBot = qqBot
    logger.info(f"源:{data}")
    event_handlers = {
        "message.receive.normal": handle_normal_message,
        "message.receive.instruction": handle_instruction_message,
        "bot.followed": handle_bot_followed,
        "bot.unfollowed": handle_bot_unfollowed,
        "bot.setting": handle_bot_setting,
        "group.join": handle_group_join,
        "group.leave": handle_group_leave,
        "button.report.inline": handle_button_event,
    }

    handler = event_handlers.get(message_data.header_event_type)
    if handler:
        await handler(message_data)
    else:
        logger.warning(f"未知事件类型: {message_data.header_event_type}")

async def handle_normal_message(message_data: MessageManager.YunhuMessageData):
    logger.info(f"收到来自 {message_data.sender_nickname} 的普通消息: {message_data.message_content}")
    
    cleaned_name = replace_blocked_words(message_data.sender_nickname)
    message_content = message_data.message_content
    
    if message_data.image_url:
        text = (
            f"[CQ:image,file={message_data.image_url}]\n"
            f"\n> 来自云湖·{await yhtools.get_group_name(message_data.message_chat_id)} | {cleaned_name}"
        )
    elif message_content:
        text = (
            f"{message_content}\n"
            f"\n> 来自云湖·{await yhtools.get_group_name(message_data.message_chat_id)} | {cleaned_name}"
        )
    else:
        return
    
    # 发送消息到所有绑定
    await MessageManager.send_to_all_bindings(
        "YH",
        message_data.message_chat_id,
        "text",
        message_content,
        message_data.sender_id,
        message_data.sender_nickname,
        noBaseContent=text
    )

async def handle_instruction_message(message_data: MessageManager.YunhuMessageData):
    if message_data.message_chat_type == "group":
        if message_data.command_name == "帮助":
            await yhtools.send(message_data.message_chat_id, message_data.message_chat_type, "markdown", content=message_yh)
            return
        elif message_data.command_name == "群列表":
            bind_infos = BindingManager.get_info("YH", message_data.message_chat_id)
            if bind_infos['status'] == 0:
                menu = f"## 云湖群: {await yhtools.get_group_name(message_data.message_chat_id)}\n"
                QQ_group_ids = bind_infos['data']['QQ_group_ids']
                QQ_item_number = 1
                if QQ_group_ids:
                    menu += "\n### QQ群\n\n"
                    for QQ_group in QQ_group_ids:
                        sync_mode = "未设置"
                        if QQ_group['sync'] and QQ_group['binding_sync']:
                            sync_mode = "互通"
                        elif QQ_group['sync'] and QQ_group['binding_sync'] is False:
                            sync_mode = "单向-云湖到QQ"
                        elif QQ_group['sync'] is False and QQ_group['binding_sync']:
                            sync_mode = "单向-QQ到云湖"
                        group_name = await qqtools.get_group_name(QQ_group['id'])
                        menu += f"{QQ_item_number}. **{group_name}** {QQ_group['id']} ({sync_mode})\n"
                        QQ_item_number += 1
                await yhtools.send(message_data.message_chat_id, message_data.message_chat_type, "markdown", content=menu)
                return
            else:
                await yhtools.send(message_data.message_chat_id, message_data.message_chat_type, "text", content=bind_infos['msg'])
        elif message_data.command_name == "绑定":
            from_infos = message_data.message_content_base.get("formJson", {})
            results = []
            member_info = await message_data.qqBot.get_group_list()
            group_ids = message_data.message_content
            if group_ids is not None:
                group_ids = re.split(r'[,\，]', group_ids)
                for group_id in group_ids[:]:
                    is_in_group = False
                    group_id = group_id.strip()
                    if group_id == "" or group_id is None:
                        results.append(f"绑定失败, 无效的QQ群号: {group_id}")
                        if group_id in group_ids:
                            group_ids.remove(group_id)
                        continue

                    for group in member_info:
                        if group['group_id'] == int(group_id):
                            is_in_group = True
                            break
                    if not is_in_group:
                        results.append(f"绑定失败, 机器人不在QQ群{group_id}中")
                        if group_id in group_ids:
                            group_ids.remove(group_id)
                        continue
            else:
                results.append(f"绑定失败, 请输入需要绑定的QQ群")
                result_message = "\n".join(results)
                await yhtools.send(message_data.message_chat_id, message_data.message_chat_type, "text", content=result_message)
                return
            if group_ids:
                for qq_group_id in group_ids:
                    bind_result = BindingManager.bind("YH", "QQ", message_data.message_chat_id, qq_group_id)
                    logger.info(f"绑定状态: {bind_result}")
                    if bind_result["status"] == 0:
                        await message_data.qqBot.send_group_msg(
                            group_id=int(qq_group_id),
                            message=f"此群已通过Amer和云湖群聊{message_data.message_chat_id}成功绑定,默认同步模式为全同步.请测试同步功能是否正常!"
                        )
                        results.append(f"云湖群已经绑定到了QQ群{qq_group_id},请检查QQ群是否有提醒")
                    else:
                        results.append(bind_result["msg"])
                result_message = "\n".join(results)
                await yhtools.send(message_data.message_chat_id, message_data.message_chat_type, "text", content=result_message)
            else:
                result_message = "\n".join(results)
                await yhtools.send(message_data.message_chat_id, message_data.message_chat_type, "text", content=result_message)
        elif message_data.command_name == "解绑":
            from_infos = message_data.message_content_base.get("formJson", {})
            group_ids = []
            results = []
            jb_input_status = False
            jb_switch_status = False
            for from_info in from_infos.values():
                id = from_info.get('id')
                id_value = from_info.get('value', from_info.get('selectValue'))
                valid_setting_ids = ['yvybln', 'rzaadk']
                if id not in valid_setting_ids:
                    logger.error(f"无效的设置ID: {id}")
                    return
                if id == "rzaadk":
                    if id_value is not None:
                        group_ids = re.split(r'[,\，]', id_value)
                        for group_id in group_ids[:]:
                            is_in_group = False
                            group_id = group_id.strip()
                            if group_id == "" or group_id is None:
                                results.append(f"解绑失败, 无效的QQ群号: {group_id}")
                                if group_id in group_ids:
                                    group_ids.remove(group_id)
                                continue
                    else:
                        jb_input_status = True
                        
                if id == "yvybln":
                    if id_value == True:
                        unbind_status =  BindingManager.unbind_all("YH", message_data.message_chat_id)
                        if unbind_status['status'] == 0:
                            await yhtools.send(message_data.message_chat_id, message_data.message_chat_type, "text", content="已解绑所有关联平台")
                            return
                        else:
                            await yhtools.send(message_data.message_chat_id, message_data.message_chat_type, "text", content=f"{unbind_status['msg']}")
                        return
                    else:
                        jb_switch_status = True
            
            if group_ids:
                for group_id in group_ids:
                    unbind_status = BindingManager.unbind("YH", "QQ", message_data.message_chat_id, group_id)
                    if unbind_status['status'] == 0:
                            results.append(f"成功解绑群号: {group_id}")
                            await message_data.qqBot.send_group_msg(
                                group_id=int(group_id),
                                message=f"此群已从云湖群聊{message_data.message_chat_id}解绑"
                            )
                    else:
                        results.append(f"解绑失败, {unbind_status['msg']}")
                result_message = "\n".join(results)
                await yhtools.send(message_data.message_chat_id, message_data.message_chat_type, "text", content=result_message)
            else:
                if jb_switch_status and jb_input_status:
                    await yhtools.send(message_data.message_chat_id, message_data.message_chat_type, "text", content="请输入需要解绑的QQ群或全部解绑")
                else:
                    result_message = "\n".join(results)
                    await yhtools.send(message_data.message_chat_id, message_data.message_chat_type, "text", content=result_message)

        elif message_data.command_name == "同步模式":
            from_infos = message_data.message_content_base.get("formJson", {})
            tb_sync_QQYH_mode = None
            tb_sync_YHQQ_mode = None
            results = []
            tb_input_status = False
            for from_info in from_infos.values():
                id = from_info.get('id')
                id_value = from_info.get('value', from_info.get('selectValue'))
                valid_setting_ids = ['vadtwo', 'tamzxv']
                sync_type = None
                if id not in valid_setting_ids:
                    logger.error(f"无效的设置ID: {id}")
                    return
                if id == "vadtwo":
                    sync_type = id_value
                    if id_value == "全同步":
                        sync_data = {"QQ": True, "YH": True}
                    if id_value == "QQ到云湖":
                        sync_data = {"QQ": False, "YH": True}
                    elif id_value == "云湖到QQ":
                        sync_data = {"YH": False, "QQ": True}
                    elif id_value == "停止":
                        sync_data = {"QQ": False, "YH": False}
                if id == "tamzxv":
                    if id_value is not None:
                        group_ids = id_value.split(',')
                        for group_id in group_ids[:]:
                            group_id = group_id.strip()
                            if group_id == "" or group_id is None:
                                results.append(f"无效的QQ群号: {group_id}")
                                if group_id in group_ids:
                                    group_ids.remove(group_id)
                                continue
                            if not group_id.isdigit():
                                results.append(f"无效的QQ群号: {group_id}")
                                if group_id in group_ids:
                                    group_ids.remove(group_id)
                                continue
                    else:
                        tb_input_status = True
            if tb_input_status is False:
                if group_ids:
                    for group_id in group_ids:
                        sync_status = BindingManager.set_sync("YH","QQ", message_data.message_chat_id, group_id, sync_data)
                        if sync_status['status'] == 0:
                            results.append(f"成功设置同步模式为: {sync_type}")
                        else:
                            results.append(f"设置同步模式失败,{sync_status['msg']}")
            else:
                sync_status = BindingManager.set_all_sync("YH", message_data.message_chat_id, sync_data)
                if sync_status['status'] == 0:
                    results.append(f"已更改所有绑定QQ群同步模式为 {sync_type}")
                else:
                    results.append(f"设置同步模式失败,{sync_status['msg']}")
            result_message = "\n".join(results)
            await yhtools.send(message_data.message_chat_id, message_data.message_chat_type, "text", content=result_message)
    else:
        if message_data.command_name == "帮助":
            await yhtools.send(message_data.sender_id, "user", "markdown", content=message_yh_followed)
        else:
            await yhtools.send(message_data.sender_id, "user", "text", content="请在群内使用指令,您目前可且仅可以使用/帮助命令")
    logger.info(f"Received instruction message from {message_data.sender_nickname}: {message_data.message_content} (Command: {message_data.command_name})")

async def handle_bot_followed(message_data: MessageManager.YunhuMessageData):
    await yhtools.send(message_data.userid, "user", "markdown", content=message_yh_followed)
    logger.info(f"{message_data.sender_nickname} 关注了机器人")

async def handle_bot_unfollowed(message_data: MessageManager.YunhuMessageData):
    logger.info(f"{message_data.sender_nickname} 取消关注了机器人")

async def handle_bot_setting(message_data: dict):
    pass
    
async def handle_group_join(message_data: MessageManager.YunhuMessageData):
    logger.info(f"{message_data.sender_nickname} 加入了群聊 {message_data.message_chat_id}")

async def handle_group_leave(message_data: MessageManager.YunhuMessageData):
    logger.info(f"{message_data.sender_nickname} 离开了群聊 {message_data.message_chat_id}")

async def handle_button_event(message_data: MessageManager.YunhuMessageData):
    event_data = message_data.data
    msg_id = event_data.get("msgId", "")
    recv_id = event_data.get("recvId", "")
    recv_type = event_data.get("recvType", "")
    user_id = event_data.get("userId", "")
    value = event_data.get("value", "")
    logger.info(f"机器人设置: msgId={msg_id}, recvId={recv_id}, recvType={recv_type}, userId={user_id}, value={value}")
