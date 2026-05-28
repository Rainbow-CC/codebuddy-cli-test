import sqlite3
import os
import logging
from langchain_core.tools import tool

# 获取数据库路径
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "trust_survey.db")

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


# ========== 兴业信托专项分析工具 ==========

XINGYE_TRUST_NAME = "兴业信托"

@tool
def analyze_xingye_strengths():
    """
    分析兴业信托的优势领域。
    对比行业平均水平，识别兴业信托在科技建设方面的优势维度。
    当用户询问兴业信托相关问题时，必须调用此工具获取优势分析。
    """
    logger.info("[工具调用] analyze_xingye_strengths -> 分析兴业信托优势领域")
    
    try:
        with _connect_readonly() as conn:
            cursor = conn.cursor()
            
            # 获取兴业信托的各项指标
            cursor.execute('SELECT * FROM survey_data WHERE c1_公司简称 = ?', (XINGYE_TRUST_NAME,))
            xingye_data = cursor.fetchone()
            
            if not xingye_data:
                return "未找到兴业信托的数据"
            
            # 获取列名
            cursor.execute("PRAGMA table_info(survey_data)")
            columns = [col[1] for col in cursor.fetchall()]
            xingye_dict = dict(zip(columns, xingye_data))
            
            # 分析优势维度（数值型字段，与行业平均对比）
            strengths = []
            
            # 1. 科技投入分析
            cursor.execute('SELECT AVG("c14_万元_2024年") FROM survey_data WHERE "c14_万元_2024年" IS NOT NULL AND "c14_万元_2024年" > 0')
            avg_investment = cursor.fetchone()[0] or 0
            xingye_investment = xingye_dict.get('c14_万元_2024年', 0) or 0
            if xingye_investment > avg_investment:
                strengths.append({
                    'dimension': '2024年科技投入',
                    'value': f"{xingye_investment:.0f}万元",
                    'industry_avg': f"{avg_investment:.0f}万元",
                    'advantage': f"高于行业平均 {((xingye_investment/avg_investment - 1) * 100):.1f}%"
                })
            
            # 2. 自有科技团队规模
            cursor.execute('SELECT AVG("c21_2_自有科技团队总人数") FROM survey_data WHERE "c21_2_自有科技团队总人数" IS NOT NULL AND "c21_2_自有科技团队总人数" > 0')
            avg_tech_team = cursor.fetchone()[0] or 0
            xingye_tech_team = xingye_dict.get('c21_2_自有科技团队总人数', 0) or 0
            if xingye_tech_team > avg_tech_team:
                strengths.append({
                    'dimension': '自有科技团队规模',
                    'value': f"{xingye_tech_team:.0f}人",
                    'industry_avg': f"{avg_tech_team:.0f}人",
                    'advantage': f"高于行业平均 {((xingye_tech_team/avg_tech_team - 1) * 100):.1f}%"
                })
            
            # 3. 科技人员占比
            cursor.execute('SELECT AVG("c21_2_自有科技团队总人数" * 100.0 / "c20_2_2人员配置_1_公司员工总人数_人") FROM survey_data WHERE "c21_2_自有科技团队总人数" > 0 AND "c20_2_2人员配置_1_公司员工总人数_人" > 0')
            avg_tech_ratio = cursor.fetchone()[0] or 0
            total_employees = xingye_dict.get('c20_2_2人员配置_1_公司员工总人数_人', 0) or 0
            if total_employees > 0:
                xingye_tech_ratio = (xingye_tech_team / total_employees) * 100
                if xingye_tech_ratio > avg_tech_ratio:
                    strengths.append({
                        'dimension': '科技人员占比',
                        'value': f"{xingye_tech_ratio:.2f}%",
                        'industry_avg': f"{avg_tech_ratio:.2f}%",
                        'advantage': f"高于行业平均 {(xingye_tech_ratio - avg_tech_ratio):.2f}个百分点"
                    })
            
            # 4. CIO设立（如果是1表示已设立）
            xingye_cio = xingye_dict.get('c65_是否设立了首席信息官CIO', 0)
            if xingye_cio == 1:
                cursor.execute('SELECT COUNT(*) FROM survey_data WHERE "c65_是否设立了首席信息官CIO" = 1')
                cio_count = cursor.fetchone()[0]
                cursor.execute('SELECT COUNT(*) FROM survey_data')
                total_count = cursor.fetchone()[0]
                cio_ratio = (cio_count / total_count) * 100 if total_count > 0 else 0
                strengths.append({
                    'dimension': 'CIO设立',
                    'value': '已设立',
                    'industry_avg': f"行业设立率 {cio_ratio:.1f}%",
                    'advantage': '已设立首席信息官，信息化治理结构完善'
                })
            
            # 5. 等保三级认证
            xingye_dengbao = xingye_dict.get('c86_等保三级', 0)
            if xingye_dengbao == 1:
                strengths.append({
                    'dimension': '信息安全等级保护',
                    'value': '已通过等保三级',
                    'industry_avg': '行业部分公司通过',
                    'advantage': '信息安全管理体系达到国家三级标准'
                })
            
            logger.info(f"[工具返回] analyze_xingye_strengths -> 找到 {len(strengths)} 项优势")
            
            if not strengths:
                return "兴业信托在各维度与行业平均水平相当，暂无显著优势领域。"
            
            result = "【兴业信托优势分析】\n\n"
            for i, s in enumerate(strengths, 1):
                result += f"{i}. {s['dimension']}\n"
                result += f"   兴业信托: {s['value']}\n"
                result += f"   {s['industry_avg']}\n"
                result += f"   ✓ {s['advantage']}\n\n"
            
            return result
            
    except Exception as e:
        logger.error(f"[工具出错] analyze_xingye_strengths -> 运行异常: {str(e)}")
        return f"分析兴业信托优势时出错: {str(e)}"


