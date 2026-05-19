# -*- coding: utf-8 -*-
"""
智能卡片管理系统
用于管理预制卡片和自定义卡片的智能分析缓存
"""
import json
import os
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

# 缓存文件路径
CACHE_DIR = Path(__file__).parent / "smart_card_cache"
CACHE_FILE = CACHE_DIR / "card_responses.json"
CARDS_CONFIG_FILE = CACHE_DIR / "cards_config.json"

# 确保缓存目录存在
CACHE_DIR.mkdir(exist_ok=True)

# 默认预制卡片配置
DEFAULT_CARDS = [
    {
        "id": "industry_overview",
        "title": "行业概览",
        "icon": "📊",
        "query": "行业整体科技建设情况概览",
        "description": "科技投入趋势、人员占比、CIO设立等核心指标汇总",
        "tags": ["行业概览", "整体情况"],
        "category": "overview"
    },
    {
        "id": "tech_strategy",
        "title": "科技战略定位",
        "icon": "💰",
        "query": "科技战略定位分析",
        "description": "金融科技战略、数字化转型战略、数据治理战略等6项规划发布情况",
        "tags": ["战略规划", "数字化转型"],
        "category": "strategy"
    },
    {
        "id": "resource_investment",
        "title": "资源投入与配置",
        "icon": "💵",
        "query": "科技投入分析",
        "description": "2023-2026年科技投入、人员配置、科技团队/外包团队规模",
        "tags": ["投入排名", "人员配置", "外包团队"],
        "category": "investment"
    },
    {
        "id": "organization",
        "title": "组织架构与人才培养",
        "icon": "🏢",
        "query": "组织架构与治理分析",
        "description": "治理机构设立、科技部门设置、CIO配置、认证资质、人才流动",
        "tags": ["组织架构", "CIO设立", "认证资质"],
        "category": "organization"
    },
    {
        "id": "infrastructure",
        "title": "基础设施架构",
        "icon": "🏗️",
        "query": "基础设施架构模式分布",
        "description": "机房架构模式、服务器虚拟化、桌面虚拟化、公有云平台使用",
        "tags": ["基础设施", "公有云", "虚拟化"],
        "category": "infrastructure"
    },
    {
        "id": "xinchuang",
        "title": "信创转型与进展",
        "icon": "🖥️",
        "query": "信创转型进展",
        "description": "信创进展阶段、信创系统占比、芯片/服务器/操作系统/数据库/中间件品牌选择",
        "tags": ["信创进展", "品牌选择"],
        "category": "xinchuang"
    },
    {
        "id": "high_tech",
        "title": "高新技术应用",
        "icon": "🤖",
        "query": "人工智能应用情况",
        "description": "人工智能、大数据、云原生、区块链四大技术的应用场景与阶段",
        "tags": ["AI应用", "大数据", "云原生", "区块链"],
        "category": "hightech"
    },
    {
        "id": "business_systems",
        "title": "业务应用系统建设",
        "icon": "💻",
        "query": "业务系统部署情况",
        "description": "27类业务系统部署覆盖率、自研/合作/外采比例、未来3-5年投入方向",
        "tags": ["系统部署", "未来方向"],
        "category": "business"
    },
    {
        "id": "digital_channels",
        "title": "数字化客户服务渠道",
        "icon": "📱",
        "query": "数字化渠道覆盖情况",
        "description": "APP/小程序/网站等渠道覆盖、远程面签/智能客服/电子合同等功能",
        "tags": ["渠道覆盖", "APP", "智能客服"],
        "category": "digital"
    },
    {
        "id": "data_governance",
        "title": "数据治理与安全",
        "icon": "🗄️",
        "query": "数据治理现状分析",
        "description": "数据中台建设、数据质量管理、分类分级、数据安全/DLP管控",
        "tags": ["数据治理", "数据安全"],
        "category": "governance"
    }
]

