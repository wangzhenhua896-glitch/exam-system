"""
Playwright 测试: 英语编辑器第3步评分细则卡片视图

用已有题目 ID=171 测试。通过 window._englishEdit 访问编辑器状态。
"""
from playwright.sync_api import sync_playwright
import time

BASE = 'http://localhost:5001'

def test_step3_cards():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        console_errors = []
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)

        # 登录
        page.goto(f'{BASE}/login')
        page.wait_for_load_state('networkidle')
        page.evaluate("""async () => {
            await fetch('/api/login', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ username: 'english' })
            });
        }""")

        # 前往题库页
        page.evaluate("""() => {
            localStorage.setItem('ai_grading_current_subject', 'english');
            localStorage.setItem('ai_grading_role', 'teacher');
            localStorage.setItem('ai_grading_teacher_name', 'english');
        }""")
        page.goto(f'{BASE}/management')
        page.wait_for_load_state('networkidle')
        time.sleep(2)

        # 搜索并点击编辑
        search = page.locator('input[placeholder*="搜索"]')
        if search.count() > 0:
            search.first.fill('Tea is more')
            time.sleep(1)

        edit_btn = page.locator('tr:has-text("Tea is more") button:has-text("编辑")')
        edit_btn.first.click()
        print("[TEST] 点击编辑按钮，等待子题加载...")

        # 等待子题加载
        time.sleep(8)

        # 通过 window._englishEdit 检查状态
        state = page.evaluate("""() => {
            const ee = window._englishEdit;
            if (!ee) return { error: 'window._englishEdit not found' };

            const sqs = ee.subQuestions || [];
            return {
                currentStep: ee.currentStep,
                subQuestionCount: sqs.length,
                rubricViewMode: ee.rubricViewMode,
                isStateA: ee.isStateA,
                parentId: ee.currentParentId,
                sq0_text: sqs[0]?.text?.substring(0, 50) || '',
                sq0_scoringPoints: sqs[0]?.scoringPoints?.length || 0,
                sq0_excludeList: sqs[0]?.excludeList?.length || 0,
                sq0_maxScore: sqs[0]?.maxScore || 0,
            };
        }""")
        print(f"[TEST] 编辑器状态: {state}")

        current_step = state.get('currentStep')
        sq_count = state.get('subQuestionCount', 0)
        print(f"[TEST] 当前步骤: {current_step}, 子题数: {sq_count}")

        # 如果不在 script 步骤，切换过去
        if current_step != 'script' and sq_count > 0:
            page.evaluate("() => { window._englishEdit.currentStep = 'script'; }")
            time.sleep(2)
            print("[TEST] 已切换到 script 步骤")

        # 检查切换后的步骤
        step = page.evaluate("() => window._englishEdit?.currentStep")
        print(f"[TEST] 切换后步骤: {step}")

        time.sleep(1)

        # ── 检查第3步卡片 DOM ──
        print("\n=== 第3步卡片验证 ===")

        # "评分细则"标题
        title = page.locator('span:has-text("评分细则")')
        print(f"1. '评分细则' 标题: {title.count()}")

        # "共 N 小问，满分 X 分" 标签
        info = page.locator('.el-tag:has-text("小问")')
        print(f"2. '小问' 标签: {info.count()}")
        if info.count() > 0:
            print(f"   内容: {info.first.text_content().strip()}")

        # 子题折叠 "第1题"
        first_q = page.locator('text=第1题')
        print(f"3. '第1题': {first_q.count()}")

        # 子题题目
        sq_text = page.locator('text=What is Longjing tea')
        print(f"4. 子题题目文字: {sq_text.count()}")

        # "采分点" 文本
        sp = page.locator('text=/采分点 [A-Z0-9]/')
        print(f"5. '采分点 X': {sp.count()}")

        # 关键词 tag (info)
        kw = page.locator('.el-tag--info:has-text("green tea")')
        print(f"6. 关键词 'green tea': {kw.count()}")

        # 等价表述 tag (success)
        syn = page.locator('.el-tag--success:has-text("green tea leaves")')
        print(f"7. 等价表述: {syn.count()}")

        # 排除词 tag (danger)
        excl = page.locator('.el-tag--danger')
        print(f"8. 排除词 danger tags: {excl.count()}")

        # 计分方式
        max_hit = page.locator('.el-tag--warning:has-text("取最高命中分")')
        hit_count = page.locator('.el-tag--success:has-text("按命中计数")')
        print(f"9. 计分方式: 取最高={max_hit.count()}, 按命中={hit_count.count()}")

        # "生成评分脚本" 按钮
        gen_btn = page.locator('button:has-text("生成评分脚本")')
        print(f"10. '生成评分脚本' 按钮: {gen_btn.count()}")

        # 原始脚本折叠面板
        raw_script = page.locator('text=原始脚本')
        print(f"11. '原始脚本' 标题: {raw_script.count()}")

        # textarea 可见性（原始脚本默认收起，不应可见）
        ta = page.locator('textarea')
        ta_vis = ta.count() > 0 and ta.first.is_visible()
        print(f"12. textarea 可见: {ta_vis}")

        # 关键错误
        critical = [e for e in console_errors if 'Cannot read' in e or 'TypeError' in e]
        print(f"\n关键错误: {critical if critical else '无'}")
        print("=== 完成 ===")
        browser.close()

if __name__ == '__main__':
    test_step3_cards()
