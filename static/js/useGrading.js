import { API_BASE } from './api.js';
// 评分核心模块
export function useGrading({ selectedQuestion, selectedQuestionId, studentAnswer, manualQuestion, manualRubric, manualMaxScore, currentMaxScore, providers, currentModelId, splitModelId }) {
    const { ref, computed } = Vue;
    const { ElMessage } = ElementPlus;

    const grading = ref(false);
    const gradeResult = ref(null);
    const gradeModelIds = ref([]);
    const lastMultiResult = ref(null);

    const scoreColor = computed(() => {
        if (!gradeResult.value || gradeResult.value.score === null) return '#909399';
        const pct = gradeResult.value.score / currentMaxScore.value * 100;
        if (pct >= 80) return '#67c23a';
        if (pct >= 60) return '#e6a23c';
        return '#f56c6c';
    });

    function viewModelDetail(row) {
        lastMultiResult.value = gradeResult.value;
        gradeResult.value = { ...row, multi: false, _fromMulti: true };
    }

    async function gradeAnswer() {
        if (!studentAnswer.value.trim()) {
            ElMessage.warning('请填写学生答案');
            return;
        }

        grading.value = true;
        gradeResult.value = null;

        const modelIds = gradeModelIds.value.length > 0
            ? gradeModelIds.value
            : [currentModelId.value];

        const results = [];

        for (let i = 0; i < modelIds.length; i++) {
            const mid = modelIds[i];
            const p = providers.value.find(x => x.id === mid) || {};
            const prov = (mid.indexOf('/') > 0) ? mid.substring(0, mid.indexOf('/')) : mid;
            const mdl = (mid.indexOf('/') > 0) ? mid.substring(mid.indexOf('/') + 1) : (p.model || '');

            let requestBody;
            const studentId = localStorage.getItem('ai_grading_username') || '';
            if (selectedQuestionId.value) {
                requestBody = { question_id: selectedQuestionId.value, answer: studentAnswer.value.trim(), student_id: studentId, provider: prov, model: mdl };
            } else {
                if (!manualQuestion.value.trim()) {
                    ElMessage.warning('请填写题目');
                    grading.value = false;
                    return;
                }
                let rubric = {};
                if (manualRubric.value.trim()) {
                    try { rubric = JSON.parse(manualRubric.value); }
                    catch (e) { ElMessage.error('评分规则JSON格式错误'); grading.value = false; return; }
                }
                requestBody = { question: manualQuestion.value, answer: studentAnswer.value.trim(), student_id: studentId, rubric, max_score: manualMaxScore.value, provider: prov, model: mdl };
            }

            try {
                const { data: result } = await axios.post(API_BASE + '/api/grade', requestBody);
                if (result.success) {
                    results.push({ model_id: mid, model_name: p.name || prov, display_name: p.display_name || mdl, ...result.data });
                } else {
                    results.push({ model_id: mid, model_name: p.name || prov, display_name: p.display_name || mdl, score: null, confidence: 0, error: result.error || '评分失败', comment: '' });
                }
            } catch (e) {
                results.push({ model_id: mid, model_name: p.name || prov, display_name: p.display_name || mdl, score: null, confidence: 0, error: '后端服务未启动', comment: '' });
            }
        }

        if (results.length === 1) {
            gradeResult.value = results[0];
            if (results[0].score === null || results[0].score === undefined) {
                ElMessage.warning(results[0].comment || '评分系统暂时无法评分');
            } else {
                ElMessage.success('评分完成');
            }
        } else {
            gradeResult.value = { multi: true, results: results };
            const scores = results.filter(r => r.score !== null).map(r => r.score);
            if (scores.length > 0) {
                ElMessage.success('多模型评分完成 (' + scores.length + '/' + results.length + ')');
            } else {
                ElMessage.warning('所有模型评分均失败');
            }
        }

        grading.value = false;
    }

    return { grading, gradeResult, gradeModelIds, lastMultiResult, scoreColor, viewModelDetail, gradeAnswer };
}