# 默认快捷提问配置
DEFAULT_QUICK_QUESTIONS = [
    {"id": "head_benchmark", "text": "头部标杆分析", "icon": "🏆"},
    {"id": "ranking_top10", "text": "综合排名TOP10", "icon": "📊"},
    {"id": "industry_overview", "text": "行业整体科技建设情况概览", "icon": "📈"},
    {"id": "investment_2024", "text": "2024年科技投入排名TOP10", "icon": "💰"},
    {"id": "tech_personnel", "text": "科技人员占比排名", "icon": "👥"},
    {"id": "ai_application", "text": "人工智能应用情况", "icon": "🤖"},
    {"id": "bigdata", "text": "大数据应用场景分析", "icon": "📊"},
    {"id": "xinchuang_progress", "text": "信创转型进展", "icon": "🖥️"},
    {"id": "systems", "text": "业务系统部署情况", "icon": "💻"},
    {"id": "cio_count", "text": "有多少家设立了CIO", "icon": "🏢"},
    {"id": "data_gov", "text": "数据治理现状分析", "icon": "🗄️"},
    {"id": "company_compare", "text": "中信信托 vs 平安信托 vs 华润信托", "icon": "⚖️"},
    {"id": "pingan_detail", "text": "平安信托的科技建设详情", "icon": "📋"},
    {"id": "future_plan", "text": "未来3-5年科技投入方向", "icon": "🎯"}
]


