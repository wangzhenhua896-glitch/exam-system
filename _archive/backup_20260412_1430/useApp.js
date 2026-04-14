// 整合所有模块
import { useModel } from './useModel.js';
import { useQuestion } from './useQuestion.js';
import { useGrading } from './useGrading.js';
import { useRubric } from './useRubric.js';
import { useTestSet } from './useTestSet.js';
import { useHistory } from './useHistory.js';
import { useAntiCheat } from './useAntiCheat.js';

export function useApp() {
    const { ref, watch, nextTick } = Vue;

    // ========== 共享 ref（多模块需要读写） ==========
    const currentPage = ref('single');
    const inputCollapsed = ref(false);
    const sidebarCollapsed = ref(true);
    const resultCollapsed = ref(false);
    const studentAnswer = ref('');
    const scriptVersion = ref(0);
    const scriptVersionCount = ref(0);
    const rubricFontSize = ref(14);
    const rubricTextareaRef = ref(null);

    // ========== 模型选择 ==========
    const model = useModel();

    // ========== 题目选择 ==========
    const question = useQuestion({ studentAnswer, scriptVersion, scriptVersionCount });

    // ========== 评分脚本 ==========
    const rubric = useRubric({ selectedQuestion: question.selectedQuestion, scriptVersion, scriptVersionCount });

    // ========== 评分核心 ==========
    const grading = useGrading({
        selectedQuestion: question.selectedQuestion,
        selectedQuestionId: question.selectedQuestionId,
        studentAnswer,
        manualQuestion: question.manualQuestion,
        manualRubric: question.manualRubric,
        manualMaxScore: question.manualMaxScore,
        currentMaxScore: question.currentMaxScore,
        providers: model.providers,
        currentModelId: model.currentModelId,
        splitModelId: model.splitModelId
    });

    // ========== 历史记录 ==========
    const hist = useHistory({ selectedQuestion: question.selectedQuestion });

    // ========== 测试集 ==========
    const testSet = useTestSet({
        selectedQuestionId: question.selectedQuestionId,
        studentAnswer,
        gradeResult: grading.gradeResult,
        splitModelId: model.splitModelId,
        currentPage
    });

    // ========== 反作弊 ==========
    const antiCheat = useAntiCheat({
        selectedQuestion: question.selectedQuestion,
        selectedQuestionId: question.selectedQuestionId,
        splitModelId: model.splitModelId
    });

    // ========== Ctrl+Enter 快捷评分 ==========
    document.addEventListener('keydown', (e) => {
        if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
            e.preventDefault();
            if (currentPage.value === 'single' && !grading.grading.value) {
                grading.gradeAnswer();
            }
        }
    });

    // ========== 字号切换 ==========
    function toggleRubricFontSize() {
        const sizes = [12, 14, 16];
        const idx = sizes.indexOf(rubricFontSize.value);
        rubricFontSize.value = sizes[(idx + 1) % sizes.length];
    }

    // ========== 评分脚本内容变更后滚动到顶部 ==========
    watch(() => question.selectedQuestion.value, () => {
        nextTick(() => {
            const el = rubricTextareaRef.value;
            if (el) {
                const textarea = el.$el?.querySelector('textarea') || el;
                if (textarea && typeof textarea.scrollTop === 'number') {
                    textarea.scrollTop = 0;
                }
            }
        });
    });

    // ========== 页面切换 ==========
    function handleMenuSelect(page) {
        currentPage.value = page;
        if (page === 'testset') testSet.loadTestCases();
        if (page === 'history') hist.loadHistoryFromApi();
    }

    // ========== 初始化 ==========
    async function init() {
        await model.loadProviders();
        await question.loadQuestionList();
        await hist.loadHistoryFromApi();

        const params = new URLSearchParams(window.location.search);
        const qid = params.get('question_id');
        if (qid) {
            question.selectedQuestionId.value = parseInt(qid);
            await question.onQuestionSelect(parseInt(qid));
        }
    }

    // ========== 组装返回 ==========
    return {
        currentPage, inputCollapsed, sidebarCollapsed, resultCollapsed,

        // 模型
        providers: model.providers,
        currentModelId: model.currentModelId,
        currentModelLabel: model.currentModelLabel,
        modelGroups: model.modelGroups,
        onModelChange: model.onModelChange,

        // 题目
        questionList: question.questionList,
        selectedQuestionId: question.selectedQuestionId,
        selectedQuestion: question.selectedQuestion,
        loadingQuestions: question.loadingQuestions,
        loadQuestionList: question.loadQuestionList,
        onQuestionSelect: question.onQuestionSelect,
        manualQuestion: question.manualQuestion,
        manualRubric: question.manualRubric,
        manualMaxScore: question.manualMaxScore,
        currentMaxScore: question.currentMaxScore,
        parentPassage: question.parentPassage,

        // 学生答案
        studentAnswer,

        // 评分
        grading: grading.grading,
        gradeResult: grading.gradeResult,
        gradeModelIds: grading.gradeModelIds,
        lastMultiResult: grading.lastMultiResult,
        scoreColor: grading.scoreColor,
        viewModelDetail: grading.viewModelDetail,
        gradeAnswer: grading.gradeAnswer,

        // AI 生成答案
        genAnswerLoading: testSet.genAnswerLoading,
        generateAnswer: testSet.generateAnswer,

        // 操作按钮
        copyRubricScript: rubric.copyRubricScript,
        saveAsTestCase: testSet.saveAsTestCase,

        // 评分脚本编辑
        rubricTextareaRef,
        rubricFontSize,
        toggleRubricFontSize,
        rubricFullscreen: rubric.rubricFullscreen,
        rubricEditing: rubric.rubricEditing,
        rubricEditValue: rubric.rubricEditValue,
        toggleRubricFullscreen: rubric.toggleRubricFullscreen,
        startRubricEdit: rubric.startRubricEdit,
        cancelRubricEdit: rubric.cancelRubricEdit,
        saveRubricEdit: rubric.saveRubricEdit,

        // 版本历史
        scriptVersion, scriptVersionCount,
        historyDialogVisible: rubric.historyDialogVisible,
        scriptHistoryList: rubric.scriptHistoryList,
        historyPreviewText: rubric.historyPreviewText,
        openScriptHistory: rubric.openScriptHistory,
        rollbackScriptVersion: rubric.rollbackScriptVersion,

        // 评分脚本对照
        rubricParsedItems: rubric.rubricParsedItems,
        rubricExpanded: rubric.rubricExpanded,
        toggleRubricExpand: rubric.toggleRubricExpand,

        // 测试集
        testCases: testSet.testCases,
        selectedCaseIds: testSet.selectedCaseIds,
        testSetRunning: testSet.testSetRunning,
        testSetProgress: testSet.testSetProgress,
        testSetText: testSet.testSetText,
        loadTestCases: testSet.loadTestCases,
        onCaseSelectionChange: testSet.onCaseSelectionChange,
        gradeTestCase: testSet.gradeTestCase,
        runSingleCase: testSet.runSingleCase,
        runSelectedCases: testSet.runSelectedCases,
        runAllCases: testSet.runAllCases,
        deleteTestCase: testSet.deleteTestCase,

        // 自动生成
        showGenDialog: testSet.showGenDialog,
        genCount: testSet.genCount,
        genDist: testSet.genDist,
        genStyles: testSet.genStyles,
        genExtra: testSet.genExtra,
        genRunning: testSet.genRunning,
        autoGenerateTestCases: testSet.autoGenerateTestCases,

        // 反作弊
        anicheatRunning: antiCheat.anicheatRunning,
        anicheatResults: antiCheat.anicheatResults,
        anicheatProgress: antiCheat.anicheatProgress,
        anicheatText: antiCheat.anicheatText,
        anicheatScenarios: antiCheat.anicheatScenarios,
        anicheatRowClass: antiCheat.anicheatRowClass,
        runAncheatTests: antiCheat.runAncheatTests,

        // 历史
        history: hist.history,
        loadHistoryFromApi: hist.loadHistoryFromApi,
        clearHistory: hist.clearHistory,

        // 导航
        handleMenuSelect,

        // 初始化
        init
    };
}
