# -*- coding: utf-8 -*-
import os
import sys
import io
import threading

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import json, re, base64
from flask import Flask, request, jsonify, send_from_directory, current_app
from flask_cors import CORS
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import numpy as np

from agent import get_agent_response, get_agent_streaming_response
import logging

# 配置全局日志输出级别和格式
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

# 自动检测static目录
static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
if not os.path.exists(static_dir):
    static_dir = '/workspace/static'
app = Flask(__name__, static_folder=static_dir, static_url_path='')
_cors_origins = [
    origin.strip()
    for origin in os.getenv(
        "TRUST_DATA_CORS_ORIGINS",
        "http://127.0.0.1:5000,http://localhost:5000"
    ).split(",")
    if origin.strip()
]
CORS(app, resources={r"/api/*": {"origins": _cors_origins}})
_analysis_lock = threading.RLock()
_config_lock = threading.RLock()


def _clean_thread_id(thread_id):
    thread_id = str(thread_id or 'user_default')
    cleaned = re.sub(r'[^A-Za-z0-9_.:-]', '_', thread_id)[:120]
    return cleaned or 'user_default'

# agent mode
import asyncio
from flask import Response, stream_with_context

@app.route('/api/chat-agent', methods=['POST'])
def chat_agent():
    """LangGraph Agent 问答接口 (阻塞式)"""
    data = request.get_json(silent=True) or {}
    query = str(data.get('query', ''))
    thread_id = _clean_thread_id(data.get('thread_id', 'user_default'))
    if len(query) > 2000:
        return jsonify({'error': '问题长度不能超过2000字符'}), 400
    
    if not query.strip():
        return jsonify({'error': '请输入问题'}), 400
        
    try:
        # 使用 asyncio.run 在同步视图中运行异步 Agent 逻辑
        response = asyncio.run(get_agent_response(query, thread_id))
        return jsonify({'result': response, 'charts': []})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/chat-agent/stream', methods=['POST'])
def chat_agent_stream():
    """LangGraph Agent 问答接口 (流式 SSE)"""
    data = request.get_json(silent=True) or {}
    query = str(data.get('query', ''))
    thread_id = _clean_thread_id(data.get('thread_id', 'user_default'))
    if len(query) > 2000:
        return jsonify({'error': '问题长度不能超过2000字符'}), 400
    
    if not query.strip():
        return jsonify({'error': '请输入问题'}), 400

    def generate():
        # 在同步环境中运行异步生成器的桥接逻辑
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        gen = get_agent_streaming_response(query, thread_id)
        try:
            while True:
                try:
                    chunk = loop.run_until_complete(gen.__anext__())
                    yield f"data: {json.dumps({'content': chunk})}\n\n"
                except StopAsyncIteration:
                    break
                except Exception as e:
                    yield f"data: {json.dumps({'error': str(e)})}\n\n"
                    break
        finally:
            loop.close()

    return Response(stream_with_context(generate()), mimetype='text/event-stream')

# Load font for Chinese
plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'WenQuanYi Micro Hei', 'Noto Sans CJK SC', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

# Try to find a Chinese font
for fp in fm.findSystemFonts():
    if any(name in fp for name in ['WenQuanYi', 'Noto', 'CJK', 'YaHei', 'SimHei']):
        fm.fontManager.addfont(fp)
        # Note: We don't break so we can find multiple fonts, 
        # but the rcParams list priority will handle selection.

# 自动检测数据文件位置（支持Linux和Windows）
DATA_FILE = None
CHART_DIR = None

# 尝试多个可能的数据文件位置
possible_paths = [
    # 当前目录
    os.path.join(os.path.dirname(os.path.abspath(__file__)), 'survey_data.json'),
    # 上级目录
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'survey_data.json'),
    # 原始Linux路径（兼容）
    '/data/user/work/survey_data.json',
    '/workspace/survey_data.json',
]

for path in possible_paths:
    if os.path.exists(path):
        DATA_FILE = path
        DATA_DIR = os.path.dirname(path)
        CHART_DIR = os.path.join(DATA_DIR, 'charts')
        break

if DATA_FILE is None:
    # 默认使用当前目录
    DATA_DIR = os.path.dirname(os.path.abspath(__file__))
    DATA_FILE = os.path.join(DATA_DIR, 'survey_data.json')
    CHART_DIR = os.path.join(DATA_DIR, 'charts')

os.makedirs(CHART_DIR, exist_ok=True)

print(f"数据文件路径: {DATA_FILE}")
print(f"图表目录: {CHART_DIR}")

# ============ 头部标杆设置规则 ============
HEAD_BENCHMARK_CONFIG = {
    'enabled': True,
    'name': '头部标杆',
    'description': '行业综合科技能力头部信托公司（高端水平对标对象）',
    'criteria': {
        'exclude_companies': ['中航信托', '中融国际信托'],  # 剔除名单
        'min_tech_employees': 10,  # 自有科技人员最低要求
        'min_investment_2026': 3000,  # 2026年投入预算最低要求（万元）
    },
    # 最终确定的10家头部标杆公司（按用户指定）
    'companies': [
        {'name': '中信信托', 'display_name': '中信信托'},
        {'name': '平安信托', 'display_name': '平安信托'},
        {'name': '华润信托', 'display_name': '华润深国投信托'},  # 实际名称为华润信托
        {'name': '建信信托', 'display_name': '建信信托'},
        {'name': '交银信托', 'display_name': '交银国际信托'},  # 实际名称为交银信托
        {'name': '华能贵诚信托', 'display_name': '华能贵诚信托'},
        {'name': '上海信托', 'display_name': '上海信托'},  # 替换昆仑信托（人员不足）
        {'name': '中诚信托', 'display_name': '中诚信托'},
        {'name': '外贸信托', 'display_name': '外贸信托'},
        {'name': '紫金信托', 'display_name': '紫金信托'},
    ]
}

# Load data
with open(DATA_FILE, 'r', encoding='utf-8') as f:
    survey_data = json.load(f)

companies = survey_data['companies']
columns_info = survey_data['columns']
categories_info = survey_data['categories']

# Build a clean column name -> col_index mapping
col_name_to_idx = {v: int(k) for k, v in columns_info.items()}

# Build a simplified column name mapping (remove leading numbers)
simple_col_map = {}
for full_name in columns_info.values():
    simple = re.sub(r'^[\d\(\)\s]+', '', full_name).strip()
    simple = re.sub(r'^[\d\.]+', '', simple).strip()
    if simple:
        simple_col_map[simple] = full_name

# Explicit field mapping for key data fields
FIELD_MAP = {
    '2023年科技投入': '13',
    '2024年科技投入': '14',
    '2025年科技投入': '15',
    '2026年科技投入预算': '16',
    '基础设施建设投入比例': '17',
    '系统开发项目投入比例': '18',
    '其他投入比例': '19',
    '公司员工总人数': '20',
    '自有科技团队总人数': '21',
    '正式员工': '22',
    '派遣员工': '23',
    '借调员工': '24',
    '应用系统建设人数': '25',
    '基础设施运维人数': '26',
    '业务分析与产品人数': '27',
    '嵌入业务式人数': '28',
    '研发质量保障人数': '29',
    '数据管理岗': '30',
    '信息安全岗': '31',
    '科技审计岗': '32',
    '科技风险管理岗': '33',
    '科技外包团队总人数': '36',
    '项目制外包人员': '37',
    '长期驻场人员': '38',
    '开发与测试人数': '39',
    '软件运维人数': '40',
    '基础设施运维外包人数': '41',
    '信息安全外包人数': '42',
    'CIO设立': '65',
    'CIO高级管理层': '66',
    '自研系统比例': '211',
    '合作开发比例': '212',
    '外采系统比例': '213',
    '对客端年度投入': '233',
    'APP投入': '234',
    '小程序投入': '235',
    '其他渠道投入': '236',
}

def get_field_col(field_name):
    """Get column name for a known field"""
    if not field_name:
        return None
    if field_name in columns_info.values():
        return field_name
    idx = FIELD_MAP.get(field_name)
    if idx:
        return columns_info.get(idx)
    return None

def resolve_field_col(field_name):
    """Resolve either a friendly field alias or a raw survey column name."""
    return get_field_col(field_name)

# Build keyword -> column mappings for smart search
keyword_col_map = {}
for full_name in columns_info.values():
    name_clean = full_name
    name_clean = re.sub(r'^[\d\(\)\s\.]+', '', name_clean).strip()
    name_clean = re.sub(r'^[\d\.]+', '', name_clean).strip()
    if name_clean:
        keyword_col_map[name_clean] = full_name
    # Also add partial keywords
    for kw in ['科技投入', '人员', '员工', '科技团队', '外包', 'CIO', '信息科技部',
               '人工智能', 'AI', '大数据', '云原生', '区块链', '信创', '数据治理',
               '数据安全', '数据中台', '业务系统', 'APP', '小程序', '客户服务',
               '数字化', '风控', '合规', '资产管理', '基础设施', '云平台',
               '虚拟化', '公有云', '服务器', '数据库', '中间件', '操作系统',
               '芯片', '认证', '资质', '科技战略', '数字化转型', '数据管理',
               '信息安全', '科技风险', '研发', '测试', '运维', '开发',
               '投入', '预算', '薪酬', '津贴', '奖励', '转岗',
               '估值', '核算', '投资决策', '家族信托', '慈善信托',
               '反洗钱', '监管报送', '档案管理', '人力资源',
               '远程视频', '智能客服', '电子合同', '线上划款',
               'DLP', '防泄露', '风险评估', '数据质量', '数据标准',
               '数据分类', '数据分级', '数据模型', '数据接口']:
        if kw in full_name or kw in name_clean:
            if full_name not in keyword_col_map.get(kw, []):
                if kw not in keyword_col_map:
                    keyword_col_map[kw] = []
                if isinstance(keyword_col_map[kw], list):
                    keyword_col_map[kw].append(full_name)
                else:
                    keyword_col_map[kw] = [keyword_col_map[kw], full_name]


def safe_num(val):
    if val is None:
        return 0
    if isinstance(val, (int, float)):
        return val
    s = str(val).strip().replace(',', '').replace('％', '%').replace('%', '')
    if s in ['(空)', '', '-', 'NaN', 'nan', 'None']:
        return 0
    try:
        return float(s)
    except:
        return 0


def get_col_values(col_name, companies_list=None):
    """Get all values for a column across companies"""
    if companies_list is None:
        companies_list = companies
    vals = []
    for c in companies_list:
        v = c['数据'].get(col_name)
        vals.append(v)
    return vals


def find_columns(query):
    """Find relevant columns based on query keywords"""
    found = []
    query_lower = query.lower()
    # Direct match
    for full_name in columns_info.values():
        if query in full_name or query_lower in full_name.lower():
            found.append(full_name)
    # Keyword match
    for kw, targets in keyword_col_map.items():
        if kw in query or kw.lower() in query_lower:
            if isinstance(targets, list):
                for t in targets:
                    if t not in found:
                        found.append(t)
            elif targets not in found:
                found.append(targets)
    return found


def generate_chart(fig, chart_id):
    """Save figure to file and return base64"""
    buffer = io.BytesIO()
    fig.savefig(buffer, format='png', dpi=120, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    buffer.seek(0)
    b64 = base64.b64encode(buffer.read()).decode()
    return f'data:image/png;base64,{b64}'


def make_bar_chart(labels, values, title, xlabel='', ylabel='', horizontal=False, figsize=(10, 6)):
    fig, ax = plt.subplots(figsize=figsize)
    colors = plt.cm.Set3(np.linspace(0, 1, len(labels)))
    if horizontal:
        bars = ax.barh(range(len(labels)), values, color=colors)
        ax.set_yticks(range(len(labels)))
        ax.set_yticklabels(labels, fontsize=9)
        ax.set_xlabel(ylabel or '数值', fontsize=10)
        for bar, val in zip(bars, values):
            ax.text(bar.get_width() + 0.5, bar.get_y() + bar.get_height()/2,
                    f'{val}', va='center', fontsize=8)
    else:
        bars = ax.bar(range(len(labels)), values, color=colors)
        ax.set_xticks(range(len(labels)))
        ax.set_xticklabels(labels, fontsize=8, rotation=45, ha='right')
        ax.set_ylabel(ylabel or '数值', fontsize=10)
        for bar, val in zip(bars, values):
            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.3,
                    f'{val}', ha='center', fontsize=8)
    ax.set_title(title, fontsize=13, fontweight='bold')
    plt.tight_layout()
    return fig


def make_pie_chart(labels, values, title, figsize=(8, 6)):
    fig, ax = plt.subplots(figsize=figsize)
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
    return fig


# ============ Analysis Functions ============

def analyze_overview():
    """行业概览分析 - 宏观全景总览"""
    total = len(companies)
    total_fields = len(columns_info)
    charts = []
    
    result = f"## 📊 信托行业科技建设整体格局\n\n"
    
    # ==================== 第一部分：样本全景 ====================
    result += "## 📋 样本全景\n\n"
    
    # 公司样本分布
    result += f"**调研样本覆盖**：\n"
    result += f"- 参与调研公司数量：{total} 家\n"
    result += f"- 基础数据字段：{total_fields} 个\n"
    
    # 计算数据完整度
    field_coverage = {}
    for col_name in columns_info.values():
        non_empty = sum(1 for c in companies if c['数据'].get(col_name) is not None and 
                       str(c['数据'].get(col_name)).strip() not in ['(空)', '', 'NaN'])
        field_coverage[col_name] = non_empty / total * 100
    
    # 完整度分布
    high_coverage = sum(1 for v in field_coverage.values() if v >= 80)
    medium_coverage = sum(1 for v in field_coverage.values() if 50 <= v < 80)
    low_coverage = sum(1 for v in field_coverage.values() if v < 50)
    
    result += f"\n**数据字段完整度分布**：\n"
    result += f"- 高完整度（≥80%）：{high_coverage} 个字段 ({high_coverage/total_fields*100:.1f}%)\n"
    result += f"- 中完整度（50-80%）：{medium_coverage} 个字段 ({medium_coverage/total_fields*100:.1f}%)\n"
    result += f"- 低完整度（<50%）：{low_coverage} 个字段 ({low_coverage/total_fields*100:.1f}%)\n"
    result += f"- 行业平均字段完整度：{np.mean(list(field_coverage.values())):.1f}%\n\n"
    
    # ==================== 第二部分：行业整体态势 ====================
    result += "## 🏛️ 行业整体态势\n\n"
    
    # 计算综合得分分布
    col_2024 = get_field_col('2024年科技投入')
    col_tech = get_field_col('自有科技团队总人数')
    col_total = get_field_col('公司员工总人数')
    col_outsource = get_field_col('科技外包团队总人数')
    
    # 科技投入统计
    if col_2024:
        vals_invest = [safe_num(c['数据'].get(col_2024)) for c in companies]
        vals_invest = [v for v in vals_invest if v > 0]
        if vals_invest:
            result += f"**科技投入（2024年，不含薪酬）**：\n"
            result += f"- 行业均值：{np.mean(vals_invest):.0f} 万元\n"
            result += f"- 行业中位数：{np.median(vals_invest):.0f} 万元\n"
            result += f"- 行业最高：{max(vals_invest):.0f} 万元\n"
            result += f"- 行业最低：{min(vals_invest):.0f} 万元\n"
            result += f"- 有效数据：{len(vals_invest)} 家\n\n"
    
    # 科技人员统计
    if col_tech and col_total:
        tech_ratios = []
        for c in companies:
            t = safe_num(c['数据'].get(col_total))
            s = safe_num(c['数据'].get(col_tech))
            if t > 0 and s > 0:
                tech_ratios.append(s / t * 100)
        if tech_ratios:
            result += f"**科技人员占比**：\n"
            result += f"- 行业均值：{np.mean(tech_ratios):.1f}%\n"
            result += f"- 行业中位数：{np.median(tech_ratios):.1f}%\n"
            result += f"- 行业最高：{max(tech_ratios):.1f}%\n\n"
    
    # 科技外包统计
    if col_outsource:
        vals_out = [safe_num(c['数据'].get(col_outsource)) for c in companies]
        vals_out = [v for v in vals_out if v > 0]
        if vals_out:
            result += f"**科技外包团队**：\n"
            result += f"- 使用外包公司：{len(vals_out)} 家\n"
            result += f"- 平均外包人数：{np.mean(vals_out):.0f} 人\n"
            result += f"- 最多外包人数：{max(vals_out)} 人\n\n"
    
    # 发展阶段判定
    result += f"**行业发展阶段判定**：\n"
    
    # 根据科技投入和人员配置判定阶段
    high_invest = 0
    for c in companies:
        inv = safe_num(c['数据'].get(col_2024)) if col_2024 else 0
        tech = safe_num(c['数据'].get(col_tech)) if col_tech else 0
        if inv >= 5000 and tech >= 50:
            high_invest += 1
    
    if high_invest >= 20:
        stage = "📈 深度数字化阶段"
        stage_desc = "头部机构引领，行业整体向数字化纵深发展"
    elif high_invest >= 10:
        stage = "🔄 规范发展阶段"
        stage_desc = "科技治理体系逐步完善，数字化转型加速"
    else:
        stage = "🏗️ 初级建设阶段"
        stage_desc = "科技基础设施初步搭建，数字化转型起步"
    
    result += f"- 当前阶段：**{stage}**\n"
    result += f"- 阶段特征：{stage_desc}\n"
    result += f"- 头部机构（投入≥5000万且科技人员≥50人）：{high_invest} 家\n\n"
    
    # ==================== 第三部分：维度整体得分 ====================
    result += "## 🎯 维度能力雷达总图\n\n"
    
    # 计算各维度平均得分
    dim_cols = {
        '科技战略定位': ['2', '3', '4', '5', '6', '7'],
        '资源投入配置': ['col_2024', 'col_tech', 'col_outsource'],
        '组织架构': ['43', '44', '45', '46', '47', '48', '49'],
        '基础设施': ['106', '111', '112', '113', '114'],
        '信创转型': ['131'],
        '高新技术应用': ['160', '161', '162', '163', '164', '167', '168', '169'],
        '业务系统': ['184', '185', '186', '187', '188', '189', '190', '191', '192', '193', '194', '195'],
        '数据治理': ['238', '239', '240', '241', '242', '243', '254', '255']
    }
    
    dim_scores = {}
    for dim_name, col_list in dim_cols.items():
        scores = []
        for c in companies:
            score = 0
            count = 0
            for col_ref in col_list:
                if col_ref == 'col_2024':
                    col = col_2024
                elif col_ref == 'col_tech':
                    col = col_tech
                elif col_ref == 'col_outsource':
                    col = col_outsource
                else:
                    col = columns_info.get(col_ref)
                
                if col:
                    val = c['数据'].get(col)
                    if val in [1, '1', 2, '2', 3, '3', 4, '4']:
                        score += 1
                    if val is not None and str(val).strip() not in ['(空)', '', 'NaN']:
                        count += 1
                        # 数值型字段处理
                        if isinstance(val, (int, float)) and val > 0:
                            score += 1
            if count > 0:
                scores.append(score / max(count, 1) * 100)
        
        if scores:
            dim_scores[dim_name] = {
                'avg': np.mean(scores),
                'head_avg': np.mean(sorted(scores, reverse=True)[:10]) if len(scores) >= 10 else np.mean(scores),
                'tail_avg': np.mean(sorted(scores)[:10]) if len(scores) >= 10 else np.mean(scores)
            }
    
    # 维度得分表格
    result += "| 维度 | 行业均值 | 头部均值 | 尾部均值 | 长短板 |\n"
    result += "|:---|:---:|:---:|:---:|:---|\n"
    
    long_short = []
    for dim, data in dim_scores.items():
        avg = data['avg']
        head = data['head_avg']
        tail = data['tail_avg']
        
        if avg >= 70:
            level = "🟢 优势"
        elif avg >= 50:
            level = "🟡 一般"
        else:
            level = "🔴 短板"
        long_short.append((dim, avg))
        
        result += f"| {dim} | {avg:.1f} | {head:.1f} | {tail:.1f} | {level} |\n"
    
    result += "\n"
    
    # 生成雷达图
    if dim_scores:
        fig, ax = plt.subplots(figsize=(10, 8), subplot_kw=dict(polar=True))
        dims = list(dim_scores.keys())
        labels = [d[:4] for d in dims]  # 截取前4个字符
        
        angles = np.linspace(0, 2 * np.pi, len(dims), endpoint=False).tolist()
        angles += angles[:1]
        
        # 行业均值
        industry_avg = [dim_scores[d]['avg'] for d in dims] + [dim_scores[dims[0]]['avg']]
        # 头部均值
        head_avg = [dim_scores[d]['head_avg'] for d in dims] + [dim_scores[dims[0]]['head_avg']]
        
        ax.plot(angles, industry_avg, 'o-', linewidth=2, label='行业均值', color='#1976D2')
        ax.fill(angles, industry_avg, alpha=0.15, color='#1976D2')
        ax.plot(angles, head_avg, 's--', linewidth=2, label='头部均值', color='#FF9800')
        ax.fill(angles, head_avg, alpha=0.1, color='#FF9800')
        
        ax.set_xticks(angles[:-1])
        ax.set_xticklabels(labels, fontsize=10)
        ax.set_ylim(0, 100)
        ax.set_title('行业能力雷达总图\n各维度平均得分对比', fontsize=14, fontweight='bold', pad=20)
        ax.legend(loc='upper right', bbox_to_anchor=(1.3, 1.1))
        
        plt.tight_layout()
        charts.append(generate_chart(fig, 'industry_radar'))
    
    # 长短板分析
    sorted_dims = sorted(long_short, key=lambda x: x[1], reverse=True)
    result += "**长短板分析**：\n"
    result += f"- 最强维度：**{sorted_dims[0][0]}**（{sorted_dims[0][1]:.1f}分）\n"
    result += f"- 最弱维度：**{sorted_dims[-1][0]}**（{sorted_dims[-1][1]:.1f}分）\n"
    result += f"- 维度间差距：{sorted_dims[0][1] - sorted_dims[-1][1]:.1f}分\n\n"
    
    return result, charts


