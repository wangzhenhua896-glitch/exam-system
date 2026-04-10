"""
评分一致性测试运行器

用法: python consistency_test/runner.py

遍历所有可用模型，对每个答案版本各评 N 次，输出 JSON 结果文件。
"""

import json
import time
import sys
import os
from datetime import datetime

import requests

# 添加项目根目录到路径，以便导入配置
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from test_data import QUESTION_ID, MAX_SCORE, VERSIONS, RUNS_PER_VERSION, BASE_URL


def get_active_models():
    """从 API 获取所有活跃模型列表"""
    resp = requests.get(f"{BASE_URL}/api/providers", timeout=10)
    resp.raise_for_status()
    data = resp.json().get("data", [])
    return [
        {
            "id": m["id"],
            "provider": m["provider"],
            "model": m["model"],
            "display_name": m.get("display_name", m["model"]),
        }
        for m in data
        if m.get("active")
    ]


def grade_once(answer: str, provider: str, model: str) -> dict:
    """调用评分 API 一次，返回评分结果"""
    payload = {
        "question_id": QUESTION_ID,
        "answer": answer,
        "provider": provider,
        "model": model,
    }
    start = time.time()
    try:
        resp = requests.post(
            f"{BASE_URL}/api/grade",
            json=payload,
            timeout=120,
        )
        elapsed = time.time() - start
        raw = resp.json()

        # API 返回格式: {success: true, data: {score, confidence, ...}}
        data = raw.get("data", raw)

        return {
            "success": resp.status_code == 200 and raw.get("success", True),
            "score": data.get("score"),
            "confidence": data.get("confidence"),
            "comment": data.get("comment", ""),
            "scoring_items": data.get("details", {}).get("scoring_items") if data.get("details") else data.get("scoring_items"),
            "needs_review": data.get("needs_review"),
            "warning": data.get("warning"),
            "error": data.get("error"),
            "elapsed_seconds": round(elapsed, 2),
        }
    except Exception as e:
        elapsed = time.time() - start
        return {
            "success": False,
            "score": None,
            "confidence": None,
            "comment": "",
            "scoring_items": None,
            "needs_review": None,
            "warning": None,
            "error": str(e),
            "elapsed_seconds": round(elapsed, 2),
        }


def run_tests():
    """执行全部测试"""
    print("=" * 60)
    print("  评分一致性测试")
    print("=" * 60)
    print()

    # 获取可用模型
    print("[1/3] 获取可用模型...")
    models = get_active_models()
    if not models:
        print("错误: 没有活跃的模型！请先在管理页面启用至少一个模型。")
        sys.exit(1)

    print(f"  找到 {len(models)} 个活跃模型:")
    for m in models:
        print(f"    - {m['display_name']} ({m['id']})")
    print()

    # 执行测试
    print(f"[2/3] 开始评分测试 ({len(VERSIONS)} 个版本 x {len(models)} 个模型 x {RUNS_PER_VERSION} 次)")
    total = len(VERSIONS) * len(models) * RUNS_PER_VERSION
    done = 0

    results = {
        "meta": {
            "question_id": QUESTION_ID,
            "max_score": MAX_SCORE,
            "runs_per_version": RUNS_PER_VERSION,
            "timestamp": datetime.now().isoformat(),
            "models": [m["id"] for m in models],
        },
        "results": {},
    }

    for ver in VERSIONS:
        ver_name = ver["name"]
        print(f"\n  版本: {ver_name} - {ver['description']}")
        print(f"    预期命中要点: {ver['should_hit']}, 预期得分: {ver['expected_score']}")

        results["results"][ver_name] = {
            "answer": ver["answer"],
            "should_hit": ver["should_hit"],
            "expected_score": ver["expected_score"],
            "description": ver["description"],
            "model_scores": {},
        }

        for model_info in models:
            model_id = model_info["id"]
            scores = []

            for run_idx in range(RUNS_PER_VERSION):
                done += 1
                print(f"    [{done}/{total}] {model_info['display_name']} 第{run_idx+1}次...", end=" ", flush=True)

                result = grade_once(ver["answer"], model_info["provider"], model_info["model"])
                scores.append(result)

                score_display = result.get("score")
                elapsed = result.get("elapsed_seconds", 0)
                if score_display is not None:
                    status = f"{score_display}分"
                elif result.get("error"):
                    status = f"失败:{str(result['error'])[:50]}"
                else:
                    status = "失败:未知错误"
                print(f"{status} ({elapsed}s)")

                # API 间隔，避免限流
                time.sleep(0.5)

            results["results"][ver_name]["model_scores"][model_id] = scores

    # 保存结果
    print()
    print("[3/3] 保存结果...")
    os.makedirs("results", exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"results/test_{timestamp}.json"
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\n  结果已保存到: {filename}")
    print(f"\n  运行 python consistency_test/report.py {filename} 生成报告")

    return filename


if __name__ == "__main__":
    run_tests()
