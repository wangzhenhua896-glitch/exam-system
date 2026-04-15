import { API_BASE } from './api.js';
// 历史记录模块
export function useHistory({ selectedQuestion }) {
    const { ref } = Vue;
    const { ElMessage, ElMessageBox } = ElementPlus;

    const history = ref([]);

    function addToHistory(requestBody, data) {
        let questionText = requestBody.question || '';
        if (!questionText && selectedQuestion.value) questionText = selectedQuestion.value.content || '';
        if (!questionText) questionText = '(题库题目 #' + requestBody.question_id + ')';
        history.value.unshift({
            question: questionText.substring(0, 80),
            answer: (requestBody.answer || '').substring(0, 50) + '...',
            score: data.score,
            confidence: data.confidence || 0,
            time: new Date().toLocaleString()
        });
        if (history.value.length > 50) history.value.pop();
        localStorage.setItem('grading-history', JSON.stringify(history.value));
    }

    async function loadHistoryFromApi() {
        try {
            const { data } = await axios.get(API_BASE + '/api/history?limit=50');
            if (data.success && data.data) {
                history.value = data.data.map(r => ({
                    question: (r.student_answer || '').substring(0, 80),
                    score: r.score,
                    confidence: r.confidence || 0,
                    time: r.graded_at || ''
                }));
            }
        } catch (e) {
            history.value = JSON.parse(localStorage.getItem('grading-history') || '[]');
            ElMessage.info('无法加载远程历史，显示本地缓存');
        }
    }

    async function clearHistory() {
        try {
            await ElMessageBox.confirm(
                '确定清空所有评分历史记录？此操作不可恢复。',
                '确认清空',
                { type: 'warning', confirmButtonText: '确定清空', cancelButtonText: '取消' }
            );
        } catch { return; }
        history.value = [];
        localStorage.removeItem('grading-history');
        ElMessage.success('历史已清空');
    }

    return { history, addToHistory, loadHistoryFromApi, clearHistory };
}
