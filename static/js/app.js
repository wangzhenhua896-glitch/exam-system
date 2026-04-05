/**
 * AI Grading System - Frontend Application
 */

class GradingApp {
    constructor() {
        this.apiUrl = window.location.origin;
        this.currentPage = 'single';
        this.history = [];
        
        this.init();
    }

    init() {
        this.bindEvents();
        this.loadModels();
        this.loadHistory();
    }

    // 绑定事件
    bindEvents() {
        // 导航切换
        document.querySelectorAll('.nav-item').forEach(item => {
            item.addEventListener('click', (e) => {
                e.preventDefault();
                const page = item.dataset.page;
                this.switchPage(page);
            });
        });

        // 评分按钮
        document.getElementById('grade-btn')?.addEventListener('click', () => {
            this.gradeAnswer();
        });

        // 批量测试按钮
        document.getElementById('batch-test-btn')?.addEventListener('click', () => {
            this.runBatchTest();
        });

        // 验证按钮
        document.getElementById('run-validation-btn')?.addEventListener('click', () => {
            this.runValidation();
        });

        // 调优按钮
        document.getElementById('start-tuning-btn')?.addEventListener('click', () => {
            this.startTuning();
        });

        // 保存配置按钮
        document.getElementById('save-config-btn')?.addEventListener('click', () => {
            this.saveConfig();
        });

        // 清空历史按钮
        document.getElementById('clear-history-btn')?.addEventListener('click', () => {
            this.clearHistory();
        });
    }

    // 切换页面
    switchPage(page) {
        this.currentPage = page;
        
        document.querySelectorAll('.nav-item').forEach(item => {
            item.classList.toggle('active', item.dataset.page === page);
        });

        document.querySelectorAll('.page').forEach(p => {
            p.classList.toggle('active', p.id === `page-${page}`);
        });

        const titles = {
            single: '单题评分',
            batch: '批量测试',
            validation: '规则验证',
            tuning: '自动调优',
            config: '评分配置',
            history: '历史记录'
        };
        document.getElementById('page-title').textContent = titles[page] || page;

        // 加载页面特定数据
        if (page === 'validation') {
            this.loadDatasetInfo();
        }
    }

    // 加载模型列表
    async loadModels() {
        try {
            const response = await fetch(`${this.apiUrl}/api/grading/models`);
            const data = await response.json();
            
            if (data.success) {
                this.renderModels(data.models);
                document.querySelector('.model-count').textContent = 
                    `${data.enabled_count} 个模型可用`;
            }
        } catch (error) {
            console.error('加载模型失败:', error);
        }
    }

    // 加载数据集信息
    async loadDatasetInfo() {
        try {
            const response = await fetch(`${this.apiUrl}/api/validation/dataset`);
            const data = await response.json();
            
            if (data.success) {
                document.getElementById('info-dataset-name').textContent = data.dataset.name;
                document.getElementById('info-question-count').textContent = data.dataset.question_count;
                document.getElementById('info-test-count').textContent = data.dataset.test_item_count;
                document.getElementById('info-max-score').textContent = data.dataset.max_score;
            }
        } catch (error) {
            console.error('加载数据集信息失败:', error);
        }
    }

