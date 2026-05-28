/**
 * 智能卡片系统前端模块
 * 为原有页面添加智能卡片分析功能
 */

// 智能卡片管理器
class SmartCardManager {
    constructor() {
        this.cards = [];
        this.quickQuestions = [];
        this.cacheStats = null;
        this.currentCardId = null;
    }

    // 初始化：加载所有卡片配置
    async init() {
        try {
            const response = await fetch('/api/cards');
            const data = await response.json();
            this.cards = [...data.preset_cards, ...data.custom_cards];
            this.quickQuestions = data.quick_questions;
            console.log('✅ 智能卡片系统已加载', this.cards.length, '个卡片');
            return true;
        } catch (e) {
            console.error('加载卡片失败:', e);
            return false;
        }
    }

    // 分析卡片（带缓存）
    async analyzeCard(cardId, forceRefresh = false) {
        const card = this.cards.find(c => c.id === cardId);
        if (!card) {
            throw new Error('卡片不存在');
        }

        this.currentCardId = cardId;

        // 显示加载状态
        showTypingIndicator(`正在分析「${card.title}」...`);

        try {
            const response = await fetch(`/api/cards/${cardId}/analyze`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ force_refresh: forceRefresh })
            });

            const data = await response.json();
            hideTypingIndicator();

            if (data.error) {
                throw new Error(data.error);
            }

            return {
                ...data,
                card: card,
                isCached: data.cached
            };
        } catch (e) {
            hideTypingIndicator();
            throw e;
        }
    }

    // 分析快捷提问
    async analyzeQuickQuestion(questionId) {
        const question = this.quickQuestions.find(q => q.id === questionId);
        if (!question) {
            throw new Error('问题不存在');
        }

        showTypingIndicator(`正在分析「${question.text}」...`);

        try {
            const response = await fetch(`/api/quick-questions/${questionId}/analyze`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });

            const data = await response.json();
            hideTypingIndicator();

            if (data.error) {
                throw new Error(data.error);
            }

            return {
                ...data,
                question: question,
                isCached: data.cached
            };
        } catch (e) {
            hideTypingIndicator();
            throw e;
        }
    }

    // 重新生成卡片分析
    async regenerateCard(cardId) {
        showTypingIndicator('正在重新生成分析...');

        try {
            const response = await fetch(`/api/cards/${cardId}/regenerate`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });

            const data = await response.json();
            hideTypingIndicator();

            if (data.error) {
                throw new Error(data.error);
            }

            const card = this.cards.find(c => c.id === cardId);
            return { ...data, card };
        } catch (e) {
            hideTypingIndicator();
            throw e;
        }
    }

    // 获取缓存统计
    async getCacheStats() {
        try {
            const response = await fetch('/api/cache/stats');
            this.cacheStats = await response.json();
            return this.cacheStats;
        } catch (e) {
            console.error('获取缓存统计失败:', e);
            return null;
        }
    }

    // 清除缓存
    async clearCache(cardId = null) {
        try {
            const response = await fetch('/api/cache/clear', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ card_id: cardId })
            });
            return await response.json();
        } catch (e) {
            console.error('清除缓存失败:', e);
            return null;
        }
    }

    // 批量初始化所有卡片缓存
    async initAllCardsCache() {
        showTypingIndicator('正在批量初始化所有卡片分析...');

        try {
            const response = await fetch('/api/cards/init-cache', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });

            const data = await response.json();
            hideTypingIndicator();
            return data;
        } catch (e) {
            hideTypingIndicator();
            throw e;
        }
    }

    // 添加自定义卡片
    async addCustomCard(title, query, description, icon, tags) {
        try {
            const response = await fetch('/api/cards/custom', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ title, query, description, icon, tags })
            });

            const data = await response.json();
            if (data.success) {
                this.cards.push(data.card);
            }
            return data;
        } catch (e) {
            console.error('添加卡片失败:', e);
            return { error: e.message };
        }
    }

    // 删除自定义卡片
    async deleteCustomCard(cardId) {
        try {
            const response = await fetch(`/api/cards/custom/${cardId}`, {
                method: 'DELETE'
            });

            const data = await response.json();
            if (data.success) {
                this.cards = this.cards.filter(c => c.id !== cardId);
            }
            return data;
        } catch (e) {
            console.error('删除卡片失败:', e);
            return { error: e.message };
        }
    }
}

// 全局卡片管理器实例
const smartCardManager = new SmartCardManager();

// ========== UI增强函数 ==========

