import json
import sys
import time
from types import SimpleNamespace

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from app.db import session_local
from app.routers.ai import MAX_DISTANCE
from app.services.generate import generate_answer
from app.services.retrieval import retrieve

TENANT_ID = "9a45b7c2-5d3e-4f2a-8b1c-6d7e8f9a0b1c"
GOLDEN_PATH = "golden_set.json"
SLEEP_SECONDS = 4.5  # Gemini API rate-limit (429) se bachne ke liye


def main():
    retrieval_only = "--retrieval-only" in sys.argv
    with open(GOLDEN_PATH, "r", encoding="utf-8") as f:
        dataset = json.load(f)

    db = session_local()
    user = SimpleNamespace(tenant_id=TENANT_ID, role="end_user")

    ans_total = 0
    unans_total = 0
    hit_at_1 = 0
    hit_at_5 = 0
    answered_with_citations = 0  # non-degraded Gemini answer with valid source labels
    abstained_correctly = 0     # answerable=False aur model ne "I don't know." bola
    fallback_count = 0          # Gemini fail/rate-limit hua

    failures = []

    try:
        for idx, item in enumerate(dataset, start=1):
            q = item["question"]
            expected = item["expected_title"]
            answerable = item["answerable"]

            rows = retrieve(db, user, question=q, limit=5, max_distance=MAX_DISTANCE)
            titles = [r.get("title") for r in rows]
            top_dist = round(rows[0]["distance"], 3) if rows and rows[0].get("distance") is not None else None

            if retrieval_only:
                res = {"text": "[skipped]", "abstained": not bool(rows), "fallback": False}
            elif not rows:
                res = {"text": "I don't know.", "abstained": True, "fallback": False}
            else:
                res = generate_answer(q, rows)
                time.sleep(SLEEP_SECONDS)

            if res["fallback"]:
                fallback_count += 1

            if answerable:
                ans_total += 1
                is_hit1 = bool(titles) and titles[0] == expected
                is_hit5 = expected in titles
                if is_hit1:
                    hit_at_1 += 1
                if is_hit5:
                    hit_at_5 += 1

                if (
                    not retrieval_only
                    and not res["abstained"]
                    and not res["fallback"]
                    and bool(res.get("source_indexes"))
                ):
                    answered_with_citations += 1

                if retrieval_only:
                    passed = is_hit5
                else:
                    passed = (
                        is_hit5
                        and not res["abstained"]
                        and not res["fallback"]
                        and bool(res.get("source_indexes"))
                    )
                status = "PASS" if passed else "FAIL"
                if status == "FAIL":
                    failures.append({
                        "idx": idx,
                        "type": "ANSWERABLE",
                        "question": q,
                        "expected": expected,
                        "retrieved": titles[:3],
                        "top_dist": top_dist,
                        "abstained": res["abstained"],
                        "fallback": res["fallback"],
                        "answer": res["text"][:140],
                    })
            else:
                unans_total += 1
                if res["abstained"]:
                    abstained_correctly += 1
                    status = "PASS"
                else:
                    status = "FAIL"
                    failures.append({
                        "idx": idx,
                        "type": "UNANSWERABLE (HALLUCINATED)",
                        "question": q,
                        "expected": "I don't know.",
                        "retrieved": titles[:3],
                        "top_dist": top_dist,
                        "abstained": res["abstained"],
                        "fallback": res["fallback"],
                        "answer": res["text"][:140],
                    })

            print(f"[{idx:02d}/{len(dataset)}] {status:4s} | dist={str(top_dist):5s} | {q[:55]}")
    finally:
        db.close()

    header = "RETRIEVAL-ONLY EVAL SUMMARY" if retrieval_only else "FULL EVAL SUMMARY"
    print("\n" + "=" * 60)
    print(header)
    print("=" * 60)
    print(f"Retrieval Hit@1 (Answerable) : {hit_at_1}/{ans_total} ({hit_at_1/ans_total:.0%})")
    print(f"Retrieval Hit@5 (Answerable) : {hit_at_5}/{ans_total} ({hit_at_5/ans_total:.0%})")
    if not retrieval_only:
        print(f"Gemini answers with citations: {answered_with_citations}/{ans_total} ({answered_with_citations/ans_total:.0%})")
        print(f"Unanswerable Abstain Rate    : {abstained_correctly}/{unans_total} ({abstained_correctly/unans_total:.0%})")
        print(f"LLM Fallbacks (errors/429)   : {fallback_count}/{len(dataset)}")
    else:
        print(f"Unanswerable Blocked by DB   : {abstained_correctly}/{unans_total} ({abstained_correctly/unans_total:.0%})")

    if failures:
        print("\n" + "-" * 60)
        print(f"FAILED CASES ({len(failures)})")
        print("-" * 60)
        for f in failures:
            print(f"\n#{f['idx']} [{f['type']}] {f['question']}")
            print(f"  Expected : {f['expected']}")
            print(f"  Retrieved: {f['retrieved']} (top_dist={f['top_dist']})")
            print(f"  Abstained: {f['abstained']} | Fallback: {f['fallback']}")
            print(f"  Answer   : {f['answer']!r}")


if __name__ == "__main__":
    main()