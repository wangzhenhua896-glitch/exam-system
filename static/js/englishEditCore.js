/**
 * 英语题目编辑器核心模块
 *
 * 暴露到 window.EnglishEditCore，question-bank.html 通过 setup() 调用。
 * 注意：非 ES Module 模式，内部使用 Vue 全局变量。
 */
(function () {
  'use strict';

  var API_BASE = '';
  var handleApiError = window.SharedApp.handleApiError;
  var ElMessage = ElementPlus.ElMessage;

  // ============================================================
  // 工作流步骤定义
  // ============================================================
  var WORKFLOW_STEPS = [
    { id: 'extract', label: '原题解析', icon: 'el-icon-document' },
    { id: 'per_question', label: '逐小问配置', icon: 'el-icon-edit' },
    { id: 'script', label: '评分脚本', icon: 'el-icon-files' },
    { id: 'validate', label: '一致性验证', icon: 'el-icon-circle-check' },
    { id: 'save', label: '确认保存', icon: 'el-icon-upload' },
  ];

  // ============================================================
  // Tag Chip 工具函数
  // ============================================================
  function addTag(list, value) {
    if (!value || !value.trim()) return false;
    var v = value.trim().toLowerCase();
    for (var i = 0; i < list.length; i++) {
      if (list[i].toLowerCase() === v) return false; // 去重
    }
    list.push(value.trim());
    return true;
  }

  function removeTag(list, index) {
    list.splice(index, 1);
  }

  function addTagsFromPaste(list, pastedText) {
    // 支持逗号分隔的批量添加
    var parts = pastedText.split(/[,，;；\n]+/);
    var added = 0;
    parts.forEach(function (p) {
      if (addTag(list, p)) added++;
    });
    return added;
  }

  // ============================================================
  // 创建空白子题表单
  // ============================================================
  function createEmptySubQuestion() {
    return {
      id: 0,
      tempId: Date.now(),
      text: '',
      standardAnswer: '',
      maxScore: 2,
      scoreFormulaType: 'max_hit_score', // 'max_hit_score' | 'hit_count'
      scoringPoints: [],
      scoringRules: [{ minHits: 2, score: 2 }, { minHits: 1, score: 1 }],
      excludeList: [],
      pinyinWhitelist: [],
      // 工作流状态
      status: 'pending', // pending | in_progress | completed
      expanded: true,
      // 关联的 DB ID
      questionId: null,
      answerId: null,
    };
  }

  function createEmptyScoringPoint(label) {
    return {
      id: label || 'A',
      score: 1,
      keywords: [],
      synonyms: [],
    };
  }

  // ============================================================
  // useEnglishEdit — 主 composable
  // ============================================================
  function useEnglishEdit() {
    var ref = Vue.ref;
    var computed = Vue.computed;

    // ---- 页面状态 ----
    var pageLoading = ref(false);
    var currentParentId = ref(null);  // 父题 ID
    var parentTitle = ref('');
    var parentContent = ref('');       // 阅读材料（纯文本）
    var parentContentHtml = ref('');   // 阅读材料（HTML 格式，来自 original_text）
    var parentContentEditing = ref(false); // 是否处于编辑模式
    var parentMaxScore = ref(6);
    var parentSubject = ref('english');
    var isStateA = ref(false);         // true=有子题(166-169), false=仅脚本(170-177)
    var rubricScript = ref('');        // 现有评分脚本（状态B用）
    var pasteText = ref('');           // 粘贴原题文本框

    // ---- 工作流状态 ----
    var currentStep = ref('extract'); // extract | per_question | script | validate | save
    var activeQuestionIndex = ref(0);
    var completedSteps = ref([]);
    var workflowStatus = ref(null);   // 原始 workflow_status JSON

    // ---- 子题列表 ----
    var subQuestions = ref([]);

    // ---- 评分脚本（step3） ----
    var generatedScript = ref('');
    var selfCheckLoading = ref(false);
    var selfCheckResult = ref(null);
    var qualityLoading = ref(false);
    var qualityResult = ref(null);

    // ---- 验证结果（step4） ----
    var validationResults = ref([]);
    var validationPassed = ref(false);

    // ---- AI 操作 loading ----
    var extractingLoading = ref(false);
    var synonymLoadingMap = ref({});   // key: spKey, val: bool
    var excludeLoading = ref(false);
    var scriptGenerating = ref(false);

    // ---- AI 建议结果（UI 弹出面板用） ----
    var synonymSuggestions = ref([]);   // [{term, confidence, disabled}]
    var synonymTargetKey = ref('');     // 当前建议的目标 key: sq.tempId + '_' + spIndex
    var synonymTargetSp = ref(null);    // 当前建议的目标 scoringPoint
    var excludeSuggestions = ref([]);   // [{term, reason, disabled}]
    var excludeTargetSqId = ref(0);     // 当前建议的目标子题 tempId
    var excludeTargetSq = ref(null);    // 当前建议的目标 subQuestion

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
      return subQuestions.value.reduce(function (sum, sq) { return sum + (sq.maxScore || 0); }, 0);
    });

    var scoreMatch = computed(function () {
      return subScoreSum.value === parentMaxScore.value;
    });

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

    function isQuestionComplete(sq) {
      if (!sq.text || !sq.text.trim()) return false;
      if (!sq.standardAnswer || !sq.standardAnswer.trim()) return false;
      if (sq.scoringPoints.length === 0) return false;
      for (var i = 0; i < sq.scoringPoints.length; i++) {
        if (sq.scoringPoints[i].keywords.length === 0) return false;
      }
      if (sq.scoreFormulaType === 'hit_count' && sq.scoringRules.length === 0) return false;
      return true;
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
      if (!sq || !isQuestionComplete(sq)) return;
      sq.status = 'completed';
      sq.expanded = false;

      // 推进到下一题
      if (activeQuestionIndex.value < subQuestions.value.length - 1) {
        activeQuestionIndex.value++;
        collapseAllSubQuestions();
        subQuestions.value[activeQuestionIndex.value].status = 'in_progress';
        subQuestions.value[activeQuestionIndex.value].expanded = true;
      } else {
        // 全部完成
        markStepCompleted('per_question');
      }
      saveWorkflowStatus();
    }

    function confirmSubQuestion(qi) {
      var sq = subQuestions.value[qi];
      if (!sq || !isQuestionComplete(sq)) return;
      sq.status = 'completed';
      sq.expanded = false;

      // 如果确认的是当前活跃题，推进到下一题
      if (qi === activeQuestionIndex.value && activeQuestionIndex.value < subQuestions.value.length - 1) {
        activeQuestionIndex.value++;
        collapseAllSubQuestions();
        subQuestions.value[activeQuestionIndex.value].status = 'in_progress';
        subQuestions.value[activeQuestionIndex.value].expanded = true;
      }

      // 检查是否全部完成
      if (allQuestionsCompleted()) {
        markStepCompleted('per_question');
      }
      saveWorkflowStatus();
    }

    function goToQuestion(index) {
      // 回到之前的题目修改
      if (index >= 0 && index < subQuestions.value.length) {
        // 把当前活跃题之后的所有题打回 pending
        for (var i = index; i < subQuestions.value.length; i++) {
          subQuestions.value[i].status = 'pending';
          subQuestions.value[i].expanded = false;
        }
        collapseAllSubQuestions();
        activeQuestionIndex.value = index;
        subQuestions.value[index].status = 'in_progress';
        subQuestions.value[index].expanded = true;
        // 移除 per_question 完成标记
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
      currentParentId.value = questionId;
      subQuestions.value = [];
      generatedScript.value = '';
      completedSteps.value = [];
      validationPassed.value = false;
      activeQuestionIndex.value = 0;

      try {
        // 加载父题
        var res = await axios.get(API_BASE + '/api/questions/' + questionId);
        if (!res.data.success) { pageLoading.value = false; return; }
        var parent = res.data.data;
        parentTitle.value = parent.title || '';
        parentMaxScore.value = parent.max_score || 6;
        parentSubject.value = parent.subject || 'english';
        rubricScript.value = parent.rubric_script || '';

        // 解析阅读材料
        parentContent.value = extractReadingMaterial(parent.content || '');
        // 保留 HTML 格式的原始材料（来自 original_text 或 content_html）
        parentContentHtml.value = parent.original_text || parent.content_html || '';

        // 恢复 workflow_status
        if (parent.workflow_status) {
          workflowStatus.value = typeof parent.workflow_status === 'string'
            ? JSON.parse(parent.workflow_status) : parent.workflow_status;
        }

        // 加载子题
        var childRes = await axios.get(API_BASE + '/api/questions/' + questionId + '/children');
        var children = childRes.data.data || [];

        if (children.length > 0) {
          isStateA.value = true;
          await loadChildren(children);
        } else {
          isStateA.value = false;
          // 状态B：根据 workflow_status 推断步骤
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
        var sq = createEmptySubQuestion();
        sq.id = child.id;
        sq.questionId = child.id;
        sq.text = child.content || child.title || '';
        sq.standardAnswer = child.standard_answer || '';
        sq.maxScore = child.max_score || 2;

        // 解析 rubric 获取计分公式
        var rubric = child.rubric;
        if (typeof rubric === 'string') {
          try { rubric = JSON.parse(rubric); } catch (e) { rubric = {}; }
        }
        if (rubric && rubric.scoring_strategy === 'max_hit_score') {
          sq.scoreFormulaType = 'max_hit_score';
        } else if (rubric && rubric.scoring_strategy === 'hit_count') {
          sq.scoreFormulaType = 'hit_count';
        }

        // 加载采分点
        try {
          var ansRes = await axios.get(API_BASE + '/api/questions/' + child.id + '/answers?scope_type=scoring_point');
          var answers = ansRes.data.data || [];
          for (var j = 0; j < answers.length; j++) {
            sq.answerId = answers[j].id;
            try {
              var spJson = JSON.parse(answers[j].answer_text);
              loadScoringPointFromJson(sq, spJson);
            } catch (e) {
              console.warn('解析采分点 JSON 失败', e);
            }
          }
        } catch (e) { /* ignore */ }

        // 从 workflow_status 恢复状态
        if (workflowStatus.value && workflowStatus.value.question_status) {
          sq.status = workflowStatus.value.question_status[String(child.id)] || 'pending';
        }
        // 数据完整性校验：如果 workflow 认为已完成但数据不完整，重置为 pending
        if (sq.status === 'completed' && !isQuestionComplete(sq)) {
          sq.status = 'pending';
        }
        sq.expanded = (sq.status === 'in_progress');
        loaded.push(sq);
      }
      subQuestions.value = loaded;

      // 恢复活跃题索引
      if (workflowStatus.value && typeof workflowStatus.value.active_question_index === 'number') {
        activeQuestionIndex.value = workflowStatus.value.active_question_index;
      } else {
        // 找第一个非 completed 的题
        var idx = loaded.findIndex(function (sq) { return sq.status !== 'completed'; });
        activeQuestionIndex.value = idx >= 0 ? idx : 0;
      }
      // 确保活跃题索引指向一个非 completed 的题
      var activeSq = loaded[activeQuestionIndex.value];
      if (!activeSq || activeSq.status === 'completed') {
        var fixIdx = loaded.findIndex(function (sq) { return sq.status !== 'completed'; });
        activeQuestionIndex.value = fixIdx >= 0 ? fixIdx : 0;
      }
      // 如果没有任何 completed 的题，从第一题开始
      var hasAnyCompleted = loaded.some(function (sq) { return sq.status === 'completed'; });
      if (!hasAnyCompleted && activeQuestionIndex.value > 0) {
        activeQuestionIndex.value = 0;
      }

      // 确保活跃题处于 in_progress 状态且展开，其他题折叠
      loaded.forEach(function (sq, i) {
        if (i === activeQuestionIndex.value && sq.status !== 'completed') {
          sq.status = 'in_progress';
          sq.expanded = true;
        } else if (sq.status !== 'completed') {
          sq.expanded = false;
        }
      });

      // 恢复 currentStep
      if (workflowStatus.value && workflowStatus.value.current_step) {
        currentStep.value = workflowStatus.value.current_step;
        completedSteps.value = workflowStatus.value.completed_steps || [];
      } else {
        // 推断步骤
        if (allQuestionsCompleted()) {
          currentStep.value = 'script';
          completedSteps.value = ['extract', 'per_question'];
        } else {
          currentStep.value = 'per_question';
          completedSteps.value = ['extract'];
        }
      }
    }

    function loadScoringPointFromJson(sq, spJson) {
      // 从评分引擎消费的 JSON 格式加载到表单状态
      sq.scoreFormulaType = (spJson.score_formula === 'max_hit_score')
        ? 'max_hit_score'
        : (typeof spJson.score_formula === 'object' && spJson.score_formula && spJson.score_formula.type === 'hit_count')
          ? 'hit_count' : sq.scoreFormulaType;

      if (typeof spJson.score_formula === 'object' && spJson.score_formula && spJson.score_formula.rules) {
        sq.scoringRules = spJson.score_formula.rules.map(function (r) {
          return { minHits: r.min_hits, score: r.score };
        });
      }

      if (spJson.scoring_points) {
        sq.scoringPoints = spJson.scoring_points.map(function (sp) {
          return {
            id: sp.id || 'A',
            score: sp.score || 1,
            keywords: (sp.keywords || []).slice(),
            synonyms: (sp.synonyms || []).slice(),
          };
        });
      }

      sq.excludeList = (spJson.exclude_list || []).slice();
      sq.pinyinWhitelist = (spJson.pinyin_whitelist || []).slice();
      sq.maxScore = spJson.max_score || sq.maxScore;
    }

    function restoreWorkflowState() {
      var ws = workflowStatus.value;
      currentStep.value = ws.current_step || 'extract';
      completedSteps.value = ws.completed_steps || [];
      activeQuestionIndex.value = ws.active_question_index || 0;
    }

    // ============================================================
    // 阅读材料拆分
    // ============================================================
    function extractReadingMaterial(content) {
      // 移除 HTML 标签
      var text = content.replace(/<[^>]+>/g, '\n').replace(/\n{3,}/g, '\n\n').trim();
      // 找 "简答题问题" 分隔符
      var markers = ['简答题问题', 'Short Answer Questions', 'Answer the following'];
      for (var i = 0; i < markers.length; i++) {
        var idx = text.indexOf(markers[i]);
        if (idx > 0) {
          return text.substring(0, idx).trim();
        }
      }
      // 按行首数字编号拆分
      var lines = text.split('\n');
      var material = [];
      for (var j = 0; j < lines.length; j++) {
        if (/^\s*\d+[\.\)）]/.test(lines[j])) break;
        material.push(lines[j]);
      }
      return material.join('\n').trim() || text;
    }

    // ============================================================
    // Step1: AI 智能解析
    // ============================================================
    async function extractFromPaste() {
      if (!pasteText.value.trim()) return;
      extractingLoading.value = true;
      try {
        var res = await axios.post(API_BASE + '/api/english/extract', {
          full_text: pasteText.value,
        });
        if (res.data.success && res.data.data) {
          var data = res.data.data;
          if (data.reading_material) {
            parentContent.value = data.reading_material;
          }
          subQuestions.value = data.sub_questions.map(function (sq, idx) {
            var form = createEmptySubQuestion();
            form.text = sq.text || '';
            form.standardAnswer = sq.standard_answer || '';
            form.maxScore = sq.max_score || 2;
            form.scoreFormulaType = (typeof sq.score_formula === 'string' && sq.score_formula === 'max_hit_score')
              ? 'max_hit_score'
              : (typeof sq.score_formula === 'object' ? 'hit_count' : 'max_hit_score');
            if (typeof sq.score_formula === 'object' && sq.score_formula.rules) {
              form.scoringRules = sq.score_formula.rules.map(function (r) {
                return { minHits: r.min_hits, score: r.score };
              });
            }
            form.scoringPoints = (sq.scoring_points || []).map(function (sp) {
              return {
                id: sp.id || String.fromCharCode(65 + form.scoringPoints.length),
                score: sp.score || 1,
                keywords: (sp.keywords || []).slice(),
                synonyms: (sp.synonyms || []).slice(),
              };
            });
            form.excludeList = (sq.exclude_list || []).slice();
            form.pinyinWhitelist = (sq.pinyin_whitelist || []).slice();
            form.status = 'pending';
            form.expanded = (idx === 0);
            return form;
          });
          if (subQuestions.value.length > 0) {
            subQuestions.value[0].status = 'in_progress';
            activeQuestionIndex.value = 0;
            markStepCompleted('extract');
            currentStep.value = 'per_question';
            saveWorkflowStatus();
          }
        } else {
          ElMessage.error('AI 提取失败：' + (res.data.error || '返回数据异常'));
        }
      } catch (e) {
        handleApiError(e, 'AI 提取异常');
      }
      extractingLoading.value = false;
    }

    // 手动添加子题
    function addSubQuestion() {
      var sq = createEmptySubQuestion();
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

    // ============================================================
    // Step2: 采分点操作
    // ============================================================
    function addScoringPoint(sq) {
      var nextLabel = String.fromCharCode(65 + sq.scoringPoints.length);
      sq.scoringPoints.push(createEmptyScoringPoint(nextLabel));
    }

    function removeScoringPoint(sq, index) {
      sq.scoringPoints.splice(index, 1);
      // 重新编号
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
    // AI 补全
    // ============================================================
    async function suggestSynonyms(sq, spIndex) {
      var sp = sq.scoringPoints[spIndex];
      if (!sp || sp.keywords.length === 0) return;
      var spKey = sq.tempId + '_' + spIndex;
      synonymLoadingMap.value[spKey] = true;
      synonymSuggestions.value = [];
      synonymTargetKey.value = spKey;
      synonymTargetSp.value = sp;
      try {
        var allExisting = sp.keywords.concat(sp.synonyms);
        var res = await axios.post(API_BASE + '/api/english/suggest-synonyms', {
          keyword: sp.keywords[0],
          context: parentContent.value,
          question_text: sq.text,
          existing_synonyms: allExisting,
        });
        if (res.data.success) {
          var suggestions = res.data.data || [];
          // 标记已存在的词
          synonymSuggestions.value = suggestions.map(function (s) {
            var termLower = (s.term || '').toLowerCase();
            var exists = allExisting.some(function (e) { return e.toLowerCase() === termLower; });
            return { term: s.term, confidence: s.confidence, disabled: exists };
          });
        }
      } catch (e) {
        handleApiError(e, '同义词补全失败');
      } finally {
        synonymLoadingMap.value[spKey] = false;
      }
    }

    function addSynonymSuggestion(sp, suggestion) {
      if (suggestion.disabled) return;
      if (addTag(sp.synonyms, suggestion.term)) {
        suggestion.disabled = true;
      }
    }

    function addAllSynonymSuggestions() {
      var sp = synonymTargetSp.value;
      if (!sp) return;
      synonymSuggestions.value.forEach(function (s) {
        if (!s.disabled) {
          if (addTag(sp.synonyms, s.term)) s.disabled = true;
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
      var allKeywords = [];
      var allSynonyms = [];
      sq.scoringPoints.forEach(function (sp) {
        allKeywords = allKeywords.concat(sp.keywords);
        allSynonyms = allSynonyms.concat(sp.synonyms);
      });
      excludeLoading.value = true;
      excludeSuggestions.value = [];
      excludeTargetSqId.value = sq.tempId;
      excludeTargetSq.value = sq;
      try {
        var res = await axios.post(API_BASE + '/api/english/suggest-exclude', {
          question_text: sq.text,
          keywords: allKeywords,
          synonyms: allSynonyms,
          context: parentContent.value,
        });
        if (res.data.success) {
          var suggestions = res.data.data || [];
          // 标记已存在的词
          excludeSuggestions.value = suggestions.map(function (s) {
            var termLower = (s.term || '').toLowerCase();
            var exists = sq.excludeList.some(function (e) { return e.toLowerCase() === termLower; });
            return { term: s.term, reason: s.reason, disabled: exists };
          });
        }
      } catch (e) {
        handleApiError(e, '排除词建议失败');
      } finally {
        excludeLoading.value = false;
      }
    }

    function addExcludeSuggestion(sq, suggestion) {
      if (suggestion.disabled) return;
      if (addTag(sq.excludeList, suggestion.term)) {
        suggestion.disabled = true;
      }
    }

    function addAllExcludeSuggestions() {
      var sq = excludeTargetSq.value;
      if (!sq) return;
      excludeSuggestions.value.forEach(function (s) {
        if (!s.disabled) {
          if (addTag(sq.excludeList, s.term)) s.disabled = true;
        }
      });
    }

    function clearExcludeSuggestions() {
      excludeSuggestions.value = [];
      excludeTargetSq.value = null;
      excludeTargetSqId.value = 0;
    }

    async function extractScoringPoints(sq) {
      if (!sq.text || !sq.standardAnswer) return;
      extractingLoading.value = true;
      try {
        var res = await axios.post(API_BASE + '/api/english/extract-scoring-points', {
          question_text: sq.text,
          standard_answer: sq.standardAnswer,
          max_score: sq.maxScore,
        });
        if (res.data.success && res.data.data) {
          var data = res.data.data;
          if (data.scoring_points) {
            sq.scoringPoints = data.scoring_points.map(function (sp) {
              return {
                id: sp.id || 'A',
                score: sp.score || 1,
                keywords: (sp.keywords || []).slice(),
                synonyms: (sp.synonyms || []).slice(),
              };
            });
            sq.scoreFormulaType = (typeof data.score_formula === 'string' && data.score_formula === 'max_hit_score')
              ? 'max_hit_score' : 'hit_count';
            if (data.exclude_list) sq.excludeList = data.exclude_list.slice();
          }
        }
      } catch (e) {
        handleApiError(e, '采分点提取失败');
      }
      extractingLoading.value = false;
    }

    // ============================================================
    // Step3: 评分脚本生成
    // ============================================================
    async function generateScript() {
      scriptGenerating.value = true;
      try {
        var configs = subQuestions.value.map(function (sq) {
          return {
            question_text: sq.text,
            standard_answer: sq.standardAnswer,
            max_score: sq.maxScore,
            scoring_points: sq.scoringPoints,
            score_formula: sq.scoreFormulaType,
            exclude_list: sq.excludeList,
          };
        });
        var res = await axios.post(API_BASE + '/api/english/generate-rubric', {
          question_text: subQuestions.value.map(function (sq) { return sq.text; }).join('\n'),
          standard_answer: subQuestions.value.map(function (sq) { return sq.standardAnswer; }).join('\n'),
          max_score: parentMaxScore.value,
          scoring_config: configs,
        });
        if (res.data.success) {
          generatedScript.value = res.data.data.script;
          markStepCompleted('script');
        }
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
        var allContent = subQuestions.value.map(function (sq) { return sq.text; }).join('\n');
        var allAnswer = subQuestions.value.map(function (sq) { return sq.standardAnswer; }).join('\n');
        var res = await axios.post(API_BASE + '/api/self-check-rubric', {
          content: allContent,
          score: parentMaxScore.value,
          standardAnswer: allAnswer,
          rubricScript: generatedScript.value,
          subject: 'english',
        });
        if (res.data.success) {
          selfCheckResult.value = res.data.data;
          if (res.data.data.issue_count === 0) {
            ElMessage.success('自查通过，未发现问题');
          }
        } else {
          ElMessage.error('自查失败：' + (res.data.error || '未知错误'));
        }
      } catch (e) {
        handleApiError(e, '自查失败');
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
        var res = await axios.post(API_BASE + '/api/evaluate-question', {
          content: sqs.map(function (sq) { return sq.text; }).join('\n'),
          standardAnswer: sqs.map(function (sq) { return sq.standardAnswer; }).join('\n'),
          maxScore: parentMaxScore.value,
          subject: 'english',
        });
        if (res.data.success) {
          qualityResult.value = res.data.data;
        } else {
          ElMessage.error('质量评估失败：' + (res.data.error || '未知错误'));
        }
      } catch (e) {
        handleApiError(e, '质量评估失败');
      } finally {
        qualityLoading.value = false;
      }
    }

    // ============================================================
    // Step4: 一致性验证
    // ============================================================
    function validateAll() {
      var results = [];
      // V1: 子题分值之和 = 总分
      var sum = subScoreSum.value;
      if (sum !== parentMaxScore.value) {
        results.push({ rule: 'V1', level: 'error', message: '子题分值之和 (' + sum + ') 不等于总分 (' + parentMaxScore.value + ')' });
      } else {
        results.push({ rule: 'V1', level: 'ok', message: '子题分值之和 = 总分 (' + sum + ')' });
      }
      // V2 & V3
      subQuestions.value.forEach(function (sq, qi) {
        if (sq.scoringPoints.length === 0) {
          results.push({ rule: 'V2', level: 'error', message: 'Q' + (qi + 1) + ' 没有采分点' });
        }
        sq.scoringPoints.forEach(function (sp, si) {
          if (sp.keywords.length === 0) {
            results.push({ rule: 'V3', level: 'error', message: 'Q' + (qi + 1) + ' 采分点 ' + sp.id + ' 没有关键词' });
          }
        });
      });
      // V4 & V5 & V9: hit_count 规则
      subQuestions.value.forEach(function (sq, qi) {
        if (sq.scoreFormulaType === 'hit_count') {
          if (sq.scoringRules.length === 0) {
            results.push({ rule: 'V4', level: 'error', message: 'Q' + (qi + 1) + ' hit_count 无计分规则' });
          }
          var hits = sq.scoringRules.map(function (r) { return r.minHits; });
          var uniqueHits = hits.filter(function (v, i) { return hits.indexOf(v) === i; });
          if (hits.length !== uniqueHits.length) {
            results.push({ rule: 'V5', level: 'error', message: 'Q' + (qi + 1) + ' hit_count 有重复命中数' });
          }
          sq.scoringRules.forEach(function (r) {
            if (r.score > sq.maxScore) {
              results.push({ rule: 'V9', level: 'error', message: 'Q' + (qi + 1) + ' 规则得分 ' + r.score + ' 超过满分 ' + sq.maxScore });
            }
          });
        }
      });
      // V6: 采分点编号唯一
      subQuestions.value.forEach(function (sq, qi) {
        var ids = sq.scoringPoints.map(function (sp) { return sp.id; });
        var uniqueIds = ids.filter(function (v, i) { return ids.indexOf(v) === i; });
        if (ids.length !== uniqueIds.length) {
          results.push({ rule: 'V6', level: 'error', message: 'Q' + (qi + 1) + ' 采分点编号不唯一' });
        }
      });
      // V7: 排除词与关键词不重叠 (warning)
      subQuestions.value.forEach(function (sq, qi) {
        var allKw = [];
        sq.scoringPoints.forEach(function (sp) { allKw = allKw.concat(sp.keywords.map(function (k) { return k.toLowerCase(); })); });
        sq.excludeList.forEach(function (ex) {
          if (allKw.indexOf(ex.toLowerCase()) >= 0) {
            results.push({ rule: 'V7', level: 'warning', message: 'Q' + (qi + 1) + ' 排除词 "' + ex + '" 与关键词重叠' });
          }
        });
      });

      var hasError = results.some(function (r) { return r.level === 'error'; });
      validationResults.value = results;
      validationPassed.value = !hasError;
      if (!hasError) markStepCompleted('validate');
    }

    // ============================================================
    // Step5: 保存
    // ============================================================
    async function saveAll() {
      if (!validationPassed.value) return;
      pageLoading.value = true;
      try {
        // 1. 更新父题
        await axios.put(API_BASE + '/api/questions/' + currentParentId.value, {
          content: parentContent.value,
          max_score: parentMaxScore.value,
          rubric_script: generatedScript.value || rubricScript.value,
          rubric: { type: 'essay', version: '2.0' },
          question_type: 'essay',
          workflow_status: buildWorkflowStatusJson(),
        });

        // 2. 更新每个子题
        for (var i = 0; i < subQuestions.value.length; i++) {
          var sq = subQuestions.value[i];
          var payload = buildApiPayload(sq);
          // 更新子题基本信息
          if (sq.questionId) {
            await axios.put(API_BASE + '/api/questions/' + sq.questionId, {
              content: sq.text,
              standard_answer: sq.standardAnswer,
              max_score: sq.maxScore,
              scoring_strategy: 'max',
              rubric: { type: 'essay', scoring_strategy: sq.scoreFormulaType },
              rubric_script: generatedScript.value || rubricScript.value,
              parent_id: currentParentId.value,
            });
            // 更新采分点答案
            if (sq.answerId) {
              await axios.put(API_BASE + '/api/questions/' + sq.questionId + '/answers/' + sq.answerId, {
                answer_text: JSON.stringify(payload),
              });
            } else {
              // 新建采分点答案
              var ansRes = await axios.post(API_BASE + '/api/questions/' + sq.questionId + '/answers', {
                scope_type: 'scoring_point',
                answer_text: JSON.stringify(payload),
                label: sq.text.substring(0, 50),
              });
              sq.answerId = ansRes.data.data.id;
            }
          } else {
            // 新子题（手动添加的）
            var childRes = await axios.post(API_BASE + '/api/questions', {
              subject: 'english',
              title: sq.text.substring(0, 50),
              content: sq.text,
              standard_answer: sq.standardAnswer,
              max_score: sq.maxScore,
              rubric: { type: 'essay', scoring_strategy: sq.scoreFormulaType },
              scoring_strategy: 'max',
              parent_id: currentParentId.value,
              question_type: 'essay',
              rubric_script: generatedScript.value || rubricScript.value,
            });
            sq.questionId = childRes.data.data.id;
            await axios.post(API_BASE + '/api/questions/' + sq.questionId + '/answers', {
              scope_type: 'scoring_point',
              answer_text: JSON.stringify(payload),
              label: sq.text.substring(0, 50),
            });
          }
        }

        markStepCompleted('save');
        // 保存 workflow_status
        await saveWorkflowStatus();
      } catch (e) {
        handleApiError(e, '保存失败');
      }
      pageLoading.value = false;
    }

    // ============================================================
    // JSON ↔ 表单映射：buildApiPayload
    // 注意：格式必须与 english_scoring_point_match() 完全一致
    // 参见计划文档中的 6 个坑点
    // ============================================================
    function buildApiPayload(sq) {
      var payload = {
        id: 'Q' + (subQuestions.value.indexOf(sq) + 1),
        max_score: sq.maxScore,
        scoring_points: sq.scoringPoints.map(function (sp) {
          return {
            id: sp.id,
            score: sp.score,
            keywords: sp.keywords.map(function (k) { return k.toLowerCase(); }),
            synonyms: sp.synonyms.map(function (s) { return s.toLowerCase(); }),
          };
        }),
        exclude_list: sq.excludeList.slice(),
        pinyin_whitelist: sq.pinyinWhitelist.slice(),
      };

      // 坑1: max_hit_score 是字符串，hit_count 是对象
      if (sq.scoreFormulaType === 'max_hit_score') {
        payload.score_formula = 'max_hit_score';
      } else {
        payload.score_formula = {
          type: 'hit_count',
          rules: sq.scoringRules.map(function (r) {
            return { min_hits: r.minHits, score: r.score };
          }),
        };
      }
      return payload;
    }

    function buildWorkflowStatusJson() {
      var qs = {};
      subQuestions.value.forEach(function (sq) {
        if (sq.questionId) {
          qs[String(sq.questionId)] = sq.status;
        }
      });
      return JSON.stringify({
        current_step: currentStep.value,
        active_question_index: activeQuestionIndex.value,
        completed_steps: completedSteps.value.slice(),
        question_status: qs,
        updated_at: new Date().toISOString(),
      });
    }

    async function saveWorkflowStatus() {
      if (!currentParentId.value) return;
      try {
        await axios.put(API_BASE + '/api/questions/' + currentParentId.value + '/workflow-status', {
          workflow_status: buildWorkflowStatusJson(),
        });
      } catch (e) {
        console.warn('workflow_status 保存失败', e);
      }
    }

    // ============================================================
    // 重新提取
    // ============================================================
    function resetAll() {
      subQuestions.value = [];
      activeQuestionIndex.value = 0;
      currentStep.value = 'extract';
      completedSteps.value = [];
      generatedScript.value = '';
      validationResults.value = [];
      validationPassed.value = false;
      pasteText.value = '';
    }

    // ============================================================
    // 返回
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
      validationResults: validationResults,
      validationPassed: validationPassed,
      extractingLoading: extractingLoading,
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
      isQuestionComplete: isQuestionComplete,
      resetAll: resetAll,
      addTag: addTag,
      removeTag: removeTag,
      addTagsFromPaste: addTagsFromPaste,
      buildApiPayload: buildApiPayload,
      allQuestionsCompleted: allQuestionsCompleted,
    };
  }

  // ============================================================
  // 暴露到全局
  // ============================================================
  window.EnglishEditCore = {
    useEnglishEdit: useEnglishEdit,
    WORKFLOW_STEPS: WORKFLOW_STEPS,
    addTag: addTag,
    removeTag: removeTag,
    addTagsFromPaste: addTagsFromPaste,
  };
})();
