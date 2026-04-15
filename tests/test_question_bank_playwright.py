"""Playwright test: question-bank page (/management) after recent changes."""
from playwright.sync_api import sync_playwright
import time

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()

    # Capture console errors
    errors = []
    page.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else None)

    # Step 1: Navigate to /management — will redirect to /login (localStorage empty)
    page.goto('http://localhost:5001/management')
    page.wait_for_load_state('networkidle')

    # Step 2: Set localStorage so the page won't redirect next time
    page.evaluate("""() => {
        localStorage.setItem('ai_grading_current_subject', 'politics');
        localStorage.setItem('ai_grading_role', 'teacher');
        localStorage.setItem('ai_grading_teacher_name', '测试老师');
    }""")

    # Step 3: Navigate to /management again — this time it should stay
    page.goto('http://localhost:5001/management')
    page.wait_for_load_state('networkidle')
    time.sleep(3)  # Wait for Vue to mount and API calls to complete

    current_url = page.url
    print(f"Current URL: {current_url}")

    # ── TEST 1: Page loaded without errors ──
    title = page.title()
    print(f"[TEST 1] Page title: {title}")
    page_loaded = '/login' not in current_url
    print(f"[TEST 1] Page loaded (no redirect to login): {page_loaded}")

    # ── TEST 2: NO subject selector/label in header ──
    header_right = page.locator('.header-right')
    header_text = header_right.text_content()
    has_subject_tag = '切换科目' in header_text or '选择科目' in header_text or '思想政治' in header_text
    print(f"[TEST 2] Header text: '{header_text.strip()}'")
    print(f"[TEST 2] Header has subject selector: {has_subject_tag} (should be False)")

    # ── TEST 3: el-switch with "显示分值/质量/删除" ──
    switch = page.locator('.el-switch')
    switch_count = switch.count()
    print(f"[TEST 3] Switch count: {switch_count} (should be >= 1)")
    if switch_count > 0:
        # el-switch's text is in sibling/descendant spans
        switch_area = page.locator('.el-switch').first
        # Look for the active-text span near the switch
        switch_label = switch_area.evaluate("el => el.closest('div')?.textContent || el.parentElement?.textContent || ''")
        has_label = '显示分值/质量/删除' in switch_label
        print(f"[TEST 3] Switch label contains expected text: {has_label} (should be True)")
        print(f"[TEST 3] Switch context text: '{switch_label.strip()}'")

    # ── TEST 4: Default — no 分值 or 质量 columns ──
    headers = page.locator('.el-table__header th .cell').all_text_contents()
    headers_stripped = [h.strip() for h in headers if h.strip()]
    print(f"[TEST 4] Table headers (default): {headers_stripped}")
    has_score_col = any('分值' in h for h in headers_stripped)
    has_quality_col = any('质量' in h for h in headers_stripped)
    print(f"[TEST 4] Has '分值' column: {has_score_col} (should be False)")
    print(f"[TEST 4] Has '质量' column: {has_quality_col} (should be False)")

    # ── TEST 5: Default — delete button NOT visible ──
    delete_btns = page.locator('.el-table__body button:has-text("删除")')
    delete_count = delete_btns.count()
    print(f"[TEST 5] Delete buttons in table body: {delete_count} (should be 0)")

    # ── TEST 6: Toggle switch ON → columns and delete button appear ──
    if switch_count > 0:
        switch.first.click()
        time.sleep(0.5)

        headers2 = page.locator('.el-table__header th .cell').all_text_contents()
        headers2_stripped = [h.strip() for h in headers2 if h.strip()]
        print(f"[TEST 6] Table headers (after toggle): {headers2_stripped}")
        has_score_col2 = any('分值' in h for h in headers2_stripped)
        has_quality_col2 = any('质量' in h for h in headers2_stripped)
        print(f"[TEST 6] Has '分值' column: {has_score_col2} (should be True)")
        print(f"[TEST 6] Has '质量' column: {has_quality_col2} (should be True)")

        delete_btns2 = page.locator('.el-table__body button:has-text("删除")')
        delete_count2 = delete_btns2.count()
        print(f"[TEST 6] Delete buttons in table body: {delete_count2} (should be > 0)")

    # ── TEST 7: API call includes subject parameter ──
    # Reload and intercept network requests
    api_urls = []
    page.on("request", lambda req: api_urls.append(req.url) if '/api/questions' in req.url else None)
    page.goto('http://localhost:5001/management')
    page.wait_for_load_state('networkidle')
    time.sleep(2)

    has_subject_param = any('subject=politics' in url for url in api_urls)
    print(f"[TEST 7] API calls with subject=politics: {has_subject_param} (should be True)")
    for url in api_urls:
        print(f"[TEST 7]   Captured: {url}")

    # ── TEST 8: Console errors ──
    print(f"\n[TEST 8] Console errors: {errors}")

    browser.close()
    print("\n=== ALL TESTS COMPLETE ===")