// 显示智能分析结果
function displaySmartAnalysis(data, isQuickQuestion = false) {
    const item = isQuickQuestion ? data.question : data.card;
    const title = item.title || item.text;
    const icon = item.icon || '🤖';

    // 构建结果HTML
    let resultHtml = `
        <div class="smart-analysis-header">
            <div class="smart-analysis-title">
                <span class="smart-analysis-icon">${escapeHtml(icon)}</span>
                <span>${escapeHtml(title)}</span>
                ${data.isCached ? '<span class="cache-badge">已缓存</span>' : '<span class="fresh-badge">实时生成</span>'}
            </div>
            <div class="smart-analysis-actions">
                <button class="smart-action-btn" onclick="regenerateCurrentCard()" title="重新生成">
                    🔄
                </button>
                <button class="smart-action-btn" onclick="copyAnalysisResult()" title="复制结果">
                    📋
                </button>
            </div>
        </div>
        <div class="smart-analysis-content">
            ${formatAnalysisResult(data.result)}
        </div>
    `;

    // 添加消息到聊天区
    addMessage(resultHtml, false);
}

// 格式化分析结果
function formatAnalysisResult(result) {
    if (typeof marked !== 'undefined') {
        const rendered = marked.parse(result, { breaks: true, gfm: true });
        return typeof sanitizeHtml === 'function' ? sanitizeHtml(rendered) : rendered;
    }
    // 将Markdown风格的格式转换为HTML (备用方案)
    let formatted = escapeHtml(result)
        .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
        .replace(/\n\n/g, '</p><p>')
        .replace(/\n/g, '<br>');

    const html = `<p>${formatted}</p>`;
    return typeof sanitizeHtml === 'function' ? sanitizeHtml(html) : html;
}

