import { API_BASE } from './api.js';
// 题目选择模块
export function useQuestion({ studentAnswer, scriptVersion, scriptVersionCount }) {
    const { ref, computed } = Vue;
    const { ElMessage } = ElementPlus;

    const questionList = ref([]);
    const selectedQuestionId = ref(null);
    const selectedQuestion = ref(null);
    const loadingQuestions = ref(false);
    const manualQuestion = ref('');
    const manualRubric = ref('');
    const manualMaxScore = ref(10);
    const manualSubject = ref('general');
    const manualRubricPoints = ref([{ description: '', score: 0 }]);
    const parentPassage = ref('');

    async function loadQuestionList() {
        loadingQuestions.value = true;
        try {
            const { data } = await axios.get(API_BASE + '/api/questions');
            if (data.success && data.data) {
                const allQuestions = data.data;
                // Build parent-child hierarchy
                const parents = allQuestions.filter(q => !q.parent_id);
                const children = allQuestions.filter(q => q.parent_id);
                // Group children by parent_id
                const childMap = {};
                children.forEach(c => {
                    if (!childMap[c.parent_id]) childMap[c.parent_id] = [];
                    childMap[c.parent_id].push(c);
                });
                // Build flat list: parents with _children, children with _isChild
                const result = [];
                parents.forEach(p => {
                    if (childMap[p.id]) {
                        p._children = childMap[p.id];
                        p._isParent = true;
                    }
                    result.push(p);
                });
                questionList.value = result;
            }
        } catch (e) {
            window.SharedApp.handleApiError(e, '加载题目列表');
        }
        loadingQuestions.value = false;
    }

    async function onQuestionSelect(qid) {
        if (!qid) {
            selectedQuestion.value = null;
            parentPassage.value = '';
            return;
        }
        loadingQuestions.value = true;
        parentPassage.value = '';
        try {
            const { data } = await axios.get(API_BASE + '/api/questions/' + qid);
            if (data.success && data.data) {
                selectedQuestion.value = data.data;
                scriptVersion.value = data.data.script_version || 0;
                scriptVersionCount.value = data.data.script_version_count || 0;
                const stdAnswer = data.data.standard_answer || '';
                if (stdAnswer) {
                    studentAnswer.value = stdAnswer;
                    setTimeout(() => {
                        const textarea = document.querySelector('.content textarea');
                        if (textarea) { textarea.focus(); textarea.select(); }
                    }, 100);
                }
                // Load parent passage for child questions
                if (data.data.parent_id) {
                    try {
                        const pRes = await axios.get(API_BASE + '/api/questions/' + data.data.parent_id);
                        if (pRes.data.success && pRes.data.data) {
                            parentPassage.value = pRes.data.data.content || '';
                        }
                    } catch (e) { /* ignore */ }
                }
                ElMessage.success('题目已加载: ' + (data.data.title || data.data.content.substring(0, 20)));
            }
        } catch (e) {
            window.SharedApp.handleApiError(e, '加载题目');
        }
        loadingQuestions.value = false;
    }

    const currentMaxScore = computed(() => {
        if (selectedQuestion.value) return selectedQuestion.value.max_score || 10;
        return manualMaxScore.value;
    });

    const getSubjectLabel = window.SharedApp.getSubjectLabel;

    return {
        questionList, selectedQuestionId, selectedQuestion, loadingQuestions,
        loadQuestionList, onQuestionSelect,
        manualQuestion, manualRubric, manualMaxScore, manualSubject, manualRubricPoints, currentMaxScore,
        parentPassage, getSubjectLabel
    };
}
