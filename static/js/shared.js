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
   * 统一 API 错误处理
   * @param {Error} e - catch 捕获的异常
   * @param {string} prefix - 操作描述，如 '加载题目列表'
   * @param {object} [opts] - 可选配置
   * @param {boolean} [opts.showElMessage=true] - 是否弹出 ElMessage 提示
   * @returns {string} 错误消息文本
   */
  function handleApiError(e, prefix, opts) {
    opts = opts || {};
    var showMsg = opts.showElMessage !== false;
    // ElMessageBox.confirm 取消时抛出 'cancel'，不提示
    if (e === 'cancel' || e?.message === 'cancel') return '';
    // 401 未登录 → 跳转登录页
    if (e.response && e.response.status === 401) {
      window.location.href = '/login?t=' + Date.now();
      return '未登录';
    }
    var msg = prefix + '：' + (e.response?.data?.error || e.response?.data?.message || e.message || '未知错误');
    if (showMsg && typeof ElMessage !== 'undefined') {
      ElMessage.error(msg);
    }
    console.error(prefix, e);
    return msg;
  }

  /**
   * 安全 JSON.parse，解析失败返回 fallback 而非抛异常
   * @param {string} raw - 待解析的字符串
   * @param {*} fallback - 解析失败时的默认值
   */
  function safeJsonParse(raw, fallback) {
    try { return JSON.parse(raw); } catch (_) { return fallback; }
  }

  /**
   * 从 localStorage 安全加载科目列表
   */
  function loadSubjectsFromStorage() {
    return safeJsonParse(localStorage.getItem(SUBJECT_STORAGE_KEY), DEFAULT_SUBJECTS) || DEFAULT_SUBJECTS;
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
    handleApiError: handleApiError,
    sanitizeHtml: sanitizeHtml,
    safeJsonParse: safeJsonParse,
    loadSubjectsFromStorage: loadSubjectsFromStorage,
  };
})();
