/**
 * 公共常量和工具函数
 *
 * 非 ES Module 模式，暴露到 window.SharedApp。
 * 所有模板页面通过 <script src="/static/js/shared.js"> 引入。
 */
(function () {
  'use strict';

  // localStorage key 常量
  var SUBJECT_STORAGE_KEY = 'ai_grading_subjects';
  var CURRENT_SUBJECT_KEY = 'ai_grading_current_subject';
  var ROLE_KEY = 'ai_grading_role';
  var TEACHER_NAME_KEY = 'ai_grading_teacher_name';

  // 默认科目
  var DEFAULT_SUBJECTS = [
    { label: '思想政治', value: 'politics' },
    { label: '语文', value: 'chinese' },
    { label: '英语', value: 'english' },
  ];

  // 科目标签映射（最全版本，各页面优先使用此映射）
  var SUBJECT_LABELS = {
    politics: '思想政治',
    chinese: '语文',
    english: '英语',
    math: '数学',
    history: '历史',
    geography: '地理',
    physics: '物理',
    chemistry: '化学',
    biology: '生物',
    general: '通用',
  };

  /**
   * 获取科目标签
   * @param {string} value - 科目值（如 'politics'）
   * @param {Array} [dynamicList] - 可选的动态科目列表，优先从这里查找
   */
  function getSubjectLabel(value, dynamicList) {
    if (dynamicList) {
      var found = dynamicList.find(function (s) { return s.value === value; });
      if (found) return found.label;
    }
    return SUBJECT_LABELS[value] || value || '';
  }

  /**
   * HTML 消毒（需要 DOMPurify 已加载）
   */
  function sanitizeHtml(html) {
    if (typeof DOMPurify !== 'undefined') {
      return DOMPurify.sanitize(html);
    }
    return html;
  }

  // 暴露到全局
  window.SharedApp = {
    SUBJECT_STORAGE_KEY: SUBJECT_STORAGE_KEY,
    CURRENT_SUBJECT_KEY: CURRENT_SUBJECT_KEY,
    ROLE_KEY: ROLE_KEY,
    TEACHER_NAME_KEY: TEACHER_NAME_KEY,
    DEFAULT_SUBJECTS: DEFAULT_SUBJECTS,
    SUBJECT_LABELS: SUBJECT_LABELS,
    getSubjectLabel: getSubjectLabel,
    sanitizeHtml: sanitizeHtml,
  };
})();