class SmartCardManager:
    """智能卡片管理器"""
    
    def __init__(self):
        self.responses_cache: Dict[str, Any] = {}
        self.cards_config: Dict[str, Any] = {
            "preset_cards": [],
            "custom_cards": [],
            "quick_questions": []
        }
        self._load_cache()
        self._load_cards_config()
    
    def _load_cache(self):
        """加载缓存的响应数据"""
        if CACHE_FILE.exists():
            try:
                with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                    self.responses_cache = json.load(f)
            except Exception as e:
                print(f"加载缓存失败: {e}")
                self.responses_cache = {}
        else:
            self.responses_cache = {}
    
    def _save_cache(self):
        """保存缓存数据"""
        try:
            with open(CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.responses_cache, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存缓存失败: {e}")
    
    def _load_cards_config(self):
        """加载卡片配置"""
        if CARDS_CONFIG_FILE.exists():
            try:
                with open(CARDS_CONFIG_FILE, 'r', encoding='utf-8') as f:
                    self.cards_config = json.load(f)
            except Exception as e:
                print(f"加载卡片配置失败: {e}")
                self._init_default_config()
        else:
            self._init_default_config()
    
    def _init_default_config(self):
        """初始化默认配置"""
        self.cards_config = {
            "preset_cards": DEFAULT_CARDS,
            "custom_cards": [],
            "quick_questions": DEFAULT_QUICK_QUESTIONS,
            "version": "1.0",
            "last_updated": datetime.now().isoformat()
        }
        self._save_cards_config()
    
    def _save_cards_config(self):
        """保存卡片配置"""
        try:
            self.cards_config["last_updated"] = datetime.now().isoformat()
            with open(CARDS_CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.cards_config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存卡片配置失败: {e}")
    
    def _generate_cache_key(self, query: str, card_id: Optional[str] = None) -> str:
        """生成缓存键"""
        content = f"{card_id or ''}:{query}"
        return hashlib.md5(content.encode()).hexdigest()
    
    # ========== 卡片配置管理 ==========
    
    def get_all_cards(self) -> List[Dict]:
        """获取所有卡片（预制+自定义）"""
        return self.cards_config.get("preset_cards", []) + self.cards_config.get("custom_cards", [])
    
    def get_preset_cards(self) -> List[Dict]:
        """获取预制卡片"""
        return self.cards_config.get("preset_cards", [])
    
    def get_custom_cards(self) -> List[Dict]:
        """获取自定义卡片"""
        return self.cards_config.get("custom_cards", [])
    
    def get_quick_questions(self) -> List[Dict]:
        """获取快捷提问列表"""
        return self.cards_config.get("quick_questions", [])
    
    def add_custom_card(self, title: str, query: str, description: str = "", 
                       icon: str = "📋", tags: List[str] = None) -> Dict:
        """添加自定义卡片"""
        card_id = f"custom_{hashlib.md5(title.encode()).hexdigest()[:8]}"
        card = {
            "id": card_id,
            "title": title,
            "icon": icon,
            "query": query,
            "description": description,
            "tags": tags or [],
            "category": "custom",
            "created_at": datetime.now().isoformat()
        }
        self.cards_config["custom_cards"].append(card)
        self._save_cards_config()
        return card
    
    def update_custom_card(self, card_id: str, **kwargs) -> Optional[Dict]:
        """更新自定义卡片"""
        for card in self.cards_config["custom_cards"]:
            if card["id"] == card_id:
                card.update(kwargs)
                card["updated_at"] = datetime.now().isoformat()
                self._save_cards_config()
                return card
        return None
    
    def delete_custom_card(self, card_id: str) -> bool:
        """删除自定义卡片"""
        original_len = len(self.cards_config["custom_cards"])
        self.cards_config["custom_cards"] = [
            c for c in self.cards_config["custom_cards"] if c["id"] != card_id
        ]
        if len(self.cards_config["custom_cards"]) < original_len:
            self._save_cards_config()
            # 同时清除相关缓存
            self.clear_card_cache(card_id)
            return True
        return False
    
    def add_quick_question(self, text: str, icon: str = "💬") -> Dict:
        """添加快捷提问"""
        question_id = f"qq_{hashlib.md5(text.encode()).hexdigest()[:8]}"
        question = {
            "id": question_id,
            "text": text,
            "icon": icon,
            "created_at": datetime.now().isoformat()
        }
        self.cards_config["quick_questions"].append(question)
        self._save_cards_config()
        return question
    
    def delete_quick_question(self, question_id: str) -> bool:
        """删除快捷提问"""
        original_len = len(self.cards_config["quick_questions"])
        self.cards_config["quick_questions"] = [
            q for q in self.cards_config["quick_questions"] if q["id"] != question_id
        ]
        if len(self.cards_config["quick_questions"]) < original_len:
            self._save_cards_config()
            return True
        return False
    
    # ========== 缓存响应管理 ==========
    
    def get_cached_response(self, query: str, card_id: Optional[str] = None) -> Optional[Dict]:
        """获取缓存的响应"""
        cache_key = self._generate_cache_key(query, card_id)
        cached = self.responses_cache.get(cache_key)
        if cached:
            return {
                "result": cached["result"],
                "charts": cached.get("charts", []),
                "cached": True,
                "cached_at": cached.get("cached_at"),
                "card_id": card_id
            }
        return None
    
    def cache_response(self, query: str, result: str, charts: List[str] = None, 
                      card_id: Optional[str] = None):
        """缓存响应"""
        cache_key = self._generate_cache_key(query, card_id)
        self.responses_cache[cache_key] = {
            "query": query,
            "result": result,
            "charts": charts or [],
            "cached_at": datetime.now().isoformat(),
            "card_id": card_id
        }
        self._save_cache()
    
    def clear_card_cache(self, card_id: str):
        """清除特定卡片的缓存"""
        keys_to_delete = []
        for key, value in self.responses_cache.items():
            if value.get("card_id") == card_id:
                keys_to_delete.append(key)
        for key in keys_to_delete:
            del self.responses_cache[key]
        if keys_to_delete:
            self._save_cache()
    
    def clear_all_cache(self):
        """清除所有缓存"""
        self.responses_cache = {}
        self._save_cache()
    
    def get_cache_stats(self) -> Dict:
        """获取缓存统计"""
        total = len(self.responses_cache)
        preset_cached = sum(1 for v in self.responses_cache.values() 
                          if v.get("card_id") and not v.get("card_id", "").startswith("custom_"))
        custom_cached = sum(1 for v in self.responses_cache.values() 
                          if v.get("card_id", "").startswith("custom_"))
        return {
            "total_cached": total,
            "preset_cached": preset_cached,
            "custom_cached": custom_cached,
            "preset_cards_count": len(self.cards_config.get("preset_cards", [])),
            "custom_cards_count": len(self.cards_config.get("custom_cards", [])),
            "quick_questions_count": len(self.cards_config.get("quick_questions", []))
        }
    
    def regenerate_card_response(self, card_id: str, agent_func) -> Optional[Dict]:
        """重新生成卡片响应"""
        # 查找卡片
        card = None
        for c in self.get_all_cards():
            if c["id"] == card_id:
                card = c
                break
        
        if not card:
            return None
        
        # 清除旧缓存
        self.clear_card_cache(card_id)
        
        # 调用Agent生成新响应
        try:
            import asyncio
            result = asyncio.run(agent_func(card["query"]))
            
            # 缓存新响应
            self.cache_response(
                query=card["query"],
                result=result,
                charts=[],  # 图表由前端生成
                card_id=card_id
            )
            
            return {
                "result": result,
                "charts": [],
                "cached": False,
                "card_id": card_id
            }
        except Exception as e:
            return {
                "error": str(e),
                "card_id": card_id
            }


# 全局管理器实例
_card_manager = None

def get_card_manager() -> SmartCardManager:
    """获取卡片管理器单例"""
    global _card_manager
    if _card_manager is None:
        _card_manager = SmartCardManager()
    return _card_manager
