import sqlite3
import os
from langchain_core.tools import tool

# 获取数据库路径
# 数据库位于 trust-survey-sql-expert/trust_survey.db
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "..", "trust-survey-sql-expert", "trust_survey.db")

@tool
def query_survey_db(sql_query: str):
    """
    执行 SQL 查询以访问信托行业调研数据库。
    在使用此工具之前，你应该先查询 metadata 表以了解字段名。
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
def get_survey_metadata():
    """
    获取信托调研数据库的元数据 (Metadata)，包括 column_id 和 original_question。
    在编写查询 survey_data 表的 SQL 之前，务必先调用此工具查找正确的字段名。
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        # 查询 metadata 表获取字段映射
        cursor.execute("SELECT column_id, original_question FROM metadata")
        rows = cursor.fetchall()
        conn.close()
        
        result = [f"{row[0]}: {row[1]}" for row in rows]
        return "\n".join(result)
    except Exception as e:
        return f"获取元数据出错: {str(e)}"

@tool
def get_db_schema():
    """
    获取数据库的表结构 (Schema)。
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