    // 运行验证
    async runValidation() {
        const strategy = document.getElementById('validation-strategy').value;
        const sampleCount = parseInt(document.getElementById('validation-sample-count').value);

        const btn = document.getElementById('run-validation-btn');
        btn.disabled = true;
        btn.innerHTML = '<span>⏳</span><span>验证中...</span>';

        document.getElementById('validation-empty').style.display = 'none';
        document.getElementById('validation-result').style.display = 'none';

        try {
            const response = await fetch(`${this.apiUrl}/api/validation/run`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    strategy,
                    sample_count: sampleCount,
                })
            });

            const data = await response.json();

            if (data.success) {
                this.renderValidationReport(data.report);
                this.showToast('验证完成', 'success');
            } else {
                this.showToast(data.error || '验证失败', 'error');
            }
        } catch (error) {
            this.showToast('验证失败：' + error.message, 'error');
        } finally {
            btn.disabled = false;
            btn.innerHTML = '<span>✅</span><span>开始验证</span>';
        }
    }

    // 渲染验证报告
    renderValidationReport(report) {
        document.getElementById('validation-result').style.display = 'block';
        
        // 统计卡片
        document.getElementById('val-accuracy').textContent = (report.accuracy * 100).toFixed(1) + '%';
        document.getElementById('val-mean-error').textContent = report.mean_error.toFixed(2);
        document.getElementById('val-max-error').textContent = report.max_error.toFixed(2);
        document.getElementById('val-correlation').textContent = report.correlation.toFixed(3);
        document.getElementById('val-success').textContent = report.success_count;
        document.getElementById('val-failed').textContent = report.failed_count;

        // 详细结果表格
        const tbody = document.getElementById('validation-results-body');
        tbody.innerHTML = report.item_results.map(item => `
            <tr>
                <td class="validation-question" title="${item.question}">${item.question}</td>
                <td>${item.description}</td>
                <td>${item.expected_score}</td>
                <td>${item.actual_score}</td>
                <td>${item.error.toFixed(2)}</td>
                <td>${(item.confidence * 100).toFixed(0)}%</td>
                <td>
                    <span class="validation-status ${item.is_acceptable ? 'success' : 'error'}">
                        ${item.is_acceptable ? '✓ 通过' : '✗ 失败'}
                    </span>
                </td>
            </tr>
        `).join('');
    }

    // 开始调优
    async function startTuning() {
        const maxIterations = parseInt(document.getElementById('tuning-max-iterations').value);
        const targetAccuracy = parseInt(document.getElementById('tuning-target-accuracy').value) / 100;
        const targetCorrelation = parseFloat(document.getElementById('tuning-target-correlation').value);
        const strategy = document.getElementById('tuning-strategy').value;

        const btn = document.getElementById('start-tuning-btn');
        btn.disabled = true;
        btn.innerHTML = '<span>⏳</span><span>调优中...</span>';

        document.getElementById('tuning-empty').style.display = 'none';
        document.getElementById('tuning-result').style.display = 'none';
        document.getElementById('tuning-progress').style.display = 'block';

        try {
            const response = await fetch(`${this.apiUrl}/api/tuning/start`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    max_iterations: maxIterations,
                    target_accuracy: targetAccuracy,
                    target_correlation: targetCorrelation,
                    strategy: strategy,
                    sample_count: 3,
                })
            });

            const data = await response.json();

            if (data.success) {
                this.renderTuningReport(data.report);
                this.showToast('调优完成', 'success');
            } else {
                this.showToast(data.error || '调优失败', 'error');
            }
        } catch (error) {
            this.showToast('调优失败：' + error.message, 'error');
        } finally {
            btn.disabled = false;
            btn.innerHTML = '<span>🎯</span><span>开始调优</span>';
            document.getElementById('tuning-progress').style.display = 'none';
        }
    }

    // 渲染调优报告
    renderTuningReport(report) {
        document.getElementById('tuning-result').style.display = 'block';
        
        // 统计卡片
        document.getElementById('tuning-success').textContent = report.success ? '✓ 是' : '✗ 否';
        document.getElementById('tuning-success').style.color = report.success ? 'var(--accent-success)' : 'var(--accent-danger)';
        document.getElementById('tuning-total-iterations').textContent = report.total_iterations;
        document.getElementById('tuning-best-iteration').textContent = report.best_iteration;
        document.getElementById('tuning-best-accuracy').textContent = (report.best_accuracy * 100).toFixed(1) + '%';
        document.getElementById('tuning-best-correlation').textContent = report.best_correlation.toFixed(3);
        document.getElementById('tuning-best-error').textContent = report.best_mean_error.toFixed(2);

        // 迭代历史表格
        const tbody = document.getElementById('tuning-history-body');
        tbody.innerHTML = report.steps.map(step => `
            <tr>
                <td>${step.iteration}</td>
                <td>${step.temperature.toFixed(2)}</td>
                <td>${(step.accuracy * 100).toFixed(1)}%</td>
                <td>${step.correlation.toFixed(3)}</td>
                <td>${step.mean_error.toFixed(2)}</td>
                <td>${step.max_error.toFixed(2)}</td>
                <td>
                    <span class="tuning-improved ${step.is_improved ? 'yes' : 'no'}">
                        ${step.is_improved ? '✓ 是' : '✗ 否'}
                    </span>
                </td>
                <td>
                    <span class="tuning-target-met ${step.is_target_met ? 'yes' : 'no'}">
                        ${step.is_target_met ? '✓ 是' : '✗ 否'}
                    </span>
                </td>
            </tr>
        `).join('');
    }

    // 渲染模型列表
    renderModels(models) {
        const container = document.getElementById('models-list');
        if (!container) return;

        const icons = {
            qwen: '🤖',
            glm: '🧠',
            minimax: '✨',
            ernie: '💡'
        };

        container.innerHTML = models.map(model => `
            <div class="model-item">
                <div class="model-info">
                    <span class="model-icon">${icons[model.provider] || '🤖'}</span>
                    <div>
                        <div class="model-name">${model.model_name}</div>
                        <div class="model-provider">${model.provider}</div>
                    </div>
                </div>
                <span class="model-status-badge ${model.enabled ? 'enabled' : 'disabled'}">
                    ${model.enabled ? '已启用' : '已禁用'}
                </span>
            </div>
        `).join('');
    }

    // 评分
    async gradeAnswer() {
        const question = document.getElementById('question').value.trim();
        const answer = document.getElementById('answer').value.trim();
        const maxScore = parseFloat(document.getElementById('max-score').value);
        const sampleCount = parseInt(document.getElementById('sample-count').value);
        const strategy = document.getElementById('strategy').value;

        if (!question || !answer) {
            this.showToast('请填写题目和答案', 'error');
            return;
        }

        const btn = document.getElementById('grade-btn');
        btn.disabled = true;
        btn.innerHTML = '<span>⏳</span><span>评分中...</span>';

        try {
            const response = await fetch(`${this.apiUrl}/api/grading/single`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    question,
                    answer,
                    max_score: maxScore,
                    sample_count: sampleCount,
                    strategy,
                    rubric: {}
                })
            });

            const data = await response.json();

            if (data.success) {
                this.renderResult(data.result, data.elapsed);
                this.addToHistory(question, answer, data.result);
                this.showToast('评分完成', 'success');
            } else {
                this.showToast(data.error || '评分失败', 'error');
            }
        } catch (error) {
            this.showToast('评分失败：' + error.message, 'error');
        } finally {
            btn.disabled = false;
            btn.innerHTML = '<span>🚀</span><span>开始评分</span>';
        }
    }

    // 渲染结果
    renderResult(result, elapsed) {
        const container = document.getElementById('result-container');
        if (!container) return;

        container.innerHTML = `
            <div class="result-card">
                <div class="result-header">
                    <div class="result-score">${result.final_score} 分</div>
                    <div class="result-confidence">
                        <span>🎯</span>
                        <span>置信度：${(result.confidence * 100).toFixed(1)}%</span>
                    </div>
                </div>
                
                ${result.warning ? `<div class="result-warning">${result.warning}</div>` : ''}
                
                <div class="result-reasoning">
                    <strong>评分理由：</strong>
                    <p>${result.reasoning}</p>
                </div>

                <div class="result-meta">
                    <span>策略：${result.strategy}</span>
                    <span>耗时：${elapsed.toFixed(2)}s</span>
                </div>

                <div class="model-scores">
                    <h3>各模型评分</h3>
                    ${result.model_scores.map(m => `
                        <div class="model-score-item">
                            <span class="model-name">${m.model}</span>
                            <span class="model-score">${m.score} 分 (${(m.confidence * 100).toFixed(0)}%)</span>
                        </div>
                    `).join('')}
                </div>
            </div>
        `;
    }

    // 批量测试
    async runBatchTest() {
        const testCount = parseInt(document.getElementById('test-count').value);
        const sampleCount = parseInt(document.getElementById('batch-sample-count').value);
        const strategy = document.getElementById('batch-strategy').value;

        const btn = document.getElementById('batch-test-btn');
        btn.disabled = true;
        btn.innerHTML = '<span>⏳</span><span>测试中...</span>';

        const progressContainer = document.getElementById('progress-container');
        const progressFill = document.getElementById('progress-fill');
        const progressText = document.getElementById('progress-text');
        progressContainer.style.display = 'block';

        try {
            const response = await fetch(`${this.apiUrl}/api/batch/test`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    count: testCount,
                    sample_count: sampleCount,
                    strategy,
                    rubric: {},
                    max_score: 10
                })
            });

            const data = await response.json();

            if (data.success) {
                this.renderBatchStats(data.stats);
                this.showToast('测试完成', 'success');
            } else {
                this.showToast(data.error || '测试失败', 'error');
            }
        } catch (error) {
            this.showToast('测试失败：' + error.message, 'error');
        } finally {
            btn.disabled = false;
            btn.innerHTML = '<span>📊</span><span>开始测试</span>';
            progressContainer.style.display = 'none';
        }
    }

    // 渲染批量统计
    renderBatchStats(stats) {
        document.getElementById('stat-total').textContent = stats.total_items;
        document.getElementById('stat-success').textContent = stats.success;
        document.getElementById('stat-failed').textContent = stats.failed;
        document.getElementById('stat-time').textContent = stats.total_time + 's';
        document.getElementById('stat-avg').textContent = stats.avg_time_per_item + 'ms';
        document.getElementById('stat-throughput').textContent = stats.throughput_per_minute + ' 题/分';
    }

    // 添加到历史
    addToHistory(question, answer, result) {
        const item = {
            question,
            answer: answer.substring(0, 50) + '...',
            score: result.final_score,
            confidence: result.confidence,
            time: new Date().toLocaleString()
        };

        this.history.unshift(item);
        if (this.history.length > 50) this.history.pop();
        
        this.renderHistory();
    }

    // 渲染历史
    renderHistory() {
        const container = document.getElementById('history-list');
        if (!container) return;

        if (this.history.length === 0) {
            container.innerHTML = `
                <div class="empty-state">
                    <span class="empty-icon">📜</span>
                    <p>暂无评分记录</p>
                </div>
            `;
            return;
        }

        container.innerHTML = this.history.map(item => `
            <div class="history-item">
                <div class="history-header">
                    <span class="history-score">${item.score} 分</span>
                    <span class="history-time">${item.time}</span>
                </div>
                <div class="history-question">${item.question}</div>
                <div class="history-meta">
                    <span>置信度：${(item.confidence * 100).toFixed(1)}%</span>
                </div>
            </div>
        `).join('');
    }

    // 加载历史
    loadHistory() {
        const saved = localStorage.getItem('grading-history');
        if (saved) {
            this.history = JSON.parse(saved);
            this.renderHistory();
        }
    }

    // 清空历史
    clearHistory() {
        this.history = [];
        localStorage.removeItem('grading-history');
        this.renderHistory();
        this.showToast('历史已清空', 'success');
    }

    // 保存配置
    saveConfig() {
        const config = {
            sampleCount: document.getElementById('config-sample-count').value,
            strategy: document.getElementById('config-strategy').value,
            lowThreshold: document.getElementById('config-low-threshold').value,
            mediumThreshold: document.getElementById('config-medium-threshold').value,
            highThreshold: document.getElementById('config-high-threshold').value,
        };

        localStorage.setItem('grading-config', JSON.stringify(config));
        this.showToast('配置已保存', 'success');
    }

    // Toast 通知
    showToast(message, type = 'info') {
        const container = document.getElementById('toast-container');
        if (!container) return;

        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        toast.innerHTML = `
            <span>${type === 'success' ? '✓' : type === 'error' ? '✗' : 'ℹ'}</span>
            <span>${message}</span>
        `;
        
        container.appendChild(toast);
        
        setTimeout(() => {
            toast.remove();
        }, 3000);
    }
}

// 初始化
document.addEventListener('DOMContentLoaded', () => {
    window.gradingApp = new GradingApp();
});