def analyze_investment(query):
    """科技投入分析"""
    result = "## 💰 科技投入分析\n\n"

    year_cols = {}
    for y, field in [('2023', '2023年科技投入'), ('2024', '2024年科技投入'),
                     ('2025', '2025年科技投入'), ('2026', '2026年科技投入预算')]:
        col = get_field_col(field)
        if col:
            year_cols[y] = col

    if not year_cols:
        return "未找到科技投入相关数据，请尝试其他问题。", []

    charts = []

    for year, col in sorted(year_cols.items()):
        vals = [(c['公司简称'], safe_num(c['数据'].get(col))) for c in companies]
        vals = [(n, v) for n, v in vals if v > 0]
        if vals:
            vals_sorted = sorted(vals, key=lambda x: x[1], reverse=True)
            result += f"**{year}年科技投入**（有效数据 {len(vals)} 家）：\n"
            result += f"- 平均：{np.mean([v for _, v in vals]):.0f} 万元\n"
            result += f"- 中位数：{np.median([v for _, v in vals]):.0f} 万元\n"
            result += f"- 总计：{sum(v for _, v in vals):.0f} 万元\n"
            result += f"- TOP5：{', '.join([f'{n}({v:.0f}万)' for n, v in vals_sorted[:5]])}\n\n"

    # Top 10 chart for latest year
    latest_year = max(year_cols.keys())
    col = year_cols[latest_year]
    vals = [(c['公司简称'], safe_num(c['数据'].get(col))) for c in companies]
    vals = [(n, v) for n, v in vals if v > 0]
    vals_sorted = sorted(vals, key=lambda x: x[1], reverse=True)[:15]

    if vals_sorted:
        fig = make_bar_chart([n for n, _ in vals_sorted], [v for _, v in vals_sorted],
                             f'{latest_year}年科技投入TOP15（万元）', horizontal=True, figsize=(10, 7))
        charts.append(generate_chart(fig, 'investment_top'))

    # Year-over-year comparison
    if len(year_cols) >= 2:
        sorted_years = sorted(year_cols.keys())
        company_trends = []
        for c in companies:
            trend = {}
            for y in sorted_years:
                v = safe_num(c['数据'].get(year_cols[y]))
                if v > 0:
                    trend[y] = v
            if len(trend) >= 2:
                company_trends.append((c['公司简称'], trend))

        if company_trends:
            result += f"**投入趋势分析**（有连续数据的公司）：\n"
            increases = 0
            decreases = 0
            for name, trend in company_trends:
                years_list = sorted(trend.keys())
                if len(years_list) >= 2:
                    change = (trend[years_list[-1]] - trend[years_list[0]]) / trend[years_list[0]] * 100
                    if change > 0:
                        increases += 1
                    else:
                        decreases += 1
            result += f"- 投入增长：{increases} 家\n"
            result += f"- 投入下降：{decreases} 家\n\n"

    return result, charts


def analyze_personnel(query):
    """人员配置分析"""
    result = "## 👥 人员配置分析\n\n"
    charts = []

    # Total employees
    col_total = get_field_col('公司员工总人数')

    # Tech team
    col_tech = get_field_col('自有科技团队总人数')

    # Outsourcing
    col_outsource = get_field_col('科技外包团队总人数')

    if col_total:
        totals = [(c['公司简称'], safe_num(c['数据'].get(col_total))) for c in companies]
        totals = [(n, v) for n, v in totals if v > 0]
        if totals:
            result += f"**公司员工总数**（有效 {len(totals)} 家）：\n"
            result += f"- 平均：{np.mean([v for _, v in totals]):.0f} 人\n"
            result += f"- 中位数：{np.median([v for _, v in totals]):.0f} 人\n"
            result += f"- 最大：{max(v for _, v in totals)} 人\n"
            result += f"- 最小：{min(v for _, v in totals)} 人\n\n"

    if col_tech:
        techs = [(c['公司简称'], safe_num(c['数据'].get(col_tech))) for c in companies]
        techs = [(n, v) for n, v in techs if v > 0]
        if techs:
            result += f"**自有科技团队**（有效 {len(techs)} 家）：\n"
            result += f"- 平均：{np.mean([v for _, v in techs]):.0f} 人\n"
            result += f"- 中位数：{np.median([v for _, v in techs]):.0f} 人\n"
            result += f"- 最大：{max(v for _, v in techs)} 人\n\n"

    if col_outsource:
        outs = [(c['公司简称'], safe_num(c['数据'].get(col_outsource))) for c in companies]
        outs = [(n, v) for n, v in outs if v > 0]
        if outs:
            result += f"**科技外包团队**（有效 {len(outs)} 家）：\n"
            result += f"- 平均：{np.mean([v for _, v in outs]):.0f} 人\n"
            result += f"- 中位数：{np.median([v for _, v in outs]):.0f} 人\n\n"

    # Tech ratio chart
    if col_total and col_tech:
        ratios = []
        for c in companies:
            t = safe_num(c['数据'].get(col_total))
            s = safe_num(c['数据'].get(col_tech))
            if t > 0 and s > 0:
                ratios.append((c['公司简称'], s/t*100))
        if ratios:
            ratios_sorted = sorted(ratios, key=lambda x: x[1], reverse=True)[:15]
            fig = make_bar_chart([n for n, _ in ratios_sorted], [round(v, 1) for _, v in ratios_sorted],
                                 '科技人员占比TOP15（%）', horizontal=True, figsize=(10, 7))
            charts.append(generate_chart(fig, 'tech_ratio'))

    # Function distribution
    func_cols = {}
    for c_name in columns_info.values():
        for func in ['应用系统建设', '基础设施运维', '业务分析与产品', '嵌入业务式', '研发质量保障']:
            if func in c_name and '职能' not in c_name and '按职能' not in c_name:
                func_cols[func] = c_name

    if func_cols:
        func_totals = {}
        for func, col in func_cols.items():
            total = sum(safe_num(c['数据'].get(col)) for c in companies)
            func_totals[func] = total
        result += "**科技人员职能分布**（全行业合计）：\n"
        for func, total in sorted(func_totals.items(), key=lambda x: x[1], reverse=True):
            result += f"- {func}：{total} 人\n"
        result += "\n"

        fig = make_pie_chart(list(func_totals.keys()), list(func_totals.values()),
                             '科技人员职能分布')
        if fig:
            charts.append(generate_chart(fig, 'func_dist'))

    return result, charts


def compare_companies(query):
    """公司对比分析"""
    # Extract company names from query
    all_names = [c['公司简称'] for c in companies]
    found_companies = [name for name in all_names if name in query]

    if len(found_companies) < 2:
        return f"请在问题中提及至少2家信托公司名称进行对比。当前识别到：{', '.join(found_companies) if found_companies else '无'}。\n\n可用的公司名称示例：爱建信托、中信信托、平安信托、华润信托等。", []

    result = f"## 📋 公司对比分析：{' vs '.join(found_companies)}\n\n"
    charts = []

    # Compare key metrics
    metrics = {}

    # 科技投入
    for y, field in [('2023', '2023年科技投入'), ('2024', '2024年科技投入'), ('2025', '2025年科技投入')]:
        col = get_field_col(field)
        if col:
            metrics[f'{y}年科技投入(万元)'] = col

    # 人员
    for field, label in [('公司员工总人数', '员工总数'), ('自有科技团队总人数', '科技团队人数'),
                         ('科技外包团队总人数', '外包团队人数')]:
        col = get_field_col(field)
        if col:
            metrics[label] = col

    # Build comparison table
    table_data = {}
    for metric_name, col in metrics.items():
        for comp_name in found_companies:
            comp = next((c for c in companies if c['公司简称'] == comp_name), None)
            if comp:
                val = comp['数据'].get(col)
                if metric_name not in table_data:
                    table_data[metric_name] = {}
                table_data[metric_name][comp_name] = safe_num(val) if val is not None else 'N/A'

    # Render table
    if table_data:
        header = '| 指标 | ' + ' | '.join(found_companies) + ' |'
        separator = '|---' * (len(found_companies) + 1) + '|'
        result += header + '\n' + separator + '\n'
        for metric, vals in table_data.items():
            row = f'| {metric} | ' + ' | '.join([str(v) for v in vals.values()]) + ' |'
            result += row + '\n'
        result += '\n'

    # Radar chart comparison
    radar_metrics = {}
    for metric_name, col in metrics.items():
        radar_metrics[metric_name] = col

    if len(radar_metrics) >= 3:
        fig, ax = plt.subplots(figsize=(8, 8), subplot_kw=dict(polar=True))
        labels = list(radar_metrics.keys())
        num_vars = len(labels)
        angles = np.linspace(0, 2 * np.pi, num_vars, endpoint=False).tolist()
        angles += angles[:1]

        colors_list = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd']
        for idx, comp_name in enumerate(found_companies):
            comp = next((c for c in companies if c['公司简称'] == comp_name), None)
            if comp:
                values = []
                for col in radar_metrics.values():
                    values.append(safe_num(comp['数据'].get(col)))
                # Normalize
                max_vals = []
                for col in radar_metrics.values():
                    all_v = [safe_num(c['数据'].get(col)) for c in companies]
                    max_vals.append(max(all_v) if max(all_v) > 0 else 1)
                norm_values = [v/m*100 if m > 0 else 0 for v, m in zip(values, max_vals)]
                norm_values += norm_values[:1]
                ax.plot(angles, norm_values, 'o-', linewidth=2, label=comp_name, color=colors_list[idx % len(colors_list)])
                ax.fill(angles, norm_values, alpha=0.1, color=colors_list[idx % len(colors_list)])

        ax.set_xticks(angles[:-1])
        ax.set_xticklabels(labels, fontsize=9)
        ax.set_title('公司综合能力对比', fontsize=14, fontweight='bold', pad=20)
        ax.legend(loc='upper right', bbox_to_anchor=(1.3, 1))
        plt.tight_layout()
        charts.append(generate_chart(fig, 'company_compare'))

    return result, charts


def analyze_ranking(query):
    """排名分析"""
    result = "## 🏆 排名分析\n\n"

    # Determine what to rank by
    rank_col = None
    rank_metric = ''

    metric_keywords = {
        '科技投入': ['2023年科技投入', '2024年科技投入', '2025年科技投入'],
        '员工总数': ['公司员工总人数'],
        '科技团队': ['自有科技团队总人数'],
        '外包团队': ['科技外包团队总人数'],
        '科技人员占比': None,
    }

    for metric, field_names in metric_keywords.items():
        if metric in query:
            if field_names is None:
                rank_metric = metric
            else:
                for field in field_names:
                    col = get_field_col(field)
                    if col:
                        rank_col = col
                        rank_metric = metric
                        break
            break

    if not rank_col and rank_metric != '科技人员占比':
        # Default: use latest year investment
        for field in ['2025年科技投入', '2024年科技投入', '2023年科技投入']:
            col = get_field_col(field)
            if col:
                rank_col = col
                rank_metric = field.replace('年科技投入', '') + '年科技投入'
                break

    if rank_metric == '科技人员占比':
        col_total = get_field_col('公司员工总人数')
        col_tech = get_field_col('自有科技团队总人数')
        if col_total and col_tech:
            rankings = []
            for c in companies:
                t = safe_num(c['数据'].get(col_total))
                s = safe_num(c['数据'].get(col_tech))
                if t > 0 and s > 0:
                    rankings.append((c['公司简称'], round(s/t*100, 2)))
            rankings.sort(key=lambda x: x[1], reverse=True)
        else:
            return "无法计算科技人员占比。", []
    elif rank_col:
        rankings = []
        for c in companies:
            v = safe_num(c['数据'].get(rank_col))
            if v > 0:
                rankings.append((c['公司简称'], v))
        rankings.sort(key=lambda x: x[1], reverse=True)
    else:
        return '请指定排名指标，如《科技投入排名》、《员工总数排名》等。', []

    if not rankings:
        return f"未找到足够的有效数据来进行{rank_metric}排名。", []

    # Determine top N
    top_n = 20
    n_match = re.search(r'前\s*(\d+)', query)
    if n_match:
        top_n = int(n_match.group(1))
    top_n = min(top_n, len(rankings))

    result += f"**{rank_metric}排名 TOP{top_n}**（共 {len(rankings)} 家有效数据）：\n\n"
    result += '| 排名 | 公司 | 数值 |\n|---|---|---|\n'
    for i, (name, val) in enumerate(rankings[:top_n]):
        medal = ['🥇', '🥈', '🥉'][i] if i < 3 else f'{i+1}'
        unit = '%' if '占比' in rank_metric else ('万元' if '投入' in rank_metric else ('人' if '人' in rank_metric else ''))
        result += f'| {medal} | {name} | {val}{unit} |\n'

    result += '\n'

    # Chart
    chart_data = rankings[:top_n]
    fig = make_bar_chart([n for n, _ in chart_data], [v for _, v in chart_data],
                         f'{rank_metric}排名TOP{top_n}', horizontal=True, figsize=(10, 8))
    charts = [generate_chart(fig, f'ranking_{rank_metric}')]
    return result, charts


