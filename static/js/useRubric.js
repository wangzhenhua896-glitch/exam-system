import { API_BASE } from './api.js';
// 评分脚本编辑/版本历史模块
export function useRubric({ selectedQuestion, scriptVersion, scriptVersionCount }) {
    const { ref, computed } = Vue;
    const { ElMessage } = ElementPlus;

    const rubricParsedItems = computed(() => {
        if (!selectedQuestion.value || !selectedQuestion.value.rubric_script) return [];
        const script = selectedQuestion.value.rubric_script;
        const byIndex = {};
        const parts = script.split(/(?=得分点\d+|第\d+问|Scoring [Pp]oint\s*\d+|Criterion\s*\d+|Part\s*\d+|Section\s*[A-Z]|第[一二三四五六七八九十]+[问题]|\n?\([a-zA-Z]\))/);
        for (const part of parts) {
            const match = part.match(/^(得分点|第|Scoring\s*[Pp]oint|Criterion|Part|Section)\s*(\d+|[A-Z]|[一二三四五六七八九十]+)[^：:]*[：:]|^\(?[a-zA-Z]\)?[：:.\s]/);
            if (match) {
                const idx = parseInt(match[2]);
                const content = part.trim();
                if (!byIndex[idx] || content.length > byIndex[idx].length) {
                    byIndex[idx] = content;
                }
            }
        }
        return Object.keys(byIndex).sort((a, b) => a - b).map(k => ({ index: parseInt(k), content: byIndex[k] }));
    });

    const rubricExpanded = ref({});
    const rubricFullscreen = ref(false);
    const rubricEditing = ref(false);
    const rubricEditValue = ref('');
    const historyDialogVisible = ref(false);
    const scriptHistoryList = ref([]);
    const historyPreviewText = ref('');

    function toggleRubricExpand(idx) {
        rubricExpanded.value = { ...rubricExpanded.value, [idx]: !rubricExpanded.value[idx] };
    }

    function toggleRubricFullscreen() {
        rubricFullscreen.value = !rubricFullscreen.value;
    }

    function startRubricEdit() {
        rubricEditValue.value = selectedQuestion.value?.rubric_script || '';
        rubricEditing.value = true;
    }

    function cancelRubricEdit() {
        rubricEditing.value = false;
    }

    async function saveRubricEdit() {
        if (!selectedQuestion.value) return;
        try {
            const { data } = await axios.put(API_BASE + '/api/questions/' + selectedQuestion.value.id, {
                rubric_script: rubricEditValue.value
            });
            if (data.success) {
                selectedQuestion.value = { ...selectedQuestion.value, rubric_script: rubricEditValue.value };
                rubricEditing.value = false;
                ElMessage.success('评分脚本已保存');
            }
        } catch (e) {
            window.SharedApp.handleApiError(e, '保存评分脚本');
        }
    }

    function copyRubricScript() {
        if (!selectedQuestion.value || !selectedQuestion.value.rubric_script) {
            ElMessage.warning('没有可复制的评分脚本');
            return;
        }
        navigator.clipboard.writeText(selectedQuestion.value.rubric_script).then(() => {
            ElMessage.success('已复制到剪贴板');
        }).catch(() => {
            ElMessage.error('复制失败，请手动选择复制');
        });
    }

    async function openScriptHistory() {
        if (!selectedQuestion.value) return;
        try {
            const { data } = await axios.get(API_BASE + '/api/questions/' + selectedQuestion.value.id + '/script-history');
            if (data.success) {
                scriptHistoryList.value = data.data || [];
                historyPreviewText.value = '';
                historyDialogVisible.value = true;
            }
        } catch (e) {
            window.SharedApp.handleApiError(e, '获取版本历史');
        }
    }

    async function rollbackScriptVersion(version) {
        if (!selectedQuestion.value) return;
        try {
            await ElMessageBox.confirm(
                '当前评分脚本将被替换为版本 v' + version + ' 的内容，此操作可再次回滚撤销。确定继续？',
                '确认回滚',
                { type: 'warning', confirmButtonText: '确定回滚', cancelButtonText: '取消' }
            );
        } catch { return; }
        try {
            const { data } = await axios.post(API_BASE + '/api/questions/' + selectedQuestion.value.id + '/script-rollback', {
                version: version
            });
            if (data.success) {
                const res = await axios.get(API_BASE + '/api/questions/' + selectedQuestion.value.id);
                if (res.data.success) {
                    selectedQuestion.value = res.data.data;
                    scriptVersion.value = res.data.data.script_version || 0;
                    scriptVersionCount.value = res.data.data.script_version_count || 0;
                }
                const histRes = await axios.get(API_BASE + '/api/questions/' + selectedQuestion.value.id + '/script-history');
                if (histRes.data.success) {
                    scriptHistoryList.value = histRes.data.data || [];
                }
                historyPreviewText.value = '';
                ElMessage.success('已回滚到版本 v' + version);
            }
        } catch (e) {
            window.SharedApp.handleApiError(e, '回滚评分脚本');
        }
    }

    return {
        rubricParsedItems, rubricExpanded, rubricFullscreen, rubricEditing, rubricEditValue,
        historyDialogVisible, scriptHistoryList, historyPreviewText,
        toggleRubricExpand, toggleRubricFullscreen, startRubricEdit, cancelRubricEdit,
        saveRubricEdit, copyRubricScript, openScriptHistory, rollbackScriptVersion
    };
}
