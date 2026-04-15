/**
 * 英语题目编辑器核心模块（编排层）
 *
 * 职责：状态定义 + 工作流控制 + 数据加载 + CRUD + wrapper
 * 依赖：window.EnglishEditHelpers, window.EnglishEditAI, window.EnglishEditValidateSave
 * 暴露：window.EnglishEditCore.useEnglishEdit()
 */
(function () {
  'use strict';

  var handleApiError = window.SharedApp.handleApiError;
  var ElMessage = ElementPlus.ElMessage;
  var ElMessageBox = ElementPlus.ElMessageBox;
  var H = window.EnglishEditHelpers;
  var AI = window.EnglishEditAI;
  var VS = window.EnglishEditValidateSave;

  var WORKFLOW_STEPS = [
    { id: 'extract', label: '原题解析', icon: 'el-icon-document' },
    { id: 'per_question', label: '逐小问配置', icon: 'el-icon-edit' },
    { id: 'script', label: '评分脚本', icon: 'el-icon-files' },
    { id: 'validate', label: '一致性验证', icon: 'el-icon-circle-check' },
    { id: 'save', label: '确认保存', icon: 'el-icon-upload' },
  ];

  // ============================================================
  // useEnglishEdit
  // ============================================================
  function useEnglishEdit() {
    var ref = Vue.ref;
    var computed = Vue.computed;

    // ---- 页面状态 ----
    var pageLoading = ref(false);
    var currentParentId = ref(null);
    var parentTitle = ref('');
    var parentContent = ref('');
    var parentContentHtml = ref('');
    var parentContentEditing = ref(false);
    var parentMaxScore = ref(6);
    var parentSubject = ref('english');
    var isStateA = ref(false);
    var rubricScript = ref('');
    var pasteText = ref('');

    // ---- 工作流状态 ----
    var currentStep = ref('extract');
    var activeQuestionIndex = ref(0);
    var completedSteps = ref([]);
    var workflowStatus = ref(null);

    // ---- 子题列表 ----
    var subQuestions = ref([]);

    // ---- 评分脚本 ----
    var generatedScript = ref('');
    var scriptCollapseActive = ref(['script']);
    var selfCheckLoading = ref(false);
    var selfCheckResult = ref(null);
    var qualityLoading = ref(false);
    var qualityResult = ref(null);

    // ---- 验证结果 ----
    var validationResults = ref([]);
    var validationPassed = ref(false);

    // ---- AI loading ----
    var extractingLoading = ref(false);
    var scoringPointExtractingMap = ref({});
    var synonymLoadingMap = ref({});
    var excludeLoading = ref(false);
    var scriptGenerating = ref(false);

    // ---- AI 建议面板 ----
    var synonymSuggestions = ref([]);
    var synonymTargetKey = ref('');
    var synonymTargetSp = ref(null);
    var excludeSuggestions = ref([]);
    var excludeTargetSqId = ref(0);
    var excludeTargetSq = ref(null);

    // ============================================================
    // 计算属性
    // ============================================================
    var canEnterStep = computed(function () {
      return {
        extract: true,
        per_question: completedSteps.value.indexOf('extract') >= 0 || subQuestions.value.length > 0,
        script: allQuestionsCompleted(),
        validate: completedSteps.value.indexOf('script') >= 0 || !!generatedScript.value,
        save: validationPassed.value,
      };
    });

    var stepIndex = computed(function () {
      var ids = WORKFLOW_STEPS.map(function (s) { return s.id; });
      return ids.indexOf(currentStep.value);
    });

    var subScoreSum = computed(function () {
      var raw = subQuestions.value.reduce(function (sum, sq) { return sum + (sq.maxScore || 0); }, 0);
      return Math.round(raw * 10) / 10;
    });

    var scoreMatch = computed(function () {
      return Math.abs(subScoreSum.value - parentMaxScore.value) < 0.01;
    });

    // ============================================================
    // 构建当前状态快照（供子模块使用）
    // ============================================================
    function buildState() {
      return {
        currentParentId: currentParentId.value,
        parentContent: parentContent.value,
        parentMaxScore: parentMaxScore.value,
        generatedScript: generatedScript.value,
        rubricScript: rubricScript.value,
        subQuestions: subQuestions.value,
        currentStep: currentStep.value,
        activeQuestionIndex: activeQuestionIndex.value,
        completedSteps: completedSteps.value,
        validationPassed: validationPassed.value,
        subScoreSum: subScoreSum.value,
      };
    }

    // ============================================================
    // resetUIState — 切换题目时清理所有 UI 辅助状态（P0 修复）
    // ============================================================
    function resetUIState() {
      validationResults.value = [];
      validationPassed.value = false;
      pasteText.value = '';
      selfCheckResult.value = null;
      selfCheckLoading.value = false;
      qualityResult.value = null;
      qualityLoading.value = false;
      synonymSuggestions.value = [];
      synonymTargetKey.value = '';
      synonymTargetSp.value = null;
      synonymLoadingMap.value = {};
      excludeSuggestions.value = [];
      excludeTargetSqId.value = 0;
      excludeTargetSq.value = null;
      excludeLoading.value = false;
      parentContentEditing.value = false;
      scriptGenerating.value = false;
      extractingLoading.value = false;
      scoringPointExtractingMap.value = {};
    }

    // ============================================================
    // 工作流推进
    // ============================================================
    function goToStep(stepId) {
      if (canEnterStep.value[stepId]) {
        currentStep.value = stepId;
      }
    }

    function markStepCompleted(stepId) {
      if (completedSteps.value.indexOf(stepId) < 0) {
        completedSteps.value.push(stepId);
      }
    }

    function allQuestionsCompleted() {
      if (subQuestions.value.length === 0) return false;
      return subQuestions.value.every(function (sq) { return sq.status === 'completed'; });
    }

    function collapseAllSubQuestions() {
      subQuestions.value.forEach(function (sq) {
        if (sq.status !== 'completed') {
          sq.expanded = false;
        }
      });
    }

    function completeCurrentQuestion() {
      var sq = subQuestions.value[activeQuestionIndex.value];
      if (!sq || !H.isQuestionComplete(sq)) return;
      sq.status = 'completed';
      sq.expanded = false;

      if (activeQuestionIndex.value < subQuestions.value.length - 1) {
        activeQuestionIndex.value++;
        collapseAllSubQuestions();
        subQuestions.value[activeQuestionIndex.value].status = 'in_progress';
        subQuestions.value[activeQuestionIndex.value].expanded = true;
      } else {
        markStepCompleted('per_question');
      }
      saveWorkflowStatus();
    }

    function confirmSubQuestion(qi) {
      var sq = subQuestions.value[qi];
      if (!sq || !H.isQuestionComplete(sq)) return;
      sq.status = 'completed';
      sq.expanded = false;

      if (qi === activeQuestionIndex.value && activeQuestionIndex.value < subQuestions.value.length - 1) {
        activeQuestionIndex.value++;
        collapseAllSubQuestions();
        subQuestions.value[activeQuestionIndex.value].status = 'in_progress';
        subQuestions.value[activeQuestionIndex.value].expanded = true;
      }

      if (allQuestionsCompleted()) {
        markStepCompleted('per_question');
      }
      saveWorkflowStatus();
    }

    function goToQuestion(index) {
      if (index >= 0 && index < subQuestions.value.length) {
        // 只重置 index 到当前 activeQuestionIndex 之间的题，不重置之后已完成的题
        var currentActive = activeQuestionIndex.value;
        var resetStart = Math.min(index, currentActive);
        var resetEnd = Math.max(index, currentActive);
        for (var i = resetStart; i <= resetEnd; i++) {
          if (i !== index) {
            subQuestions.value[i].status = 'pending';
          }
          subQuestions.value[i].expanded = false;
        }
        collapseAllSubQuestions();
        activeQuestionIndex.value = index;
        subQuestions.value[index].status = 'in_progress';
        subQuestions.value[index].expanded = true;
        var ci = completedSteps.value.indexOf('per_question');
        if (ci >= 0) completedSteps.value.splice(ci, 1);
        saveWorkflowStatus();
      }
    }

    // ============================================================
    // 数据加载
    // ============================================================
    async function loadQuestion(questionId) {
      pageLoading.value = true;
      resetUIState(); // P0 修复：清理上一题残留状态
      currentParentId.value = questionId;
      subQuestions.value = [];
      generatedScript.value = '';
      completedSteps.value = [];
      activeQuestionIndex.value = 0;

      try {
        var res = await axios.get('/api/questions/' + questionId);
        if (!res.data.success) { pageLoading.value = false; return; }
        var parent = res.data.data;
        parentTitle.value = parent.title || '';
        parentMaxScore.value = parent.max_score || 6;
        parentSubject.value = parent.subject || 'english';
        rubricScript.value = parent.rubric_script || '';

        parentContent.value = H.extractReadingMaterial(parent.content || '');
        parentContentHtml.value = parent.original_text || parent.content_html || (parent.content && parent.content.includes('<') ? parent.content : '');

        if (parent.workflow_status) {
          try {
            workflowStatus.value = typeof parent.workflow_status === 'string'
              ? JSON.parse(parent.workflow_status) : parent.workflow_status;
          } catch (_) {
            console.warn('workflow_status 解析失败，重置为空');
            workflowStatus.value = {};
          }
        }

        var childRes = await axios.get('/api/questions/' + questionId + '/children');
        var children = childRes.data.data || [];

        if (children.length > 0) {
          isStateA.value = true;
          await loadChildren(children);
        } else {
          isStateA.value = false;
          if (workflowStatus.value) {
            restoreWorkflowState();
          } else {
            currentStep.value = 'extract';
          }
        }
      } catch (e) {
        handleApiError(e, '加载题目失败');
      }
      pageLoading.value = false;
    }

    async function loadChildren(children) {
      var loaded = [];
      for (var i = 0; i < children.length; i++) {
        var child = children[i];
        var sq = H.createEmptySubQuestion();
        sq.id = child.id;
        sq.questionId = child.id;
        sq.text = child.content || child.title || '';
        sq.standardAnswer = child.standard_answer || '';
        sq.maxScore = child.max_score || 2;

        var rubric = child.rubric;
        if (typeof rubric === 'string') {
          try { rubric = JSON.parse(rubric); } catch (_) { rubric = {}; }
        }
        if (rubric && rubric.scoring_strategy === 'max_hit_score') {
          sq.scoreFormulaType = 'max_hit_score';
        } else if (rubric && rubric.scoring_strategy === 'hit_count') {
          sq.scoreFormulaType = 'hit_count';
        }

        try {
          var ansRes = await axios.get('/api/questions/' + child.id + '/answers?scope_type=scoring_point');
          var answers = ansRes.data.data || [];
          for (var j = 0; j < answers.length; j++) {
            sq.answerId = answers[j].id;
            try {
              var spJson = JSON.parse(answers[j].answer_text);
              H.loadScoringPointFromJson(sq, spJson);
            } catch (e) {
              console.warn('解析采分点 JSON 失败', e);
            }
          }
        } catch (_) { /* ignore */ }

        if (workflowStatus.value && workflowStatus.value.question_status) {
          sq.status = workflowStatus.value.question_status[String(child.id)] || 'pending';
        }
        if (sq.status === 'completed' && !H.isQuestionComplete(sq)) {
          sq.status = 'pending';
        }
        sq.expanded = (sq.status === 'in_progress');
        loaded.push(sq);
      }
      subQuestions.value = loaded;

      if (workflowStatus.value && typeof workflowStatus.value.active_question_index === 'number') {
        activeQuestionIndex.value = workflowStatus.value.active_question_index;
      } else {
        var idx = loaded.findIndex(function (sq) { return sq.status !== 'completed'; });
        activeQuestionIndex.value = idx >= 0 ? idx : 0;
      }
      var activeSq = loaded[activeQuestionIndex.value];
      if (!activeSq || activeSq.status === 'completed') {
        var fixIdx = loaded.findIndex(function (sq) { return sq.status !== 'completed'; });
        activeQuestionIndex.value = fixIdx >= 0 ? fixIdx : 0;
      }
      var hasAnyCompleted = loaded.some(function (sq) { return sq.status === 'completed'; });
      if (!hasAnyCompleted && activeQuestionIndex.value > 0) {
        activeQuestionIndex.value = 0;
      }

      loaded.forEach(function (sq, i) {
        if (i === activeQuestionIndex.value && sq.status !== 'completed') {
          sq.status = 'in_progress';
          sq.expanded = true;
        } else if (sq.status !== 'completed') {
          sq.expanded = false;
        }
      });

      if (workflowStatus.value && workflowStatus.value.current_step) {
        currentStep.value = workflowStatus.value.current_step;
        completedSteps.value = workflowStatus.value.completed_steps || [];
      } else {
        if (allQuestionsCompleted()) {
          currentStep.value = 'script';
          completedSteps.value = ['extract', 'per_question'];
        } else {
          currentStep.value = 'per_question';
          completedSteps.value = ['extract'];
        }
      }
    }

    // P0 修复：State B 下校验状态一致性
    function restoreWorkflowState() {
      var ws = workflowStatus.value;
      currentStep.value = ws.current_step || 'extract';
      completedSteps.value = ws.completed_steps || [];
      activeQuestionIndex.value = ws.active_question_index || 0;
      // State B（无子题）不应停留在 per_question 步骤
      if (currentStep.value === 'per_question') {
        currentStep.value = 'extract';
      }
    }

    // ============================================================
    // 子题 CRUD
    // ============================================================
    function addSubQuestion() {
      var sq = H.createEmptySubQuestion();
      sq.tempId = Date.now();
      subQuestions.value.push(sq);
      if (subQuestions.value.length === 1) {
        sq.status = 'in_progress';
        activeQuestionIndex.value = 0;
      }
    }

    function removeSubQuestion(index) {
      subQuestions.value.splice(index, 1);
      if (activeQuestionIndex.value >= subQuestions.value.length) {
        activeQuestionIndex.value = Math.max(0, subQuestions.value.length - 1);
      }
    }

    function addScoringPoint(sq) {
      var nextLabel = String.fromCharCode(65 + sq.scoringPoints.length);
      sq.scoringPoints.push(H.createEmptyScoringPoint(nextLabel));
    }

    function removeScoringPoint(sq, index) {
      sq.scoringPoints.splice(index, 1);
      sq.scoringPoints.forEach(function (sp, i) {
        sp.id = String.fromCharCode(65 + i);
      });
    }

    function addScoringRule(sq) {
      sq.scoringRules.push({ minHits: 1, score: 1 });
    }

    function removeScoringRule(sq, index) {
      sq.scoringRules.splice(index, 1);
    }

    // ============================================================
    // AI wrapper — 包装子模块函数，处理 ref 读写和 loading
    // ============================================================
    async function extractFromPaste() {
      if (!pasteText.value.trim()) return;
      extractingLoading.value = true;
      try {
        var result = await AI.extractFromPaste(pasteText.value);
        if (result) {
          parentContent.value = result.readingMaterial;
          subQuestions.value = result.subQuestions;
          if (result.subQuestions.length > 0) {
            result.subQuestions[0].status = 'in_progress';
            activeQuestionIndex.value = 0;
            markStepCompleted('extract');
            currentStep.value = 'per_question';
            saveWorkflowStatus();
          }
        }
      } catch (e) {
        ElMessage.error('AI 提取失败：' + e.message);
      }
      extractingLoading.value = false;
    }

    async function extractScoringPoints(sq) {
      if (!sq.text || !sq.standardAnswer) return;
      scoringPointExtractingMap.value[sq.tempId] = true;
      try {
        var result = await AI.extractScoringPoints(sq);
        if (result) {
          sq.scoringPoints = result.scoringPoints;
          sq.scoreFormulaType = result.scoreFormulaType;
          if (result.excludeList) sq.excludeList = result.excludeList;
        }
      } catch (e) {
        handleApiError(e, '采分点提取失败');
      }
      scoringPointExtractingMap.value[sq.tempId] = false;
    }

    async function suggestSynonyms(sq, spIndex) {
      var sp = sq.scoringPoints[spIndex];
      if (!sp || sp.keywords.length === 0) return;
      var spKey = sq.tempId + '_' + spIndex;
      synonymLoadingMap.value[spKey] = true;
      synonymSuggestions.value = [];
      synonymTargetKey.value = spKey;
      synonymTargetSp.value = sp;
      try {
        var result = await AI.suggestSynonyms(parentContent.value, sq, spIndex);
        if (result) {
          synonymSuggestions.value = result;
        }
      } catch (e) {
        handleApiError(e, '同义词补全失败');
      } finally {
        synonymLoadingMap.value[spKey] = false;
      }
    }

    function addSynonymSuggestion(sp, suggestion) {
      if (suggestion.disabled) return;
      if (H.addTag(sp.synonyms, suggestion.term)) {
        suggestion.disabled = true;
      }
    }

    function addAllSynonymSuggestions() {
      var sp = synonymTargetSp.value;
      if (!sp) return;
      synonymSuggestions.value.forEach(function (s) {
        if (!s.disabled) {
          if (H.addTag(sp.synonyms, s.term)) s.disabled = true;
        }
      });
    }

    function clearSynonymSuggestions() {
      synonymSuggestions.value = [];
      synonymTargetSp.value = null;
      synonymTargetKey.value = '';
    }

    async function suggestExclude(sq) {
      if (sq.scoringPoints.length === 0) return;
      excludeLoading.value = true;
      excludeSuggestions.value = [];
      excludeTargetSqId.value = sq.tempId;
      excludeTargetSq.value = sq;
      try {
        var result = await AI.suggestExclude(parentContent.value, sq);
        if (result) {
          excludeSuggestions.value = result;
        }
      } catch (e) {
        handleApiError(e, '排除词建议失败');
      } finally {
        excludeLoading.value = false;
      }
    }

    function addExcludeSuggestion(sq, suggestion) {
      if (suggestion.disabled) return;
      if (H.addTag(sq.excludeList, suggestion.term)) {
        suggestion.disabled = true;
      }
    }

    function addAllExcludeSuggestions() {
      var sq = excludeTargetSq.value;
      if (!sq) return;
      excludeSuggestions.value.forEach(function (s) {
        if (!s.disabled) {
          if (H.addTag(sq.excludeList, s.term)) s.disabled = true;
        }
      });
    }

    function clearExcludeSuggestions() {
      excludeSuggestions.value = [];
      excludeTargetSq.value = null;
      excludeTargetSqId.value = 0;
    }

    // ============================================================
    // 评分脚本 wrapper
    // ============================================================
    async function generateScript() {
      scriptGenerating.value = true;
      try {
        var script = await AI.generateScript(subQuestions.value, parentMaxScore.value);
        generatedScript.value = script;
        scriptCollapseActive.value = ['script'];
        markStepCompleted('script');
      } catch (e) {
        handleApiError(e, '脚本生成失败');
      }
      scriptGenerating.value = false;
    }

    async function selfCheckScript() {
      if (!generatedScript.value) return;
      selfCheckLoading.value = true;
      selfCheckResult.value = null;
      try {
        var result = await AI.selfCheckScript(generatedScript.value, subQuestions.value, parentMaxScore.value);
        selfCheckResult.value = result;
        if (result.issue_count === 0) {
          ElMessage.success('自查通过，未发现问题');
        }
      } catch (e) {
        handleApiError(e, '自查失败');
        ElMessage.error('自查失败：' + e.message);
      } finally {
        selfCheckLoading.value = false;
      }
    }

    function applyImprovedScript() {
      if (selfCheckResult.value && selfCheckResult.value.improved_script) {
        generatedScript.value = selfCheckResult.value.improved_script;
        selfCheckResult.value = null;
        ElMessage.success('已应用完善后的评分脚本');
      }
    }

    async function evaluateQuality() {
      var sqs = subQuestions.value;
      if (!sqs.length || !sqs[0].standardAnswer) {
        ElMessage.warning('请先完成子题配置');
        return;
      }
      qualityLoading.value = true;
      qualityResult.value = null;
      try {
        var result = await AI.evaluateQuality(subQuestions.value, parentMaxScore.value);
        qualityResult.value = result;
      } catch (e) {
        handleApiError(e, '质量评估失败');
        ElMessage.error('质量评估失败：' + e.message);
      } finally {
        qualityLoading.value = false;
      }
    }

    // ============================================================
    // 验证 + 保存 wrapper
    // ============================================================
    function validateAll() {
      var state = buildState();
      var result = VS.validateAll(state);
      validationResults.value = result.results;
      validationPassed.value = result.passed;
      if (result.passed) markStepCompleted('validate');
    }

    async function saveAll() {
      if (!validationPassed.value) return;
      pageLoading.value = true;
      try {
        var state = buildState();
        await VS.saveAll(state);
        markStepCompleted('save');
        await saveWorkflowStatus();
        ElMessage.success('保存成功！');
      } catch (e) {
        handleApiError(e, '保存失败');
      }
      pageLoading.value = false;
    }

    function saveWorkflowStatus() {
      var state = buildState();
      return VS.saveWorkflowStatus(state);
    }

    // ============================================================
    // 重置
    // ============================================================
    function confirmResetAll() {
      ElMessageBox.confirm(
        '重新提取将清空当前所有采分点和评分脚本配置，确定？',
        '确认',
        { confirmButtonText: '确定', cancelButtonText: '取消', type: 'warning' }
      ).then(function () {
        resetAll();
      }).catch(function () {});
    }

    function resetAll() {
      subQuestions.value = [];
      activeQuestionIndex.value = 0;
      currentStep.value = 'extract';
      completedSteps.value = [];
      generatedScript.value = '';
      pasteText.value = '';
      resetUIState();
    }

    // ============================================================
    // 返回（接口不变，模板零改动）
    // ============================================================
    return {
      // 状态
      pageLoading: pageLoading,
      currentParentId: currentParentId,
      parentTitle: parentTitle,
      parentContent: parentContent,
      parentContentHtml: parentContentHtml,
      parentContentEditing: parentContentEditing,
      parentMaxScore: parentMaxScore,
      isStateA: isStateA,
      rubricScript: rubricScript,
      pasteText: pasteText,
      currentStep: currentStep,
      activeQuestionIndex: activeQuestionIndex,
      completedSteps: completedSteps,
      subQuestions: subQuestions,
      generatedScript: generatedScript,
      scriptCollapseActive: scriptCollapseActive,
      validationResults: validationResults,
      validationPassed: validationPassed,
      extractingLoading: extractingLoading,
      scoringPointExtractingMap: scoringPointExtractingMap,
      synonymLoadingMap: synonymLoadingMap,
      excludeLoading: excludeLoading,
      scriptGenerating: scriptGenerating,
      synonymSuggestions: synonymSuggestions,
      synonymTargetKey: synonymTargetKey,
      excludeSuggestions: excludeSuggestions,
      excludeTargetSqId: excludeTargetSqId,
      // 计算属性
      canEnterStep: canEnterStep,
      stepIndex: stepIndex,
      subScoreSum: subScoreSum,
      scoreMatch: scoreMatch,
      // 常量
      WORKFLOW_STEPS: WORKFLOW_STEPS,
      // 方法
      loadQuestion: loadQuestion,
      goToStep: goToStep,
      completeCurrentQuestion: completeCurrentQuestion,
      confirmSubQuestion: confirmSubQuestion,
      goToQuestion: goToQuestion,
      extractFromPaste: extractFromPaste,
      addSubQuestion: addSubQuestion,
      removeSubQuestion: removeSubQuestion,
      addScoringPoint: addScoringPoint,
      removeScoringPoint: removeScoringPoint,
      addScoringRule: addScoringRule,
      removeScoringRule: removeScoringRule,
      suggestSynonyms: suggestSynonyms,
      addSynonymSuggestion: addSynonymSuggestion,
      addAllSynonymSuggestions: addAllSynonymSuggestions,
      clearSynonymSuggestions: clearSynonymSuggestions,
      suggestExclude: suggestExclude,
      addExcludeSuggestion: addExcludeSuggestion,
      addAllExcludeSuggestions: addAllExcludeSuggestions,
      clearExcludeSuggestions: clearExcludeSuggestions,
      extractScoringPoints: extractScoringPoints,
      generateScript: generateScript,
      selfCheckScript: selfCheckScript,
      applyImprovedScript: applyImprovedScript,
      evaluateQuality: evaluateQuality,
      selfCheckLoading: selfCheckLoading,
      selfCheckResult: selfCheckResult,
      qualityLoading: qualityLoading,
      qualityResult: qualityResult,
      validateAll: validateAll,
      saveAll: saveAll,
      isQuestionComplete: H.isQuestionComplete,
      confirmResetAll: confirmResetAll,
      resetAll: resetAll,
      addTag: H.addTag,
      removeTag: H.removeTag,
      addTagsFromPaste: H.addTagsFromPaste,
      buildApiPayload: function (sq) { return H.buildApiPayload(sq, subQuestions.value); },
      allQuestionsCompleted: allQuestionsCompleted,
    };
  }

  // ============================================================
  // 暴露到全局
  // ============================================================
  window.EnglishEditCore = {
    useEnglishEdit: useEnglishEdit,
    WORKFLOW_STEPS: WORKFLOW_STEPS,
    addTag: H.addTag,
    removeTag: H.removeTag,
    addTagsFromPaste: H.addTagsFromPaste,
  };
})();