def analyze_proportion(query):
    """占比分析"""
    result = "## 📈 占比分析\n\n"
    charts = []

    # Find binary columns (0/1) for proportion analysis
    binary_cols = []
    for c_name in columns_info.values():
        vals = [c['数据'].get(c_name) for c in companies]
        vals_clean = [v for v in vals if v is not None and str(v).strip() not in ['(空)', '', 'NaN']]
        if vals_clean and all(str(v).strip() in ['0', '1', '2', '3', '4', '5'] for v in vals_clean):
            binary_cols.append(c_name)

    # Find relevant binary columns based on query
    relevant_cols = []
    query_lower = query.lower()

    # Check for specific topics
    topic_keywords = {
        '战略': ['金融科技发展战略', '数字化转型发展战略', '科技外包战略', '数据治理战略'],
        'AI': ['人工智能'],
        '大数据': ['大数据'],
        '云原生': ['云原生'],
        '区块链': ['区块链'],
        '信创': ['信创'],
        '系统': ['资产管理业务系统', '标品投资交易系统', '数据平台', '监管报送系统'],
        'APP': ['移动APP'],
        '小程序': ['微信小程序'],
        '智能客服': ['智能客服'],
        '电子合同': ['电子合同'],
        '数据中台': ['数据中台'],
        'CIO': ['首席信息官CIO'],
        '认证': ['ISO/IEC 27001', 'CMMI', 'DCMM'],
    }

    matched_topic = None
    for topic, keywords in topic_keywords.items():
        if topic in query or topic.lower() in query_lower:
            matched_topic = topic
            for kw in keywords:
                for col in binary_cols:
                    if kw in col:
                        relevant_cols.append(col)
            break

    if not matched_topic:
        # General search
        for col in binary_cols:
            for kw in query:
                if kw in col:
                    relevant_cols.append(col)
                    break

    # If still no match, show general adoption overview
    if not relevant_cols:
        # Show a general overview of key technology adoptions
        key_items = {
            '金融科技发展战略': '金融科技发展战略',
            '数字化转型战略': '数字化转型发展战略',
            '数据治理战略': '数据治理战略',
            '人工智能应用': None,  # special handling
            '大数据应用': None,
            '云原生应用': None,
            '区块链应用': None,
            '数据中台': '企业级数据中台',
            'CIO设立': '首席信息官CIO',
            '移动APP': '移动APP',
            '智能客服': '智能客服',
            '电子合同': '电子合同',
        }

        for label, keyword in key_items.items():
            if keyword:
                for col in binary_cols:
                    if keyword in col:
                        vals = [c['数据'].get(col) for c in companies]
                        yes = sum(1 for v in vals if v in [1, '1', 2, '2'])
                        pct = yes / len(companies) * 100
                        result += f"- **{label}**：{yes}/{len(companies)} 家 ({pct:.1f}%)\n"

        result += '\n💡 提示：您可以询问更具体的问题，例如：\n'
        result += '- "有多少家公司部署了人工智能？"\n'
        result += '- "信创转型的进展如何？"\n'
        result += '- "哪些公司有数据中台？"\n'

        # Pie chart for general overview
        if result.count('\n- ') > 3:
            return result, []

        return result, []

    # Analyze specific topic
    for col in relevant_cols:
        col_label = re.sub(r'^[\d\(\)\s\.]+', '', col).strip()
        vals = [c['数据'].get(col) for c in companies]
        yes = sum(1 for v in vals if v in [1, '1', 2, '2'])
        no = sum(1 for v in vals if v in [0, '0'])
        other = len(vals) - yes - no
        pct = yes / len(companies) * 100

        result += f"**{col_label}**：\n"
        result += f"- 已采纳：{yes} 家 ({pct:.1f}%)\n"
        result += f"- 未采纳：{no} 家\n"
        if other > 0:
            result += f"- 其他/未填报：{other} 家\n"

        # List companies that adopted
        adopted = [c['公司简称'] for c in companies if c['数据'].get(col) in [1, '1', 2, '2']]
        if adopted:
            result += f"- 已采纳的公司：{', '.join(adopted)}\n"
        result += '\n'

        # Pie chart
        fig = make_pie_chart(['已采纳', '未采纳'], [yes, no], f'{col_label}采纳情况')
        if fig:
            charts.append(generate_chart(fig, f'prop_{hash(col) % 10000}'))

    return result, charts


def analyze_tech(query):
    """高新技术应用分析"""
    result = "## 🔬 高新技术应用分析\n\n"
    charts = []

    tech_areas = {
        '人工智能': {
            'cols': ['智能风控与合规', '客户服务与营销', '智能运营与内部管理',
                     '投资与资产管理', '科技研发增效与管理', '暂无投产'],
            'keyword': '人工智能'
        },
        '大数据': {
            'cols': ['客户洞察与精准营销', '风险管理与合规控制', '监管报送与数据治理',
                     '投资研究与资产配置', '内部运营优化', '经营分析与决策支持', '尚无实质性应用'],
            'keyword': '大数据'
        },
        '云原生': {
            'cols': ['核心系统已规模化应用', '局部业务试点应用', '技术研究与方案规划中', '暂未涉及'],
            'keyword': '云原生'
        },
        '区块链': {
            'cols': ['已有生产级应用', '处于概念验证阶段', '仍在研究评估中', '暂未涉及'],
            'keyword': '区块链'
        }
    }

    target_tech = None
    for tech_name in tech_areas:
        if tech_name in query or tech_name.lower() in query.lower():
            target_tech = tech_name
            break

    if 'AI' in query.upper():
        target_tech = '人工智能'

    if not target_tech:
        # Show all tech overview
        for tech_name, info in tech_areas.items():
            # Find matching columns
            matched_cols = []
            for col in columns_info.values():
                if info['keyword'] in col:
                    for sub_kw in info['cols']:
                        if sub_kw in col:
                            matched_cols.append((sub_kw, col))
                            break

            if matched_cols:
                result += f"### {tech_name}\n"
                for sub_name, col in matched_cols:
                    vals = [c['数据'].get(col) for c in companies]
                    yes = sum(1 for v in vals if v in [1, '1', 2, '2'])
                    result += f"- {sub_name}：{yes} 家\n"
                result += '\n'

        # Summary chart
        tech_summary = {}
        for tech_name, info in tech_areas.items():
            matched_cols = []
            for col in columns_info.values():
                if info['keyword'] in col:
                    for sub_kw in info['cols']:
                        if sub_kw in col and sub_kw not in ['暂无投产', '尚无实质性应用', '暂未涉及']:
                            matched_cols.append(col)
                            break
            # Count companies with at least one application
            applied = 0
            for c in companies:
                has_any = False
                for col in matched_cols:
                    if c['数据'].get(col) in [1, '1', 2, '2']:
                        has_any = True
                        break
                if has_any:
                    applied += 1
            tech_summary[tech_name] = applied

        if tech_summary:
            fig = make_bar_chart(list(tech_summary.keys()), list(tech_summary.values()),
                                 '各技术领域应用情况（已有应用的公司数）', figsize=(9, 5))
            charts.append(generate_chart(fig, 'tech_overview'))

        result += '\n💡 您可以进一步询问具体技术领域，如"人工智能应用详情"、"大数据应用了哪些场景"等。'
        return result, charts

    # Detailed analysis for specific tech
    info = tech_areas[target_tech]
    matched_cols = []
    for col in columns_info.values():
        if info['keyword'] in col:
            for sub_kw in info['cols']:
                if sub_kw in col:
                    matched_cols.append((sub_kw, col))
                    break

    if not matched_cols:
        return f"未找到{target_tech}相关数据。", []

    result += f"### {target_tech}应用详情\n\n"

    for sub_name, col in matched_cols:
        vals = [c['数据'].get(col) for c in companies]
        yes = sum(1 for v in vals if v in [1, '1', 2, '2'])
        pct = yes / len(companies) * 100
        result += f"**{sub_name}**：{yes} 家 ({pct:.1f}%)\n"
        adopted = [c['公司简称'] for c in companies if c['数据'].get(col) in [1, '1', 2, '2']]
        if adopted:
            result += f"  - 代表公司：{', '.join(adopted[:10])}"
            if len(adopted) > 10:
                result += f" 等{len(adopted)}家"
            result += '\n'
        result += '\n'

    # Chart
    labels = [m[0] for m in matched_cols]
    values = []
    for _, col in matched_cols:
        vals = [c['数据'].get(col) for c in companies]
        yes = sum(1 for v in vals if v in [1, '1', 2, '2'])
        values.append(yes)

    fig = make_bar_chart(labels, values, f'{target_tech}各应用场景分布（公司数）', figsize=(10, 5))
    charts.append(generate_chart(fig, f'tech_{target_tech}'))

    return result, charts


def analyze_data_governance(query):
    """数据治理分析"""
    result = "## 🗄️ 数据治理分析\n\n"
    charts = []

    gov_cols = {}
    for c_name in columns_info.values():
        for kw in ['数据中台', '数据质量管理', '数据接口标准化', '数据分类分级',
                    '数据敏感性', '统一数据模型', '数据标准', '数据治理规章制度',
                    '数据质量监控', '数据认责']:
            if kw in c_name:
                if kw not in gov_cols:
                    gov_cols[kw] = []
                gov_cols[kw].append(c_name)

    if not gov_cols:
        return "未找到数据治理相关数据。", []

    for kw, cols in gov_cols.items():
        for col in cols:
            col_label = re.sub(r'^[\d\(\)\s\.]+', '', col).strip()
            vals = [c['数据'].get(col) for c in companies]
            # Handle multi-level values
            val_counts = {}
            for v in vals:
                if v is not None and str(v).strip() not in ['(空)', '', 'NaN']:
                    val_counts[str(v)] = val_counts.get(str(v), 0) + 1

            result += f"**{col_label}**：\n"
            for val, count in sorted(val_counts.items(), key=lambda x: x[1], reverse=True):
                result += f"  - {val}：{count} 家\n"
            result += '\n'

    # Data governance maturity summary
    maturity_cols = []
    for c_name in columns_info.values():
        if '数据质量管理' in c_name and '现状' in c_name:
            maturity_cols.append(c_name)
        if '数据接口标准化' in c_name:
            maturity_cols.append(c_name)
        if '数据分类分级标准' in c_name:
            maturity_cols.append(c_name)

    if maturity_cols:
        fig, axes = plt.subplots(1, min(len(maturity_cols), 3), figsize=(15, 5))
        if len(maturity_cols) == 1:
            axes = [axes]

        for idx, col in enumerate(maturity_cols[:3]):
            ax = axes[idx]
            col_label = re.sub(r'^[\d\(\)\s\.]+', '', col).strip()
            col_label = col_label[:15] + '...' if len(col_label) > 15 else col_label
            vals = [c['数据'].get(col) for c in companies]
            val_counts = {}
            for v in vals:
                if v is not None and str(v).strip() not in ['(空)', '', 'NaN']:
                    val_counts[str(v)] = val_counts.get(str(v), 0) + 1
            if val_counts:
                labels = list(val_counts.keys())
                values = list(val_counts.values())
                ax.bar(range(len(labels)), values, color=plt.cm.Set3(np.linspace(0, 1, len(labels))))
                ax.set_xticks(range(len(labels)))
                ax.set_xticklabels(labels, fontsize=8, rotation=30, ha='right')
                ax.set_title(col_label, fontsize=10)
                for i, v in enumerate(values):
                    ax.text(i, v + 0.3, str(v), ha='center', fontsize=9)

        plt.suptitle('数据治理关键指标分布', fontsize=14, fontweight='bold')
        plt.tight_layout()
        charts.append(generate_chart(fig, 'data_governance'))

    return result, charts


def analyze_xinchuang(query):
    """信创分析"""
    result = "## 🖥️ 信创转型分析\n\n"
    charts = []

    # 信创进展
    progress_col = None
    for c_name in columns_info.values():
        if '信创' in c_name and '进展' in c_name:
            progress_col = c_name
            break

    if progress_col:
        vals = [c['数据'].get(progress_col) for c in companies]
        val_counts = {}
        for v in vals:
            if v is not None and str(v).strip() not in ['(空)', '', 'NaN']:
                val_counts[str(v)] = val_counts.get(str(v), 0) + 1
        result += "**信创进展分布**：\n"
        for val, count in sorted(val_counts.items()):
            result += f"- {val}：{count} 家\n"
        result += '\n'

        fig = make_pie_chart(list(val_counts.keys()), list(val_counts.values()),
                             '信创进展分布')
        if fig:
            charts.append(generate_chart(fig, 'xinchuang_progress'))

    # 信创品牌偏好
    brand_categories = {
        '芯片': ['飞腾', '鲲鹏', '海光', '龙芯'],
        '服务器': ['华为', '新华三', '浪潮', '中科曙光', '联想'],
        '操作系统': ['麒麟软件', '统信软件', '中科方德', '华为欧拉'],
        '数据库': ['达梦', '人大金仓', '神舟通用', '南大通用', '华为高斯'],
        '中间件': ['东方通', '中创软件', '金蝶天燕'],
    }

    for category, brands in brand_categories.items():
        brand_counts = {}
        for brand in brands:
            for c_name in columns_info.values():
                if brand in c_name and '信创' in c_name:
                    count = sum(1 for c in companies if c['数据'].get(c_name) in [1, '1', 2, '2'])
                    if count > 0:
                        brand_counts[brand] = count
                    break

        if brand_counts:
            result += f"**{category}品牌选择**：\n"
            for brand, count in sorted(brand_counts.items(), key=lambda x: x[1], reverse=True):
                result += f"- {brand}：{count} 家\n"
            result += '\n'

            fig = make_bar_chart(list(brand_counts.keys()), list(brand_counts.values()),
                                 f'信创{category}品牌选择（公司数）', figsize=(9, 5))
            charts.append(generate_chart(fig, f'xinchuang_{category}'))

    return result, charts


def analyze_system(query):
    """业务系统分析"""
    result = "## 💻 业务应用系统分析\n\n"
    charts = []

    system_cols = []
    for c_name in columns_info.values():
        if '已投入使用的信息系统' in c_name or any(
            kw in c_name for kw in ['资产管理业务系统', '标品投资交易系统', '非标债权管理系统',
                                     '产品估值与核算系统', '投资决策支持系统', '家族信托管理系统',
                                     '保险金信托管理系统', '家庭服务信托管理系统', '企业财富服务信托管理系统',
                                     '预付类资金服务信托管理系统', '个人财富服务信托系统',
                                     '资管产品受托服务系统', '企业年金受托服务系统',
                                     '担保品受托服务信托系统', '资产证券化服务信托系统',
                                     '风险处置服务信托系统', '慈善信托管理系统', '公益信托管理系统',
                                     '统一客户管理系统', '信托项目管理系统', '合规管理系统',
                                     '反洗钱系统', '数据平台', '接口管理平台', '监管报送系统',
                                     '业务档案管理系统', '人力资源管理系统']):
            if '已投入使用' not in c_name or '信息系统包括' in c_name:
                system_cols.append(c_name)

    # Deduplicate
    seen = set()
    unique_cols = []
    for col in system_cols:
        label = re.sub(r'^[\d\(\)\s\.]+', '', col).strip()
        if label and label not in seen:
            seen.add(label)
            unique_cols.append((label, col))

    system_adoption = {}
    for label, col in unique_cols:
        vals = [c['数据'].get(col) for c in companies]
        yes = sum(1 for v in vals if v in [1, '1', 2, '2'])
        system_adoption[label] = yes

    # Sort by adoption
    sorted_systems = sorted(system_adoption.items(), key=lambda x: x[1], reverse=True)

    result += f"**各系统部署情况**（共 {len(sorted_systems)} 类系统）：\n\n"
    result += '| 排名 | 系统名称 | 已部署家数 | 覆盖率 |\n|---|---|---|---|\n'
    for i, (name, count) in enumerate(sorted_systems):
        pct = count / len(companies) * 100
        result += f'| {i+1} | {name} | {count} | {pct:.1f}% |\n'

    result += '\n'

    # Chart
    top_systems = sorted_systems[:20]
    fig = make_bar_chart([n for n, _ in top_systems], [v for _, v in top_systems],
                         '业务系统部署情况TOP20（公司数）', horizontal=True, figsize=(10, 8))
    charts.append(generate_chart(fig, 'systems_adoption'))

    return result, charts


def analyze_digital_channel(query):
    """数字化渠道分析"""
    result = "## 📱 数字化客户服务渠道分析\n\n"
    charts = []

    channel_cols = {}
    for c_name in columns_info.values():
        for kw in ['移动APP', '微信小程序', '公众号服务', '网站']:
            if kw in c_name and '数字化' in c_name:
                channel_cols[kw] = c_name

    func_cols = {}
    for c_name in columns_info.values():
        for kw in ['远程视频面签', '智能双录', '智能客服', '电子合同', '线上划款']:
            if kw in c_name and '数字化' in c_name:
                func_cols[kw] = c_name

    if channel_cols:
        result += "**渠道覆盖**：\n"
        channel_data = {}
        for label, col in channel_cols.items():
            vals = [c['数据'].get(col) for c in companies]
            yes = sum(1 for v in vals if v in [1, '1', 2, '2'])
            channel_data[label] = yes
            result += f"- {label}：{yes}/{len(companies)} 家 ({yes/len(companies)*100:.1f}%)\n"
        result += '\n'

        fig = make_bar_chart(list(channel_data.keys()), list(channel_data.values()),
                             '数字化渠道覆盖情况', figsize=(8, 5))
        charts.append(generate_chart(fig, 'digital_channels'))

    if func_cols:
        result += "**功能覆盖**：\n"
        func_data = {}
        for label, col in func_cols.items():
            vals = [c['数据'].get(col) for c in companies]
            yes = sum(1 for v in vals if v in [1, '1', 2, '2'])
            func_data[label] = yes
            result += f"- {label}：{yes}/{len(companies)} 家 ({yes/len(companies)*100:.1f}%)\n"
        result += '\n'

        fig = make_bar_chart(list(func_data.keys()), list(func_data.values()),
                             '数字化服务功能覆盖情况', figsize=(9, 5))
        charts.append(generate_chart(fig, 'digital_functions'))

    return result, charts


