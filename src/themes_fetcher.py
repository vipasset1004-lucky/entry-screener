"""다른 스크리너(new-high·divergence)의 results.json에서 종목 테마 정보 수집.
   FDR엔 테마가 없어서 별도 fetch로 합성."""
from __future__ import annotations

import json
from urllib.error import URLError
from urllib.request import Request, urlopen

SOURCES = [
    "https://vipasset1004-lucky.github.io/new-high-screener/results.json",
    "https://vipasset1004-lucky.github.io/divergence-screener/divergence_results.json",
]


def _fetch_json(url: str, timeout: int = 20):
    req = Request(url, headers={"User-Agent": "entry-screener/1.0", "Cache-Control": "no-cache"})
    try:
        with urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (URLError, json.JSONDecodeError, TimeoutError):
        return None


def build_theme_map() -> dict[str, list[str]]:
    """ticker → themes 매핑. 여러 소스의 테마를 합집합으로 결합."""
    themes_by_ticker: dict[str, set[str]] = {}
    for url in SOURCES:
        data = _fetch_json(url)
        if not data:
            continue
        results = data.get("results") or []
        for item in results:
            if not isinstance(item, dict):
                continue
            t = str(item.get("ticker") or "").strip()
            if not t:
                continue
            themes = item.get("themes") or []
            if not isinstance(themes, list):
                continue
            bucket = themes_by_ticker.setdefault(t, set())
            for th in themes:
                if isinstance(th, str) and th.strip():
                    bucket.add(th.strip())
    return {t: sorted(themes)[:5] for t, themes in themes_by_ticker.items()}


if __name__ == "__main__":
    m = build_theme_map()
    print(f"수집된 ticker: {len(m)}")
    for t in list(m.keys())[:5]:
        print(f"  {t}: {m[t]}")
