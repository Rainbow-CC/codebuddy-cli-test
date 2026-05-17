import sqlite3
import os
from langchain_core.tools import tool

# 获取当前文件的绝对路径，方便定位数据库
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# 假设我们要访问项目根目录下的 academic-researcher/academic.sqlite
DB_PATH = os.path.join(BASE_DIR, "..", "academic-researcher", "academic.sqlite")

@tool
def query_academic_sqlite(sql_query: str):
    """
    执行 SQL 查询以访问学术数据库。
    在使用此工具之前，你应该先查询 schema 以了解表结构。
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(sql_query)
        rows = cursor.fetchall()
        # 获取列名
        columns = [description[0] for description in cursor.description]
        conn.close()
        
        if not rows:
            return "查询成功，但未找到匹配结果。"
        
        # 格式化输出
        result = [dict(zip(columns, row)) for row in rows]
        return str(result)
    except Exception as e:
        return f"执行 SQL 出错: {str(e)}"

@tool
def get_database_schema():
    """
    获取学术数据库的表结构 (Schema)。
    编写 SQL 之前务必调用此工具。
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT sql FROM sqlite_master WHERE type='table';")
        schemas = cursor.fetchall()
        conn.close()
        return "\n".join([s[0] for s in schemas if s[0]])
    except Exception as e:
        return f"获取 Schema 出错: {str(e)}"