def analyze_org(query):
    """组织架构分析"""
    result = "## 🏢 组织架构与治理分析\n\n"
    charts = []

    # 治理机构
    gov_cols = {}
    for c_name in columns_info.values():
        for kw in ['信息科技管理委员会', '数字化转型战略委员会', '信息科技风险管理委员会',
                    '业务连续性管理委员会', '数据管理委员会', '网络安全与信息化委员会',
                    '金融科技与创新委员会']:
            if kw in c_name and '是否已设立' not in c_name:
                gov_cols[kw] = c_name

    if gov_cols:
        result += "**治理机构设立情况**：\n"
        gov_data = {}
        for label, col in gov_cols.items():
            vals = [c['数据'].get(col) for c in companies]
            yes = sum(1 for v in vals if v in [1, '1', 2, '2'])
            gov_data[label] = yes
            result += f"- {label}：{yes}/{len(companies)} 家 ({yes/len(companies)*100:.1f}%)\n"
        result += '\n'

        fig = make_bar_chart(list(gov_data.keys()), list(gov_data.values()),
                             '治理机构设立情况', figsize=(12, 5))
        plt.xticks(rotation=30, ha='right')
        charts.append(generate_chart(fig, 'gov_committees'))

    # 科技部门
    dept_cols = {}
    for c_name in columns_info.values():
        for kw in ['信息科技部', '数字金融部', '数据管理部', '信息安全部', '科技风险管理部']:
            if kw in c_name and '已设立' not in c_name and '独立的科技团队' not in c_name:
                dept_cols[kw] = c_name

    if dept_cols:
        result += "**独立科技部门设立**：\n"
        dept_data = {}
        for label, col in dept_cols.items():
            vals = [c['数据'].get(col) for c in companies]
            yes = sum(1 for v in vals if v in [1, '1', 2, '2'])
            dept_data[label] = yes
            result += f"- {label}：{yes}/{len(companies)} 家 ({yes/len(companies)*100:.1f}%)\n"
        result += '\n'

    # CIO
    cio_col = None
    cio_senior_col = None
    for c_name in columns_info.values():
        if '首席信息官CIO' in c_name and '高级管理层' not in c_name:
            cio_col = c_name
        if '高级管理层成员' in c_name:
            cio_senior_col = c_name

    if cio_col:
        vals = [c['数据'].get(cio_col) for c in companies]
        yes = sum(1 for v in vals if v in [1, '1', 2, '2'])
        result += f"**CIO设立**：{yes}/{len(companies)} 家 ({yes/len(companies)*100:.1f}%)\n"
        if cio_senior_col:
            senior_vals = [c['数据'].get(cio_senior_col) for c in companies
                          if c['数据'].get(cio_col) in [1, '1', 2, '2']]
            senior_yes = sum(1 for v in senior_vals if v in [1, '1', 2, '2'])
            result += f"  - 其中为高级管理层成员：{senior_yes}/{yes} 家\n"
        result += '\n'

    # Decision model
    decision_cols = {}
    for c_name in columns_info.values():
        for kw in ['战略集中型', '科技主导型', '业务驱动型', '分层授权型']:
            if kw in c_name and '决策' in c_name:
                decision_cols[kw] = c_name

    if decision_cols:
        result += "**科技项目决策模式**：\n"
        for label, col in decision_cols.items():
            vals = [c['数据'].get(col) for c in companies]
            yes = sum(1 for v in vals if v in [1, '1', 2, '2'])
            result += f"- {label}：{yes} 家\n"
        result += '\n'

    return result, charts


def analyze_infrastructure(query):
    """基础设施分析"""
    result = "## 🏗️ 基础设施分析\n\n"
    charts = []

    # Infrastructure architecture
    arch_col = None
    for c_name in columns_info.values():
        if '当前基础设施架构模式' in c_name:
            arch_col = c_name
            break

    if arch_col:
        vals = [c['数据'].get(arch_col) for c in companies]
        val_counts = {}
        for v in vals:
            if v is not None and str(v).strip() not in ['(空)', '', 'NaN']:
                val_counts[str(v)] = val_counts.get(str(v), 0) + 1
        result += "**基础设施架构模式**：\n"
        for val, count in sorted(val_counts.items(), key=lambda x: x[1], reverse=True):
            result += f"- {val}：{count} 家\n"
        result += '\n'

        fig = make_pie_chart(list(val_counts.keys()), list(val_counts.values()),
                             '基础设施架构模式分布')
        if fig:
            charts.append(generate_chart(fig, 'infra_arch'))

    # Virtualization
    virt_cols = {}
    for c_name in columns_info.values():
        for kw in ['VMware VSphere', '华为 FusionSphere', '深信服 HCI']:
            if kw in c_name and '虚拟化' in c_name:
                virt_cols[kw] = c_name

    if virt_cols:
        result += "**服务器虚拟化/云平台**：\n"
        virt_data = {}
        for label, col in virt_cols.items():
            vals = [c['数据'].get(col) for c in companies]
            yes = sum(1 for v in vals if v in [1, '1', 2, '2'])
            virt_data[label] = yes
            result += f"- {label}：{yes} 家\n"
        result += '\n'

    # Public cloud
    cloud_cols = {}
    for c_name in columns_info.values():
        for kw in ['阿里云', '腾讯云', '华为云', '移动云', '天翼云', '联通云']:
            if kw in c_name and '公有云' in c_name:
                cloud_cols[kw] = c_name

    if cloud_cols:
        result += "**公有云平台使用**：\n"
        cloud_data = {}
        for label, col in cloud_cols.items():
            vals = [c['数据'].get(col) for c in companies]
            yes = sum(1 for v in vals if v in [1, '1', 2, '2'])
            cloud_data[label] = yes
            result += f"- {label}：{yes} 家\n"
        result += '\n'

        if cloud_data:
            fig = make_bar_chart(list(cloud_data.keys()), list(cloud_data.values()),
                                 '公有云平台使用情况', figsize=(9, 5))
            charts.append(generate_chart(fig, 'public_cloud'))

    return result, charts


def analyze_company_detail(query):
    """单家公司详情分析"""
    target = None
    for c in companies:
        if c['公司简称'] in query:
            target = c
            break

    if not target:
        return None, []

    name = target['公司简称']
    data = target['数据']
    result = f"## 📊 {name} 科技建设详情\n\n"

    # Key metrics
    key_metrics = {}
    for field, label in [('2023年科技投入', '2023年科技投入'), ('2024年科技投入', '2024年科技投入'),
                         ('2025年科技投入', '2025年科技投入'), ('公司员工总人数', '员工总数'),
                         ('自有科技团队总人数', '科技团队人数'), ('科技外包团队总人数', '外包团队人数')]:
        col = get_field_col(field)
        if col:
            key_metrics[label] = data.get(col)

    result += "**核心指标**：\n\n"
    result += '| 指标 | 数值 |\n|---|---|\n'
    for metric, val in key_metrics.items():
        if val is not None and str(val).strip() not in ['(空)', '', 'NaN']:
            unit = '万元' if '投入' in metric else '人'
            result += f'| {metric} | {val} {unit} |\n'
    result += '\n'

    # Strategy
    result += "**战略规划**：\n"
    strategies = ['金融科技发展战略', '数字化转型发展战略', '科技外包战略', '数据治理战略',
                  '信息安全整体规划', '人工智能规划']
    for s in strategies:
        for c_name in columns_info.values():
            if s in c_name:
                v = data.get(c_name)
                if v in [1, '1', 2, '2']:
                    result += f"- ✅ 已制定{s}\n"
                else:
                    result += f"- ❌ 未制定{s}\n"
                break
    result += '\n'

    # CIO
    for c_name in columns_info.values():
        if '首席信息官CIO' in c_name and '高级管理层' not in c_name:
            v = data.get(c_name)
            if v in [1, '1', 2, '2']:
                result += "- ✅ 已设立CIO\n"
            else:
                result += "- ❌ 未设立CIO\n"
            break

    # Key systems
    result += "\n**主要信息系统**：\n"
    key_systems = ['资产管理业务系统', '标品投资交易系统', '数据平台', '监管报送系统',
                   '统一客户管理系统', '反洗钱系统', '合规管理系统']
    for sys_name in key_systems:
        for c_name in columns_info.values():
            if sys_name in c_name:
                v = data.get(c_name)
                if v in [1, '1', 2, '2']:
                    result += f"- ✅ {sys_name}\n"
                break

    return result, []


def analyze_certification(query):
    """认证资质分析"""
    result = "## 📜 认证与资质分析\n\n"
    charts = []

    cert_cols = {}
    for c_name in columns_info.values():
        for kw in ['ISO/IEC 27001', 'ISO/IEC 9001', 'ITSS', 'CMMI', 'CSMM', 'DCMM', 'DSMM']:
            if kw in c_name and '科技专项认证' in c_name:
                cert_cols[kw] = c_name

    if cert_cols:
        result += "**科技专项认证**：\n"
        cert_data = {}
        for label, col in cert_cols.items():
            vals = [c['数据'].get(col) for c in companies]
            yes = sum(1 for v in vals if v in [1, '1', 2, '2'])
            cert_data[label] = yes
            result += f"- {label}：{yes}/{len(companies)} 家 ({yes/len(companies)*100:.1f}%)\n"
        result += '\n'

        fig = make_bar_chart(list(cert_data.keys()), list(cert_data.values()),
                             '科技专项认证获取情况', figsize=(10, 5))
        charts.append(generate_chart(fig, 'certifications'))

    # Business qualifications
    biz_cols = {}
    for c_name in columns_info.values():
        for kw in ['特定目的信托受托机构资格', '全国银行间同业拆借市场交易资格',
                    '全国银行间债券市场业务资格', '私募投资基金管理人资格',
                    '股指期货交易业务资格', '受托境外理财业务资格',
                    '企业年金基金管理机构资格']:
            if kw in c_name and '业务资质' in c_name:
                biz_cols[kw] = c_name

    if biz_cols:
        result += "**业务资质**：\n"
        biz_data = {}
        for label, col in biz_cols.items():
            vals = [c['数据'].get(col) for c in companies]
            yes = sum(1 for v in vals if v in [1, '1', 2, '2'])
            biz_data[label] = yes
            short_label = label[:12] + '...' if len(label) > 12 else label
            result += f"- {label}：{yes} 家\n"
        result += '\n'

    return result, charts


def analyze_future_investment(query):
    """未来投入方向分析"""
    result = "## 🎯 未来3-5年科技投入方向\n\n"
    charts = []

    direction_cols = {}
    for c_name in columns_info.values():
        for kw in ['资产管理信托', '资产服务信托', '公益慈善信托', '风险管理与合规科技',
                    '运营整合与效率提升']:
            if kw in c_name and '重点投入' in c_name:
                direction_cols[kw] = c_name

    if direction_cols:
        dir_data = {}
        for label, col in direction_cols.items():
            vals = [c['数据'].get(col) for c in companies]
            yes = sum(1 for v in vals if v in [1, '1', 2, '2'])
            dir_data[label] = yes
            result += f"- **{label}**：{yes}/{len(companies)} 家 ({yes/len(companies)*100:.1f}%)\n"
        result += '\n'

        fig = make_bar_chart(list(dir_data.keys()), list(dir_data.values()),
                             '未来3-5年科技重点投入方向', figsize=(10, 5))
        charts.append(generate_chart(fig, 'future_direction'))

    return result, charts


