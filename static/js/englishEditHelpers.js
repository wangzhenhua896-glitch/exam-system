/**
 * 英语编辑器 — 纯工具函数
 *
 * 无状态依赖，可被 englishEditCore.js / englishEditAI.js / englishEditValidateSave.js 共用。
 * 暴露到 window.EnglishEditHelpers。
 */
(function () {
  'use strict';

  // ============================================================
  // Tag Chip 操作
  // ============================================================
  function addTag(list, value) {
    if (!value || !value.trim()) return false;
    var v = value.trim().toLowerCase();
    for (var i = 0; i < list.length; i++) {
      if (list[i].toLowerCase() === v) return false;
    }
    list.push(value.trim());
    return true;
  }

  function removeTag(list, index) {
    list.splice(index, 1);
  }

  function addTagsFromPaste(list, pastedText) {
    var parts = pastedText.split(/[,，;；\n]+/);
    var added = 0;
    parts.forEach(function (p) {
      if (addTag(list, p)) added++;
    });
    return added;
  }

  // ============================================================
  // 空白模板工厂
  // ============================================================
  function createEmptySubQuestion() {
    return {
      id: 0,
      tempId: Date.now(),
      text: '',
      standardAnswer: '',
      maxScore: 2,
      scoreFormulaType: 'max_hit_score',
      scoringPoints: [],
      scoringRules: [{ minHits: 2, score: 2 }, { minHits: 1, score: 1 }],
      excludeList: [],
      pinyinWhitelist: [],
      status: 'pending',
      expanded: true,
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
  // 阅读材料提取
  // ============================================================
  function extractReadingMaterial(content) {
    var text = content.replace(/<[^>]+>/g, '\n').replace(/\n{3,}/g, '\n\n').trim();
    var markers = ['简答题问题', 'Short Answer Questions', 'Answer the following'];
    for (var i = 0; i < markers.length; i++) {
      var idx = text.indexOf(markers[i]);
      if (idx > 0) {
        return text.substring(0, idx).trim();
      }
    }
    var lines = text.split('\n');
    var material = [];
    for (var j = 0; j < lines.length; j++) {
      if (/^\s*\d+[\.\)）]/.test(lines[j])) break;
      material.push(lines[j]);
    }
    return material.join('\n').trim() || text;
  }

  // ============================================================
  // JSON ↔ 表单映射
  // ============================================================
  function loadScoringPointFromJson(sq, spJson) {
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

  function buildApiPayload(sq, subQuestions) {
    var idx = subQuestions.indexOf(sq);
    var payload = {
      id: 'Q' + (idx + 1),
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

  function buildWorkflowStatusJson(state) {
    var qs = {};
    state.subQuestions.forEach(function (sq) {
      if (sq.questionId) {
        qs[String(sq.questionId)] = sq.status;
      }
    });
    return JSON.stringify({
      current_step: state.currentStep,
      active_question_index: state.activeQuestionIndex,
      completed_steps: state.completedSteps.slice(),
      question_status: qs,
      updated_at: new Date().toISOString(),
    });
  }

  // ============================================================
  // 暴露
  // ============================================================
  window.EnglishEditHelpers = {
    addTag: addTag,
    removeTag: removeTag,
    addTagsFromPaste: addTagsFromPaste,
    createEmptySubQuestion: createEmptySubQuestion,
    createEmptyScoringPoint: createEmptyScoringPoint,
    extractReadingMaterial: extractReadingMaterial,
    loadScoringPointFromJson: loadScoringPointFromJson,
    isQuestionComplete: isQuestionComplete,
    buildApiPayload: buildApiPayload,
    buildWorkflowStatusJson: buildWorkflowStatusJson,
  };
})();
