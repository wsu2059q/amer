from utils.config import redis_client, blocked_words, replace_blocked_words
from utils import logger
import datetime
import json
from . import BindingManager
from .ToolManager import YunhuTools, QQTools, BaseTools
from typing import Dict, Any
yhtools = YunhuTools()
qqtools = QQTools()
basetools = BaseTools()
class QQMessageData:
    def __init__(self, data: Dict[str, Any]):
        self.self_id = data.get('self_id', "")
        self.user_id = data.get('user_id', "")
        self.time = data.get('time', "")
        self.message_id = data.get('message_id', "")
        self.message_seq = data.get('message_seq', "")
        self.real_id = data.get('real_id', "")
        self.message_type = data.get('message_type', "")
        self.raw_message = data.get('raw_message', "")
        self.font = data.get('font', "")
        self.sub_type = data.get('sub_type', "")
        self.message_format = data.get('message_format', "")
        self.post_type = data.get('post_type', "")
        self.group_id = data.get('group_id', "")
        
        sender_info = data.get('sender', {})
        self.sender_user_id = sender_info.get('user_id', "")
        self.sender_nickname = sender_info.get('nickname', "")
        self.sender_card = sender_info.get('card', "")
        self.sender_role = sender_info.get('role', "")

class YunhuMessageData:
    def __init__(self, data: Dict[str, Any]):
        self.version = data.get("version", "")
        self.header_event_id = data.get("header", {}).get("eventId", "")
        self.header_event_type = data.get("header", {}).get("eventType", "")
        self.header_event_time = data.get("header", {}).get("eventTime", "")

        # sender相关
        event_info = data.get("event", {})
        sender_info = event_info.get("sender", {})
        self.userid = event_info.get("userId", "")
        self.sender_id = sender_info.get("senderId", "")
        self.sender_type = sender_info.get("senderType", "")
        self.sender_user_level = sender_info.get("senderUserLevel", "")
        self.sender_nickname = sender_info.get("senderNickname", "")

        # msg相关
        message_info = event_info.get("message", {})
        self.msg_id = message_info.get("msgId", "")
        self.parent_id = message_info.get("parentId", "")
        self.send_time = message_info.get("sendTime", "")
        self.message_chat_id = message_info.get("chatId", "")
        self.message_chat_type = message_info.get("chatType", "")
        self.content_type = message_info.get("contentType", "")
        self.message_content = message_info.get("content", {}).get("text", "")
        self.message_content_base = message_info.get("content", {})
        self.instruction_id = message_info.get("instructionId", "")
        self.instruction_name = message_info.get("instructionName", "")
        self.command_id = message_info.get("commandId", "")
        self.command_name = message_info.get("commandName", "")

        # img相关
        self.image_url = self.message_content_base.get("imageUrl", "")
        self.image_name = self.message_content_base.get("imageName", "")
        self.etag = self.message_content_base.get("etag", "")
        self.is_gif = self.image_url.lower().endswith('.gif')

        self.setting_json = event_info.get('settingJson', '{}')
        self.settings = json.loads(self.setting_json)
        self.setting_group_id = event_info.get("groupId", "")

async def send(platform_a, platform_b, id_a, id_b, message_type, message_content, sender_id, sender_nickname, noBaseContent=None, msg_id=None):
    ban_status = await basetools.is_in_blacklist(sender_id)
    if ban_status["is_banned"]:
        return False
    # 屏蔽词处理
    original_message_content = message_content
    message_content = replace_blocked_words(message_content)
    
    logger.info(f"Original message: {original_message_content}, Replaced message: {message_content}")
    if original_message_content != message_content:
        logger.info("Sensitive word detected")
        sensitive_message = {
            "sender_id": sender_id,
            "sender_nickname": sender_nickname,
            "message_type": message_type,
            "message_content": original_message_content,
            "timestamp": str(datetime.datetime.now()),
            "msg_id": msg_id,
            "platform_from": platform_a,
            "id_from": id_a
        }
        # 存储到相应的敏感消息列表中
        sensitive_key = f"sensitive_messages:{platform_a}:{id_a}"
        redis_client.rpush(sensitive_key, json.dumps(sensitive_message))
        logger.info(f"存储敏感消息: {sensitive_key} -> {sensitive_message}")
    
    key_ab = f"{platform_a}:{id_a}:{platform_b}:{id_b}"
    key_ba = f"{platform_b}:{id_b}:{platform_a}:{id_a}"
    key_local = f"{platform_a}:{id_a}:{platform_a}:{id_a}"
    message_to_save = {
        "sender_id": sender_id,
        "sender_nickname": sender_nickname,
        "message_type": message_type,
        "message_content": message_content,
        "timestamp": str(datetime.datetime.now()),
        "msg_id": msg_id,
        "platform_from": platform_a,
        "id_from": id_a
    }
    if platform_a == platform_b and id_a == id_b:
        redis_client.rpush(key_local, json.dumps(message_to_save))
    else:
        redis_client.rpush(key_ab, json.dumps(message_to_save))
        redis_client.rpush(key_ba, json.dumps(message_to_save))
        redis_client.rpush(key_local, json.dumps(message_to_save))
    if msg_id is not None:
        # 将 msg_id 作为键存储，值可以是消息的主键或完整消息内容
        redis_client.set(f"msg_id:{msg_id}", json.dumps(message_to_save))
        logger.info(f"存储 msg_id: msg_id:{msg_id} -> {message_to_save}")

    if noBaseContent:
        message_content = noBaseContent
    logger.info(f"存储消息: {key_local} -> {message_to_save}")

    if platform_b == "QQ" or platform_b == "qq":
        try:
            await qqtools.send("group", int(group['id']), message_content)
        except Exception as e:
            logger.error(f"发送QQ群消息失败，群组ID: {group['id']}, 错误信息: {e}")
    elif platform_b == "YH" or platform_b == "yh":
        await yhtools.send(recvId=id_b, recvType="group", contentType="html", content=message_content)
    else:
        return "不支持的平台"