def analyze_comprehensive_ranking(query):
    """综合排名分析 - 支持自定义维度与权重"""
    
    # 获取用户自定义维度配置（使用线程安全的获取方式）
    user_dim_config = get_user_dimensions()
    
    if user_dim_config is not None:
        # 使用用户自定义配置
        dim_config = user_dim_config
        is_user_defined_dims = True
    else:
        # 使用默认配置
        dim_config = DEFAULT_DIMENSIONS
        is_user_defined_dims = False
    
    # 构建维度映射（键 -> 配置）
    dim_map = {
        'd1': dim_config.get('d1_strategy', {}),
        'd2': dim_config.get('d2_resource', {}),
        'd3': dim_config.get('d3_org', {}),
        'd4': dim_config.get('d4_infra', {}),
        'd5': dim_config.get('d5_xc', {}),
        'd6': dim_config.get('d6_tech', {}),
        'd7': dim_config.get('d7_system', {}),
        'd8': dim_config.get('d8_data', {}),
    }
    
    # 过滤启用的维度
    enabled_dims = {k: v for k, v in dim_map.items() if v.get('enabled', False)}
    
    # 分离参考维度和排名维度
    ref_dims = {k: v for k, v in enabled_dims.items() if v.get('is_reference', False)}
    ranking_dims = {k: v for k, v in enabled_dims.items() if not v.get('is_reference', False)}
    
    # 计算排名维度的权重（需要归一化）
    total_ranking_weight = sum(v.get('weight', 0) for v in ranking_dims.values())
    
    # 构建归一化权重
    normalized_weights = {}
    for k, v in ranking_dims.items():
        if total_ranking_weight > 0:
            normalized_weights[k] = v.get('weight', 0) / total_ranking_weight
        else:
            normalized_weights[k] = 0
    
    # 构建结果标题
    result = "## 🏆 综合实力排名分析\n\n"
    
    if is_user_defined_dims:
        result += "**⚙️ 用户自定义维度评分模型**：\n\n"
    else:
        result += "**八大评价维度评分模型**：\n\n"
    
    # 维度说明表格
    result += "| 维度 | 权重 | 状态 | 说明 |\n"
    result += "|---|---|---|---|\n"
    
    dim_names = {
        'd1': '科技战略定位', 'd2': '资源投入与配置', 'd3': '组织架构与人才培养',
        'd4': '基础设施架构', 'd5': '信创转型', 'd6': '高新技术应用',
        'd7': '业务应用系统建设', 'd8': '数据治理与安全'
    }
    
    for k in ['d1', 'd2', 'd3', 'd4', 'd5', 'd6', 'd7', 'd8']:
        v = dim_map.get(k, {})
        if v.get('enabled', False):
            weight = v.get('weight', 0)
            weight_str = f"{weight*100:.0f}%"
            if v.get('is_reference', False):
                status = "📌 参考"
                weight_str = f"{weight_str} (不计入排名)"
            else:
                norm_w = normalized_weights.get(k, 0)
                status = f"✅ 排名 ({norm_w*100:.1f}%)"
            result += f"| {dim_names.get(k, k)} | {weight_str} | {status} |\n"
        else:
            result += f"| {dim_names.get(k, k)} | — | ❌ 禁用 |\n"
    
    result += f"\n💡 **排名规则**：共启用{len(ranking_dims)}个排名维度，权重已归一化。"
    if ref_dims:
        result += f"{len(ref_dims)}个参考维度仅展示不参与排名。"
    result += "\n\n"

    charts = []

    # ===== 维度1：科技战略定位 (参考维度) =====
    # 核心指标：公司级科技战略发文数量、三分类新规配套准备进度
    strategy_cols = ['2', '3', '4', '5', '6', '7']  # 6项战略规划
    
    # ===== 维度2：资源投入与配置 (20%) =====
    # 核心指标：科技投入金额及增速、科技人员规模及结构占比
    col_invest_2023 = get_field_col('2023年科技投入')
    col_invest_2024 = get_field_col('2024年科技投入')
    col_invest_2025 = get_field_col('2025年科技投入')
    col_total_emp = get_field_col('公司员工总人数')
    col_tech_emp = get_field_col('自有科技团队总人数')
    col_outsource = get_field_col('科技外包团队总人数')
    
    # ===== 维度3：组织架构与人才培养 (15%) =====
    # 核心指标：科技治理机构设立数量、独立科技部门配置、人才激励机制
    gov_cols = ['43', '44', '45', '46', '47', '48', '49']  # 7个治理机构
    dept_cols = ['51', '52', '53', '54', '55', '56']  # 6个科技部门
    col_cio = '65'
    col_cio_senior = '66'
    cert_cols = ['87', '88', '89', '90', '91', '92', '93']  # 7项认证
    
    # ===== 维度4：基础设施架构 (10%) =====
    # 核心指标：机房与云平台建设、虚拟化技术部署、公有云应用
    col_infra_arch = '106'
    virt_cols = ['111', '112', '113', '114']  # 服务器虚拟化
    vdi_cols = ['116', '117', '118', '119', '120']  # 桌面虚拟化
    cloud_cols = ['122', '123', '124', '125', '126', '127']  # 公有云
    
    # ===== 维度5：信创转型 (10%) =====
    # 核心指标：信创系统占比、国产软硬件适配品牌数量
    col_xc_progress = '131'
    col_xc_ratio = '132'
    xc_brand_cols = ['133', '134', '135', '136', '137',  # 芯片
                     '138', '139', '140', '141', '142', '143',  # 服务器
                     '144', '145', '146', '147', '148',  # 操作系统
                     '149', '150', '151', '152', '153', '154',  # 数据库
                     '155', '156', '157', '158']  # 中间件
    
    # ===== 维度6：高新技术应用 (15%) =====
    # 核心指标：AI/大数据/云原生/区块链应用场景覆盖度
    ai_cols = ['160', '161', '162', '163', '164']  # AI 5个场景
    bigdata_cols = ['167', '168', '169', '170', '171', '172']  # 大数据6个场景
    col_cloud_native = '175'  # 云原生阶段
    col_blockchain = '180'  # 区块链阶段
    
    # ===== 维度7：业务应用系统建设 (10%) =====
    # 核心指标：核心业务系统覆盖率、自研/外采比例
    biz_sys_cols = ['184', '185', '186', '187', '188', '189', '190', '191', '192',
                    '193', '194', '195', '196', '197', '198', '199', '200', '201',
                    '202', '203', '204', '205', '206', '207', '208', '209', '210']
    
    # ===== 维度8：数据治理与安全 (10%) =====
    # 核心指标：数据中台建设、数据安全管控措施、专项治理开展情况
    dg_cols = ['238', '239', '240', '241', '242', '243', '244', '245', '246']  # 9项数据治理
    ds_cols = ['254', '255']  # 2项数据安全

    # 预计算各维度最大值用于归一化
    all_invests = [safe_num(c['数据'].get(col_invest_2024)) for c in companies] if col_invest_2024 else [0]
    max_invest = max(all_invests) if max(all_invests) > 0 else 1

    all_tech_ratios = []
    for c in companies:
        te = safe_num(c['数据'].get(col_total_emp)) if col_total_emp else 0
        se = safe_num(c['数据'].get(col_tech_emp)) if col_tech_emp else 0
        if te > 0:
            all_tech_ratios.append(se / te * 100)
    max_ratio = max(all_tech_ratios) if all_tech_ratios else 1

    all_outsources = [safe_num(c['数据'].get(col_outsource)) for c in companies] if col_outsource else [0]
    max_outsource = max(all_outsources) if max(all_outsources) > 0 else 1

    # 计算每家公司的各维度得分
    scores = []
    for c in companies:
        name = c['公司简称']
        d = c['数据']

        # --- 维度1：科技战略定位 (参考维度，不参与排名) ---
        # 核心指标：公司级科技战略发文数量、三分类新规配套准备进度
        strategy_count = sum(1 for col_idx in strategy_cols if d.get(columns_info.get(col_idx)) in [1, '1', 2, '2'])
        d1 = strategy_count / len(strategy_cols) * 100

        # --- 维度2：资源投入与配置 (20%) ---
        # 核心指标：科技投入金额及增速、科技人员规模及结构占比
        invest = safe_num(d.get(col_invest_2024)) if col_invest_2024 else 0
        invest_score = (invest / max_invest * 100) if invest > 0 else 0
        total_emp = safe_num(d.get(col_total_emp)) if col_total_emp else 0
        tech_emp = safe_num(d.get(col_tech_emp)) if col_tech_emp else 0
        ratio_score = (tech_emp / total_emp * 100 / max_ratio * 100) if total_emp > 0 else 0
        outsource = safe_num(d.get(col_outsource)) if col_outsource else 0
        outsource_score = (outsource / max_outsource * 100) if outsource > 0 else 0
        d2 = invest_score * 0.40 + ratio_score * 0.30 + outsource_score * 0.30

        # --- 维度3：组织架构与人才培养 (15%) ---
        # 核心指标：科技治理机构设立数量、独立科技部门配置、人才激励机制
        gov_count = sum(1 for col_idx in gov_cols if d.get(columns_info.get(col_idx)) in [1, '1', 2, '2'])
        gov_score = gov_count / len(gov_cols) * 100
        dept_count = sum(1 for col_idx in dept_cols if d.get(columns_info.get(col_idx)) in [1, '1', 2, '2'])
        dept_score = dept_count / len(dept_cols) * 100
        cio_score = 50  # 基础分
        if d.get(columns_info.get(col_cio)) in [1, '1', 2, '2']:
            cio_score = 80
            if d.get(columns_info.get(col_cio_senior)) in [1, '1', 2, '2']:
                cio_score = 100
        cert_count = sum(1 for col_idx in cert_cols if d.get(columns_info.get(col_idx)) in [1, '1', 2, '2'])
        cert_score = cert_count / len(cert_cols) * 100
        d3 = gov_score * 0.25 + dept_score * 0.25 + cio_score * 0.25 + cert_score * 0.25

        # --- 维度4：基础设施架构 (10%) ---
        # 核心指标：机房与云平台建设、虚拟化技术部署、公有云应用
        arch_val = d.get(columns_info.get(col_infra_arch))
        arch_score_map = {1: 25, 2: 50, 3: 75, 4: 100, 5: 100}
        arch_score = arch_score_map.get(safe_num(arch_val), 20)
        virt_count = sum(1 for col_idx in virt_cols if d.get(columns_info.get(col_idx)) in [1, '1', 2, '2'])
        virt_score = virt_count / max(len(virt_cols), 1) * 100
        vdi_count = sum(1 for col_idx in vdi_cols if d.get(columns_info.get(col_idx)) in [1, '1', 2, '2'])
        vdi_score = vdi_count / max(len(vdi_cols), 1) * 100
        cloud_count = sum(1 for col_idx in cloud_cols if d.get(columns_info.get(col_idx)) in [1, '1', 2, '2'])
        cloud_score = cloud_count / max(len(cloud_cols), 1) * 100
        d4 = arch_score * 0.30 + virt_score * 0.25 + vdi_score * 0.20 + cloud_score * 0.25

        # --- 维度5：信创转型 (10%) ---
        # 核心指标：信创系统占比、国产软硬件适配品牌数量
        xc_progress = safe_num(d.get(columns_info.get(col_xc_progress)))
        progress_map = {1: 20, 2: 50, 3: 75, 4: 100}
        progress_score = progress_map.get(xc_progress, 10)
        xc_ratio = safe_num(d.get(columns_info.get(col_xc_ratio)))
        ratio_score_xc = min(xc_ratio, 100) if xc_ratio > 0 else 0
        brand_count = sum(1 for col_idx in xc_brand_cols if d.get(columns_info.get(str(col_idx))) in [1, '1', 2, '2'])
        brand_score = brand_count / max(len(xc_brand_cols), 1) * 100
        d5 = progress_score * 0.35 + ratio_score_xc * 0.35 + brand_score * 0.30

        # --- 维度6：高新技术应用 (15%) ---
        # 核心指标：AI/大数据/云原生/区块链应用场景覆盖度
        ai_count = sum(1 for col_idx in ai_cols if d.get(columns_info.get(col_idx)) in [1, '1', 2, '2'])
        ai_score = ai_count / len(ai_cols) * 100
        bd_count = sum(1 for col_idx in bigdata_cols if d.get(columns_info.get(col_idx)) in [1, '1', 2, '2'])
        bd_score = bd_count / len(bigdata_cols) * 100
        cn_val = safe_num(d.get(columns_info.get(col_cloud_native)))
        cn_map = {1: 100, 2: 70, 3: 40, 4: 0}
        cn_score = cn_map.get(cn_val, 0)
        bc_val = safe_num(d.get(columns_info.get(col_blockchain)))
        bc_map = {1: 100, 2: 60, 3: 30, 4: 0}
        bc_score = bc_map.get(bc_val, 0)
        d6 = ai_score * 0.30 + bd_score * 0.25 + cn_score * 0.25 + bc_score * 0.20

        # --- 维度7：业务应用系统建设 (10%) ---
        # 核心指标：核心业务系统覆盖率、自研/外采比例
        sys_count = sum(1 for col_idx in biz_sys_cols if d.get(columns_info.get(col_idx)) in [1, '1', 2, '2'])
        d7 = sys_count / len(biz_sys_cols) * 100

        # --- 维度8：数据治理与安全 (10%) ---
        # 核心指标：数据中台建设、数据安全管控措施、专项治理开展情况
        dg_count = sum(1 for col_idx in dg_cols if d.get(columns_info.get(col_idx)) in [1, '1', 2, '2', 3, '3', 4, '4'])
        dg_score = dg_count / len(dg_cols) * 100
        ds_count = sum(1 for col_idx in ds_cols if d.get(columns_info.get(col_idx)) in [1, '1', 2, '2', 3, '3', 4, '4'])
        ds_score = ds_count / len(ds_cols) * 100
        d8 = dg_score * 0.70 + ds_score * 0.30

        # 综合得分计算（根据启用的排名维度动态计算）
        # 使用归一化权重
        total_ranking = 0
        dim_scores = {'d1': d1, 'd2': d2, 'd3': d3, 'd4': d4, 'd5': d5, 'd6': d6, 'd7': d7, 'd8': d8}
        
        for dim_key, dim_score in dim_scores.items():
            if dim_key in normalized_weights:
                total_ranking += dim_score * normalized_weights[dim_key]
        
        # 计算含参考维度的总分（仅用于展示）
        total_with_ref = total_ranking
        for dim_key, dim_config in ref_dims.items():
            if dim_key in dim_scores:
                total_with_ref += dim_scores[dim_key] * dim_config.get('weight', 0)

        scores.append({
            'name': name, 
            'total': round(total_ranking, 1),  # 排名用总分（七维度）
            'total_with_ref': round(total_with_ref, 1),  # 含参考维度的总分
            'd1': round(d1, 1),  # 战略定位（参考）
            'd2': round(d2, 1),  # 资源投入
            'd3': round(d3, 1),  # 组织架构
            'd4': round(d4, 1),  # 基础设施
            'd5': round(d5, 1),  # 信创转型
            'd6': round(d6, 1),  # 高新技术
            'd7': round(d7, 1),  # 业务系统
            'd8': round(d8, 1),  # 数据治理
        })

    # 获取头部标杆公司名称集合（优先使用用户自定义配置）
    head_names = set()
    is_user_defined = False
    
    # 检查是否有用户自定义的头部标杆（使用线程安全的获取方式）
    user_head_config = get_user_head_benchmark()
    if user_head_config is not None:
        # 使用用户自定义配置
        for cfg in user_head_config:
            head_names.add(cfg['name'])
        is_user_defined = True
    elif HEAD_BENCHMARK_CONFIG.get('enabled'):
        # 使用系统默认配置
        for cfg in HEAD_BENCHMARK_CONFIG['companies']:
            head_names.add(cfg['name'])

    # 排序规则：头部标杆优先排入前十（标杆内部按得分排序），其余公司按得分排序
    head_scores = sorted([s for s in scores if s['name'] in head_names], key=lambda x: x['total'], reverse=True)
    other_scores = sorted([s for s in scores if s['name'] not in head_names], key=lambda x: x['total'], reverse=True)
    scores_sorted = head_scores + other_scores

    # 默认显示全部65家，除非指定TOP N
    top_n = len(scores_sorted)  # 默认全部
    n_match = re.search(r'前\s*(\d+)|TOP\s*(\d+)|top\s*(\d+)', query, re.IGNORECASE)
    if n_match:
        top_n = int(n_match.group(1) or n_match.group(2) or n_match.group(3))
    top_n = min(top_n, len(scores_sorted))

    # 统计头部标杆在排名中的分布
    head_in_top = sum(1 for s in scores_sorted[:top_n] if s['name'] in head_names)

    # 头部标杆来源说明
    head_source = "用户自定义" if is_user_defined else "系统默认"

    # 构建排名表格（只显示启用的维度）
    result += f"### 综合实力排名 TOP{top_n}（共{len(scores_sorted)}家）\n\n"
    
    dim_source = "用户自定义" if is_user_defined_dims else "系统默认"
    result += f"💡 **说明**：综合排名基于{len(ranking_dims)}个排名维度，🏆 标记为头部标杆公司（共{len(head_names)}家，本次排名前{top_n}中占{head_in_top}家，头部来源：{head_source}，维度来源：{dim_source}）。\n\n"
    
    # 构建表头
    header_cols = ['排名', '公司', '综合得分']
    header_abbr = {'d1': '战略📌', 'd2': '资源', 'd3': '组织', 'd4': '设施', 'd5': '信创', 'd6': '技术', 'd7': '系统', 'd8': '数安'}
    for k in ['d1', 'd2', 'd3', 'd4', 'd5', 'd6', 'd7', 'd8']:
        if k in enabled_dims:
            header_cols.append(header_abbr.get(k, k))
    
    result += '| ' + ' | '.join(header_cols) + ' |\n'
    result += '|' + ':---:|' * len(header_cols) + '\n'
    
    for i, s in enumerate(scores_sorted[:top_n]):
        medal = ['🥇', '🥈', '🥉'][i] if i < 3 else str(i + 1)
        head_tag = '🏆 ' if s['name'] in head_names else ''
        row_cols = [medal, f"{head_tag}{s['name']}", f"**{s['total']}**"]
        for k in ['d1', 'd2', 'd3', 'd4', 'd5', 'd6', 'd7', 'd8']:
            if k in enabled_dims:
                row_cols.append(str(s.get(k, '-')))
        result += '| ' + ' | '.join(row_cols) + ' |\n'
    result += '\n'
    
    result += "📌 **战略定位列**：仅作参考，不参与排名计算\n"
    result += "🏆 **头部标杆**：以投入规模（≥3000万）和人员配置（≥10人）筛选的10家高端对标公司\n\n"

    # 头部标杆排名分布摘要
    result += "### 头部标杆排名分布\n\n"
    result += '| 头部标杆公司 | 综合排名 | 综合得分 |\n'
    result += '|---|:---:|:---:|\n'
    for s in scores_sorted:
        if s['name'] in head_names:
            rank = scores_sorted.index(s) + 1
            medal = '🥇' if rank == 1 else ('🥈' if rank == 2 else ('🥉' if rank == 3 else str(rank)))
            result += f"| 🏆 {s['name']} | {medal} | **{s['total']}** |\n"
    result += '\n'

    # 综合排名柱状图
    fig = make_bar_chart(
        [s['name'] for s in scores_sorted[:top_n]],
        [s['total'] for s in scores_sorted[:top_n]],
        f'信托公司科技建设综合实力排名TOP{top_n}',
        horizontal=True, figsize=(10, 8))
    charts.append(generate_chart(fig, 'comp_ranking'))

    # 雷达图 - TOP5各维度对比
    top5 = scores_sorted[:5]
    fig2, ax = plt.subplots(figsize=(10, 8), subplot_kw=dict(polar=True))
    dims = ['d1', 'd2', 'd3', 'd4', 'd5', 'd6', 'd7', 'd8']
    labels = ['科技战略\n定位', '资源投入\n与配置', '组织架构\n与人才培养', '基础设施\n架构', '信创\n转型', '高新技术\n应用', '业务应用\n系统建设', '数据治理\n与安全']
    angles = np.linspace(0, 2 * np.pi, len(dims), endpoint=False).tolist()
    angles += angles[:1]
    colors_list = ['#e74c3c', '#3498db', '#2ecc71', '#f39c12', '#9b59b6']
    for idx, s in enumerate(top5):
        values = [s[dim] for dim in dims]
        values += values[:1]
        ax.plot(angles, values, 'o-', linewidth=2, label=s['name'], color=colors_list[idx])
        ax.fill(angles, values, alpha=0.08, color=colors_list[idx])
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(labels, fontsize=9)
    ax.set_title('TOP5 综合实力各维度对比', fontsize=14, fontweight='bold', pad=25)
    ax.legend(loc='upper right', bbox_to_anchor=(1.35, 1.1), fontsize=10)
    plt.tight_layout()
    charts.append(generate_chart(fig2, 'comp_radar'))

    # 各维度领先公司
    result += "### 各维度领先公司\n\n"
    dim_full_names = {
        'd1': ('科技战略定位', 'd1'), 'd2': ('资源投入与配置', 'd2'),
        'd3': ('组织架构与人才培养', 'd3'), 'd4': ('基础设施架构', 'd4'),
        'd5': ('信创转型', 'd5'), 'd6': ('高新技术应用', 'd6'),
        'd7': ('业务应用系统建设', 'd7'), 'd8': ('数据治理与安全', 'd8'),
    }
    for dim_key, (dim_name, _) in dim_full_names.items():
        top3 = sorted(scores, key=lambda x: x[dim_key], reverse=True)[:3]
        parts = [f'{s["name"]}({s[dim_key]}分)' for s in top3]
        result += f"**{dim_name}TOP3**：{', '.join(parts)}\n"

    return result, charts


