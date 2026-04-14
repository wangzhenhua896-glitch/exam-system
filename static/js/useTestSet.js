import { API_BASE } from './api.js';
// 测试集管理模块
export function useTestSet({ selectedQuestionId, selectedQuestion, studentAnswer, gradeResult, splitModelId, currentPage, loadedTestCaseInfo }) {
    const { ref, computed } = Vue;
    const { ElMessage, ElMessageBox } = ElementPlus;

    const testCases = ref([]);
    const selectedCaseIds = ref([]);
    const testSetRunning = ref(false);
    const testSetProgress = ref(0);
    const testSetText = ref('');
    const showGenDialog = ref(false);
    const genCount = ref(7);
    const genDist = ref('gradient');
    const genStyles = ref([]);
    const genExtra = ref('');
    const genRunning = ref(false);
    const genAnswerLoading = ref(false);
    const testCaseDetail = ref(null); // { answer, expected_score, actual_score, comment, scoring_items }
    const testCaseDetailVisible = ref(false);

    // 根据科目动态切换风格选项
    const genStyleOptions = computed(() => {
        const subj = selectedQuestion?.value?.subject;
        if (subj === 'english') {
            return [
                { label: 'Formal', value: 'formal' },
                { label: 'Colloquial', value: 'colloquial' },
                { label: 'Incomplete', value: 'incomplete' },
                { label: 'Off-topic', value: 'off-topic' },
                { label: 'Verbatim copy', value: 'verbatim copy' },
                { label: 'Blank', value: 'blank' },
            ];
        }
        return [
            { label: '标准规范', value: '标准规范' },
            { label: '口语化', value: '口语化' },
            { label: '要点遗漏', value: '要点遗漏' },
            { label: '偏题跑题', value: '偏题跑题' },
            { label: '复制原文', value: '复制原文' },
            { label: '空白作答', value: '空白作答' },
        ];
    });

    // 科目切换时重置默认风格
    const { watch } = Vue;
    watch(() => selectedQuestion?.value?.subject, (subj) => {
        if (subj === 'english') {
            genStyles.value = ['formal', 'colloquial', 'incomplete'];
        } else {
            genStyles.value = ['标准规范', '口语化', '要点遗漏'];
        }
    }, { immediate: true });

    async function saveAsTestCase() {
        if (!selectedQuestionId.value || !gradeResult.value) {
            ElMessage.warning('没有可保存的评分结果');
            return;
        }
        try {
            const { data } = await axios.post(API_BASE + '/api/questions/' + selectedQuestionId.value + '/test-cases', {
                answer_text: studentAnswer.value.trim(),
                expected_score: gradeResult.value.score,
                description: '来自评分页面 ' + new Date().toISOString(),
                case_type: 'real'
            });
            if (data.success) {
                ElMessage.success('已保存为测试用例（期望分 ' + gradeResult.value.score + '）');
            } else {
                ElMessage.error(data.error || '保存失败');
            }
        } catch (e) {
            window.SharedApp.handleApiError(e, '保存测试用例');
        }
    }

    async function generateAnswer() {
        if (!selectedQuestionId.value) {
            ElMessage.warning('请先选择题目');
            return;
        }
        genAnswerLoading.value = true;
        try {
            const { data } = await axios.post(API_BASE + '/api/generate-answer', {
                question_id: selectedQuestionId.value
            });
            if (data.success) {
                studentAnswer.value = data.data.answer;
                gradeResult.value = null;
                ElMessage.success('已生成「' + data.data.level + '」水平的模拟答案（目标约 ' + data.data.target_score + ' 分）');
            } else {
                ElMessage.error(data.error || '生成失败');
            }
        } catch (e) {
            window.SharedApp.handleApiError(e, '生成模拟答案');
        }
        genAnswerLoading.value = false;
    }

    async function loadTestCases() {
        if (!selectedQuestionId.value) { testCases.value = []; return; }
        try {
            const { data } = await axios.get(API_BASE + '/api/questions/' + selectedQuestionId.value + '/test-cases');
            if (data.success) testCases.value = data.data || [];
        } catch (e) {
            window.SharedApp.handleApiError(e, '加载测试用例');
        }
    }

    function onCaseSelectionChange(rows) {
        selectedCaseIds.value = rows.map(r => r.id);
    }

    function gradeTestCase(tc) {
        studentAnswer.value = tc.answer_text;
        gradeResult.value = null;
        currentPage.value = 'single';
        if (loadedTestCaseInfo) {
            loadedTestCaseInfo.value = { description: tc.description || '', expected_score: tc.expected_score };
        }
    }

    async function runSingleCase(caseId) {
        if (testSetRunning.value || !selectedQuestionId.value) return;
        const tc = testCases.value.find(c => c.id === caseId);
        if (!tc) return;
        testSetRunning.value = true;
        const { provider: prov3, model: mdl3 } = splitModelId();
        try {
            const { data: result } = await axios.post(API_BASE + '/api/grade', {
                question_id: selectedQuestionId.value,
                answer: tc.answer_text,
                provider: prov3,
                model: mdl3
            });
            if (result.success && result.data && result.data.score !== null) {
                const actualScore = result.data.score;
                const error = Math.abs(actualScore - tc.expected_score);
                await axios.put(API_BASE + '/api/questions/' + selectedQuestionId.value + '/test-cases/' + caseId, {
                    last_actual_score: actualScore, last_error: error, last_run_at: new Date().toISOString()
                });
                // 保存最新评分详情供查看
                tc._lastResult = {
                    actual_score: actualScore,
                    comment: result.data.comment || '',
                    scoring_items: result.data.details?.scoring_items || [],
                };
                ElMessage.success('测试用例运行完成：' + actualScore + ' 分');
            } else {
                ElMessage.error('评分失败：' + (result.data?.comment || '未知错误'));
            }
        } catch (e) {
            window.SharedApp.handleApiError(e, '运行测试用例');
        }
        testSetRunning.value = false;
        loadTestCases();
    }

    function showTestCaseDetail(tc) {
        testCaseDetail.value = {
            answer: tc.answer_text,
            expected_score: tc.expected_score,
            actual_score: tc.last_actual_score,
            comment: tc._lastResult?.comment || '',
            scoring_items: tc._lastResult?.scoring_items || [],
        };
        testCaseDetailVisible.value = true;
    }

    async function runSelectedCases() {
        const ids = [...selectedCaseIds.value];
        if (ids.length === 0) return;
        testSetRunning.value = true;
        for (let i = 0; i < ids.length; i++) {
            testSetText.value = '运行中... (' + (i + 1) + '/' + ids.length + ')';
            testSetProgress.value = Math.round((i + 1) / ids.length * 100);
            await runSingleCase(ids[i]);
        }
        testSetText.value = '全部完成';
        testSetProgress.value = 100;
        setTimeout(() => { testSetRunning.value = false; }, 2000);
    }

    async function runAllCases() {
        if (testCases.value.length === 0) return;
        testSetRunning.value = true;
        for (let i = 0; i < testCases.value.length; i++) {
            testSetText.value = '运行中... (' + (i + 1) + '/' + testCases.value.length + ')';
            testSetProgress.value = Math.round((i + 1) / testCases.value.length * 100);
            await runSingleCase(testCases.value[i].id);
        }
        testSetText.value = '全部完成';
        testSetProgress.value = 100;
        setTimeout(() => { testSetRunning.value = false; }, 2000);
    }

    async function deleteTestCase(caseId) {
        if (!selectedQuestionId.value) return;
        try {
            await ElMessageBox.confirm('确定删除此测试用例？', '确认', { type: 'warning' });
            await axios.delete(API_BASE + '/api/questions/' + selectedQuestionId.value + '/test-cases/' + caseId);
            ElMessage.success('已删除');
            loadTestCases();
        } catch (e) {
            window.SharedApp.handleApiError(e, '删除测试用例');
        }
    }

    async function autoGenerateTestCases() {
        if (!selectedQuestionId.value) return;
        if (genStyles.value.length === 0) {
            ElMessage.warning('请至少选择一种作答风格');
            return;
        }
        genRunning.value = true;
        showGenDialog.value = false;
        try {
            const { data } = await axios.post(API_BASE + '/api/questions/' + selectedQuestionId.value + '/generate-test-cases', {
                count: genCount.value,
                distribution: genDist.value,
                styles: genStyles.value,
                extra: genExtra.value.trim()
            });
            if (data.success) {
                ElMessage.success('已生成 ' + data.data.count + ' 个测试用例');
                loadTestCases();
            } else {
                ElMessage.error('生成失败：' + (data.error || '未知错误'));
            }
        } catch (e) {
            window.SharedApp.handleApiError(e, '生成测试用例');
        }
        genRunning.value = false;
    }

    return {
        testCases, selectedCaseIds, testSetRunning, testSetProgress, testSetText,
        showGenDialog, genCount, genDist, genStyles, genStyleOptions, genExtra, genRunning, genAnswerLoading,
        testCaseDetail, testCaseDetailVisible,
        saveAsTestCase, generateAnswer, loadTestCases, onCaseSelectionChange,
        gradeTestCase, runSingleCase, runSelectedCases, runAllCases, deleteTestCase,
        showTestCaseDetail, autoGenerateTestCases
    };
}
