import sqlite3
from utils.config import sqlite_db_path
from utils import logger
import json
import logging
from .ToolManager import YunhuTools
yhtools = YunhuTools()
conn = sqlite3.connect(sqlite_db_path)
c = conn.cursor()
def get_base_sync(platform_A, platform_B, id_A, id_B):
    try:
        logger.debug(f"尝试获取 {platform_A} 和 {platform_B} 的基础同步信息")
        
        if platform_A == "QQ":
            if platform_B == "YH":
                c.execute("SELECT YH_group_ids FROM QQ_table WHERE QQ_group_id=?", (id_A,))
                row = c.fetchone()
                if row:
                    yh_group_ids = json.loads(row[0]) if row[0] else []
                    for group in yh_group_ids:
                        if group['id'] == id_B:
                            return group.get('sync', True)

        elif platform_A == "YH":
            if platform_B == "QQ":
                c.execute("SELECT QQ_group_ids FROM YH_table WHERE YH_group_id=?", (id_A,))
                row = c.fetchone()
                if row:
                    qq_group_ids = json.loads(row[0]) if row[0] else []
                    for group in qq_group_ids:
                        if group['id'] == id_B:
                            return group.get('sync', True)

        logger.debug(f"未找到 {platform_A} 和 {platform_B} 的基础同步信息")
        return None

    except sqlite3.Error as e:
        logger.error(f"获取 {platform_A} 和 {platform_B} 的基础同步信息时发生错误: {e}")
        return None

def get_info(platform, id):
    try:
        logger.debug(f"尝试获取 {platform} 的绑定信息")
        sync_other = {}
        if platform == "QQ" or platform == "qq":
            c.execute("SELECT YH_group_ids, MCTokens FROM QQ_table WHERE QQ_group_id=?", (id,))
            row = c.fetchone()
            if row:
                YH_group_ids = json.loads(row[0]) if row[0] else []
                MCTokens = json.loads(row[1]) if row[1] else []
                
                # 获取并设置 YH 的 binding_sync 状态
                for group in YH_group_ids:
                    base_sync = get_base_sync("YH", "QQ", group['id'], id)
                    group['binding_sync'] = base_sync if base_sync is not None else group.get('sync', True)
                
                logger.debug(f"获取到 {platform} 的绑定信息: {YH_group_ids}")
                return {"status": 0, "msg": "查询成功", "data": {"YH_group_ids": YH_group_ids}}
            else:
                return {"status": 5, "msg": "未绑定任何平台"}
        if platform == "YH" or platform == "yh":
            c.execute("SELECT QQ_group_ids, MCTokens FROM YH_table WHERE YH_group_id=?", (id,))
            row = c.fetchone()
            if row:
                QQ_group_ids = json.loads(row[0]) if row[0] else []
                MCTokens = json.loads(row[1]) if row[1] else []
                
                # 获取 QQ 的 sync 状态
                sync_other['QQ'] = {group['id']: group['sync'] for group in QQ_group_ids}
                
                # 添加 binding_sync 到 QQ_group_ids
                for group in QQ_group_ids:
                    base_sync = get_base_sync("QQ", "YH", group['id'], id)
                    group['binding_sync'] = base_sync if base_sync is not None else sync_other['QQ'].get(group['id'], True)
                
                logger.debug(f"获取到 {platform} 的绑定信息: {QQ_group_ids}")
                return {"status": 0, "msg": "查询成功", "data": {"QQ_group_ids": QQ_group_ids}}
            else:
                return {"status": 5, "msg": "未绑定任何平台"}
        else:
            logger.warning(f"未知平台: {platform}")
            return {"status": 3, "msg": "未知平台"}
    except sqlite3.Error as e:
        logger.error(f"获取 {platform} 的绑定信息时发生错误: {e}")
        return None

def bind(platform_A, platform_B, id_A, id_B):
    try:
        logger.debug(f"尝试绑定 {platform_A} 和 {platform_B}")
        result = None
        if platform_A == "QQ":
            if platform_B == "YH":
                result = update_QQ_table("add", "YH", id_A, id_B)
        
        elif platform_A == "YH":
            if platform_B == "QQ":
                result = update_YH_table("add", "QQ", id_A, id_B)
        else:
            logger.warning(f"未知平台: {platform_A}")
            return {"status": 3, "msg": "未知平台"}
        logger.debug(result)
        return result
    except Exception as e:
        logger.error(f"绑定失败: {e}")
        return {"status": -1, "msg": "绑定失败"}