async def send_to_all_bindings(platform, id, message_type, message_content, sender_id, sender_nickname, noBaseContent=None, msg_id=None):
    """发送消息到指定平台的所有绑定群聊，排除消息来源的平台"""
    ban_status = await basetools.is_in_blacklist(sender_id)
    if ban_status["is_banned"]:
        return False

    # 获取所有绑定信息
    bind_info = BindingManager.get_info(platform, id)
    if bind_info['status'] != 0:
        return bind_info['msg']
    
    # 屏蔽词处理
    original_message_content = message_content
    message_content = replace_blocked_words(message_content)
    
    logger.info(f"Original message: {original_message_content}, Replaced message: {message_content}")
    if original_message_content != message_content:
        logger.info("Sensitive word detected")
        sensitive_message = {
            "sender_id": sender_id,
            "sender_nickname": sender_nickname,
            "message_type": message_type,
            "message_content": original_message_content,
            "timestamp": str(datetime.datetime.now()),
            "msg_id": msg_id,
            "platform_from": platform,
            "id_from": id
        }
        # 存储到相应的敏感消息列表中
        sensitive_key = f"sensitive_messages:{platform}:{id}"
        redis_client.rpush(sensitive_key, json.dumps(sensitive_message))
        logger.info(f"存储敏感消息: {sensitive_key} -> {sensitive_message}")
    # 创建消息记录
    key_local = f"{platform}:{id}:{platform}:{id}"
    message_to_save = {
        "sender_id": sender_id,
        "sender_nickname": sender_nickname,
        "message_type": message_type,
        "message_content": message_content,
        "timestamp": str(datetime.datetime.now()),
        "msg_id": msg_id,
        "platform_from": platform,
        "id_from": id
    }

    if msg_id is not None:
        # 将 msg_id 作为键存储，值可以是消息的主键或完整消息内容
        redis_client.set(f"msg_id:{msg_id}", json.dumps(message_to_save))
        logger.info(f"存储 msg_id: msg_id:{msg_id} -> {message_to_save}")

    message_content_alltext = message_content
    if noBaseContent:
        message_content = replace_blocked_words(noBaseContent)
    # 存储到所有相关key
    redis_client.rpush(key_local, json.dumps(message_to_save))
    logger.info(f"存储消息: {key_local} -> {message_to_save}")
    
    # 对于每个绑定群聊，存储key_ab/key_ba
    bind_data = bind_info['data']
    logger.info(f"绑定信息: {bind_data}")
    if platform == "QQ":
        for group in bind_data.get("YH_group_ids", []):
            if group['sync']:
                key_ab = f"{platform}:{id}:YH:{group['id']}"
                key_ba = f"YH:{group['id']}:{platform}:{id}"
                redis_client.rpush(key_ab, json.dumps(message_to_save))
                redis_client.rpush(key_ba, json.dumps(message_to_save))
    elif platform == "YH":
        for group in bind_data.get("QQ_group_ids", []):
            if group['sync']:
                key_ab = f"{platform}:{id}:QQ:{group['id']}"
                key_ba = f"QQ:{group['id']}:{platform}:{id}"
                redis_client.rpush(key_ab, json.dumps(message_to_save))
                redis_client.rpush(key_ba, json.dumps(message_to_save))
    
    bind_data = bind_info['data']
    if platform == "QQ":
        for group in bind_data.get("YH_group_ids", []):
            if group['sync']:
                await yhtools.send(recvId=group['id'], recvType="group", contentType="html", content=message_content)
    elif platform == "YH":
        for group in bind_data.get("QQ_group_ids", []):
            if group['sync']:
                try:
                    await qqtools.send("group", int(group['id']), message_content)
                except Exception as e:
                    logger.error(f"发送QQ群消息失败，群组ID: {group['id']}, 错误信息: {e}")
                    continue
    return "消息已发送到所有绑定群聊"
