import { API_BASE } from './api.js';
// 反作弊测试模块
export function useAntiCheat({ selectedQuestion, selectedQuestionId, splitModelId }) {
    const { ref } = Vue;
    const { ElMessage } = ElementPlus;

    const anicheatRunning = ref(false);
    const anicheatResults = ref([]);
    const anicheatProgress = ref(0);
    const anicheatText = ref('');

    const anicheatScenarios = [
        { name: '复制原文', generate: (q) => q.standard_answer || q.content },
        { name: '复制题干', generate: (q) => q.content },
        { name: '中文翻译作答', generate: (q) => {
            if (q.subject !== 'english') return null;
            // 英语题用中文回答（可能抄袭了翻译）
            return '李明在北京的一所职业学校学习计算机科学。他每天坐地铁上学，大约需要30分钟。周末他经常去看望爷爷奶奶。';
        }},
        { name: '复制题干+无作答', generate: (q) => {
            const isEnglish = q.subject === 'english';
            return (isEnglish ? 'Answer:\n' : '答：\n') + (q.content || '');
        }},
        { name: '空白作答', generate: () => '' },
        { name: '答非所问', generate: (q) => {
            const isEnglish = q.subject === 'english';
            return isEnglish
                ? 'The weather is really nice today. I think this question has nothing to do with me.'
                : '今天天气真好，阳光明媚，适合出门散步。我觉得这个问题和我没有太大关系。';
        }},
    ];

    function anicheatRowClass({ row }) {
        if (row.score === null && !row.error) return '';
        return row.passed ? 'anicheat-pass' : 'anicheat-fail';
    }

    async function runAncheatTests() {
        if (!selectedQuestionId.value || !selectedQuestion.value) {
            ElMessage.warning('请先选择题目');
            return;
        }
        anicheatRunning.value = true;
        anicheatResults.value = [];
        const q = selectedQuestion.value;

        for (let i = 0; i < anicheatScenarios.length; i++) {
            const scenario = anicheatScenarios[i];
            anicheatText.value = '测试中... (' + (i + 1) + '/' + anicheatScenarios.length + ') ' + scenario.name;
            anicheatProgress.value = Math.round((i + 1) / anicheatScenarios.length * 100);

            const answer = scenario.generate(q);
            if (answer === null) continue; // 场景不适用于当前科目
            const result = { scenario: scenario.name, answerPreview: (answer || '(空白)').substring(0, 80), score: null, passed: false, comment: '', error: '' };

            const { provider: prov4, model: mdl4 } = splitModelId();
            try {
                const { data } = await axios.post(API_BASE + '/api/grade', {
                    question_id: selectedQuestionId.value,
                    answer: answer,
                    provider: prov4,
                    model: mdl4
                });
                if (data.success && data.data) {
                    result.score = data.data.score;
                    result.passed = data.data.score === 0;
                    result.comment = (data.data.comment || '').substring(0, 100);
                    if (data.data.score === null) {
                        result.error = '异常';
                        result.comment = data.data.comment || '';
                    }
                } else {
                    result.error = '失败';
                    result.comment = data.error || '未知错误';
                }
            } catch (e) {
                result.error = '异常';
                result.comment = e.message;
            }

            anicheatResults.value.push(result);
        }

        anicheatText.value = '测试完成';
        setTimeout(() => { anicheatRunning.value = false; }, 1500);
    }

    return {
        anicheatRunning, anicheatResults, anicheatProgress, anicheatText,
        anicheatScenarios, anicheatRowClass, runAncheatTests
    };
}
