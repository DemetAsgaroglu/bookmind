"""BookMind degerlendirme betigi.

    python eval/run_eval.py retrieval   # sadece embedding + FAISS, API anahtari gerekmez
    python eval/run_eval.py agent       # LLM gerektirir (.env icindeki saglayici kullanilir)

Retrieval: her sorgu icin ilk 5 sonucta beklenen turden kitap var mi (Hit@5) ve
ilk 5 sonucun ne kadari beklenen turde (Precision@5).

Agent: dogru araci secme orani ve SQL gerektiren sorularda cevabin dogru
kitaplari/sayiyi icerip icermedigi. Dogru cevap, gold_sql sorgusu ayni
veritabaninda calistirilarak bulunur.
"""

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from bookmind.config import get_settings  # noqa: E402
from bookmind.database import Database  # noqa: E402
from bookmind.sql_guard import run_readonly_query  # noqa: E402
from bookmind.text import normalize  # noqa: E402

EVAL_DIR = Path(__file__).resolve().parent
EVAL_USER = "eval_kullanici"
# get_my_library sorulari icin ornek bir okuma gecmisi
EVAL_LIBRARY = [("book_064", 5), ("book_060", 4), ("book_020", 5)]


def evaluate_retrieval(k: int = 5) -> dict:
    from bookmind.services import create_services

    services = create_services(with_agent=False)
    cases = json.loads((EVAL_DIR / "retrieval_set.json").read_text(encoding="utf-8"))
    hits, precisions = 0, []
    for case in cases:
        results = services.store.search(case["query"], k=k)
        books = services.db.get_books([book_id for book_id, _ in results])
        target = normalize(case["genre"])
        matches = [normalize(books[b]["genre"]).find(target) >= 0 for b, _ in results]
        hits += any(matches)
        precisions.append(sum(matches) / k)
        mark = "+" if any(matches) else "-"
        print(f"[{mark}] {case['query']:<45} beklenen: {case['genre']:<22} isabet: {sum(matches)}/{k}")
    summary = {
        "hit_at_5": round(hits / len(cases), 3),
        "precision_at_5": round(sum(precisions) / len(cases), 3),
        "n": len(cases),
    }
    print(f"\nHit@{k}: {summary['hit_at_5']:.1%}  Precision@{k}: {summary['precision_at_5']:.1%}  ({len(cases)} sorgu)")
    return summary


def _expected_answer(db: Database, case: dict) -> list[str]:
    rows = run_readonly_query(db, case["gold_sql"])
    if case.get("answer_is_count"):
        return [str(rows[0]["n"])]
    return [normalize(r["title"]) for r in rows]


def evaluate_agent(pause: float = 1.0) -> dict:
    from bookmind.agent import BUSY_REPLY
    from bookmind.services import create_services

    services = create_services()
    db = services.db
    for book_id, rating in EVAL_LIBRARY:
        db.add_to_library(EVAL_USER, book_id, "okudum", rating)

    cases = json.loads((EVAL_DIR / "agent_set.json").read_text(encoding="utf-8"))
    tool_ok, answer_ok, answer_total, scored, api_errors = 0, 0, 0, 0, 0
    try:
        for case in cases:
            services.agent.reset(EVAL_USER)
            start = time.perf_counter()
            result = services.agent.chat(EVAL_USER, case["question"])
            elapsed = time.perf_counter() - start
            time.sleep(pause)  # ucretsiz API limitlerine takilmamak icin

            # Kota/yogunluk hatasi modelin karari degil; skora katilmaz, ayrica sayilir
            if result.reply == BUSY_REPLY:
                api_errors += 1
                print(f"[!] {case['question']:<60} API hatasi, skora katilmadi ({elapsed:.1f} sn)")
                continue
            scored += 1

            used_tool = case["tool"] in result.tools_used
            tool_ok += used_tool
            line = f"[{'+' if used_tool else '-'}] {case['question']:<60} araclar: {result.tools_used}"

            if "gold_sql" in case:
                answer_total += 1
                expected = _expected_answer(db, case)
                reply = normalize(result.reply)
                correct = any(item in reply for item in expected)
                answer_ok += correct
                line += f" | cevap: {'dogru' if correct else 'yanlis'}"
            print(f"{line} ({elapsed:.1f} sn)")
    finally:
        for book_id, _ in EVAL_LIBRARY:
            db.remove_from_library(EVAL_USER, book_id)

    summary = {
        "tool_accuracy": round(tool_ok / scored, 3) if scored else None,
        "sql_answer_accuracy": round(answer_ok / answer_total, 3) if answer_total else None,
        "n": scored,
        "api_errors": api_errors,
    }
    if api_errors:
        print(f"\nUYARI: {api_errors} soru API hatasi yuzunden cevaplanamadi; skorlar {scored} soru uzerinden.")
    if scored:
        sql_acc = f"{summary['sql_answer_accuracy']:.1%}" if answer_total else "-"
        print(
            f"\nArac secimi: {summary['tool_accuracy']:.1%} ({scored} soru)  "
            f"SQL cevap dogrulugu: {sql_acc} ({answer_total} soru)"
        )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["retrieval", "agent"])
    parser.add_argument("--pause", type=float, default=1.0, help="Agent sorulari arasi bekleme (sn)")
    args = parser.parse_args()

    summary = evaluate_retrieval() if args.mode == "retrieval" else evaluate_agent(args.pause)
    settings = get_settings()
    out = EVAL_DIR / "results" / f"{args.mode}.json"
    out.parent.mkdir(exist_ok=True)
    summary["llm"] = None
    if args.mode == "agent":
        if settings.llm_provider == "gemini":
            summary["llm"] = f"gemini:{settings.gemini_model}"
            summary["fallback_models"] = settings.gemini_fallback_models
        else:
            summary["llm"] = f"{settings.llm_provider}:{settings.ollama_model}"
    summary["embedding_model"] = settings.embedding_model
    out.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Sonuc kaydedildi: {out}")


if __name__ == "__main__":
    main()