async def set_board_for_all_groups(platform, id, message_content, group_name, board_content):
    # 获取所有绑定信息
    bind_info = BindingManager.get_info(platform, id)
    if bind_info['status'] != 0:
        return bind_info['msg']
    
    board_content = (
        f"【提醒】\n{platform}群：{group_name} | {id}"
        f"\n  {message_content}"
    )
    bind_data = bind_info['data']
    if platform == "QQ":
        for group in bind_data.get("QQ_group_ids", []):
            if group['sync']:
                await yhtools.set_board(
                    group['id'],
                    "group", 
                    board_content
                )
                logger.info(f"发送看板云湖群 {group['id']} 设置看板: {board_content}")
        for group in bind_data.get("YH_group_ids", []):
            if group['sync']:
                await yhtools.set_board(
                    group['id'],
                    "group", 
                    board_content
                )
                logger.info(f"发送看板云湖群 {group['id']} 设置看板: {board_content}")
            
async def send_private_msg(platform, id, message_content):
    """发送私聊消息"""
    if platform == "QQ":
        await qqtools.send("private", int(group['id']), message_content)
    elif platform == "YH":
        await yhtools.send(recvId=id, recvType="user", contentType="text", content=message_content)
    else:
        return "平台不存在"
async def get_message(platform_a, platform_b, id_a, id_b):
    if platform_a == platform_b and id_a == id_b:
        # 本地消息查询，与get_total_message_count保持一致
        key_local = f"{platform_a}:{id_a}:{platform_a}:{id_a}"
        local_messages = redis_client.lrange(key_local, 0, -1)
        if local_messages:
            messages = [json.loads(msg) for msg in local_messages]
            # 按时间戳排序
            messages.sort(key=lambda x: x["timestamp"], reverse=True)
            return messages
    else:
        # 跨平台消息查询
        key_ab = f"{platform_a}:{id_a}:{platform_b}:{id_b}"
        key_ba = f"{platform_b}:{id_b}:{platform_a}:{id_a}"
        
        # 从Redis获取消息
        messages_ab = redis_client.lrange(key_ab, 0, -1)
        messages_ba = redis_client.lrange(key_ba, 0, -1)
        
        # 合并消息并去重
        all_messages = []
        seen = set()
        for msg in messages_ab + messages_ba:
            if msg not in seen:
                seen.add(msg)
                all_messages.append(json.loads(msg))
        
        # 按时间戳排序
        all_messages.sort(key=lambda x: x["timestamp"], reverse=True)
        return all_messages
    
    return []

async def get_total_message_count(platform, id_PF):
    """获取本地消息数"""
    # 仅获取本地消息
    key_local = f"{platform}:{id_PF}:{platform}:{id_PF}"
    local_messages = redis_client.lrange(key_local, 0, -1)
    return len(local_messages) if local_messages else 0

async def get_sync_message_count(platform, id_PF):
    """获取同步消息数"""
    # 获取本群聊的消息
    key_local = f"{platform}:{id_PF}:{platform}:{id_PF}"
    local_messages = redis_client.lrange(key_local, 0, -1)
    
    # 获取所有发送到我们平台的消息
    keys_ba = redis_client.keys(f"*:*:{platform}:{id_PF}")
    ba_messages = []
    for key in keys_ba:
        ba_messages.extend(redis_client.lrange(key, 0, -1))
    
    # 使用集合去重
    sync_messages = set(local_messages + ba_messages)
    return len(sync_messages) if sync_messages else 0

async def get_sensitive_messages(platform, id_PF):
    """获取敏感消息数"""
    # 从相应的敏感消息列表中获取消息
    sensitive_key = f"sensitive_messages:{platform}:{id_PF}"
    sensitive_messages = redis_client.lrange(sensitive_key, 0, -1)
    count = len(sensitive_messages)
    return count if count > 0 else 0