def unbind(platform_A, platform_B, id_A, id_B):
    try:
        logger.debug(f"尝试绑定 {platform_A} 和 {platform_B}")
        if platform_A == "QQ":
            if platform_B == "YH":
                result = update_QQ_table("del", "YH", id_A, id_B)
            return result
            logger.debug(result)
        elif platform_A == "YH":
            if platform_B == "QQ":
                result = update_YH_table("del", "QQ", id_A, id_B)
            return result
            logger.debug(result)
        else:
            logger.warning(f"未知平台: {platform_A}")
            return {"status": 3, "msg": "未知平台"}
    except Exception as e:
        logger.error(f"绑定失败: {e}")
        return {"status": -1, "msg": "绑定失败"}
    finally:
        return {"status": 0, "msg": "群聊已解绑"}

def unbind_all(platform, id):
    try:
        logger.debug(f"尝试解绑所有 {platform} 和 {id}")
        if platform == "QQ" or platform == "qq":
            result = update_QQ_table("del_all", None, id, None)
        elif platform == "YH" or platform == "yh":
            result = update_YH_table("del_all", None, id, None)
        else:
            logger.warning(f"未知平台: {platform}")
            return {"status": 3, "msg": "未知平台"}
    except Exception as e:
        logger.error(f"解绑失败: {e}")
        return {"status": -1, "msg": "解绑失败"}
    finally:
        return {"status": 0, "msg": "群聊已全部解绑"}

def list_platform_table(platform, id_PF):
    try:
        if platform == "QQ" or platform == "qq":
            c.execute("SELECT * FROM QQ_table WHERE QQ_group_id=?", (id_PF,))
        elif platform == "YH" or platform == "yh":
            c.execute("SELECT * FROM YH_table WHERE YH_group_id=?", (id_PF,))
        row = c.fetchone()
        return {"status": 0,"platform": platform, "data": row, "msg": "查询成功"}
    except sqlite3.Error as e:
        logger.error(f"SQLite 错误: {e}")
        return {"status": -1, "platform": platform, "data": e, "msg": "查询失败"}

def set_all_sync(platform, id_PF, sync_data):
    try:
        logger.debug(f"尝试设置 {platform} 的同步状态, ID: {id_PF}, 同步数据: {sync_data}")

        if platform == "QQ" or platform == "qq":
            result = update_QQ_table("set_all_sync", None, id_PF, None, sync_data)
        elif platform == "YH" or platform == "yh":
            result = update_YH_table("set_all_sync", None, id_PF, None, sync_data)
        else:
            logger.warning(f"未知平台: {platform}")
            return {"status": 3, "msg": "未知平台"}
        
        logger.debug(result)
        return result
    except Exception as e:
        logger.error(f"设置同步状态失败: {e}")
        return {"status": -1, "msg": "设置同步状态失败"}
def set_sync(platform_A, platform_B, id_A, id_B, sync_data):
    try:
        logger.debug(f"尝试设置 {platform_A} 和 {platform_B} 的同步状态, ID: {id_A}, {id_B}, 同步数据: {sync_data}")

        if platform_A == "QQ":
            result = update_QQ_table("set_sync", platform_B, id_A, id_B, sync_data)
        elif platform_A == "YH":
            result = update_YH_table("set_sync", platform_B, id_A, id_B, sync_data)
        else:
            logger.warning(f"未知平台: {platform_A}")
            return {"status": 3, "msg": "未知平台"}
        logger.debug(result)
        return result
    except Exception as e:
        logger.error(f"设置同步状态失败: {e}")
        return {"status": -1, "msg": "设置同步状态失败"}

