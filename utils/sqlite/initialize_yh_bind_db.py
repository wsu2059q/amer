import sqlite3

def initialize_database():
    conn = sqlite3.connect("amer.db")
    c = conn.cursor()
    
    c.execute('''
    CREATE TABLE QQ_table (
        QQ_group_id TEXT PRIMARY KEY,
        YH_group_ids TEXT,
    )
    ''')

    c.execute('''
    CREATE TABLE YH_table (
        YH_group_id TEXT PRIMARY KEY,
        QQ_group_ids TEXT,
    )
    ''')
    
    conn.commit()
    conn.close()
    print("数据库初始化完成。")

if __name__ == "__main__":
    initialize_database()