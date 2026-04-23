"""Quick benchmark — upload MR-161 and measure end-to-end timings.

Run inside the backend container:
    docker exec pdfgraph-backend python -m src.scripts.benchmark
"""

import asyncio
import time
from pathlib import Path

import httpx

API = "http://localhost:8000"
PDF_PATH = Path("/data/samples/MR-161-2018-Tender-Specs.pdf")


async def main() -> None:
    async with httpx.AsyncClient(timeout=300.0) as client:
        print("=" * 60)
        print("Upload / Extraction")
        print("=" * 60)
        with PDF_PATH.open("rb") as fh:
            t0 = time.perf_counter()
            resp = await client.post(
                f"{API}/upload", files={"file": (PDF_PATH.name, fh, "application/pdf")}
            )
        upload = resp.json()
        print(f"  elapsed: {time.perf_counter() - t0:.2f}s")
        print(f"  pages: {upload['page_count']}, sections: {upload['sections']}, "
              f"tables: {upload['tables']}, rule_hits: {upload['rule_hits']}")
        print(f"  graph: {upload['graph_stats']}")

        doc_id = upload["doc_id"]

        print()
        print("=" * 60)
        print("Validation (R001~R005)")
        print("=" * 60)
        t0 = time.perf_counter()
        resp = await client.get(f"{API}/validation/{doc_id}")
        val = resp.json()
        print(f"  elapsed: {time.perf_counter() - t0:.2f}s")
        print(f"  issues: {len(val['issues'])}, passed: {len(val['passed'])}")
        for iss in val["issues"]:
            print(f"    - [{iss['severity']}] {iss['rule_id']}: {iss['title']}")

        print()
        print("=" * 60)
        print("Similarity (Top-4)")
        print("=" * 60)
        t0 = time.perf_counter()
        resp = await client.get(f"{API}/similarity/{doc_id}?top_k=4")
        sim = resp.json()
        print(f"  elapsed: {time.perf_counter() - t0:.2f}s")
        for m in sim["matches"]:
            print(f"    {m['score']*100:5.1f}% {m['title']}  "
                  f"(cos={m['cosine']:.2f} jac={m['jaccard']:.2f})")

        print()
        print("=" * 60)
        print("Chat — 3 sample questions")
        print("=" * 60)
        for q in [
            "이 입찰의 가장 불리한 독소조항 3개는?",
            "Saliferous 환경에서 이 볼트 사양이 안전한가?",
            "Table 1.1에 있는 품목 개수는?",
        ]:
            t0 = time.perf_counter()
            resp = await client.post(f"{API}/chat/{doc_id}", json={"question": q})
            ans = resp.json()
            dt = time.perf_counter() - t0
            print(f"\n  Q: {q}")
            print(f"  elapsed: {dt:.2f}s, citations: {len(ans['citations'])}, "
                  f"graph_facts: {ans['used_graph_facts']}")
            print(f"  A: {ans['answer'][:200]}...")


if __name__ == "__main__":
    asyncio.run(main())
