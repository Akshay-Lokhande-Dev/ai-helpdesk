import json
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
    with open(GOLDEN_PATH, "r", encoding="utf-8") as f:
        dataset = json.load(f)

    db = session_local()
    user = SimpleNamespace(tenant_id=TENANT_ID, role="end_user")

    ans_total = 0
    unans_total = 0
    hit_at_1 = 0
    hit_at_5 = 0
    answered_correctly = 0      # answerable=True aur model ne abstain nahi kiya
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

            if not rows:
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

                if not res["abstained"] and not res["fallback"]:
                    answered_correctly += 1

                status = "PASS" if (is_hit5 and not res["abstained"] and not res["fallback"]) else "FAIL"
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

    print("\n" + "=" * 60)
    print("BASELINE EVAL SUMMARY")
    print("=" * 60)
    print(f"Retrieval Hit@1 (Answerable) : {hit_at_1}/{ans_total} ({hit_at_1/ans_total:.0%})")
    print(f"Retrieval Hit@5 (Answerable) : {hit_at_5}/{ans_total} ({hit_at_5/ans_total:.0%})")
    print(f"Answered (non-abstain)       : {answered_correctly}/{ans_total} ({answered_correctly/ans_total:.0%})")
    print(f"Unanswerable Abstain Rate    : {abstained_correctly}/{unans_total} ({abstained_correctly/unans_total:.0%})")
    print(f"LLM Fallbacks (errors/429)   : {fallback_count}/{len(dataset)}")

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