def update_QQ_table(type, platform, id_QQ, id_PF, sync_data=None, called_from=None):
    try:
        logger.debug(f"尝试更新 QQ_table 类型: {type}, 平台: {platform}, ID: {id_PF}")

        c.execute("SELECT * FROM QQ_table WHERE QQ_group_id=?", (id_QQ,))
        existing_record = c.fetchone()
        logger.debug(f"查询结果: {existing_record}")

        if existing_record:
            if platform == "YH" or platform == "yh":
                yh_group_ids = json.loads(existing_record[1]) if existing_record[1] else []
                logger.debug(f"YH_group_ids: {yh_group_ids}")
        else:
            if platform == "YH" or platform == "yh":
                yh_group_ids = []

        if type == "add":
            if platform == "YH" or platform == "yh":
                if existing_record and any(item['id'] == id_PF for item in yh_group_ids):
                    return {"status": 4, "msg": "绑定已存在"}
                yh_group_ids.append({"id": id_PF, "sync": True})
                if existing_record:
                    c.execute("UPDATE QQ_table SET YH_group_ids=? WHERE QQ_group_id=?", (json.dumps(yh_group_ids), id_QQ))
                else:
                    c.execute("INSERT INTO QQ_table (QQ_group_id, YH_group_ids) VALUES (?, ?)", (id_QQ, json.dumps(yh_group_ids)))

                # 更新 YH_table
                update_YH_table("add", "QQ", id_PF, id_QQ)

        elif type == "del":
            if platform == "YH" or platform == "yh":
                if not existing_record or not any(item['id'] == id_PF for item in yh_group_ids):
                    return {"status": 5, "msg": "绑定不存在"}
                yh_group_ids = [item for item in yh_group_ids if item['id'] != id_PF]
                c.execute("UPDATE QQ_table SET YH_group_ids=? WHERE QQ_group_id=?", (json.dumps(yh_group_ids), id_QQ))

                # 删除 YH_table 中的记录
                update_YH_table("del", "QQ", id_PF, id_QQ)

        elif type == "del_all":
            # 删除 YH_table 和 MC_table 中的相关记录
            c.execute("SELECT YH_group_ids, MCTokens FROM QQ_table WHERE QQ_group_id=?", (id_QQ,))
            record_to_delete = c.fetchone()
            if record_to_delete:
                yh_group_ids = json.loads(record_to_delete[0]) if record_to_delete[0] else []
                mc_tokens = json.loads(record_to_delete[1]) if record_to_delete[1] else []
                for item in yh_group_ids:
                    from .ToolManager import YunhuTools
                    yhBot = YunhuTools()
                    yhBot.send(
                            recvId=item['id'],
                            recvType="group",
                            contentType="text",
                            content=f"与QQ群{id_QQ}绑定已删除")
                    logger.debug(update_YH_table("del", "QQ", item['id'], id_QQ))
                c.execute("DELETE FROM QQ_table WHERE QQ_group_id=?", (id_QQ,))
        elif type == "set_sync":
            if platform == "YH" or platform == "yh":
                yh_group_ids = json.loads(existing_record[1]) if existing_record[1] else []
                for item in yh_group_ids:
                    if item['id'] == id_PF:
                        item['sync'] = sync_data.get('YH', item['sync'])
                        break
                c.execute("UPDATE QQ_table SET YH_group_ids=? WHERE QQ_group_id=?", (json.dumps(yh_group_ids), id_QQ))

                # 更新 YH_table 中的同步状态
                if called_from != "YH":
                    update_YH_table("set_sync", "QQ", id_PF, id_QQ, sync_data, called_from="QQ")

        elif type == "set_all_sync":
            if existing_record:
                yh_group_ids = json.loads(existing_record[1]) if existing_record[1] else []
                mc_tokens = json.loads(existing_record[2]) if existing_record[2] else []

                for item in yh_group_ids:
                    item['sync'] = sync_data.get('YH', item['sync'])

                c.execute("UPDATE QQ_table SET YH_group_ids=?, MCTokens=? WHERE QQ_group_id=?", 
                        (json.dumps(yh_group_ids), json.dumps(mc_tokens), id_QQ))

                # 更新 YH_table 和 MC_table 中的同步状态
                for item in yh_group_ids:
                    update_YH_table("set_sync", "QQ", item['id'], id_QQ, sync_data, called_from="QQ")
            
        conn.commit()
        return {"status": 0, "msg": "操作成功"}
    except Exception as e:
        logger.error(f"更新表时发生错误: {e}")
        return {"status": -1, "msg": str(e)}