def analyze_head_benchmark(query):
    """头部标杆分析 - 分析10家头部公司的各项指标"""
    result = "## 🏆 头部标杆分析\n\n"
    result += f"**分析对象**：{HEAD_BENCHMARK_CONFIG['description']}\n\n"
    result += f"**筛选标准**：\n"
    result += f"- 剔除：{', '.join(HEAD_BENCHMARK_CONFIG['criteria']['exclude_companies'])}\n"
    result += f"- 自有科技人员 ≥ {HEAD_BENCHMARK_CONFIG['criteria']['min_tech_employees']}人\n"
    result += f"- 2026年科技预计投入 ≥ {HEAD_BENCHMARK_CONFIG['criteria']['min_investment_2026']}万元\n\n"
    
    charts = []
    
    # 获取头部标杆公司数据
    head_companies = []
    for cfg in HEAD_BENCHMARK_CONFIG['companies']:
        comp = next((c for c in companies if cfg['name'] in c['公司简称']), None)
        if comp:
            head_companies.append({
                'data': comp,
                'display_name': cfg['display_name']
            })
    
    if not head_companies:
        return "未找到头部标杆公司数据。", []
    
    result += f"**头部标杆公司**（共{len(head_companies)}家）：\n\n"
    result += '| 序号 | 公司名称 | 简称 |\n'
    result += '|---|---|---|\n'
    for i, hc in enumerate(head_companies, 1):
        short_name = hc['data']['公司简称']
        display = hc['display_name']
        result += f'| {i} | {display} | {short_name} |\n'
    result += '\n'
    
    # 获取关键字段
    col_invest_2024 = get_field_col('2024年科技投入')
    col_invest_2025 = get_field_col('2025年科技投入')
    col_invest_2026 = get_field_col('2026年科技投入预算')
    col_total_emp = get_field_col('公司员工总人数')
    col_tech_emp = get_field_col('自有科技团队总人数')
    col_outsource = get_field_col('科技外包团队总人数')
    
    # 1. 科技投入分析
    result += "### 💰 科技投入分析（头部标杆 vs 行业平均）\n\n"
    
    invest_data = []
    for year, col in [('2024', col_invest_2024), ('2025', col_invest_2025), ('2026', col_invest_2026)]:
        if col:
            # 头部公司投入
            head_vals = [safe_num(hc['data']['数据'].get(col)) for hc in head_companies]
            head_vals = [v for v in head_vals if v > 0]
            head_avg = np.mean(head_vals) if head_vals else 0
            
            # 全行业投入
            all_vals = [safe_num(c['数据'].get(col)) for c in companies]
            all_vals = [v for v in all_vals if v > 0]
            all_avg = np.mean(all_vals) if all_vals else 0
            
            invest_data.append({
                'year': year,
                'head_avg': head_avg,
                'all_avg': all_avg,
                'ratio': head_avg / all_avg if all_avg > 0 else 0
            })
    
    if invest_data:
        result += '| 年份 | 头部平均(万元) | 行业平均(万元) | 头部/行业 |\n'
        result += '|---|---|---|---|\n'
        for d in invest_data:
            result += f"| {d['year']} | {d['head_avg']:.0f} | {d['all_avg']:.0f} | {d['ratio']:.1f}x |\n"
        result += '\n'
        
        # 图表：头部vs行业投入对比
        fig, ax = plt.subplots(figsize=(10, 5))
        years = [d['year'] for d in invest_data]
        head_avgs = [d['head_avg'] for d in invest_data]
        all_avgs = [d['all_avg'] for d in invest_data]
        x = range(len(years))
        width = 0.35
        ax.bar([i - width/2 for i in x], head_avgs, width, label='头部标杆平均', color='#1a73e8')
        ax.bar([i + width/2 for i in x], all_avgs, width, label='行业平均', color='#9aa0a6')
        ax.set_xticks(list(x))
        ax.set_xticklabels(years)
        ax.set_ylabel('万元')
        ax.set_title('科技投入对比：头部标杆 vs 行业平均', fontsize=14, fontweight='bold')
        ax.legend()
        for i, (h, a) in enumerate(zip(head_avgs, all_avgs)):
            ax.text(i - width/2, h + 100, f'{h:.0f}', ha='center', fontsize=9)
            ax.text(i + width/2, a + 100, f'{a:.0f}', ha='center', fontsize=9)
        plt.tight_layout()
        charts.append(generate_chart(fig, 'head_invest_compare'))
    
    # 2. 人员配置分析
    result += "### 👥 人员配置分析\n\n"
    
    if col_tech_emp and col_total_emp:
        # 头部公司人员
        head_tech_emps = [safe_num(hc['data']['数据'].get(col_tech_emp)) for hc in head_companies]
        head_total_emps = [safe_num(hc['data']['数据'].get(col_total_emp)) for hc in head_companies]
        head_ratios = [t/tot*100 for t, tot in zip(head_tech_emps, head_total_emps) if tot > 0]
        
        # 全行业人员
        all_tech_emps = [safe_num(c['数据'].get(col_tech_emp)) for c in companies]
        all_total_emps = [safe_num(c['数据'].get(col_total_emp)) for c in companies]
        all_ratios = [t/tot*100 for t, tot in zip(all_tech_emps, all_total_emps) if tot > 0]
        
        result += '| 指标 | 头部平均 | 行业平均 |\n'
        result += '|---|---|---|\n'
        result += f"| 自有科技人员 | {np.mean(head_tech_emps):.0f}人 | {np.mean(all_tech_emps):.0f}人 |\n"
        result += f"| 科技人员占比 | {np.mean(head_ratios):.1f}% | {np.mean(all_ratios):.1f}% |\n"
        if col_outsource:
            head_out = [safe_num(hc['data']['数据'].get(col_outsource)) for hc in head_companies]
            all_out = [safe_num(c['数据'].get(col_outsource)) for c in companies]
            result += f"| 外包团队人数 | {np.mean(head_out):.0f}人 | {np.mean(all_out):.0f}人 |\n"
        result += '\n'
    
    # 3. 头部公司详细数据表
    result += "### 📋 头部标杆公司详细数据\n\n"
    result += '| 公司 | 2024投入 | 2025投入 | 2026预算 | 科技人员 | 人员占比 |\n'
    result += '|---|---|---|---|---|---|\n'
    
    for hc in head_companies:
        name = hc['data']['公司简称']
        d = hc['data']['数据']
        inv24 = safe_num(d.get(col_invest_2024)) if col_invest_2024 else 0
        inv25 = safe_num(d.get(col_invest_2025)) if col_invest_2025 else 0
        inv26 = safe_num(d.get(col_invest_2026)) if col_invest_2026 else 0
        tech_emp = safe_num(d.get(col_tech_emp)) if col_tech_emp else 0
        total_emp = safe_num(d.get(col_total_emp)) if col_total_emp else 0
        ratio = tech_emp / total_emp * 100 if total_emp > 0 else 0
        
        inv24_str = f'{inv24:.0f}' if inv24 > 0 else '-'
        inv25_str = f'{inv25:.0f}' if inv25 > 0 else '-'
        inv26_str = f'{inv26:.0f}' if inv26 > 0 else '-'
        
        result += f'| {name} | {inv24_str} | {inv25_str} | {inv26_str} | {tech_emp:.0f} | {ratio:.1f}% |\n'
    
    result += '\n'
    
    # 4. 头部公司投入排名图
    if col_invest_2024:
        head_invests = []
        for hc in head_companies:
            val = safe_num(hc['data']['数据'].get(col_invest_2024))
            if val > 0:
                head_invests.append((hc['data']['公司简称'], val))
        head_invests.sort(key=lambda x: x[1], reverse=True)
        
        if head_invests:
            fig = make_bar_chart([n for n, _ in head_invests], [v for _, v in head_invests],
                                 '头部标杆公司2024年科技投入排名', horizontal=True, figsize=(10, 6))
            charts.append(generate_chart(fig, 'head_invest_ranking'))
    
    return result, charts


def analyze_all_dimensions(query):
    """全维度综合分析 - 当用户未指定具体维度时，从所有维度进行分析"""
    result = "## 📊 全维度综合分析\n\n"
    result += "以下从八大评价维度对行业科技建设情况进行全面分析：\n\n"
    charts = []

    # ===== 维度1：科技战略定位 =====
    strategy_cols = ['2', '3', '4', '5', '6', '7']
    strategy_counts = []
    for c in companies:
        cnt = sum(1 for col_idx in strategy_cols if c['数据'].get(columns_info.get(col_idx)) in [1, '1', 2, '2'])
        strategy_counts.append(cnt)
    avg_strategy = np.mean(strategy_counts)
    full_strategy = sum(1 for cnt in strategy_counts if cnt == len(strategy_cols))

    result += "### 📌 科技战略定位（参考维度）\n\n"
    result += f"- 6项战略规划平均发布：{avg_strategy:.1f} 项/家\n"
    result += f"- 全部发布的公司：{full_strategy} 家（{full_strategy/len(companies)*100:.0f}%）\n"
    result += f"- 未发布任何战略的公司：{sum(1 for cnt in strategy_counts if cnt == 0)} 家\n\n"

    # ===== 维度2：资源投入与配置 =====
    col_invest_2024 = get_field_col('2024年科技投入')
    col_invest_2025 = get_field_col('2025年科技投入')
    col_total_emp = get_field_col('公司员工总人数')
    col_tech_emp = get_field_col('自有科技团队总人数')
    col_outsource = get_field_col('科技外包团队总人数')

    result += "### 💵 资源投入与配置\n\n"
    if col_invest_2024:
        vals_24 = [safe_num(c['数据'].get(col_invest_2024)) for c in companies]
        vals_24 = [v for v in vals_24 if v > 0]
        if vals_24:
            result += f"**2024年科技投入**（{len(vals_24)}家有效数据）：\n"
            result += f"- 平均：{np.mean(vals_24):.0f} 万元 | 中位数：{np.median(vals_24):.0f} 万元\n"
            result += f"- 最高：{max(vals_24):.0f} 万元 | 最低：{min(vals_24):.0f} 万元\n"
    if col_invest_2025:
        vals_25 = [safe_num(c['数据'].get(col_invest_2025)) for c in companies]
        vals_25 = [v for v in vals_25 if v > 0]
        if vals_25:
            result += f"**2025年科技投入**（{len(vals_25)}家有效数据）：\n"
            result += f"- 平均：{np.mean(vals_25):.0f} 万元 | 中位数：{np.median(vals_25):.0f} 万元\n"
    if col_tech_emp and col_total_emp:
        ratios = []
        for c in companies:
            te = safe_num(c['数据'].get(col_total_emp))
            se = safe_num(c['数据'].get(col_tech_emp))
            if te > 0 and se > 0:
                ratios.append(se / te * 100)
        if ratios:
            result += f"**科技人员占比**：平均 {np.mean(ratios):.1f}%，中位数 {np.median(ratios):.1f}%\n"
    if col_outsource:
        out_vals = [safe_num(c['数据'].get(col_outsource)) for c in companies]
        out_vals = [v for v in out_vals if v > 0]
        if out_vals:
            result += f"**外包团队**：{len(out_vals)}家使用外包，平均 {np.mean(out_vals):.0f} 人\n"
    result += '\n'

    # ===== 维度3：组织架构与人才培养 =====
    gov_cols = ['43', '44', '45', '46', '47', '48', '49']
    dept_cols = ['51', '52', '53', '54', '55', '56']
    col_cio = '65'

    result += "### 🏢 组织架构与人才培养\n\n"
    gov_counts = []
    for c in companies:
        cnt = sum(1 for col_idx in gov_cols if c['数据'].get(columns_info.get(col_idx)) in [1, '1', 2, '2'])
        gov_counts.append(cnt)
    result += f"- 科技治理机构：平均设立 {np.mean(gov_counts):.1f} 个，全部设立（7个）的公司 {sum(1 for cnt in gov_counts if cnt == 7)} 家\n"
    dept_counts = []
    for c in companies:
        cnt = sum(1 for col_idx in dept_cols if c['数据'].get(columns_info.get(col_idx)) in [1, '1', 2, '2'])
        dept_counts.append(cnt)
    result += f"- 科技部门配置：平均 {np.mean(dept_counts):.1f} 个\n"
    cio_count = sum(1 for c in companies if c['数据'].get(columns_info.get(col_cio)) in [1, '1', 2, '2'])
    result += f"- 设立CIO：{cio_count} 家（{cio_count/len(companies)*100:.0f}%）\n\n"

    # ===== 维度4：基础设施架构 =====
    col_infra_arch = '106'
    result += "### 🏗️ 基础设施架构\n\n"
    arch_vals = [safe_num(c['数据'].get(columns_info.get(col_infra_arch))) for c in companies]
    arch_labels = {1: '无', 2: '托管', 3: '自建', 4: '多活', 5: '混合云'}
    arch_counts = {}
    for v in arch_vals:
        label = arch_labels.get(v, '未填')
        arch_counts[label] = arch_counts.get(label, 0) + 1
    for label, cnt in sorted(arch_counts.items(), key=lambda x: x[1], reverse=True):
        result += f"- {label}：{cnt} 家\n"
    virt_cols = ['111', '112', '113', '114']
    virt_users = sum(1 for c in companies if any(c['数据'].get(columns_info.get(ci)) in [1, '1', 2, '2'] for ci in virt_cols))
    result += f"- 服务器虚拟化：{virt_users} 家部署\n"
    cloud_cols = ['122', '123', '124', '125', '126', '127']
    cloud_users = sum(1 for c in companies if any(c['数据'].get(columns_info.get(ci)) in [1, '1', 2, '2'] for ci in cloud_cols))
    result += f"- 公有云平台：{cloud_users} 家使用\n\n"

    # ===== 维度5：信创转型 =====
    col_xc_progress = '131'
    result += "### 🖥️ 信创转型\n\n"
    xc_vals = [safe_num(c['数据'].get(columns_info.get(col_xc_progress))) for c in companies]
    xc_labels = {1: '规模化应用', 2: '试点应用', 3: '规划中', 4: '未启动'}
    xc_counts = {}
    for v in xc_vals:
        label = xc_labels.get(v, '未填')
        xc_counts[label] = xc_counts.get(label, 0) + 1
    for label, cnt in sorted(xc_counts.items(), key=lambda x: x[1], reverse=True):
        result += f"- {label}：{cnt} 家\n"
    result += '\n'

    # ===== 维度6：高新技术应用 =====
    ai_cols = ['160', '161', '162', '163', '164']
    bigdata_cols = ['167', '168', '169', '170', '171', '172']
    col_cloud_native = '175'
    col_blockchain = '180'

    result += "### 🤖 高新技术应用\n\n"
    ai_counts = []
    for c in companies:
        cnt = sum(1 for ci in ai_cols if c['数据'].get(columns_info.get(ci)) in [1, '1', 2, '2'])
        ai_counts.append(cnt)
    result += f"- **人工智能**（5场景）：平均覆盖 {np.mean(ai_counts):.1f} 个，全覆盖 {sum(1 for cnt in ai_counts if cnt == 5)} 家\n"
    bd_counts = []
    for c in companies:
        cnt = sum(1 for ci in bigdata_cols if c['数据'].get(columns_info.get(ci)) in [1, '1', 2, '2'])
        bd_counts.append(cnt)
    result += f"- **大数据**（6场景）：平均覆盖 {np.mean(bd_counts):.1f} 个\n"
    cn_vals = [safe_num(c['数据'].get(columns_info.get(col_cloud_native))) for c in companies]
    cn_labels = {1: '规模化', 2: '试点', 3: '规划', 4: '未涉及'}
    cn_counts_map = {}
    for v in cn_vals:
        label = cn_labels.get(v, '未填')
        cn_counts_map[label] = cn_counts_map.get(label, 0) + 1
    cn_str = '、'.join([f'{k} {v}家' for k, v in sorted(cn_counts_map.items(), key=lambda x: x[1], reverse=True)])
    result += f"- **云原生**：{cn_str}\n"
    bc_vals = [safe_num(c['数据'].get(columns_info.get(col_blockchain))) for c in companies]
    bc_labels = {1: '规模化', 2: '试点', 3: '规划', 4: '未涉及'}
    bc_counts_map = {}
    for v in bc_vals:
        label = bc_labels.get(v, '未填')
        bc_counts_map[label] = bc_counts_map.get(label, 0) + 1
    bc_str = '、'.join([f'{k} {v}家' for k, v in sorted(bc_counts_map.items(), key=lambda x: x[1], reverse=True)])
    result += f"- **区块链**：{bc_str}\n\n"

    # ===== 维度7：业务应用系统建设 =====
    biz_sys_cols = ['184', '185', '186', '187', '188', '189', '190', '191', '192',
                    '193', '194', '195', '196', '197', '198', '199', '200', '201',
                    '202', '203', '204', '205', '206', '207', '208', '209', '210']
    result += "### 💻 业务应用系统建设\n\n"
    sys_counts = []
    for c in companies:
        cnt = sum(1 for ci in biz_sys_cols if c['数据'].get(columns_info.get(ci)) in [1, '1', 2, '2'])
        sys_counts.append(cnt)
    result += f"- 核心业务系统（27类）：平均部署 {np.mean(sys_counts):.1f} 个\n"
    result += f"- 全覆盖（27个）：{sum(1 for cnt in sys_counts if cnt == len(biz_sys_cols))} 家\n"
    result += f"- 覆盖率超过80%：{sum(1 for cnt in sys_counts if cnt >= len(biz_sys_cols)*0.8)} 家\n"
    result += f"- 覆盖率低于50%：{sum(1 for cnt in sys_counts if cnt < len(biz_sys_cols)*0.5)} 家\n\n"

    # ===== 维度8：数据治理与安全 =====
    dg_cols = ['238', '239', '240', '241', '242', '243', '244', '245', '246']
    ds_cols = ['254', '255']
    result += "### 🗄️ 数据治理与安全\n\n"
    dg_counts = []
    for c in companies:
        cnt = sum(1 for ci in dg_cols if c['数据'].get(columns_info.get(ci)) in [1, '1', 2, '2', 3, '3', 4, '4'])
        dg_counts.append(cnt)
    result += f"- 数据治理措施（9项）：平均开展 {np.mean(dg_counts):.1f} 项\n"
    result += f"- 全部开展：{sum(1 for cnt in dg_counts if cnt == len(dg_cols))} 家\n"
    ds_counts = []
    for c in companies:
        cnt = sum(1 for ci in ds_cols if c['数据'].get(columns_info.get(ci)) in [1, '1', 2, '2', 3, '3', 4, '4'])
        ds_counts.append(cnt)
    result += f"- 数据安全措施（2项）：平均 {np.mean(ds_counts):.1f} 项，全部开展 {sum(1 for cnt in ds_counts if cnt == len(ds_cols))} 家\n\n"

    # 综合雷达图 - 行业平均各维度得分
    head_names_set = set()
    if HEAD_BENCHMARK_CONFIG.get('enabled'):
        for cfg in HEAD_BENCHMARK_CONFIG['companies']:
            head_names_set.add(cfg['name'])

    # 计算行业平均和头部平均各维度得分
    all_d = {'d1': [], 'd2': [], 'd3': [], 'd4': [], 'd5': [], 'd6': [], 'd7': [], 'd8': []}
    head_d = {'d1': [], 'd2': [], 'd3': [], 'd4': [], 'd5': [], 'd6': [], 'd7': [], 'd8': []}
    for c in companies:
        name = c['公司简称']
        d = c['数据']
        s1 = sum(1 for ci in strategy_cols if d.get(columns_info.get(ci)) in [1, '1', 2, '2']) / len(strategy_cols) * 100
        invest = safe_num(d.get(col_invest_2024)) if col_invest_2024 else 0
        all_inv = [safe_num(x['数据'].get(col_invest_2024)) for x in companies] if col_invest_2024 else [1]
        mx_inv = max(all_inv) if max(all_inv) > 0 else 1
        s2_i = (invest / mx_inv * 100) if invest > 0 else 0
        te = safe_num(d.get(col_total_emp)) if col_total_emp else 0
        se = safe_num(d.get(col_tech_emp)) if col_tech_emp else 0
        all_ratios = [safe_num(x['数据'].get(col_tech_emp)) / safe_num(x['数据'].get(col_total_emp)) * 100 for x in companies if safe_num(x['数据'].get(col_total_emp)) > 0]
        mx_rat = max(all_ratios) if all_ratios else 1
        s2_r = (se / te * 100 / mx_rat * 100) if te > 0 else 0
        out = safe_num(d.get(col_outsource)) if col_outsource else 0
        all_out = [safe_num(x['数据'].get(col_outsource)) for x in companies] if col_outsource else [1]
        mx_out = max(all_out) if max(all_out) > 0 else 1
        s2_o = (out / mx_out * 100) if out > 0 else 0
        s2 = s2_i * 0.40 + s2_r * 0.30 + s2_o * 0.30
        s3_g = sum(1 for ci in gov_cols if d.get(columns_info.get(ci)) in [1, '1', 2, '2']) / len(gov_cols) * 100
        s3_d = sum(1 for ci in dept_cols if d.get(columns_info.get(ci)) in [1, '1', 2, '2']) / len(dept_cols) * 100
        s3_c = 50
        if d.get(columns_info.get(col_cio)) in [1, '1', 2, '2']:
            s3_c = 80
            if d.get(columns_info.get('66')) in [1, '1', 2, '2']:
                s3_c = 100
        s3 = s3_g * 0.25 + s3_d * 0.25 + s3_c * 0.25 + 50 * 0.25
        s4_a = {1: 25, 2: 50, 3: 75, 4: 100, 5: 100}.get(safe_num(d.get(columns_info.get(col_infra_arch))), 20)
        s4_v = sum(1 for ci in virt_cols if d.get(columns_info.get(ci)) in [1, '1', 2, '2']) / max(len(virt_cols), 1) * 100
        s4_c = sum(1 for ci in cloud_cols if d.get(columns_info.get(ci)) in [1, '1', 2, '2']) / max(len(cloud_cols), 1) * 100
        s4 = s4_a * 0.30 + s4_v * 0.25 + s4_c * 0.25 + 50 * 0.20
        s5_p = {1: 20, 2: 50, 3: 75, 4: 100}.get(safe_num(d.get(columns_info.get(col_xc_progress))), 10)
        s5 = s5_p
        s6_ai = sum(1 for ci in ai_cols if d.get(columns_info.get(ci)) in [1, '1', 2, '2']) / len(ai_cols) * 100
        s6_bd = sum(1 for ci in bigdata_cols if d.get(columns_info.get(ci)) in [1, '1', 2, '2']) / len(bigdata_cols) * 100
        s6_cn = {1: 100, 2: 70, 3: 40, 4: 0}.get(safe_num(d.get(columns_info.get(col_cloud_native))), 0)
        s6_bc = {1: 100, 2: 60, 3: 30, 4: 0}.get(safe_num(d.get(columns_info.get(col_blockchain))), 0)
        s6 = s6_ai * 0.30 + s6_bd * 0.25 + s6_cn * 0.25 + s6_bc * 0.20
        s7 = sum(1 for ci in biz_sys_cols if d.get(columns_info.get(ci)) in [1, '1', 2, '2']) / len(biz_sys_cols) * 100
        s8 = sum(1 for ci in dg_cols if d.get(columns_info.get(ci)) in [1, '1', 2, '2', 3, '3', 4, '4']) / len(dg_cols) * 100

        for dim_key, val in [('d1', s1), ('d2', s2), ('d3', s3), ('d4', s4), ('d5', s5), ('d6', s6), ('d7', s7), ('d8', s8)]:
            all_d[dim_key].append(val)
            if name in head_names_set:
                head_d[dim_key].append(val)

    # 行业平均 vs 头部平均 雷达图
    fig, ax = plt.subplots(figsize=(10, 8), subplot_kw=dict(polar=True))
    dims = ['d1', 'd2', 'd3', 'd4', 'd5', 'd6', 'd7', 'd8']
    labels = ['科技战略\n定位', '资源投入\n与配置', '组织架构\n与人才培养', '基础设施\n架构', '信创\n转型', '高新技术\n应用', '业务应用\n系统建设', '数据治理\n与安全']
    angles = np.linspace(0, 2 * np.pi, len(dims), endpoint=False).tolist()
    angles += angles[:1]
    all_avgs = [np.mean(all_d[dim]) for dim in dims]
    all_avgs += all_avgs[:1]
    head_avgs = [np.mean(head_d[dim]) if head_d[dim] else 0 for dim in dims]
    head_avgs += head_avgs[:1]
    ax.plot(angles, all_avgs, 'o-', linewidth=2, label='行业平均', color='#9aa0a6')
    ax.fill(angles, all_avgs, alpha=0.1, color='#9aa0a6')
    ax.plot(angles, head_avgs, 'o-', linewidth=2, label='头部标杆平均', color='#1a73e8')
    ax.fill(angles, head_avgs, alpha=0.15, color='#1a73e8')
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(labels, fontsize=9)
    ax.set_title('行业平均 vs 头部标杆平均 · 八大维度对比', fontsize=14, fontweight='bold', pad=25)
    ax.legend(loc='upper right', bbox_to_anchor=(1.35, 1.1), fontsize=10)
    plt.tight_layout()
    charts.append(generate_chart(fig, 'all_dims_radar'))

    # 各维度得分对比表
    result += "### 📈 行业平均 vs 头部标杆平均\n\n"
    dim_names = ['科技战略定位', '资源投入与配置', '组织架构与人才培养', '基础设施架构', '信创转型', '高新技术应用', '业务应用系统建设', '数据治理与安全']
    result += '| 维度 | 行业平均 | 头部标杆平均 | 差距 |\n'
    result += '|---|:---:|:---:|:---:|\n'
    for i, dim in enumerate(dims):
        avg_all = np.mean(all_d[dim])
        avg_head = np.mean(head_d[dim]) if head_d[dim] else 0
        diff = avg_head - avg_all
        diff_str = f'+{diff:.1f}' if diff > 0 else f'{diff:.1f}'
        result += f'| {dim_names[i]} | {avg_all:.1f} | {avg_head:.1f} | {diff_str} |\n'
    result += '\n'

    return result, charts


