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

    async function loadQuestionList() {
        loadingQuestions.value = true;
        try {
            const { data } = await axios.get(API_BASE + '/api/questions');
            if (data.success && data.data) {
                questionList.value = data.data;
            }
        } catch (e) {
            console.error('加载题目列表失败', e);
        }
        loadingQuestions.value = false;
    }

    async function onQuestionSelect(qid) {
        if (!qid) {
            selectedQuestion.value = null;
            return;
        }
        loadingQuestions.value = true;
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
                ElMessage.success('题目已加载: ' + (data.data.title || data.data.content.substring(0, 20)));
            }
        } catch (e) {
            ElMessage.error('加载题目失败');
        }
        loadingQuestions.value = false;
    }

    const currentMaxScore = computed(() => {
        if (selectedQuestion.value) return selectedQuestion.value.max_score || 10;
        return manualMaxScore.value;
    });

    return {
        questionList, selectedQuestionId, selectedQuestion, loadingQuestions,
        loadQuestionList, onQuestionSelect,
        manualQuestion, manualRubric, manualMaxScore, currentMaxScore
    };
}
