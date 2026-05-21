import sqlite3
import os
import logging
from langchain_core.tools import tool

# 获取数据库路径
# 数据库位于 trust-survey-sql-expert/trust_survey.db
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "trust-survey-sql-expert", "trust_survey.db")

logger = logging.getLogger("agent.tools")

READ_ONLY_SQL_PREFIXES = ("select", "with")


def _connect_readonly():
    return sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)


def _is_readonly_query(sql_query: str) -> bool:
    stripped = sql_query.strip().lower()
    if not stripped.startswith(READ_ONLY_SQL_PREFIXES):
        return False
    # execute() only runs one statement, but reject explicit multi-statement input
    # so the tool cannot be coaxed into write attempts or schema changes.
    return ";" not in stripped.rstrip(";")

@tool
def query_survey_db(sql_query: str):
    """
    执行 SQL 查询以访问信托行业调研数据库。
    在使用此工具之前，你应该先查询 metadata 表以了解字段名。
    """
    if not _is_readonly_query(sql_query):
        return "安全限制：只允许执行单条只读 SELECT/WITH 查询。"

    clean_sql = " ".join(sql_query.split())
    logger.info(f"[工具调用] query_survey_db -> 执行 SQL:\n   {clean_sql}")
    try:
        with _connect_readonly() as conn:
            cursor = conn.cursor()
            cursor.execute(sql_query)
            rows = cursor.fetchall()
            # 获取列名
            columns = [description[0] for description in cursor.description]
        
        if not rows:
            logger.info("[工具返回] query_survey_db -> 执行成功，但返回数据为空。")
            return "查询成功，但未找到匹配结果。"
        
        # 格式化输出
        result = [dict(zip(columns, row)) for row in rows]
        logger.info(f"[工具返回] query_survey_db -> 执行成功，返回 {len(rows)} 行记录。列信息: {columns}")
        return str(result)
    except Exception as e:
        logger.error(f"[工具出错] query_survey_db -> 运行异常: {str(e)}")
        return f"执行 SQL 出错: {str(e)}"

@tool
def get_survey_metadata():
    """
    获取信托调研数据库的元数据 (Metadata)，包括 column_id 和 original_question。
    在编写查询 survey_data 表的 SQL 之前，务必先调用此工具查找正确的字段名。
    """
    logger.info("[工具调用] get_survey_metadata -> 正在读取信托调研数据库元数据...")
    try:
        with _connect_readonly() as conn:
            cursor = conn.cursor()
            # 查询 metadata 表获取字段映射
            cursor.execute("SELECT column_id, original_question FROM metadata")
            rows = cursor.fetchall()
        
        result = [f"{row[0]}: {row[1]}" for row in rows]
        logger.info(f"[工具返回] get_survey_metadata -> 成功读取 {len(rows)} 条元数据记录")
        return "\n".join(result)
    except Exception as e:
        logger.error(f"[工具出错] get_survey_metadata -> 运行异常: {str(e)}")
        return f"获取元数据出错: {str(e)}"

@tool
def get_db_schema():
    """
    获取数据库的表结构 (Schema)。
    """
    logger.info("[工具调用] get_db_schema -> 正在获取数据库表结构...")
    try:
        with _connect_readonly() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT sql FROM sqlite_master WHERE type='table';")
            schemas = cursor.fetchall()
        logger.info("[工具返回] get_db_schema -> 成功获取表结构")
        return "\n".join([s[0] for s in schemas if s[0]])
    except Exception as e:
        logger.error(f"[工具出错] get_db_schema -> 运行异常: {str(e)}")
        return f"获取 Schema 出错: {str(e)}"