def analyze_security(query):
    """信息安全分析"""
    result = "## 🔒 信息安全分析\n\n"
    charts = []

    sec_cols = {}
    for c_name in columns_info.values():
        for kw in ['DLP', '数据防泄露', '数据安全风险评估']:
            if kw in c_name:
                sec_cols[kw] = c_name

    if sec_cols:
        for label, col in sec_cols.items():
            col_label = re.sub(r'^[\d\(\)\s\.]+', '', col).strip()
            vals = [c['数据'].get(col) for c in companies]
            val_counts = {}
            for v in vals:
                if v is not None and str(v).strip() not in ['(空)', '', 'NaN']:
                    val_counts[str(v)] = val_counts.get(str(v), 0) + 1
            result += f"**{col_label}**：\n"
            for val, count in sorted(val_counts.items(), key=lambda x: x[1], reverse=True):
                result += f"  - {val}：{count} 家\n"
            result += '\n'

    # Data sensitivity
    for c_name in columns_info.values():
        if '数据敏感性' in c_name and '安全管控' in c_name:
            vals = [c['数据'].get(c_name) for c in companies]
            yes = sum(1 for v in vals if v in [1, '1', 2, '2'])
            result += f"**数据敏感性差异化管控**：{yes}/{len(companies)} 家已实施\n\n"
            break

    return result, charts


# ============ Query Router ============

def route_query(query):
    """Route query to appropriate analysis function"""
    query_lower = query.lower()

    # Check for specific company detail
    for c in companies:
        if c['公司简称'] in query and ('详情' in query or '情况' in query or '介绍' in query or '怎么样' in query):
            result, charts = analyze_company_detail(query)
            if result:
                return result, charts

    # Check for company comparison
    company_count = sum(1 for c in companies if c['公司简称'] in query)
    if company_count >= 2:
        return compare_companies(query)

    # Route by topic
    if any(kw in query for kw in ['概览', '总览', '整体', '总体', '概况', '总结']):
        return analyze_overview()

    if any(kw in query for kw in ['投入', '预算', '花费', '经费', '资金']):
        return analyze_investment(query)

    if any(kw in query for kw in ['人员', '员工', '团队', '人数', '人力']):
        return analyze_personnel(query)

    # 头部标杆分析优先匹配
    if any(kw in query for kw in ['头部标杆', '头部公司', '高端水平', '对标', '头部排名']):
        return analyze_head_benchmark(query)

    # 综合排名优先匹配
    if any(kw in query for kw in ['综合排名', '综合实力', '综合得分', '综合评估']):
        return analyze_comprehensive_ranking(query)

    if any(kw in query for kw in ['排名', '排行', 'TOP', 'top', '最高', '最大', '最低', '最小', '前']):
        return analyze_ranking(query)

    if any(kw in query for kw in ['占比', '比例', '多少家', '覆盖率', '普及', '采纳']):
        return analyze_proportion(query)

    if any(kw in query for kw in ['人工智能', 'AI', '大数据', '云原生', '区块链', '高新技术', '新技术']):
        return analyze_tech(query)

    if any(kw in query for kw in ['数据治理', '数据质量', '数据标准', '数据模型', '数据中台', '数据管理']):
        return analyze_data_governance(query)

    if any(kw in query for kw in ['信创', '国产化', '自主创新']):
        return analyze_xinchuang(query)

    if any(kw in query for kw in ['系统', '软件', '平台', '应用']):
        return analyze_system(query)

    if any(kw in query for kw in ['数字化', '渠道', 'APP', '小程序', '客户服务', '线上']):
        return analyze_digital_channel(query)

    if any(kw in query for kw in ['组织', '架构', '部门', '委员会', 'CIO', '治理机构', '决策']):
        return analyze_org(query)

    if any(kw in query for kw in ['基础设施', '云平台', '机房', '服务器', '虚拟化', '公有云']):
        return analyze_infrastructure(query)

    if any(kw in query for kw in ['认证', '资质', 'ISO', 'CMMI', 'DCMM', '证书']):
        return analyze_certification(query)

    if any(kw in query for kw in ['未来', '规划', '方向', '趋势', '3-5年', '三年', '五年']):
        return analyze_future_investment(query)

    if any(kw in query for kw in ['安全', 'DLP', '防泄露', '信息安全']):
        return analyze_security(query)

    # Check for specific company mention (single company) - 优化匹配逻辑
    # 如果查询包含公司名+具体字段，返回该公司该字段的精确值
    for c in companies:
        if c['公司简称'] in query:
            # 提取字段关键词（去掉公司名后的部分）
            remaining = query.replace(c['公司简称'], '').strip()
            
            # 如果没有剩余内容，返回公司详情
            if not remaining or remaining in ['详情', '情况', '介绍', '怎么样', '的']:
                result, charts = analyze_company_detail(query)
                if result:
                    return result, charts
                continue
            
            # 尝试匹配字段 - 支持任意字段
            matched_field = None
            best_score = 0
            
            # 首先尝试精确匹配
            for col_idx, col_name in columns_info.items():
                if remaining == col_name or remaining in col_name:
                    score = len(remaining) / len(col_name) if len(col_name) > 0 else 0
                    if score > best_score:
                        best_score = score
                        matched_field = col_name
            
            # 如果没有精确匹配，尝试模糊匹配
            if not matched_field or best_score < 0.3:
                for col_idx, col_name in columns_info.items():
                    # 检查关键词是否在字段名中
                    if remaining in col_name:
                        score = len(remaining) / len(col_name)
                        if score > best_score:
                            best_score = score
                            matched_field = col_name
                    # 或者字段名中的关键词在查询中
                    elif any(kw in remaining for kw in col_name.split('、')):
                        score = 0.5  # 部分匹配
                        if score > best_score:
                            best_score = score
                            matched_field = col_name
            
            if matched_field and best_score >= 0.2:
                col = get_field_col(matched_field)
                if col:
                    val = c['数据'].get(col)
                    
                    # 构建结果
                    result = f"## 📊 {c['公司简称']} - {matched_field}\n\n"
                    
                    if val is not None and str(val).strip() not in ['(空)', '', 'NaN']:
                        result += f"**{matched_field}**：{val}\n\n"
                    else:
                        result += f"**{matched_field}**：暂无数据\n\n"
                    
                    # 获取行业统计
                    all_vals = [x['数据'].get(col) for x in companies]
                    all_vals_clean = [safe_num(v) for v in all_vals if v is not None and str(v).strip() not in ['(空)', '', 'NaN']]
                    
                    if all_vals_clean:
                        result += f"**行业参考**（共{len(all_vals_clean)}家有效数据）：\n"
                        result += f"- 行业平均：{np.mean(all_vals_clean):.2f}\n"
                        result += f"- 行业最高：{max(all_vals_clean)}\n"
                        result += f"- 行业最低：{min(all_vals_clean)}\n"
                        
                        # 判断该公司在行业中的位置
                        if val is not None and str(val).strip() not in ['(空)', '', 'NaN']:
                            try:
                                val_num = safe_num(val)
                                sorted_vals = sorted(all_vals_clean, reverse=True)
                                rank = sorted_vals.index(val_num) + 1 if val_num in sorted_vals else None
                                if rank:
                                    percentile = (len(sorted_vals) - rank) / len(sorted_vals) * 100
                                    result += f"- **{c['公司简称']}排名**：第{rank}名（前{percentile:.1f}%）\n"
                            except:
                                pass
                    
                    return result, []
            
            # 如果字段匹配失败，返回公司详情
            result, charts = analyze_company_detail(query)
            if result:
                return result, charts

    # Default: try keyword matching
    found_cols = find_columns(query)
    if found_cols:
        result = f"## 🔍 自定义查询结果\n\n"
        result += f"根据您的问题，找到以下相关数据字段（{len(found_cols)}个）：\n\n"
        charts = []

        for col in found_cols[:10]:
            col_label = re.sub(r'^[\d\(\)\s\.]+', '', col).strip()
            vals = [c['数据'].get(col) for c in companies]
            vals_clean = [v for v in vals if v is not None and str(v).strip() not in ['(空)', '', 'NaN']]

            if not vals_clean:
                continue

            # Check if numeric
            numeric_vals = [safe_num(v) for v in vals_clean]
            is_numeric = all(v == 0 or isinstance(v, (int, float)) for v in vals_clean)

            if is_numeric and any(v > 0 for v in numeric_vals):
                num_vals = [v for v in numeric_vals if v > 0]
                result += f"**{col_label}**：\n"
                result += f"- 有效数据：{len(num_vals)} 家\n"
                result += f"- 平均值：{np.mean(num_vals):.1f}\n"
                result += f"- 中位数：{np.median(num_vals):.1f}\n"
                result += f"- 最大值：{max(num_vals)}\n"
                result += f"- 最小值：{min(num_vals)}\n\n"
            else:
                val_counts = {}
                for v in vals_clean:
                    sv = str(v).strip()
                    val_counts[sv] = val_counts.get(sv, 0) + 1
                result += f"**{col_label}**：\n"
                for val, count in sorted(val_counts.items(), key=lambda x: x[1], reverse=True)[:5]:
                    result += f"- {val}：{count} 家\n"
                result += '\n'

        result += '\n💡 提示：您可以尝试更具体的问题，如"科技投入排名TOP10"、"人工智能应用情况"等。'
        return result, charts

    # No match -> 全维度综合分析
    return analyze_all_dimensions(query)

    # 以下代码不再执行（已被全维度分析替代）
    # No match
    help_text = (
        '抱歉，未能理解您的问题。您可以尝试以下类型的提问：\n\n'
        '1. **行业概览**：行业整体情况概览\n'
        '2. **投入分析**：科技投入分析、2024年投入排名TOP10\n'
        '3. **人员分析**：科技团队人员配置、科技人员占比排名\n'
        '4. **占比分析**：有多少家设立了CIO、APP覆盖率\n'
        '5. **技术分析**：人工智能应用情况、信创进展如何\n'
        '6. **系统分析**：业务系统部署情况\n'
        '7. **公司对比**：中信信托 vs 平安信托 vs 华润信托\n'
        '8. **公司详情**：平安信托的科技建设情况\n'
        '9. **组织架构**：治理机构设立情况\n'
        '10. **数据治理**：数据治理现状分析\n'
        '11. **基础设施**：云平台使用情况\n'
        '12. **认证资质**：科技认证获取情况\n'
        '13. **未来规划**：未来3-5年科技投入方向\n'
        '14. **信息安全**：数据安全管控情况'
    )
    return help_text, []