@tool
def analyze_xingye_gaps():
    """
    分析兴业信托的待提升领域。
    对比行业TOP10水平，识别兴业信托在科技建设方面的改进空间。
    当用户询问兴业信托相关问题时，必须调用此工具获取改进建议。
    """
    logger.info("[工具调用] analyze_xingye_gaps -> 分析兴业信托待提升领域")
    
    try:
        with _connect_readonly() as conn:
            cursor = conn.cursor()
            
            # 获取兴业信托的各项指标
            cursor.execute('SELECT * FROM survey_data WHERE c1_公司简称 = ?', (XINGYE_TRUST_NAME,))
            xingye_data = cursor.fetchone()
            
            if not xingye_data:
                return "未找到兴业信托的数据"
            
            # 获取列名
            cursor.execute("PRAGMA table_info(survey_data)")
            columns = [col[1] for col in cursor.fetchall()]
            xingye_dict = dict(zip(columns, xingye_data))
            
            gaps = []
            
            # 1. 科技投入与TOP10对比
            cursor.execute('SELECT "c14_万元_2024年" FROM survey_data WHERE "c14_万元_2024年" IS NOT NULL AND "c14_万元_2024年" > 0 ORDER BY "c14_万元_2024年" DESC LIMIT 10')
            top10_investments = [row[0] for row in cursor.fetchall()]
            if top10_investments:
                avg_top10_investment = sum(top10_investments) / len(top10_investments)
                xingye_investment = xingye_dict.get('c14_万元_2024年', 0) or 0
                if xingye_investment < avg_top10_investment:
                    gap_ratio = ((avg_top10_investment - xingye_investment) / avg_top10_investment) * 100
                    gaps.append({
                        'dimension': '2024年科技投入',
                        'xingye_value': f"{xingye_investment:.0f}万元",
                        'benchmark': f"TOP10平均 {avg_top10_investment:.0f}万元",
                        'gap': f"差距 {gap_ratio:.1f}%",
                        'suggestion': '建议加大科技投入力度，向行业标杆看齐'
                    })
            
            # 2. 自有科技团队与TOP10对比
            cursor.execute('SELECT "c21_2_自有科技团队总人数" FROM survey_data WHERE "c21_2_自有科技团队总人数" IS NOT NULL AND "c21_2_自有科技团队总人数" > 0 ORDER BY "c21_2_自有科技团队总人数" DESC LIMIT 10')
            top10_teams = [row[0] for row in cursor.fetchall()]
            if top10_teams:
                avg_top10_team = sum(top10_teams) / len(top10_teams)
                xingye_team = xingye_dict.get('c21_2_自有科技团队总人数', 0) or 0
                if xingye_team < avg_top10_team:
                    gap_ratio = ((avg_top10_team - xingye_team) / avg_top10_team) * 100
                    gaps.append({
                        'dimension': '自有科技团队规模',
                        'xingye_value': f"{xingye_team:.0f}人",
                        'benchmark': f"TOP10平均 {avg_top10_team:.0f}人",
                        'gap': f"差距 {gap_ratio:.1f}%",
                        'suggestion': '建议扩充科技人才队伍，提升自主研发能力'
                    })
            
            # 3. 信创转型进展
            xingye_xinchuang = xingye_dict.get('c131_信创转型与进展2_1', 0)
            if xingye_xinchuang in [0, 1]:  # 0=未启动, 1=规划中
                xinchuang_status = {0: '尚未启动', 1: '规划中', 2: '部分完成', 3: '基本完成'}
                gaps.append({
                    'dimension': '信创转型进展',
                    'xingye_value': xinchuang_status.get(xingye_xinchuang, '未知'),
                    'benchmark': '行业领先者已基本完成',
                    'gap': '进展较慢',
                    'suggestion': '建议加快信创转型步伐，制定明确的替代路线图'
                })
            
            # 4. AI技术应用
            xingye_ai = xingye_dict.get('c160_高新技术的应用情况', 0)
            if xingye_ai == 0:  # 0表示未应用
                gaps.append({
                    'dimension': 'AI技术应用',
                    'xingye_value': '尚未应用',
                    'benchmark': '行业部分公司已应用AI技术',
                    'gap': '尚未布局',
                    'suggestion': '建议探索AI技术在风控、客服、投研等领域的应用'
                })
            
            # 5. 科技外包占比（如果外包比例过高）
            cursor.execute('SELECT AVG("c36_3_科技外包团队总人数_人") FROM survey_data WHERE "c36_3_科技外包团队总人数_人" IS NOT NULL AND "c36_3_科技外包团队总人数_人" > 0')
            avg_outsource = cursor.fetchone()[0] or 0
            xingye_outsource = xingye_dict.get('c36_3_科技外包团队总人数_人', 0) or 0
            xingye_own = xingye_dict.get('c21_2_自有科技团队总人数', 0) or 0
            
            if xingye_own > 0 and xingye_outsource > 0:
                outsource_ratio = xingye_outsource / (xingye_outsource + xingye_own)
                if outsource_ratio > 0.5:  # 外包占比超过50%
                    gaps.append({
                        'dimension': '科技外包占比',
                        'xingye_value': f"外包占比 {outsource_ratio*100:.1f}%",
                        'benchmark': '建议控制在50%以内',
                        'gap': '外包依赖度较高',
                        'suggestion': '建议逐步提升自有团队能力，降低外包依赖'
                    })
            
            logger.info(f"[工具返回] analyze_xingye_gaps -> 找到 {len(gaps)} 项待提升点")
            
            if not gaps:
                return "兴业信托在各维度表现良好，与行业TOP10水平相当，暂无显著改进空间。"
            
            result = "【兴业信托待提升领域分析】\n\n"
            for i, g in enumerate(gaps, 1):
                result += f"{i}. {g['dimension']}\n"
                result += f"   当前状态: {g['xingye_value']}\n"
                result += f"   对标: {g['benchmark']}\n"
                result += f"   △ {g['gap']}\n"
                result += f"   → 建议: {g['suggestion']}\n\n"
            
            return result
            
    except Exception as e:
        logger.error(f"[工具出错] analyze_xingye_gaps -> 运行异常: {str(e)}")
        return f"分析兴业信托待提升领域时出错: {str(e)}"

