/**
 * ESLint 配置 — AI 智能评分系统
 *
 * 目标：
 * 1. 语法检查（catch 变量未使用、常见错误）
 * 2. catch 块规范：禁止手动解析 e.response?.data?.error，统一用 handleApiError
 * 3. 适配 CDN + 原生 JS 项目（非 npm 构建）
 */

import globals from "globals";

// 项目全局变量（script 类型，非 ES Module）
const scriptGlobals = {
  ...globals.browser,
  axios: "readonly",
  ElMessage: "readonly",
  ElMessageBox: "readonly",
  ElementPlus: "readonly",
  ElementPlusIconsVue: "readonly",
  Vue: "readonly",
  window: "readonly",
  localStorage: "readonly",
  console: "readonly",
  setTimeout: "readonly",
  setInterval: "readonly",
  clearInterval: "readonly",
  clearTimeout: "readonly",
  Promise: "readonly",
  JSON: "readonly",
  FormData: "readonly",
  document: "readonly",
  Math: "readonly",
  DOMPurify: "readonly",
  Quill: "readonly",
  fetch: "readonly",
  URL: "readonly",
  Blob: "readonly",
  FileReader: "readonly",
  SharedApp: "readonly",
};

// ES Module 文件的全局变量
const moduleGlobals = {
  ...globals.browser,
  axios: "readonly",
  ElMessage: "readonly",
  ElMessageBox: "readonly",
  Vue: "readonly",
  ElementPlus: "readonly",
  window: "readonly",
  console: "readonly",
  JSON: "readonly",
  FormData: "readonly",
  setTimeout: "readonly",
  clearTimeout: "readonly",
  fetch: "readonly",
};

// 公共基础规则
const baseRules = {
  "no-unused-vars": ["warn", { argsIgnorePattern: "^_", caughtErrorsIgnorePattern: "^_" }],
  "no-undef": "error",
  "no-redeclare": "error",
  "no-dupe-keys": "error",
  "no-duplicate-case": "error",
  "no-unreachable": "error",
  "no-constant-condition": "warn",
  "use-isnan": "error",
  "valid-typeof": "error",
};

export default [
  // ========== script 类型（shared.js, englishEditCore.js 等）==========
  {
    files: ["static/js/shared.js", "static/js/englishEditCore.js"],
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: "script",
      globals: scriptGlobals,
    },
    rules: { ...baseRules },
  },

  // ========== ES Module 类型（api.js, useXxx.js）==========
  {
    files: ["static/js/api.js", "static/js/use*.js"],
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: "module",
      globals: moduleGlobals,
    },
    rules: { ...baseRules },
  },

  // ========== 自定义规则：禁止手动解析 API 错误 ==========
  // 排除 shared.js（handleApiError 实现文件本身）
  {
    files: ["static/js/**/*.js"],
    ignores: ["static/js/shared.js"],
    plugins: {
      local: {
        rules: {
          "no-manual-error-parse": {
            meta: {
              type: "suggestion",
              docs: { description: "禁止手动解析 e.response?.data?.error，统一用 handleApiError" },
              schema: [],
            },
            create(context) {
              const pattern = /e\.response(\?\.data\?\.error|\.data\.error|\?\.data\?\.message|\.data\.message)/;
              return {
                MemberExpression(node) {
                  const source = context.getSourceCode().getText(node);
                  if (pattern.test(source)) {
                    context.report({
                      node,
                      message: "禁止手动解析 API 错误 (e.response?.data?.error)，请使用 handleApiError(e, '前缀') 替代。",
                    });
                  }
                },
              };
            },
          },

          "no-catch-raw-elmessage": {
            meta: {
              type: "suggestion",
              docs: { description: "catch 块中禁止直接 ElMessage.error 拼接错误信息，应使用 handleApiError" },
              schema: [],
            },
            create(context) {
              return {
                CatchClause(node) {
                  const body = node.body.body;
                  for (const stmt of body) {
                    checkStatement(stmt, context);
                  }
                },
              };

              function checkStatement(stmt, context) {
                if (
                  stmt.type === "ExpressionStatement" &&
                  stmt.expression.type === "CallExpression" &&
                  stmt.expression.callee.type === "MemberExpression" &&
                  stmt.expression.callee.object?.name === "ElMessage" &&
                  stmt.expression.callee.property?.name === "error"
                ) {
                  const args = stmt.expression.arguments;
                  if (args.length > 0) {
                    const argSource = context.getSourceCode().getText(args[0]);
                    if (/e\.message|e\.response/.test(argSource)) {
                      context.report({
                        node: stmt,
                        message: "catch 块中禁止 ElMessage.error 拼接错误信息，请使用 handleApiError(e, '前缀') 替代。",
                      });
                    }
                  }
                }
                // 嵌套 if
                if (stmt.type === "IfStatement" && stmt.consequent?.body) {
                  for (const inner of stmt.consequent.body) {
                    checkStatement(inner, context);
                  }
                }
              }
            },
          },
        },
      },
    },
    rules: {
      "local/no-manual-error-parse": "error",
      "local/no-catch-raw-elmessage": "warn",
    },
  },
];