# ============ Flask Routes ============

@app.route('/')
def index():
    # 自动查找index.html
    possible_index_paths = [
        os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'index.html'),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), 'index.html'),
        '/workspace/static/index.html',
    ]
    for index_path in possible_index_paths:
        if os.path.exists(index_path):
            return send_from_directory(os.path.dirname(index_path), 'index.html')
    return "index.html not found. Searched: " + str(possible_index_paths)


# chatbox message handler
@app.route('/api/analyze', methods=['POST'])
def analyze():
    data = request.get_json(silent=True) or {}
    query = str(data.get('query', ''))
    if not query.strip():
        return jsonify({'error': '请输入问题'}), 400
    if len(query) > 2000:
        return jsonify({'error': '问题长度不能超过2000字符'}), 400
    with _analysis_lock:
        result, charts = route_query(query)
    return jsonify({'result': result, 'charts': charts})


@app.route('/api/suggestions')
def suggestions():
    return jsonify({
        'suggestions': [
            '头部标杆分析',
            '综合排名TOP10',
            '行业整体科技建设情况概览',
            '2024年科技投入排名TOP10',
            '科技人员占比排名',
            '人工智能应用情况',
            '大数据应用场景分析',
            '信创转型进展',
            '业务系统部署情况',
            '有多少家设立了CIO',
            '数据治理现状分析',
            '中信信托 vs 平安信托 vs 华润信托',
            '平安信托的科技建设详情',
            '未来3-5年科技投入方向',
            '数字化渠道覆盖情况',
            '科技专项认证获取情况',
            '基础设施架构模式分布',
        ]
    })


# ============ 自定义头部标杆API ============

# 使用Flask app配置存储用户自定义配置（线程安全）
def get_user_head_benchmark():
    """获取用户自定义的头部标杆配置"""
    with _config_lock:
        return current_app.config.get('USER_HEAD_BENCHMARK', None)

def set_user_head_benchmark(config):
    """设置用户自定义的头部标杆配置"""
    with _config_lock:
        current_app.config['USER_HEAD_BENCHMARK'] = config

def clear_user_head_benchmark():
    """清除用户自定义的头部标杆配置"""
    with _config_lock:
        current_app.config['USER_HEAD_BENCHMARK'] = None


@app.route('/api/head-benchmark', methods=['GET'])
def get_head_benchmark():
    """获取当前头部标杆配置"""
    user_config = get_user_head_benchmark()
    
    if user_config is not None:
        # 使用用户自定义的配置
        return jsonify({
            'enabled': True,
            'is_user_defined': True,
            'companies': user_config,
            'all_companies': [{'name': c['公司简称'], 'display_name': c['公司简称']} for c in companies]
        })
    else:
        # 使用系统默认配置
        return jsonify({
            'enabled': HEAD_BENCHMARK_CONFIG.get('enabled', False),
            'is_user_defined': False,
            'companies': HEAD_BENCHMARK_CONFIG.get('companies', []),
            'all_companies': [{'name': c['公司简称'], 'display_name': c['公司简称']} for c in companies]
        })


@app.route('/api/head-benchmark', methods=['POST'])
def set_head_benchmark():
    """设置用户自定义的头部标杆"""
    data = request.get_json()
    if not data or 'companies' not in data:
        return jsonify({'error': '缺少companies参数'}), 400
    
    selected_companies = data['companies']
    if not isinstance(selected_companies, list):
        return jsonify({'error': 'companies必须是数组'}), 400
    selected_companies = [str(name).strip() for name in selected_companies if str(name).strip()]
    
    # 验证公司名是否有效
    valid_names = [c['公司简称'] for c in companies]
    invalid_names = [name for name in selected_companies if name not in valid_names]
    if invalid_names:
        return jsonify({'error': f'无效的公司名: {invalid_names}'}), 400
    
    # 限制数量（建议10家）
    if len(selected_companies) > 15:
        return jsonify({'error': '头部标杆公司数量不能超过15家'}), 400
    
    # 保存用户自定义配置
    user_config = [
        {'name': name, 'display_name': name} for name in selected_companies
    ]
    set_user_head_benchmark(user_config)
    
    return jsonify({
        'success': True,
        'message': f'已设置{len(selected_companies)}家头部标杆公司',
        'companies': user_config
    })


@app.route('/api/head-benchmark', methods=['DELETE'])
def reset_head_benchmark():
    """重置为系统默认头部标杆"""
    clear_user_head_benchmark()
    return jsonify({
        'success': True,
        'message': '已重置为系统默认头部标杆配置'
    })


# ============ 自定义排名维度与权重API ============

# 默认维度配置（八大维度）
DEFAULT_DIMENSIONS = {
    'd1_strategy': {'name': '科技战略定位', 'weight': 0.10, 'enabled': True, 'is_reference': True},
    'd2_resource': {'name': '资源投入与配置', 'weight': 0.20, 'enabled': True, 'is_reference': False},
    'd3_org': {'name': '组织架构与人才培养', 'weight': 0.15, 'enabled': True, 'is_reference': False},
    'd4_infra': {'name': '基础设施架构', 'weight': 0.10, 'enabled': True, 'is_reference': False},
    'd5_xc': {'name': '信创转型', 'weight': 0.10, 'enabled': True, 'is_reference': False},
    'd6_tech': {'name': '高新技术应用', 'weight': 0.15, 'enabled': True, 'is_reference': False},
    'd7_system': {'name': '业务应用系统建设', 'weight': 0.10, 'enabled': True, 'is_reference': False},
    'd8_data': {'name': '数据治理与安全', 'weight': 0.10, 'enabled': True, 'is_reference': False},
}

# 使用Flask app配置存储用户自定义维度配置（线程安全）
def get_user_dimensions():
    """获取用户自定义的维度配置"""
    with _config_lock:
        return current_app.config.get('USER_DIMENSIONS', None)

def set_user_dimensions(config):
    """设置用户自定义的维度配置"""
    with _config_lock:
        current_app.config['USER_DIMENSIONS'] = config

def clear_user_dimensions():
    """清除用户自定义的维度配置"""
    with _config_lock:
        current_app.config['USER_DIMENSIONS'] = None


@app.route('/api/dimensions', methods=['GET'])
def get_dimensions():
    """获取当前维度与权重配置"""
    user_config = get_user_dimensions()
    
    if user_config is not None:
        return jsonify({
            'is_user_defined': True,
            'dimensions': user_config,
            'default_dimensions': DEFAULT_DIMENSIONS
        })
    else:
        return jsonify({
            'is_user_defined': False,
            'dimensions': DEFAULT_DIMENSIONS,
            'default_dimensions': DEFAULT_DIMENSIONS
        })


@app.route('/api/dimensions', methods=['POST'])
def set_dimensions():
    """设置用户自定义维度与权重"""
    data = request.get_json()
    if not data or 'dimensions' not in data:
        return jsonify({'error': '缺少dimensions参数'}), 400
    
    dimensions = data['dimensions']
    if not isinstance(dimensions, dict):
        return jsonify({'error': 'dimensions必须是对象'}), 400
    allowed_keys = set(DEFAULT_DIMENSIONS.keys())
    if set(dimensions.keys()) - allowed_keys:
        return jsonify({'error': '包含未知维度'}), 400
    normalized_dimensions = {}
    for dim_key, default_dim in DEFAULT_DIMENSIONS.items():
        dim = dimensions.get(dim_key, default_dim)
        if not isinstance(dim, dict):
            return jsonify({'error': f'{dim_key}配置无效'}), 400
        try:
            weight = float(dim.get('weight', default_dim['weight']))
        except (TypeError, ValueError):
            return jsonify({'error': f'{dim_key}权重必须是数字'}), 400
        if not 0 <= weight <= 1:
            return jsonify({'error': f'{dim_key}权重必须在0到1之间'}), 400
        normalized_dimensions[dim_key] = {
            'name': default_dim['name'],
            'weight': weight,
            'enabled': bool(dim.get('enabled', default_dim['enabled'])),
            'is_reference': bool(default_dim.get('is_reference', False)),
        }
    dimensions = normalized_dimensions
    
    # 验证维度配置
    enabled_dims = [d for d in dimensions.values() if d.get('enabled', False) and not d.get('is_reference', False)]
    
    if len(enabled_dims) == 0:
        return jsonify({'error': '至少需要启用一个非参考维度'}), 400
    
    # 计算非参考维度的权重总和
    total_weight = sum(d.get('weight', 0) for d in enabled_dims)
    
    if abs(total_weight - 1.0) > 0.001:  # 允许0.001的误差
        return jsonify({'error': f'非参考维度的权重总和必须等于100%，当前为{total_weight*100:.1f}%'}), 400
    
    # 保存用户配置
    set_user_dimensions(dimensions)
    
    return jsonify({
        'success': True,
        'message': f'已设置自定义维度配置，共启用{len(enabled_dims)}个维度',
        'dimensions': dimensions,
        'total_weight': total_weight
    })


@app.route('/api/dimensions', methods=['DELETE'])
def reset_dimensions():
    """重置为默认维度配置"""
    clear_user_dimensions()
    return jsonify({
        'success': True,
        'message': '已重置为默认维度配置'
    })


# ============ 原始数据查询API ============

@app.route('/api/company/<company_name>')
def get_company_data(company_name):
    """获取指定公司的原始数据"""
    for c in companies:
        if c['公司简称'] == company_name:
            return jsonify({
                'success': True,
                'company_name': company_name,
                'data': c['数据']
            })
    return jsonify({'error': '公司不存在'}), 404


@app.route('/api/company/field')
def get_company_field():
    """获取指定公司指定字段的值（使用查询参数）"""
    import urllib.parse
    company_name = urllib.parse.unquote(request.args.get('company', ''))
    field_name = urllib.parse.unquote(request.args.get('field', ''))
    
    if not company_name or not field_name:
        return jsonify({'error': '缺少company或field参数'}), 400
    
    for c in companies:
        if c['公司简称'] == company_name:
            col = get_field_col(field_name)
            if col:
                val = c['数据'].get(col)
                # 获取行业统计
                all_vals = [x['数据'].get(col) for x in companies]
                all_vals_clean = [safe_num(v) for v in all_vals if v is not None and str(v).strip() not in ['(空)', '', 'NaN']]
                return jsonify({
                    'success': True,
                    'company_name': company_name,
                    'field_name': field_name,
                    'value': val,
                    'industry_stats': {
                        'avg': float(np.mean(all_vals_clean)) if all_vals_clean else None,
                        'max': float(max(all_vals_clean)) if all_vals_clean else None,
                        'min': float(min(all_vals_clean)) if all_vals_clean else None,
                        'count': len(all_vals_clean)
                    } if all_vals_clean else None
                })
            return jsonify({'error': f'字段不存在: {field_name}'}), 404
    return jsonify({'error': f'公司不存在: {company_name}'}), 404


@app.route('/api/raw-data')
def get_all_raw_data():
    """获取所有原始数据（用于原始数据查看模块）"""
    # 转换为表格格式
    headers = ['序号', '公司简称'] + list(columns_info.values())
    rows = []
    for i, c in enumerate(companies, 1):
        row = [i, c['公司简称']]
        for col_idx in sorted(columns_info.keys(), key=int):
            col_name = columns_info[col_idx]
            val = c['数据'].get(col_name, '')
            row.append(val)
        rows.append(row)
    
    return jsonify({
        'success': True,
        'headers': headers,
        'rows': rows,
        'total_companies': len(companies),
        'total_fields': len(columns_info)
    })


@app.route('/api/fields')
def get_all_fields():
    """获取所有可用字段列表"""
    fields = []
    for col_idx, col_name in sorted(columns_info.items(), key=lambda x: int(x[0])):
        # 统计该字段的数据分布
        values = [c['数据'].get(col_name) for c in companies]
        non_empty = [v for v in values if v is not None and str(v).strip() not in ['(空)', '', 'NaN']]
        
        # 判断字段类型
        field_type = 'text'
        if any(kw in col_name for kw in ['投入', '金额', '人数', '人数', '比例', '占比', '数量']):
            field_type = 'number'
        elif any(kw in col_name for kw in ['是否', '有无', '是否设立', '是否制定']):
            field_type = 'boolean'
        
        fields.append({
            'id': col_idx,
            'name': col_name,
            'type': field_type,
            'has_data_count': len(non_empty),
            'sample': non_empty[0] if non_empty else None
        })
    
    return jsonify({
        'success': True,
        'fields': fields,
        'total': len(fields)
    })


@app.route('/api/fields/search')
def search_fields():
    """搜索字段"""
    import urllib.parse
    keyword = urllib.parse.unquote(request.args.get('keyword', '')).lower()
    
    if not keyword:
        return jsonify({'error': '缺少keyword参数'}), 400
    
    matched_fields = []
    for col_idx, col_name in columns_info.items():
        if keyword in col_name.lower():
            matched_fields.append({
                'id': col_idx,
                'name': col_name
            })
    
    return jsonify({
        'success': True,
        'keyword': keyword,
        'matched_count': len(matched_fields),
        'fields': matched_fields
    })


@app.route('/api/company/<company_name>/all-fields')
def get_company_all_fields(company_name):
    """获取指定公司的所有字段数据"""
    import urllib.parse
    company_name = urllib.parse.unquote(company_name)
    
    for c in companies:
        if c['公司简称'] == company_name:
            # 返回所有非空字段
            fields_data = []
            for col_idx, col_name in sorted(columns_info.items(), key=lambda x: int(x[0])):
                val = c['数据'].get(col_name)
                if val is not None and str(val).strip() not in ['(空)', '', 'NaN']:
                    fields_data.append({
                        'field_id': col_idx,
                        'field_name': col_name,
                        'value': val
                    })
            
            return jsonify({
                'success': True,
                'company_name': company_name,
                'total_fields': len(fields_data),
                'fields': fields_data
            })
    
    return jsonify({'error': f'公司不存在: {company_name}'}), 404


@app.route('/api/query-smart')
def smart_query():
    """智能查询 - 根据自然语言查询公司和字段"""
    import urllib.parse
    query = urllib.parse.unquote(request.args.get('q', ''))
    
    if not query:
        return jsonify({'error': '缺少q参数'}), 400
    
    # 查找公司名
    target_company = None
    for c in companies:
        if c['公司简称'] in query:
            target_company = c
            break
    
    if not target_company:
        return jsonify({
            'success': False,
            'error': '未识别到公司名',
            'query': query,
            'available_companies': [c['公司简称'] for c in companies[:10]]  # 返回前10个示例
        })
    
    # 从查询中移除公司名，剩下的作为字段关键词
    remaining = query.replace(target_company['公司简称'], '').strip()
    
    # 尝试匹配字段
    matched_field = None
    best_score = 0
    
    for col_idx, col_name in columns_info.items():
        # 计算匹配分数
        score = 0
        if remaining in col_name:
            score = len(remaining) / len(col_name)  # 匹配度越高分数越高
        
        if score > best_score:
            best_score = score
            matched_field = col_name
    
    if matched_field and best_score > 0.3:  # 阈值
        col = get_field_col(matched_field)
        val = target_company['数据'].get(col)
        
        # 获取行业统计
        all_vals = [x['数据'].get(col) for x in companies]
        all_vals_clean = [safe_num(v) for v in all_vals if v is not None and str(v).strip() not in ['(空)', '', 'NaN']]
        
        return jsonify({
            'success': True,
            'query': query,
            'company_name': target_company['公司简称'],
            'field_name': matched_field,
            'value': val,
            'match_score': round(best_score, 2),
            'industry_stats': {
                'avg': float(np.mean(all_vals_clean)) if all_vals_clean else None,
                'max': float(max(all_vals_clean)) if all_vals_clean else None,
                'min': float(min(all_vals_clean)) if all_vals_clean else None,
                'count': len(all_vals_clean)
            } if all_vals_clean else None
        })
    else:
        # 返回该公司所有可用字段供选择
        available_fields = []
        for col_idx, col_name in list(columns_info.items())[:20]:  # 返回前20个
            val = target_company['数据'].get(col_name)
            if val is not None and str(val).strip() not in ['(空)', '', 'NaN']:
                available_fields.append({
                    'field_name': col_name,
                    'value': val
                })
        
        return jsonify({
            'success': False,
            'error': '未找到匹配的字段',
            'query': query,
            'company_name': target_company['公司简称'],
            'suggested_fields': available_fields
        })

# ========== 注册智能卡片蓝图 ==========
from app_smart_cards import register_smart_cards_blueprint
register_smart_cards_blueprint(app)

if __name__ == '__main__':
    os.makedirs('/data/user/work/static', exist_ok=True)
    app.run(host=os.getenv('TRUST_DATA_HOST', '127.0.0.1'), port=5000, debug=False)
