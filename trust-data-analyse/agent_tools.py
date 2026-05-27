import sqlite3
import os
import logging
import json
import base64
import io
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from langchain_core.tools import tool

# 获取数据库路径
# 数据库位于 trust-survey-sql-expert/trust_survey.db
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "trust-survey-sql-expert", "trust_survey.db")

logger = logging.getLogger("agent.tools")

READ_ONLY_SQL_PREFIXES = ("select", "with")

# 配置中文字体
plt.rcParams['font.sans-serif'] = ['Noto Sans CJK SC', 'WenQuanYi Micro Hei', 'Microsoft YaHei', 'SimHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

def _connect_readonly():
    return sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)


def _is_readonly_query(sql_query: str) -> bool:
    stripped = sql_query.strip().lower()
    if not stripped.startswith(READ_ONLY_SQL_PREFIXES):
        return False
    # execute() only runs one statement, but reject explicit multi-statement input
    # so the tool cannot be coaxed into write attempts or schema changes.
    return ";" not in stripped.rstrip(";")


def _generate_chart_base64(fig):
    """将matplotlib图表转换为base64编码的PNG图片"""
    buffer = io.BytesIO()
    fig.savefig(buffer, format='png', dpi=120, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    buffer.seek(0)
    b64 = base64.b64encode(buffer.read()).decode()
    return f'data:image/png;base64,{b64}'

def _create_bar_chart(labels, values, title, horizontal=False):
    """创建柱状图"""
    fig, ax = plt.subplots(figsize=(10, 6))
    colors = plt.cm.Set3(np.linspace(0, 1, len(labels)))
    if horizontal:
        bars = ax.barh(range(len(labels)), values, color=colors)
        ax.set_yticks(range(len(labels)))
        ax.set_yticklabels(labels, fontsize=9)
        ax.set_xlabel('数值', fontsize=10)
        for bar, val in zip(bars, values):
            ax.text(bar.get_width() + 0.5, bar.get_y() + bar.get_height()/2, f'{val}', va='center', fontsize=8)
    else:
        bars = ax.bar(range(len(labels)), values, color=colors)
        ax.set_xticks(range(len(labels)))
        ax.set_xticklabels(labels, fontsize=8, rotation=45, ha='right')
        ax.set_ylabel('数值', fontsize=10)
        for bar, val in zip(bars, values):
            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.3, f'{val}', ha='center', fontsize=8)
    ax.set_title(title, fontsize=13, fontweight='bold')
    plt.tight_layout()
    return _generate_chart_base64(fig)

def _create_pie_chart(labels, values, title):
    """创建饼图"""
    fig, ax = plt.subplots(figsize=(8, 6))
    non_zero = [(l, v) for l, v in zip(labels, values) if v > 0]
    if not non_zero:
        plt.close(fig)
        return None
    labels_nz, values_nz = zip(*non_zero)
    colors = plt.cm.Set3(np.linspace(0, 1, len(labels_nz)))
    wedges, texts, autotexts = ax.pie(values_nz, labels=labels_nz, autopct='%1.1f%%',
                                       colors=colors, startangle=90, textprops={'fontsize': 9})
    ax.set_title(title, fontsize=13, fontweight='bold')
    plt.tight_layout()
    return _generate_chart_base64(fig)

def _create_radar_chart(categories, values, title):
    """创建雷达图"""
    fig, ax = plt.subplots(figsize=(8, 8), subplot_kw=dict(polar=True))
    angles = np.linspace(0, 2 * np.pi, len(categories), endpoint=False).tolist()
    angles += angles[:1]
    values = list(values) + values[:1]
    ax.plot(angles, values, 'o-', linewidth=2, color='#1976D2')
    ax.fill(angles, values, alpha=0.15, color='#1976D2')
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(categories, fontsize=10)
    ax.set_title(title, fontsize=14, fontweight='bold', pad=20)
    plt.tight_layout()
    return _generate_chart_base64(fig)

def _create_line_chart(x_labels, y_values, title, xlabel='', ylabel=''):
    """创建折线图"""
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.plot(range(len(x_labels)), y_values, 'o-', linewidth=2, color='#1976D2', markersize=8)
    ax.set_xticks(range(len(x_labels)))
    ax.set_xticklabels(x_labels, fontsize=9)
    ax.set_xlabel(xlabel, fontsize=10)
    ax.set_ylabel(ylabel, fontsize=10)
    ax.set_title(title, fontsize=13, fontweight='bold')
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    return _generate_chart_base64(fig)

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


@tool
def generate_chart(chart_type: str, labels: str, values: str, title: str):
    """
    根据数据生成图表，返回base64编码的PNG图片。
    
    参数:
    - chart_type: 图表类型，可选值: 'bar'(柱状图), 'pie'(饼图), 'radar'(雷达图), 'line'(折线图), 'horizontal_bar'(横向柱状图)
    - labels: 标签列表，JSON格式字符串，例如: '["标签1", "标签2", "标签3"]'
    - values: 数值列表，JSON格式字符串，例如: '[10, 20, 30]'
    - title: 图表标题
    
    返回: base64编码的PNG图片数据URI，可直接嵌入HTML显示
    """
    logger.info(f"[工具调用] generate_chart -> 类型: {chart_type}, 标题: {title}")
    try:
        label_list = json.loads(labels)
        value_list = json.loads(values)
        if len(label_list) != len(value_list):
            return "错误：标签和数值列表长度不一致"
        if len(label_list) == 0:
            return "错误：数据为空"
        chart_base64 = None
        if chart_type == 'bar':
            chart_base64 = _create_bar_chart(label_list, value_list, title, horizontal=False)
        elif chart_type == 'horizontal_bar':
            chart_base64 = _create_bar_chart(label_list, value_list, title, horizontal=True)
        elif chart_type == 'pie':
            chart_base64 = _create_pie_chart(label_list, value_list, title)
        elif chart_type == 'radar':
            chart_base64 = _create_radar_chart(label_list, value_list, title)
        elif chart_type == 'line':
            chart_base64 = _create_line_chart(label_list, value_list, title)
        else:
            return f"错误：不支持的图表类型 '{chart_type}'，可选类型: bar, horizontal_bar, pie, radar, line"
        if chart_base64:
            logger.info(f"[工具返回] generate_chart -> 成功生成图表")
            return f"[CHART]{chart_base64}[/CHART]"
        else:
            return "错误：图表生成失败"
    except json.JSONDecodeError as e:
        logger.error(f"[工具出错] generate_chart -> JSON解析错误: {str(e)}")
        return f"错误：JSON解析失败，请确保labels和values是有效的JSON数组格式"
    except Exception as e:
        logger.error(f"[工具出错] generate_chart -> 运行异常: {str(e)}")
        return f"图表生成出错: {str(e)}"
