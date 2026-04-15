/**
 * 英语编辑器 — AI API 调用
 *
 * 所有函数为纯异步逻辑，不直接操作 Vue ref。
 * 由 englishEditCore.js 的 wrapper 函数负责读写 ref 和 loading 状态。
 * 暴露到 window.EnglishEditAI。
 */
(function () {
  'use strict';

  var API_BASE = '';
  var handleApiError = window.SharedApp.handleApiError;
  var ElMessage = ElementPlus.ElMessage;
  var H = window.EnglishEditHelpers;

  // ============================================================
  // Step1: AI 智能解析
  // ============================================================
  async function extractFromPaste(pasteText) {
    var res = await axios.post(API_BASE + '/api/english/extract', {
      full_text: pasteText,
    });
    if (res.data.success && res.data.data) {
      var data = res.data.data;
      var readingMaterial = data.reading_material || '';
      var subQuestions = (data.sub_questions || []).map(function (sq, idx) {
        var form = H.createEmptySubQuestion();
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
      return { readingMaterial: readingMaterial, subQuestions: subQuestions };
    } else {
      throw new Error(res.data.error || '返回数据异常');
    }
  }

  // ============================================================
  // 采分点提取
  // ============================================================
  async function extractScoringPoints(sq) {
    var res = await axios.post(API_BASE + '/api/english/extract-scoring-points', {
      question_text: sq.text,
      standard_answer: sq.standardAnswer,
      max_score: sq.maxScore,
    });
    if (res.data.success && res.data.data) {
      var data = res.data.data;
      return {
        scoringPoints: (data.scoring_points || []).map(function (sp) {
          return {
            id: sp.id || 'A',
            score: sp.score || 1,
            keywords: (sp.keywords || []).slice(),
            synonyms: (sp.synonyms || []).slice(),
          };
        }),
        scoreFormulaType: (typeof data.score_formula === 'string' && data.score_formula === 'max_hit_score')
          ? 'max_hit_score' : 'hit_count',
        excludeList: data.exclude_list ? data.exclude_list.slice() : null,
      };
    }
    return null;
  }

  // ============================================================
  // 同义词补全
  // ============================================================
  async function suggestSynonyms(parentContent, sq, spIndex) {
    var sp = sq.scoringPoints[spIndex];
    if (!sp || sp.keywords.length === 0) return null;
    var allExisting = sp.keywords.concat(sp.synonyms);
    var res = await axios.post(API_BASE + '/api/english/suggest-synonyms', {
      keyword: sp.keywords[0],
      context: parentContent,
      question_text: sq.text,
      existing_synonyms: allExisting,
    });
    if (res.data.success) {
      var suggestions = res.data.data || [];
      return suggestions.map(function (s) {
        var termLower = (s.term || '').toLowerCase();
        var exists = allExisting.some(function (e) { return e.toLowerCase() === termLower; });
        return { term: s.term, confidence: s.confidence, disabled: exists };
      });
    }
    return null;
  }

  // ============================================================
  // 排除词建议
  // ============================================================
  async function suggestExclude(parentContent, sq) {
    var allKeywords = [];
    var allSynonyms = [];
    sq.scoringPoints.forEach(function (sp) {
      allKeywords = allKeywords.concat(sp.keywords);
      allSynonyms = allSynonyms.concat(sp.synonyms);
    });
    var res = await axios.post(API_BASE + '/api/english/suggest-exclude', {
      question_text: sq.text,
      keywords: allKeywords,
      synonyms: allSynonyms,
      context: parentContent,
    });
    if (res.data.success) {
      var suggestions = res.data.data || [];
      return suggestions.map(function (s) {
        var termLower = (s.term || '').toLowerCase();
        var exists = sq.excludeList.some(function (e) { return e.toLowerCase() === termLower; });
        return { term: s.term, reason: s.reason, disabled: exists };
      });
    }
    return null;
  }

  // ============================================================
  // 评分脚本
  // ============================================================
  async function generateScript(subQuestions, parentMaxScore) {
    var configs = subQuestions.map(function (sq) {
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
      question_text: subQuestions.map(function (sq) { return sq.text; }).join('\n'),
      standard_answer: subQuestions.map(function (sq) { return sq.standardAnswer; }).join('\n'),
      max_score: parentMaxScore,
      scoring_config: configs,
    });
    if (res.data.success) {
      return res.data.data.script;
    }
    throw new Error(res.data.error || '脚本生成失败');
  }

  async function selfCheckScript(generatedScript, subQuestions, parentMaxScore) {
    var allContent = subQuestions.map(function (sq) { return sq.text; }).join('\n');
    var allAnswer = subQuestions.map(function (sq) { return sq.standardAnswer; }).join('\n');
    var res = await axios.post(API_BASE + '/api/self-check-rubric', {
      content: allContent,
      score: parentMaxScore,
      standardAnswer: allAnswer,
      rubricScript: generatedScript,
      subject: 'english',
    });
    if (res.data.success) {
      return res.data.data;
    }
    throw new Error(res.data.error || '自查失败');
  }

  async function evaluateQuality(subQuestions, parentMaxScore) {
    var res = await axios.post(API_BASE + '/api/evaluate-question', {
      content: subQuestions.map(function (sq) { return sq.text; }).join('\n'),
      standardAnswer: subQuestions.map(function (sq) { return sq.standardAnswer; }).join('\n'),
      maxScore: parentMaxScore,
      subject: 'english',
    });
    if (res.data.success) {
      return res.data.data;
    }
    throw new Error(res.data.error || '质量评估失败');
  }

  // ============================================================
  // 暴露
  // ============================================================
  window.EnglishEditAI = {
    extractFromPaste: extractFromPaste,
    extractScoringPoints: extractScoringPoints,
    suggestSynonyms: suggestSynonyms,
    suggestExclude: suggestExclude,
    generateScript: generateScript,
    selfCheckScript: selfCheckScript,
    evaluateQuality: evaluateQuality,
  };
})();
