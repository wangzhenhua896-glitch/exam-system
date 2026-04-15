/**
 * 英语编辑器 — 验证 + 保存
 *
 * 函数接收状态参数对象，返回结果或执行保存。
 * 暴露到 window.EnglishEditValidateSave。
 */
(function () {
  'use strict';

  var API_BASE = '';
  var handleApiError = window.SharedApp.handleApiError;
  var ElMessage = ElementPlus.ElMessage;
  var H = window.EnglishEditHelpers;

  // ============================================================
  // V1-V9 规则验证
  // state = { subQuestions, subScoreSum, parentMaxScore }
  // 返回 { results: [...], passed: bool }
  // ============================================================
  function validateAll(state) {
    var results = [];
    var sum = state.subScoreSum;

    // V1: 子题分值之和 = 总分
    if (sum !== state.parentMaxScore) {
      results.push({ rule: 'V1', level: 'error', message: '子题分值之和 (' + sum + ') 不等于总分 (' + state.parentMaxScore + ')' });
    } else {
      results.push({ rule: 'V1', level: 'ok', message: '子题分值之和 = 总分 (' + sum + ')' });
    }

    // V2 & V3
    state.subQuestions.forEach(function (sq, qi) {
      if (sq.scoringPoints.length === 0) {
        results.push({ rule: 'V2', level: 'error', qi: qi, message: 'Q' + (qi + 1) + ' 没有采分点' });
      }
      sq.scoringPoints.forEach(function (sp) {
        if (sp.keywords.length === 0) {
          results.push({ rule: 'V3', level: 'error', qi: qi, message: 'Q' + (qi + 1) + ' 采分点 ' + sp.id + ' 没有关键词' });
        }
      });
    });

    // V4 & V5 & V9: hit_count 规则
    state.subQuestions.forEach(function (sq, qi) {
      if (sq.scoreFormulaType === 'hit_count') {
        if (sq.scoringRules.length === 0) {
          results.push({ rule: 'V4', level: 'error', qi: qi, message: 'Q' + (qi + 1) + ' hit_count 无计分规则' });
        }
        var hits = sq.scoringRules.map(function (r) { return r.minHits; });
        var uniqueHits = hits.filter(function (v, i) { return hits.indexOf(v) === i; });
        if (hits.length !== uniqueHits.length) {
          results.push({ rule: 'V5', level: 'error', qi: qi, message: 'Q' + (qi + 1) + ' hit_count 有重复命中数' });
        }
        sq.scoringRules.forEach(function (r) {
          if (r.score > sq.maxScore) {
            results.push({ rule: 'V9', level: 'error', qi: qi, message: 'Q' + (qi + 1) + ' 规则得分 ' + r.score + ' 超过满分 ' + sq.maxScore });
          }
        });
      }
    });

    // V6: 采分点编号唯一
    state.subQuestions.forEach(function (sq, qi) {
      var ids = sq.scoringPoints.map(function (sp) { return sp.id; });
      var uniqueIds = ids.filter(function (v, i) { return ids.indexOf(v) === i; });
      if (ids.length !== uniqueIds.length) {
        results.push({ rule: 'V6', level: 'error', qi: qi, message: 'Q' + (qi + 1) + ' 采分点编号不唯一' });
      }
    });

    // V7: 排除词与关键词不重叠 (warning)
    state.subQuestions.forEach(function (sq, qi) {
      var allKw = [];
      sq.scoringPoints.forEach(function (sp) {
        allKw = allKw.concat(sp.keywords.map(function (k) { return k.toLowerCase(); }));
      });
      sq.excludeList.forEach(function (ex) {
        if (allKw.indexOf(ex.toLowerCase()) >= 0) {
          results.push({ rule: 'V7', level: 'warning', qi: qi, message: 'Q' + (qi + 1) + ' 排除词 "' + ex + '" 与关键词重叠' });
        }
      });
    });

    // V8: 每个子题的采分点分值之和必须等于子题满分
    state.subQuestions.forEach(function (sq, qi) {
      var spSum = sq.scoringPoints.reduce(function (sum, sp) { return sum + (sp.score || 0); }, 0);
      if (spSum !== sq.maxScore) {
        results.push({ rule: 'V8', level: 'error', qi: qi, message: 'Q' + (qi + 1) + ' 采分点分值之和 (' + spSum + ') 不等于满分 (' + sq.maxScore + ')' });
      }
    });

    var hasError = results.some(function (r) { return r.level === 'error'; });
    return { results: results, passed: !hasError };
  }

  // ============================================================
  // 保存
  // state = { currentParentId, parentContent, parentMaxScore, generatedScript,
  //           rubricScript, subQuestions, validationPassed }
  // ============================================================
  async function saveAll(state) {
    // 1. 更新父题
    await axios.put(API_BASE + '/api/questions/' + state.currentParentId, {
      content: state.parentContent,
      max_score: state.parentMaxScore,
      rubric_script: state.generatedScript || state.rubricScript,
      rubric: { type: 'essay', version: '2.0' },
      question_type: 'essay',
      workflow_status: H.buildWorkflowStatusJson(state),
    });

    // 2. 更新每个子题
    for (var i = 0; i < state.subQuestions.length; i++) {
      var sq = state.subQuestions[i];
      var payload = H.buildApiPayload(sq, state.subQuestions);

      if (sq.questionId) {
        await axios.put(API_BASE + '/api/questions/' + sq.questionId, {
          content: sq.text,
          standard_answer: sq.standardAnswer,
          max_score: sq.maxScore,
          scoring_strategy: 'max',
          rubric: { type: 'essay', scoring_strategy: sq.scoreFormulaType },
          rubric_script: state.generatedScript || state.rubricScript,
          parent_id: state.currentParentId,
        });
        if (sq.answerId) {
          await axios.put(API_BASE + '/api/questions/' + sq.questionId + '/answers/' + sq.answerId, {
            answer_text: JSON.stringify(payload),
          });
        } else {
          var ansRes = await axios.post(API_BASE + '/api/questions/' + sq.questionId + '/answers', {
            scope_type: 'scoring_point',
            answer_text: JSON.stringify(payload),
            label: sq.text.substring(0, 50),
          });
          sq.answerId = ansRes.data.data.id;
        }
      } else {
        var childRes = await axios.post(API_BASE + '/api/questions', {
          subject: 'english',
          title: sq.text.substring(0, 50),
          content: sq.text,
          standard_answer: sq.standardAnswer,
          max_score: sq.maxScore,
          rubric: { type: 'essay', scoring_strategy: sq.scoreFormulaType },
          scoring_strategy: 'max',
          parent_id: state.currentParentId,
          question_type: 'essay',
          rubric_script: state.generatedScript || state.rubricScript,
        });
        sq.questionId = childRes.data.data.id;
        await axios.post(API_BASE + '/api/questions/' + sq.questionId + '/answers', {
          scope_type: 'scoring_point',
          answer_text: JSON.stringify(payload),
          label: sq.text.substring(0, 50),
        });
      }
    }
  }

  // ============================================================
  // 轻量级 workflow_status 保存
  // state = { currentParentId, currentStep, activeQuestionIndex, completedSteps, subQuestions }
  // ============================================================
  async function saveWorkflowStatus(state) {
    if (!state.currentParentId) return;
    try {
      await axios.put(API_BASE + '/api/questions/' + state.currentParentId + '/workflow-status', {
        workflow_status: H.buildWorkflowStatusJson(state),
      });
    } catch (e) {
      console.warn('workflow_status 保存失败', e);
      if (typeof ElMessage !== 'undefined') ElMessage.warning('编辑进度保存失败');
    }
  }

  // ============================================================
  // 暴露
  // ============================================================
  window.EnglishEditValidateSave = {
    validateAll: validateAll,
    saveAll: saveAll,
    saveWorkflowStatus: saveWorkflowStatus,
  };
})();
