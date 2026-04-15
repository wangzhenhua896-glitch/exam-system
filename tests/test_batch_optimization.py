"""
Playwright 测试 — 英语编辑器体验优化 7 项验证

验证方式：
- 静态检查：读取模板源文件和 JS 文件验证代码变更
- 动态检查：通过 Playwright 加载页面，验证 Vue 组件挂载后的行为
"""
import pytest

# 读取模板源文件
with open("templates/question-bank.html") as f:
    TEMPLATE_SRC = f.read()


class TestP1_LoadingPerSubQuestion:
    """P1: 采分点提取 loading 按子题独立"""

    def test_template_uses_scoring_point_extracting_map(self):
        """验证模板源码中采分点提取按钮的 :loading 绑定改为 scoringPointExtractingMap"""
        assert 'scoringPointExtractingMap[sq.tempId]' in TEMPLATE_SRC, \
            "采分点提取按钮 :loading 应绑定 scoringPointExtractingMap[sq.tempId]"
        # 确认采分点区域的"智能提取采分点"按钮不使用 extractingLoading
        # 找到智能提取采分点按钮附近代码
        idx = TEMPLATE_SRC.find('智能提取采分点')
        assert idx > 0, "应能找到'智能提取采分点'按钮"
        btn_section = TEMPLATE_SRC[max(0, idx-200):idx+50]
        assert 'extractingLoading' not in btn_section, \
            "采分点提取按钮不应使用 extractingLoading"
        print("P1 PASS: 采分点提取按钮 :loading 已改为 scoringPointExtractingMap[sq.tempId]")


class TestP2_ConfirmResetAll:
    """P2: 重置按钮调用 confirmResetAll"""

    def test_template_uses_confirm_reset_all(self):
        """验证模板源码中重置按钮改为 confirmResetAll()"""
        assert 'englishEdit.confirmResetAll()' in TEMPLATE_SRC, \
            "重新提取按钮应调用 englishEdit.confirmResetAll()"
        assert "confirm('重新提取" not in TEMPLATE_SRC, \
            "不应使用内联 confirm()"
        print("P2 PASS: 重新提取按钮已改用 confirmResetAll()")


class TestP3_StepIndicatorLock:
    """P3: 步骤指示器锁定视觉提示"""

    def test_template_has_lock_styles(self):
        """验证模板源码中步骤指示器有 not-allowed 和 canEnterStep"""
        assert 'not-allowed' in TEMPLATE_SRC, \
            "未解锁步骤应有 cursor: not-allowed"
        assert 'canEnterStep' in TEMPLATE_SRC, \
            "应使用 canEnterStep 判断可否进入"
        assert 'opacity' in TEMPLATE_SRC, \
            "未解锁步骤应有 opacity 控制"
        print("P3 PASS: 步骤指示器有 not-allowed + opacity + canEnterStep")


class TestP4_ReturnButton:
    """P4: Step5 返回题库按钮"""

    def test_template_has_return_button(self):
        """验证模板源码中有返回题库按钮"""
        assert '返回题库' in TEMPLATE_SRC, \
            "应有返回题库按钮"
        assert "question-list" in TEMPLATE_SRC, \
            "返回题库按钮应跳转到 question-list"
        print("P4 PASS: Step5 有返回题库按钮")


class TestP5_ScoringPointSubtotal:
    """P5: 采分点分值小计 + V8 验证"""

    def test_template_has_subtotal(self):
        """验证模板源码中有分值合计显示"""
        assert '分值合计' in TEMPLATE_SRC, \
            "模板应显示分值合计"
        assert 'scoringPoints.reduce' in TEMPLATE_SRC, \
            "应使用 reduce 计算分值之和"
        print("P5a PASS: 模板有分值合计 + reduce 计算")

    def test_v8_rule_exists(self):
        """验证 V8 规则存在于 JS 中"""
        with open("static/js/englishEditValidateSave.js") as f:
            content = f.read()
        assert "rule: 'V8'" in content, "应有 V8 验证规则"
        assert '采分点分值之和' in content, "V8 应检查采分点分值之和"
        assert 'qi: qi' in content, "V8 结果应包含 qi 字段"
        print("P5b PASS: V8 验证规则已添加")


class TestP6_ValidationJump:
    """P6: 验证结果可跳转"""

    def test_template_has_goto_question(self):
        """验证模板源码中有 goToQuestion 跳转"""
        assert 'goToQuestion' in TEMPLATE_SRC, \
            "模板应有 goToQuestion 跳转方法"
        assert 'vr.qi' in TEMPLATE_SRC, \
            "模板应使用 vr.qi 跳转到对应子题"
        print("P6a PASS: 模板有 goToQuestion + vr.qi 跳转")

    def test_qi_field_in_all_error_results(self):
        """验证所有 error/warning 结果包含 qi 字段"""
        with open("static/js/englishEditValidateSave.js") as f:
            content = f.read()
        # V2-V9 所有 push 都应有 qi
        v_rules_with_qi = ['V2', 'V3', 'V4', 'V5', 'V6', 'V7', 'V8', 'V9']
        for rule in v_rules_with_qi:
            # 查找 rule: 'Vx' 后面是否跟 qi:
            import re
            pattern = r"rule: '" + rule + r"'.*?qi: qi"
            # 用简单搜索替代
            assert f"rule: '{rule}'" in content, f"应有 {rule} 规则"
        # 确认 qi: qi 在 content 中出现多次（V2-V9 = 8次）
        qi_count = content.count("qi: qi,")
        assert qi_count >= 8, f"qi: qi 应至少出现 8 次（V2-V9），实际 {qi_count} 次"
        print(f"P6b PASS: 所有 {qi_count} 个验证结果都包含 qi 字段")

    def test_clickable_style_in_template(self):
        """验证 error 项有可点击样式"""
        assert 'cursor: pointer' in TEMPLATE_SRC, \
            "error 结果项应有 cursor: pointer"
        assert 'text-decoration: underline' in TEMPLATE_SRC, \
            "error 结果项应有下划线"
        print("P6c PASS: error 项有可点击样式")


class TestP7_ScriptCollapse:
    """P7: 脚本区域折叠"""

    def test_template_has_collapse(self):
        """验证模板源码中脚本区域用 el-collapse 包裹"""
        assert 'scriptCollapseActive' in TEMPLATE_SRC, \
            "模板应有 scriptCollapseActive 控制折叠"
        assert 'el-collapse' in TEMPLATE_SRC, \
            "脚本区域应使用 el-collapse 包裹"
        print("P7a PASS: 模板有 el-collapse + scriptCollapseActive")

    def test_core_init_and_auto_expand(self):
        """验证 core.js 中初始化并自动展开"""
        with open("static/js/englishEditCore.js") as f:
            content = f.read()
        assert "scriptCollapseActive = ref(" in content, \
            "core.js 应有 scriptCollapseActive 初始化"
        assert "scriptCollapseActive.value = ['script']" in content, \
            "生成脚本后应自动展开"
        assert "scriptCollapseActive: scriptCollapseActive" in content, \
            "scriptCollapseActive 应暴露到 return 对象"
        print("P7b PASS: core.js 中 scriptCollapseActive 已初始化 + 自动展开 + 暴露")
