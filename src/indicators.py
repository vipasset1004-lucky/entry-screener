"""일목균형표 + 볼린저밴드 + 엔벨로프 계산."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd


# === 파라미터 ================================================================
ICHIMOKU_TENKAN  = 9    # 전환선
ICHIMOKU_KIJUN   = 26   # 기준선 / 후행스팬
ICHIMOKU_SPAN_B  = 52   # 선행스팬2

BB_PERIOD = 20          # 볼린저 SMA
BB_STDDEV = 2.0

ENV_PERIOD = 20         # 엔벨로프 SMA
ENV_PCT    = 5.0        # ±5%


# === 헬퍼 ====================================================================
def _midpoint_hl(high: pd.Series, low: pd.Series, period: int) -> pd.Series:
    return (high.rolling(period).max() + low.rolling(period).min()) / 2.0


# === 일목 ====================================================================
def compute_ichimoku(df: pd.DataFrame) -> dict[str, pd.Series]:
    """df는 '시가','고가','저가','종가','거래량' 컬럼 (pykrx 한글 컬럼명)."""
    high = df["고가"]
    low  = df["저가"]
    close = df["종가"]

    tenkan = _midpoint_hl(high, low, ICHIMOKU_TENKAN)           # 전환선
    kijun  = _midpoint_hl(high, low, ICHIMOKU_KIJUN)            # 기준선
    span_a = ((tenkan + kijun) / 2.0).shift(ICHIMOKU_KIJUN)     # 선행스팬1 (26일 앞)
    span_b = _midpoint_hl(high, low, ICHIMOKU_SPAN_B).shift(ICHIMOKU_KIJUN)  # 선행스팬2
    chikou = close.shift(-ICHIMOKU_KIJUN)                        # 후행스팬 (26일 뒤)

    return {
        "tenkan": tenkan,
        "kijun":  kijun,
        "span_a": span_a,
        "span_b": span_b,
        "chikou": chikou,
    }


# === 볼린저밴드 ==============================================================
def compute_bollinger(df: pd.DataFrame) -> dict[str, pd.Series]:
    close = df["종가"]
    mid = close.rolling(BB_PERIOD).mean()
    std = close.rolling(BB_PERIOD).std()
    upper = mid + BB_STDDEV * std
    lower = mid - BB_STDDEV * std
    bandwidth = (upper - lower) / mid * 100  # %
    percent_b = (close - lower) / (upper - lower)
    return {
        "bb_mid": mid,
        "bb_upper": upper,
        "bb_lower": lower,
        "bb_width": bandwidth,
        "bb_pctb": percent_b,
    }


# === 엔벨로프 =================================================================
def compute_envelope(df: pd.DataFrame) -> dict[str, pd.Series]:
    close = df["종가"]
    mid = close.rolling(ENV_PERIOD).mean()
    upper = mid * (1 + ENV_PCT / 100.0)
    lower = mid * (1 - ENV_PCT / 100.0)
    position_pct = (close - mid) / mid * 100   # 중심 대비 가격 위치 (%)
    return {
        "env_mid":   mid,
        "env_upper": upper,
        "env_lower": lower,
        "env_pos":   position_pct,
    }


# === 모두 합쳐 가장 최근 값 추출 ===========================================
@dataclass
class IndicatorSnapshot:
    ticker: str
    name: str
    market: str
    close: float
    volume_amount: float       # 거래대금

    # 일목
    tenkan: float
    kijun: float
    span_a: float
    span_b: float
    cloud_top: float           # max(span_a, span_b)
    cloud_bottom: float        # min(span_a, span_b)
    cloud_thickness_pct: float # (cloud_top - cloud_bottom) / close * 100
    above_cloud: bool
    below_cloud: bool
    tenkan_above_kijun: bool
    tenkan_kijun_cross_days_ago: int | None  # 골든크로스 발생 후 경과 일수
    chikou_above_price_26d_ago: bool

    # 볼린저
    bb_mid: float
    bb_upper: float
    bb_lower: float
    bb_width: float
    bb_pctb: float
    bb_squeeze: bool           # 폭이 최근 20일 중 하위 20%
    bb_expanding: bool         # 어제보다 폭 확대

    # 엔벨로프
    env_mid: float
    env_upper: float
    env_lower: float
    env_pos_pct: float         # 중심 대비 가격 위치 (%)
    env_above_lower: bool      # 어제 하한 아래였다가 오늘 회복?
    env_just_broke_upper: bool # 어제 상한 아래였다가 오늘 돌파?

    # 추가 컨텍스트
    rsi14: float | None        # 보조 지표
    ret_20d_pct: float | None
    above_ma20: bool

    raw: dict[str, Any]        # 전체 시리즈 dict (디버깅용, JSON 출력 시 제외)


def _safe_last(s: pd.Series) -> float | None:
    if s is None or s.empty:
        return None
    val = s.iloc[-1]
    if pd.isna(val):
        return None
    return float(val)


def _safe_at(s: pd.Series, idx: int) -> float | None:
    if s is None or len(s) <= abs(idx):
        return None
    val = s.iloc[idx]
    if pd.isna(val):
        return None
    return float(val)


def _rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.where(delta > 0, 0).rolling(period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def snapshot(ticker: str, name: str, market: str, df: pd.DataFrame) -> IndicatorSnapshot | None:
    if df is None or len(df) < 60:
        return None
    df = df.copy().dropna(how="all")
    if len(df) < 60:
        return None

    close_series = df["종가"]
    ichi = compute_ichimoku(df)
    bb   = compute_bollinger(df)
    env  = compute_envelope(df)
    rsi  = _rsi(close_series, 14)

    close = _safe_last(close_series)
    if close is None:
        return None
    amount_last = float(df["거래대금"].iloc[-1]) if "거래대금" in df.columns else 0.0

    tenkan = _safe_last(ichi["tenkan"])
    kijun  = _safe_last(ichi["kijun"])
    span_a = _safe_last(ichi["span_a"])
    span_b = _safe_last(ichi["span_b"])

    if None in (tenkan, kijun, span_a, span_b):
        return None

    cloud_top    = max(span_a, span_b)
    cloud_bottom = min(span_a, span_b)
    cloud_thick_pct = (cloud_top - cloud_bottom) / close * 100 if close else 0

    above_cloud = close > cloud_top
    below_cloud = close < cloud_bottom

    # 골든크로스 발생 후 경과 일수 (전환선 - 기준선 부호 변경)
    diff = ichi["tenkan"] - ichi["kijun"]
    cross_days_ago = None
    for i in range(1, min(11, len(diff))):
        try:
            if diff.iloc[-i] > 0 and diff.iloc[-i - 1] <= 0:
                cross_days_ago = i - 1
                break
        except Exception:
            continue

    # 후행스팬 vs 26일 전 가격
    chikou_above = False
    if len(close_series) > ICHIMOKU_KIJUN:
        price_26d_ago = close_series.iloc[-1 - ICHIMOKU_KIJUN]
        chikou_above = close > price_26d_ago

    # 볼린저
    bb_mid_v   = _safe_last(bb["bb_mid"])
    bb_upper_v = _safe_last(bb["bb_upper"])
    bb_lower_v = _safe_last(bb["bb_lower"])
    bb_width_v = _safe_last(bb["bb_width"]) or 0
    bb_pctb_v  = _safe_last(bb["bb_pctb"]) or 0

    # 스퀴즈: 폭이 최근 20일 중 하위 20% 이하
    bb_squeeze = False
    if bb["bb_width"].dropna().size >= 20:
        q20 = bb["bb_width"].tail(20).quantile(0.2)
        bb_squeeze = bb_width_v <= q20

    # 폭 확대 (어제보다 큼)
    bb_yesterday = _safe_at(bb["bb_width"], -2)
    bb_expanding = bb_yesterday is not None and bb_width_v > bb_yesterday

    # 엔벨로프
    env_mid_v   = _safe_last(env["env_mid"])
    env_upper_v = _safe_last(env["env_upper"])
    env_lower_v = _safe_last(env["env_lower"])
    env_pos_v   = _safe_last(env["env_pos"]) or 0

    # 하한 회복: 어제 하한 아래 → 오늘 위
    env_pos_yest = _safe_at(env["env_pos"], -2)
    env_above_lower = env_pos_yest is not None and env_pos_yest < -ENV_PCT and env_pos_v > -ENV_PCT

    # 상한 돌파: 어제 상한 아래 → 오늘 위
    env_just_broke_upper = env_pos_yest is not None and env_pos_yest < ENV_PCT and env_pos_v > ENV_PCT

    # 보조
    rsi14 = _safe_last(rsi)
    ret_20d = None
    if len(close_series) > 20:
        ret_20d = (close / close_series.iloc[-21] - 1) * 100
    ma20 = bb_mid_v
    above_ma20 = ma20 is not None and close > ma20

    return IndicatorSnapshot(
        ticker=ticker,
        name=name,
        market=market,
        close=close,
        volume_amount=amount_last,
        tenkan=tenkan,
        kijun=kijun,
        span_a=span_a,
        span_b=span_b,
        cloud_top=cloud_top,
        cloud_bottom=cloud_bottom,
        cloud_thickness_pct=round(cloud_thick_pct, 2),
        above_cloud=above_cloud,
        below_cloud=below_cloud,
        tenkan_above_kijun=tenkan > kijun,
        tenkan_kijun_cross_days_ago=cross_days_ago,
        chikou_above_price_26d_ago=chikou_above,
        bb_mid=bb_mid_v,
        bb_upper=bb_upper_v,
        bb_lower=bb_lower_v,
        bb_width=round(bb_width_v, 2),
        bb_pctb=round(bb_pctb_v, 2),
        bb_squeeze=bb_squeeze,
        bb_expanding=bb_expanding,
        env_mid=env_mid_v,
        env_upper=env_upper_v,
        env_lower=env_lower_v,
        env_pos_pct=round(env_pos_v, 2),
        env_above_lower=env_above_lower,
        env_just_broke_upper=env_just_broke_upper,
        rsi14=round(rsi14, 1) if rsi14 is not None else None,
        ret_20d_pct=round(ret_20d, 1) if ret_20d is not None else None,
        above_ma20=above_ma20,
        raw={},
    )
