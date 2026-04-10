"""
评分一致性报告生成器

用法: python consistency_test/report.py [结果文件路径]

如果不指定路径，自动读取 results/ 目录下最新的测试结果。
"""

import json
import sys
import os
import glob
from statistics import mean, stdev


def load_result(path: str = None) -> dict:
    """加载测试结果"""
    if not path:
        files = sorted(glob.glob("results/test_*.json"), reverse=True)
        if not files:
            print("错误: results/ 目录下没有测试结果文件。请先运行 runner.py")
            sys.exit(1)
        path = files[0]
        print(f"自动选择最新结果: {path}")

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def get_model_display_name(model_id: str, meta: dict) -> str:
    """获取模型显示名（用 ID 的最后一段）"""
    return model_id.split("/")[-1] if "/" in model_id else model_id


def analyze(result: dict) -> str:
    """分析结果并生成报告"""
    meta = result["meta"]
    results = result["results"]
    model_ids = meta["models"]
    max_score = meta["max_score"]
    runs = meta["runs_per_version"]

    lines = []
    lines.append("=" * 70)
    lines.append("  评分一致性测试报告")
    lines.append("=" * 70)
    lines.append(f"  测试时间: {meta['timestamp']}")
    lines.append(f"  题目ID: {meta['question_id']}")
    lines.append(f"  满分: {max_score}")
    lines.append(f"  模型数: {len(model_ids)}")
    lines.append(f"  每版本运行次数: {runs}")
    lines.append("")

    # ==================== 1. 基线对比 ====================
    lines.append("-" * 70)
    lines.append("  1. 基线对比（完整答案 V0）")
    lines.append("-" * 70)

    baseline_key = [k for k in results.keys() if k.startswith("V0")]
    if baseline_key:
        baseline = results[baseline_key[0]]
        expected = baseline["expected_score"]
        lines.append(f"  预期得分: {expected} 分")
        lines.append("")

        for mid in model_ids:
            scores_data = baseline["model_scores"].get(mid, [])
            scores = [s["score"] for s in scores_data if s["score"] is not None]
            display = get_model_display_name(mid, meta)

            if not scores:
                lines.append(f"  {display}: 全部评分失败 ⚠️")
                continue

            avg = round(mean(scores), 2)
            spread = max(scores) - min(scores) if len(scores) > 1 else 0
            stable = "稳定" if spread == 0 else f"波动{spread}分 ⚠️"
            correct = "✓" if abs(avg - expected) <= 0.5 else f"✗ 偏差{round(avg-expected,1)}分"

            lines.append(f"  {display}: {scores}  均值={avg}  {stable}  {correct}")
    lines.append("")

    # ==================== 2. 渐进删减敏感度 ====================
    lines.append("-" * 70)
    lines.append("  2. 渐进删减敏感度")
    lines.append("-" * 70)

    # 按版本顺序分析（V0 完整 → V1 删1句 → V2 删2句 → ...）
    sorted_versions = sorted(results.keys(), key=lambda k: (
        0 if k.startswith("V0") else
        1 if k.startswith("V1") else
        2 if k.startswith("V2") else
        3 if k.startswith("V3") else
        4 if k.startswith("V4") else
        5 if k.startswith("V5") else
        6 if k.startswith("V6") else
        7
    ))

    # 构建分数矩阵: version -> model -> avg_score
    matrix = {}
    for ver_name in sorted_versions:
        ver = results[ver_name]
        matrix[ver_name] = {}
        for mid in model_ids:
            scores_data = ver["model_scores"].get(mid, [])
            scores = [s["score"] for s in scores_data if s["score"] is not None]
            matrix[ver_name][mid] = round(mean(scores), 2) if scores else None

    # 输出矩阵表格
    col_width = max(len(get_model_display_name(m, meta)) for m in model_ids) + 2
    ver_width = max(len(v) for v in sorted_versions) + 2

    header = " " * ver_width + "预期".ljust(6)
    for mid in model_ids:
        header += get_model_display_name(mid, meta).ljust(col_width)
    lines.append(header)
    lines.append("─" * len(header))

    for ver_name in sorted_versions:
        ver = results[ver_name]
        expected = ver["expected_score"]
        row = ver_name.ljust(ver_width) + str(expected).ljust(6)
        for mid in model_ids:
            avg = matrix[ver_name].get(mid)
            if avg is None:
                row += "FAIL".ljust(col_width)
            else:
                diff = avg - expected
                marker = ""
                if abs(diff) > 1:
                    marker = " ⚠️"
                elif abs(diff) > 0:
                    marker = " △"
                row += f"{avg}{marker}".ljust(col_width)
        lines.append(row)

    lines.append("")

    # ==================== 3. 不一致检测 ====================
    lines.append("-" * 70)
    lines.append("  3. 不一致检测")
    lines.append("-" * 70)

    inconsistencies = []

    # 检测相邻版本之间的降分是否一致
    if len(sorted_versions) >= 2 and "V0" in sorted_versions[0]:
        baseline_ver = sorted_versions[0]
        baseline_scores = matrix[baseline_ver]

        for i in range(1, len(sorted_versions)):
            ver_name = sorted_versions[i]
            ver = results[ver_name]
            desc = ver["description"]
            expected_drop = results[baseline_ver]["expected_score"] - ver["expected_score"]

            drops = {}
            for mid in model_ids:
                b = baseline_scores.get(mid)
                c = matrix[ver_name].get(mid)
                if b is not None and c is not None:
                    drops[mid] = round(b - c, 2)

            if not drops:
                continue

            drop_values = list(drops.values())
            drop_spread = max(drop_values) - min(drop_values) if len(drop_values) > 1 else 0

            if drop_spread > 1.5:
                drop_detail = ", ".join(
                    f"{get_model_display_name(m, meta)}:降{d}分"
                    for m, d in drops.items()
                )
                inconsistencies.append({
                    "version": ver_name,
                    "description": desc,
                    "expected_drop": expected_drop,
                    "drops": drops,
                    "spread": drop_spread,
                    "detail": drop_detail,
                })

    if inconsistencies:
        lines.append(f"  发现 {len(inconsistencies)} 处不一致（降分差异 > 1.5 分）:\n")
        for inc in inconsistencies:
            lines.append(f"  [{inc['version']}] {inc['description']}")
            lines.append(f"    预期降分: {inc['expected_drop']} 分")
            lines.append(f"    实际降分: {inc['detail']}")
            lines.append("")
    else:
        lines.append("  未发现显著不一致 ✓")
    lines.append("")

    # ==================== 4. 稳定性分析 ====================
    lines.append("-" * 70)
    lines.append("  4. 同一输入多次评分稳定性")
    lines.append("-" * 70)

    for ver_name in sorted_versions:
        ver = results[ver_name]
        has_unstable = False
        unstable_details = []

        for mid in model_ids:
            scores_data = ver["model_scores"].get(mid, [])
            scores = [s["score"] for s in scores_data if s["score"] is not None]
            if len(scores) < 2:
                continue
            spread = max(scores) - min(scores)
            if spread > 0:
                has_unstable = True
                display = get_model_display_name(mid, meta)
                unstable_details.append(f"  {display}: {scores} (波动{spread}分)")

        if has_unstable:
            lines.append(f"  [{ver_name}] 不稳定:")
            for d in unstable_details:
                lines.append(d)
            lines.append("")

    if not any(
        max(s["score"] for s in ver["model_scores"].get(mid, []) if s["score"] is not None) -
        min(s["score"] for s in ver["model_scores"].get(mid, []) if s["score"] is not None) > 0
        for ver_name, ver in results.items()
        for mid in model_ids
        if len([s for s in ver["model_scores"].get(mid, []) if s["score"] is not None]) >= 2
    ):
        lines.append("  所有模型评分稳定 ✓")
    lines.append("")

    # ==================== 5. 近义表达测试 ====================
    if "V7" in "".join(sorted_versions):
        lines.append("-" * 70)
        lines.append("  5. 近义表达一致性（V7 改写版 vs V0 完整版）")
        lines.append("-" * 70)

        v7_key = [k for k in sorted_versions if k.startswith("V7")]
        if v7_key:
            v7_scores = matrix[v7_key[0]]
            v0_scores = matrix[sorted_versions[0]]
            for mid in model_ids:
                v0 = v0_scores.get(mid)
                v7 = v7_scores.get(mid)
                display = get_model_display_name(mid, meta)
                if v0 is not None and v7 is not None:
                    diff = round(v7 - v0, 2)
                    status = "一致 ✓" if abs(diff) <= 0.5 else f"偏差{diff}分 ⚠️"
                    lines.append(f"  {display}: V0={v0}  V7={v7}  {status}")
            lines.append("")

    # ==================== 总结 ====================
    lines.append("=" * 70)
    lines.append("  总结")
    lines.append("=" * 70)

    issue_count = len(inconsistencies)
    lines.append(f"  不一致项: {issue_count}")

    if issue_count > 0:
        lines.append("  建议: 以上不一致项需要排查根因，可能是:")
        lines.append("    - 不同模型对评分标准的理解差异")
        lines.append("    - Prompt 中某些表述对特定模型效果不好")
        lines.append("    - 模型本身对同一问题的回答不稳定性")
    else:
        lines.append("  所有模型在删减测试中表现一致 ✓")

    lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else None
    result = load_result(path)
    report = analyze(result)
    print(report)

    # 同时保存到文件
    os.makedirs("results", exist_ok=True)
    from datetime import datetime
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_file = f"results/report_{ts}.txt"
    with open(report_file, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"报告已保存到: {report_file}")