async def get_active_users(platform, id_PF):
    """获取活跃用户数"""
    # 获取本群聊的消息
    key_local = f"{platform}:{id_PF}:{platform}:{id_PF}"
    local_messages = redis_client.lrange(key_local, 0, -1)
    
    # 获取所有发送到我们平台的消息
    keys_ba = redis_client.keys(f"*:*:{platform}:{id_PF}")
    ba_messages = []
    for key in keys_ba:
        ba_messages.extend(redis_client.lrange(key, 0, -1))
    
    # 合并消息并去重
    users = set()
    for msg in local_messages + ba_messages:
        message = json.loads(msg)
        users.add(message["sender_id"])
    return len(users) if users else 0

async def get_total_message_details(platform, id_PF, page=1, page_size=20):
    """获取本地消息详情"""
    # 仅获取本地消息
    key_local = f"{platform}:{id_PF}:{platform}:{id_PF}"
    total_count = redis_client.llen(key_local)
    
    # 计算分页偏移
    start = (page - 1) * page_size
    end = start + page_size - 1
    
    # 获取分页数据
    local_messages = redis_client.lrange(key_local, start, end)
    
    # 解析消息
    messages = []
    for msg in local_messages:
        message = json.loads(msg)
        messages.append({
            "sender": message["sender_nickname"],
            "content": message["message_content"],
            "timestamp": message["timestamp"]
        })
    
    # 按照时间戳倒序排列
    messages = sorted(messages, key=lambda x: x["timestamp"], reverse=True)
    
    return {
        "total_count": total_count,
        "page": page,
        "page_size": page_size,
        "messages": messages
    }

async def get_sync_message_details(platform, id_PF, page=1, page_size=20):
    """获取同步消息详情"""
    # 获取本群聊的消息
    key_local = f"{platform}:{id_PF}:{platform}:{id_PF}"
    local_messages = redis_client.lrange(key_local, 0, -1)
    
    # 获取所有发送到我们平台的消息
    keys_ba = redis_client.keys(f"*:*:{platform}:{id_PF}")
    ba_messages = []
    for key in keys_ba:
        ba_messages.extend(redis_client.lrange(key, 0, -1))
    
    # 合并消息并去重
    all_messages = []
    seen = set()
    for msg in local_messages + ba_messages:
        if msg not in seen:
            seen.add(msg)
            message = json.loads(msg)
            all_messages.append({
                "sender": message["sender_nickname"],
                "content": message["message_content"],
                "timestamp": message["timestamp"]
            })
    
    # 按照时间戳倒序排列
    all_messages = sorted(all_messages, key=lambda x: x["timestamp"], reverse=True)
    
    # 分页处理
    total_count = len(all_messages)
    start = (page - 1) * page_size
    end = start + page_size
    messages = all_messages[start:end]
    
    return {
        "total_count": total_count,
        "page": page,
        "page_size": page_size,
        "messages": messages
    }

async def get_sensitive_message_details(platform, id_PF, page=1, page_size=20):
    """获取敏感消息详情"""
    sensitive_key = f"sensitive_messages:{platform}:{id_PF}"
    total_count = redis_client.llen(sensitive_key)
    
    # 计算分页偏移
    start = (page - 1) * page_size
    end = start + page_size - 1
    
    # 获取分页数据
    sensitive_messages = redis_client.lrange(sensitive_key, start, end)
    
    messages = []
    for msg in sensitive_messages:
        try:
            message = json.loads(msg)
            messages.append({
                "sender": message["sender_nickname"],
                "content": message["message_content"],
                "timestamp": message["timestamp"]
            })
        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Error parsing sensitive message: {e}")
    
    # 按照时间戳倒序排列
    messages = sorted(messages, key=lambda x: x["timestamp"], reverse=True)
    
    return {
        "total_count": total_count,
        "page": page,
        "page_size": page_size,
        "messages": messages
    }

async def get_active_user_details(platform, id_PF, page=1, page_size=20):
    """获取活跃用户详情"""
    key_local = f"{platform}:{id_PF}:{platform}:{id_PF}"
    messages = redis_client.lrange(key_local, 0, -1)
    
    users = {}
    for msg in messages:
        message = json.loads(msg)
        user_id = message["sender_id"]
        if user_id not in users:
            users[user_id] = {
                "nickname": message["sender_nickname"],
                "last_active": message["timestamp"],
                "message_count": 0
            }
        users[user_id]["message_count"] += 1
    
    # 按消息数量排序
    sorted_users = sorted(users.values(), key=lambda x: x["message_count"], reverse=True)
    
    # 分页处理
    total_count = len(sorted_users)
    start = (page - 1) * page_size
    end = start + page_size
    paged_users = sorted_users[start:end]
    
    return {
        "total_count": total_count,
        "page": page,
        "page_size": page_size,
        "users": paged_users
    }