// 显示加载指示器
function showTypingIndicator(message = 'AI正在思考...') {
    const existing = document.querySelector('.typing-indicator-wrapper');
    if (existing) existing.remove();

    const div = document.createElement('div');
    div.className = 'message message-assistant typing-indicator-wrapper';
    div.innerHTML = `
        <div class="avatar">🤖</div>
        <div class="bubble">
            <div class="typing-message">${escapeHtml(message)}</div>
            <div class="typing-indicator">
                <span></span><span></span><span></span>
            </div>
        </div>
    `;
    chatMessages.appendChild(div);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

// 隐藏加载指示器
function hideTypingIndicator() {
    const indicator = document.querySelector('.typing-indicator-wrapper');
    if (indicator) {
        indicator.remove();
    }
}

// 重新生成当前卡片
// 创建智能分析的流式占位占点消息气泡
function createSmartAnalysisPlaceholder(item, isQuickQuestion = false) {
    const title = item.title || item.text;
    const icon = item.icon || '🤖';

    const welcomeEl = typeof welcome !== 'undefined' ? welcome : document.getElementById('welcome');
    if (welcomeEl) welcomeEl.style.display = 'none';

    const catalogSection = document.getElementById('catalogSection');
    if (catalogSection) catalogSection.style.display = 'none';

    const container = typeof chatMessages !== 'undefined' ? chatMessages : document.getElementById('chatMessages');

    const div = document.createElement('div');
    div.className = 'message message-assistant';
    
    div.innerHTML = `
        <div class="avatar">🤖</div>
        <div class="bubble">
            <div class="smart-analysis-header">
                <div class="smart-analysis-title">
                    <span class="smart-analysis-icon">${escapeHtml(icon)}</span>
                    <span>${escapeHtml(title)}</span>
                    <span class="badge-placeholder"></span>
                </div>
                <div class="smart-analysis-actions">
                    <button class="smart-action-btn" onclick="regenerateCurrentCard()" title="重新生成">
                        🔄
                    </button>
                    <button class="smart-action-btn" onclick="copyAnalysisResult()" title="复制结果">
                        📋
                    </button>
                </div>
            </div>
            <div class="smart-analysis-content">
                <div class="typing-indicator" style="margin: 10px 0;">
                    <span></span><span></span><span></span>
                </div>
            </div>
        </div>
    `;

    container.appendChild(div);
    container.scrollTop = container.scrollHeight;

    return {
        messageDiv: div,
        contentDiv: div.querySelector('.smart-analysis-content'),
        badgePlaceholder: div.querySelector('.badge-placeholder')
    };
}

// 流式获取智能分析结果并实时渲染
async function streamSmartAnalysis(endpoint, payload, item, isQuickQuestion = false) {
    const placeholder = createSmartAnalysisPlaceholder(item, isQuickQuestion);
    const contentDiv = placeholder.contentDiv;
    const badgePlaceholder = placeholder.badgePlaceholder;
    const container = typeof chatMessages !== 'undefined' ? chatMessages : document.getElementById('chatMessages');
    
    let fullContent = "";
    let pendingBuffer = "";
    let renderedCharts = [];
    let badgeSet = false;

    const renderContent = () => {
        const chartHtml = renderedCharts.map(chartSrc =>
            `<div class="chart-container"><img src="${chartSrc}" alt="分析图表" onclick="window.open(this.src)"></div>`
        ).join('');
        contentDiv.innerHTML = formatAnalysisResult(fullContent) + chartHtml;
        container.scrollTop = container.scrollHeight;
    };

    try {
        const response = await fetch(endpoint, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (!response.ok) {
            throw new Error(`HTTP 错误！状态码: ${response.status}`);
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            pendingBuffer += decoder.decode(value, { stream: true });
            const lines = pendingBuffer.split('\n');
            pendingBuffer = lines.pop() || '';

            for (const line of lines) {
                if (line.trim().startsWith('data: ')) {
                    try {
                        const data = JSON.parse(line.trim().substring(6));
                        if (data.error) {
                            contentDiv.innerHTML = `<span style="color:#c5221f">分析失败: ${escapeHtml(data.error)}</span>`;
                            return;
                        }
                        
                        // 动态设置缓存/实时生成徽章
                        if (!badgeSet) {
                            const isCached = data.cached;
                            badgePlaceholder.innerHTML = isCached 
                                ? '<span class="cache-badge">已缓存</span>' 
                                : '<span class="fresh-badge">实时生成</span>';
                            badgeSet = true;
                        }

                        if (data.content) {
                            fullContent += data.content;
                            renderContent();
                        }

                        if (data.chart) {
                            renderedCharts.push(data.chart);
                            renderContent();
                        }

                        if (Array.isArray(data.charts)) {
                            renderedCharts.push(...data.charts.filter(Boolean));
                            renderContent();
                        }
                    } catch (e) {
                        console.error("解析流数据出错", e);
                    }
                }
            }
        }

        if (pendingBuffer.trim().startsWith('data: ')) {
            try {
                const data = JSON.parse(pendingBuffer.trim().substring(6));
                if (data.content) {
                    fullContent += data.content;
                }
                if (data.chart) {
                    renderedCharts.push(data.chart);
                }
                if (Array.isArray(data.charts)) {
                    renderedCharts.push(...data.charts.filter(Boolean));
                }
                renderContent();
            } catch (e) {
                console.error("解析流数据出错", e);
            }
        }
    } catch (e) {
        console.error("流式读取失败:", e);
        contentDiv.innerHTML = `<span style="color:#c5221f">分析失败: ${escapeHtml(e.message)}</span>`;
    }
}

// 重新生成当前卡片
async function regenerateCurrentCard() {
    if (!smartCardManager.currentCardId) {
        alert('请先选择一个卡片');
        return;
    }

    const card = smartCardManager.cards.find(c => c.id === smartCardManager.currentCardId);
    if (!card) {
        alert('未找到当前卡片配置');
        return;
    }

    try {
        await streamSmartAnalysis(`/api/cards/${card.id}/analyze/stream`, { force_refresh: true }, card, false);
    } catch (e) {
        addMessage(`<p style="color: #c5221f;">重新生成失败: ${escapeHtml(e.message)}</p>`, false);
    }
}

// 复制分析结果
function copyAnalysisResult() {
    const lastBubble = document.querySelector('.message-assistant:last-child .bubble');
    if (lastBubble) {
        const text = lastBubble.innerText;
        navigator.clipboard.writeText(text).then(() => {
            alert('已复制到剪贴板');
        });
    }
}

// ========== 重写原有函数 ==========

// 重写askQuestion函数，支持智能卡片
const originalAskQuestion = window.askQuestion;
window.askQuestion = async function(text, cardId = null) {
    // 如果提供了cardId，使用智能卡片流式分析
    if (cardId) {
        try {
            queryInput.value = text;
            addMessage(text, true);

            const card = smartCardManager.cards.find(c => c.id === cardId);
            if (!card) {
                throw new Error('卡片不存在');
            }
            smartCardManager.currentCardId = cardId;

            await streamSmartAnalysis(`/api/cards/${cardId}/analyze/stream`, {}, card, false);
        } catch (e) {
            addMessage(`<p style="color: #c5221f;">分析失败: ${escapeHtml(e.message)}</p>`, false);
        }
    } else {
        // 原有逻辑
        queryInput.value = text;
        sendMessage();
    }
};

// 快捷提问点击处理
async function askQuickQuestion(questionId, text) {
    try {
        queryInput.value = text;
        addMessage(text, true);

        const question = smartCardManager.quickQuestions.find(q => q.id === questionId);
        if (!question) {
            throw new Error('问题不存在');
        }

        await streamSmartAnalysis(`/api/quick-questions/${questionId}/analyze/stream`, {}, question, true);
    } catch (e) {
        addMessage(`<p style="color: #c5221f;">分析失败: ${escapeHtml(e.message)}</p>`, false);
    }
}

// ========== 初始化 ==========

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', async function() {
    // 初始化智能卡片管理器
    await smartCardManager.init();

    // 更新快捷提问列表，添加点击事件
    updateQuickQuestionsList();

    // 更新卡片点击事件
    updateCardClickHandlers();

    console.log('✅ 智能卡片系统初始化完成');
});