def update_YH_table(type, platform, id_YH, id_PF, sync_data=None, called_from=None):
    try:
        logger.debug(f"尝试更新 YH_table 类型: {type}, 平台: {platform}, ID: {id_PF}")

        c.execute("SELECT * FROM YH_table WHERE YH_group_id=?", (id_YH,))
        existing_record = c.fetchone()

        if existing_record:
            if platform == "QQ" or platform == "qq":
                qq_group_ids = json.loads(existing_record[1]) if existing_record[1] else []
                logger.debug(f"QQ_group_ids: {qq_group_ids}")
        else:
            if platform == "QQ" or platform == "qq":
                qq_group_ids = []

        if type == "add":
            if platform == "QQ" or platform == "qq":
                if existing_record and any(item['id'] == id_PF for item in qq_group_ids):
                    return {"status": 4, "msg": "绑定已存在"}
                qq_group_ids.append({"id": id_PF, "sync": True})
                if existing_record:
                    c.execute("UPDATE YH_table SET QQ_group_ids=? WHERE YH_group_id=?", (json.dumps(qq_group_ids), id_YH))
                else:
                    c.execute("INSERT INTO YH_table (YH_group_id, QQ_group_ids) VALUES (?, ?)", (id_YH, json.dumps(qq_group_ids)))

                # 更新 QQ_table
                update_QQ_table("add", "YH", id_PF, id_YH)

        elif type == "del":
            if platform == "QQ" or platform == "qq":
                if not existing_record or not any(item['id'] == id_PF for item in qq_group_ids):
                    return {"status": 5, "msg": "绑定不存在"}
                qq_group_ids = [item for item in qq_group_ids if item['id'] != id_PF]
                c.execute("UPDATE YH_table SET QQ_group_ids=? WHERE YH_group_id=?", (json.dumps(qq_group_ids), id_YH))

                # 删除 QQ_table 中的记录
                update_QQ_table("del", "YH", id_PF, id_YH)

        elif type == "del_all":
            # 删除 QQ_table 和 MC_table 中的相关记录
            c.execute("SELECT QQ_group_ids, MCTokens FROM YH_table WHERE YH_group_id=?", (id_YH,))
            record_to_delete = c.fetchone()
            logger.debug(f"查询结果: {record_to_delete}")
            if record_to_delete:
                logger.debug(f"record_to_delete: {record_to_delete}")
                qq_group_ids = json.loads(record_to_delete[0]) if record_to_delete[0] else []
                mc_tokens = json.loads(record_to_delete[1]) if record_to_delete[1] else []
                logger.debug(f"QQ_group_ids: {qq_group_ids}")
                for item in qq_group_ids:
                    from main import qqBot
                    qqBot.send_group_msg(group_id=item['id'], message=f"该群的云湖{id_MC}已被解绑")
                    logger.debug(f"向 QQ_group_id:{item['id']} 发送消息")
                    update_QQ_table("del", "YH", item['id'], id_YH)
                c.execute("DELETE FROM YH_table WHERE YH_group_id=?", (id_YH,))

            if platform == "QQ" or platform == "qq":
                qq_group_ids = json.loads(existing_record[1]) if existing_record[1] else []
                for item in qq_group_ids:
                    if item['id'] == id_PF:
                        item['sync'] = sync_data.get('QQ', item['sync'])
                        break
                c.execute("UPDATE YH_table SET QQ_group_ids=? WHERE YH_group_id=?", (json.dumps(qq_group_ids), id_YH))

                # 更新 QQ_table 中的同步状态
                if called_from != "QQ":
                    update_QQ_table("set_sync", "YH", id_PF, id_YH, sync_data, called_from="YH")

        elif type == "set_all_sync":
            if existing_record:
                qq_group_ids = json.loads(existing_record[1]) if existing_record[1] else []
                mc_tokens = json.loads(existing_record[2]) if existing_record[2] else []

                for item in qq_group_ids:
                    item['sync'] = sync_data.get('QQ', item['sync'])

                c.execute("UPDATE YH_table SET QQ_group_ids=?, MCTokens=? WHERE YH_group_id=?", 
                        (json.dumps(qq_group_ids), json.dumps(mc_tokens), id_YH))

                # 更新 QQ_table 中的同步状态
                for item in qq_group_ids:
                    update_QQ_table("set_sync", "YH", item['id'], id_YH, sync_data, called_from="YH")
        conn.commit()
        return {"status": 0, "msg": "操作成功"}
    except Exception as e:
        logger.error(f"更新表时发生错误: {e}")
        return {"status": -1, "msg": str(e)}

if __name__ == "__main__":
    # result = unbind_all("QQ", "786432215")
    # bind_result = bind("QQ", "YH", "786432215", "1234567890")
    # get_info = get_info("QQ", "786432215")
    set_sync = set_sync(QQ_group_id = "786432215", YH_group_id = "1234567890", sync_QQYH_mode = False, sync_YHQQ_mode = False)
    logger.info(set_sync)