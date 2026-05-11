"""파이프라인 진입점: pykrx → 지표 계산 → 매수/매도 타점 점수 → results.json + index.html."""
from __future__ import annotations

import json
import sys
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from .indicators import snapshot
from .ohlcv_fetcher import fetch_ohlcv_for, get_universe
from .signals import buy_score, sell_score, trade_levels

REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH       = REPO_ROOT / "results.json"
LAST_UPDATE_PATH  = REPO_ROOT / "last_update.json"
INDEX_HTML_PATH   = REPO_ROOT / "index.html"
TEMPLATE_PATH     = REPO_ROOT / "src" / "template.html"

# 결과 저장 임계값 — buy_score 35+ 또는 sell_score 55+ 만 저장 (파일 크기 절감)
MIN_BUY_KEEP  = 35
MIN_SELL_KEEP = 55


def run() -> int:
    t0 = time.time()
    print(f"[start] {datetime.now(timezone.utc).isoformat()}", flush=True)

    print("[1/4] 유니버스 수집 (거래대금 5억+ KOSPI/KOSDAQ)...", flush=True)
    universe = get_universe()
    if not universe:
        print("[ERROR] 유니버스 비어있음. 종료.", file=sys.stderr)
        return 1
    print(f"  -> {len(universe)}개 종목", flush=True)

    # 종목 메타 캐시
    meta_cache = {u.code: (u.name, u.market, u.marcap, u.amount) for u in universe}
    codes = [u.code for u in universe]

    print("[2/4] OHLCV 페치...", flush=True)
    fetch = fetch_ohlcv_for(codes, max_workers=12)
    print(f"  성공 {len(fetch.success)}/{fetch.universe_size}, 실패 {len(fetch.failed)}, 소요 {fetch.elapsed_sec}s", flush=True)

    print("[3/4] 지표 계산 및 점수...", flush=True)
    results: list[dict] = []
    n_kept = 0
    for ticker, df in fetch.success.items():
        name, market, marcap, _ = meta_cache.get(ticker, (ticker, "", 0, 0))
        snap = snapshot(ticker, name, market, df)
        if snap is None:
            continue
        bs = buy_score(snap)
        ss = sell_score(snap)
        if bs["score"] < MIN_BUY_KEEP and ss["score"] < MIN_SELL_KEEP:
            continue
        # JSON 직렬화용으로 raw 제거 (이미 빈 dict이지만 명시)
        d = asdict(snap)
        d.pop("raw", None)
        d["marcap"] = marcap
        d["buy"] = bs
        d["sell"] = ss
        d["trade"] = trade_levels(snap)
        results.append(d)
        n_kept += 1

    print(f"  저장 대상 {n_kept}개 (buy {MIN_BUY_KEEP}+ or sell {MIN_SELL_KEEP}+)", flush=True)

    # 정렬: 매수 점수 내림차순
    results.sort(key=lambda x: -x["buy"]["score"])

    print("[4/4] 출력 파일 작성...", flush=True)

    # 통계
    by_rank = {"황금 타점": 0, "강한 매수": 0, "매수": 0, "관찰": 0, "부적합": 0}
    triple = 0
    for r in results:
        by_rank[r["buy"]["rank"]] = by_rank.get(r["buy"]["rank"], 0) + 1
        if r["buy"].get("triple_aligned"):
            triple += 1

    output = {
        "meta": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "universe_size": fetch.universe_size,
            "fetched": len(fetch.success),
            "failed": len(fetch.failed),
            "kept": n_kept,
            "elapsed_sec": round(time.time() - t0, 1),
            "version": "1.0.0",
        },
        "counts": {
            "by_rank": by_rank,
            "triple_aligned": triple,
            "sell_strong": sum(1 for r in results if r["sell"]["score"] >= 70),
        },
        "stocks": results,
    }

    json_text = json.dumps(output, ensure_ascii=False, indent=2, default=str)
    json_compact = json.dumps(output, ensure_ascii=False, separators=(",", ":"), default=str)
    OUTPUT_PATH.write_text(json_text, encoding="utf-8")
    LAST_UPDATE_PATH.write_text(
        json.dumps({"updated_at": output["meta"]["generated_at"]}, ensure_ascii=False),
        encoding="utf-8",
    )

    # index.html 생성 — 템플릿에 데이터 inline 임베드 (외부 의존 0)
    if TEMPLATE_PATH.exists():
        html = TEMPLATE_PATH.read_text(encoding="utf-8")
        inline = "<script>window.EMBEDDED_DATA=" + json_compact + ";</script>"
        if "<!-- __EMBEDDED_DATA__ -->" in html:
            html = html.replace("<!-- __EMBEDDED_DATA__ -->", inline, 1)
        else:
            html = html.replace("</body>", inline + "\n</body>", 1)
        INDEX_HTML_PATH.write_text(html, encoding="utf-8")

    c = output["counts"]
    print(
        f"[OK] {OUTPUT_PATH.name} 작성. "
        f"황금 {c['by_rank']['황금 타점']} | 강매 {c['by_rank']['강한 매수']} | "
        f"매수 {c['by_rank']['매수']} | 3중정렬 {c['triple_aligned']} | 청산 {c['sell_strong']}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    sys.exit(run())
