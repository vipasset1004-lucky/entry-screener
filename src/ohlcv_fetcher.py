"""FinanceDataReader로 KOSPI/KOSDAQ 거래대금 5억+ 종목의 일봉 200일 OHLCV 수집."""
from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Iterable

import FinanceDataReader as fdr
import pandas as pd

# 분석 대상 거래대금 임계값 (5억원)
MIN_AMOUNT = 500_000_000
# 일봉 lookback (일목스팬2 = 52일 + 후행 26일 + 여유)
LOOKBACK_DAYS = 200

# 제외 키워드 (ETF·우선주 등)
_EXCLUDE_KEYWORDS = ("ETF", "ETN", "스팩", "리츠", "선물", "인버스", "레버리지")


def _is_etf_or_special(name: str) -> bool:
    if not name:
        return True
    if any(k in name for k in _EXCLUDE_KEYWORDS):
        return True
    # 우선주: 끝자리 "우", "우B", "(우)"
    if name.endswith("우") or name.endswith("(우)") or "우B" in name:
        return True
    return False


@dataclass
class UniverseItem:
    code: str
    name: str
    market: str
    marcap: int
    amount: int  # 전 영업일 거래대금


def get_universe_full() -> list[UniverseItem]:
    """KOSPI+KOSDAQ 상장 종목 + 시총·거래대금 일괄 조회.
       FDR StockListing은 가장 최근 영업일 기준."""
    items: list[UniverseItem] = []
    for market in ("KOSPI", "KOSDAQ"):
        try:
            df = fdr.StockListing(market)
        except Exception as e:
            print(f"[WARN] StockListing({market}) 실패: {e}")
            continue
        for _, row in df.iterrows():
            code = str(row.get("Code") or "").zfill(6)
            name = str(row.get("Name") or "")
            amount = int(row.get("Amount") or 0)
            marcap = int(row.get("Marcap") or 0)
            if not code or not name:
                continue
            if _is_etf_or_special(name):
                continue
            items.append(UniverseItem(
                code=code, name=name, market=market,
                marcap=marcap, amount=amount,
            ))
    return items


def get_universe(min_amount: int = MIN_AMOUNT) -> list[UniverseItem]:
    full = get_universe_full()
    return [u for u in full if u.amount >= min_amount]


def _fetch_one(ticker: str) -> tuple[str, pd.DataFrame | None]:
    end = datetime.now()
    start = end - timedelta(days=int(LOOKBACK_DAYS * 1.5))
    for attempt in range(3):
        try:
            df = fdr.DataReader(ticker, start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"))
            if df is None or df.empty or len(df) < 60:
                return ticker, None
            # 컬럼명 한글 매핑 (indicators가 기대하는 형식)
            df = df.rename(columns={
                "Open": "시가", "High": "고가", "Low": "저가",
                "Close": "종가", "Volume": "거래량",
            })
            # 거래대금 계산
            df["거래대금"] = df["종가"] * df["거래량"]
            return ticker, df
        except Exception:
            time.sleep(1.0 * (attempt + 1))
    return ticker, None


@dataclass
class FetchResult:
    success: dict[str, pd.DataFrame]
    failed: list[str]
    universe_size: int
    elapsed_sec: float


def fetch_ohlcv_for(tickers: Iterable[str], max_workers: int = 12) -> FetchResult:
    tickers = list(tickers)
    success: dict[str, pd.DataFrame] = {}
    failed: list[str] = []
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = {ex.submit(_fetch_one, t): t for t in tickers}
        for fut in as_completed(futures):
            t, df = fut.result()
            if df is not None:
                success[t] = df
            else:
                failed.append(t)
    return FetchResult(
        success=success, failed=failed,
        universe_size=len(tickers),
        elapsed_sec=round(time.time() - t0, 1),
    )


if __name__ == "__main__":
    print("[1] 유니버스 수집...")
    uni = get_universe()
    print(f"  거래대금 5억+ 종목: {len(uni)}개")
    for u in uni[:5]:
        print(f"    {u.code} {u.name} ({u.market}) — 거래대금 {u.amount/1e8:.1f}억, 시총 {u.marcap/1e8:.0f}억")

    if uni:
        print("[2] OHLCV 페치 테스트 (상위 5개)...")
        codes = [u.code for u in uni[:5]]
        r = fetch_ohlcv_for(codes, max_workers=4)
        print(f"  성공 {len(r.success)}/{r.universe_size}, 실패 {len(r.failed)}, 소요 {r.elapsed_sec}s")
        for tk, df in list(r.success.items())[:2]:
            print(f"    {tk}: rows={len(df)}, 마지막 종가={df['종가'].iloc[-1]:.0f}")