// 更新快捷提问列表
function updateQuickQuestionsList() {
    const container = document.getElementById('suggestions');
    if (!container) return;

    const questions = smartCardManager.quickQuestions;
    container.innerHTML = '';
    questions.slice(0, 8).forEach(q => {
        const item = document.createElement('div');
        item.className = 'suggestion-item';
        item.onclick = () => askQuickQuestion(q.id, q.text);

        const icon = document.createElement('span');
        icon.className = 'icon';
        icon.textContent = q.icon || '';
        item.appendChild(icon);
        item.appendChild(document.createTextNode(` ${q.text || ''}`));
        container.appendChild(item);
    });
}

// 更新卡片点击处理器
function updateCardClickHandlers() {
    // 只有显式声明 data-card-id 的目录卡片才启用智能分析。
    const cards = document.querySelectorAll('.catalog-card');
    cards.forEach(card => {
        const cardId = card.dataset.cardId;
        if (!cardId) return;

        const cardData = smartCardManager.cards.find(c => c.id === cardId);
        if (cardData) {
            card.onclick = () => askQuestion(cardData.query, cardData.id);
            updateCardCacheIndicator(card, cardData.id);
        }
    });
}

// 更新卡片缓存状态指示
async function updateCardCacheIndicator(cardElement, cardId) {
    // 检查是否有缓存
    const stats = await smartCardManager.getCacheStats();
    // 这里可以添加视觉指示，比如小圆点表示已缓存
}

// HTML转义函数
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// ========== 管理面板功能 ==========

// 显示缓存管理面板
function showCacheManager() {
    const panel = document.createElement('div');
    panel.className = 'cache-manager-panel';
    panel.innerHTML = `
        <div class="cache-manager-overlay" onclick="closeCacheManager()"></div>
        <div class="cache-manager-content">
            <div class="cache-manager-header">
                <h3>智能卡片缓存管理</h3>
                <button onclick="closeCacheManager()">✕</button>
            </div>
            <div class="cache-manager-body">
                <div class="cache-stats" id="cacheStats">加载中...</div>
                <div class="cache-actions">
                    <button onclick="initAllCards()">批量初始化所有卡片</button>
                    <button onclick="clearAllCache()">清除所有缓存</button>
                </div>
            </div>
        </div>
    `;
    document.body.appendChild(panel);

    // 加载统计
    loadCacheStats();
}

// 关闭缓存管理面板
function closeCacheManager() {
    const panel = document.querySelector('.cache-manager-panel');
    if (panel) panel.remove();
}

// 加载缓存统计
async function loadCacheStats() {
    const stats = await smartCardManager.getCacheStats();
    const container = document.getElementById('cacheStats');
    if (container && stats) {
        container.innerHTML = `
            <div class="stat-row">
                <span>预制卡片:</span> <strong>${stats.preset_cards_count}</strong>
            </div>
            <div class="stat-row">
                <span>自定义卡片:</span> <strong>${stats.custom_cards_count}</strong>
            </div>
            <div class="stat-row">
                <span>已缓存分析:</span> <strong>${stats.total_cached}</strong>
                (预制:${stats.preset_cached}, 自定义:${stats.custom_cached})
            </div>
            <div class="stat-row">
                <span>快捷提问:</span> <strong>${stats.quick_questions_count}</strong>
            </div>
        `;
    }
}

// 批量初始化所有卡片
async function initAllCards() {
    try {
        const data = await smartCardManager.initAllCardsCache();
        alert(`初始化完成! 成功:${data.successful}, 跳过:${data.skipped}, 失败:${data.failed}`);
        loadCacheStats();
    } catch (e) {
        alert('初始化失败: ' + e.message);
    }
}

// 清除所有缓存
async function clearAllCache() {
    if (!confirm('确定要清除所有缓存吗?')) return;

    try {
        await smartCardManager.clearCache();
        alert('缓存已清除');
        loadCacheStats();
    } catch (e) {
        alert('清除失败: ' + e.message);
    }
}
