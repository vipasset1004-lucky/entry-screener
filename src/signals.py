"""일목 + 볼린저 + 엔벨로프 3중 정렬 기반 매수·매도 타점 점수."""
from __future__ import annotations

from typing import Any

from .indicators import IndicatorSnapshot


def buy_score(s: IndicatorSnapshot) -> dict[str, Any]:
    """매수 타점 점수 (0~100). 백테스트 검증 없이 이론적 가중치."""
    score = 0
    hits: list[str] = []
    penalties: list[str] = []

    # === A. 일목균형표 (40점) ===
    if s.above_cloud:
        score += 15; hits.append("구름 위 (추세 적격)")
    elif s.below_cloud:
        penalties.append("구름 아래")
    if s.tenkan_above_kijun:
        score += 10; hits.append("전환선 > 기준선")
        if s.tenkan_kijun_cross_days_ago is not None and s.tenkan_kijun_cross_days_ago <= 3:
            score += 5; hits.append(f"막 골든크로스 (-{s.tenkan_kijun_cross_days_ago}d)")
    if s.chikou_above_price_26d_ago:
        score += 8; hits.append("후행스팬 양호")
    # 구름 두께 (지지/저항 강도)
    if s.cloud_thickness_pct >= 5:
        score += 7; hits.append(f"구름 두꺼움 {s.cloud_thickness_pct:.1f}%")
    elif s.cloud_thickness_pct >= 2:
        score += 4

    # === B. 볼린저밴드 (30점) ===
    # 눌림 매수: 중간선 위 + 하단 근접 (%B 0.2~0.5)
    if s.above_ma20 and 0.2 <= s.bb_pctb <= 0.5:
        score += 15; hits.append(f"%B {s.bb_pctb:.2f} 눌림 매수권")
    elif s.above_ma20 and 0.5 < s.bb_pctb <= 0.7:
        score += 6
    elif s.bb_pctb >= 0.95:
        penalties.append(f"%B {s.bb_pctb:.2f} 상단 (단기 과열)")

    # 스퀴즈 + 확장 = 폭발 신호
    if s.bb_squeeze and s.bb_expanding:
        score += 10; hits.append("스퀴즈 후 확장 시작")
    elif s.bb_squeeze:
        score += 5; hits.append("볼린저 스퀴즈 (대기)")

    # 좁은 폭 자체도 부분 가산
    if s.bb_width < 10 and not s.bb_squeeze:
        score += 2

    # === C. 엔벨로프 (30점) ===
    # 0% ~ -3% 구간 = 최적 저점 매수
    if -3 <= s.env_pos_pct <= 0:
        score += 15; hits.append(f"엔벨로프 {s.env_pos_pct:+.1f}% 저점")
    elif 0 < s.env_pos_pct <= 3:
        score += 10; hits.append(f"엔벨로프 {s.env_pos_pct:+.1f}% 중심권")
    elif s.env_pos_pct < -3:
        score += 6  # 너무 빠짐은 약한 점수
    elif s.env_pos_pct > 4:
        penalties.append(f"엔벨로프 +{s.env_pos_pct:.1f}% 상한 근접")

    # 하한 반등
    if s.env_above_lower:
        score += 10; hits.append("엔벨로프 하한 반등")
    # 상한 돌파 직후
    elif s.env_just_broke_upper:
        score += 5; hits.append("엔벨로프 상한 돌파")

    # === 보조 페널티 (RSI 과열, 20일 과속) ===
    if s.rsi14 is not None and s.rsi14 >= 80:
        score -= 12; penalties.append(f"RSI {s.rsi14:.0f} 과열")
    elif s.rsi14 is not None and s.rsi14 >= 75:
        score -= 5; penalties.append(f"RSI {s.rsi14:.0f} 부담")

    if s.ret_20d_pct is not None and s.ret_20d_pct >= 35:
        score -= 8; penalties.append(f"20일 +{s.ret_20d_pct:.0f}% 과속")

    score = max(0, min(100, score))

    # 등급
    if score >= 80:
        rank = ("황금 타점", "🏆")
    elif score >= 65:
        rank = ("강한 매수", "💎")
    elif score >= 50:
        rank = ("매수", "🎯")
    elif score >= 35:
        rank = ("관찰", "🔍")
    else:
        rank = ("부적합", "")

    # 3중 정렬 보너스 (구름 위 + BB 중간 위 + ENV 0% 위)
    triple_aligned = s.above_cloud and s.above_ma20 and s.env_pos_pct >= -2 and s.env_pos_pct <= 4
    if triple_aligned:
        hits.insert(0, "✨ 3중 정렬")

    return {
        "score": score,
        "rank": rank[0],
        "rank_emoji": rank[1],
        "hits": hits,
        "penalties": penalties,
        "triple_aligned": triple_aligned,
    }


def sell_score(s: IndicatorSnapshot) -> dict[str, Any]:
    """매도/차익실현 타점 점수 (0~100). 보유 종목 청산 시점 판정용."""
    score = 0
    hits: list[str] = []

    # 일목 하락 신호
    if s.below_cloud:
        score += 15; hits.append("구름 아래로 빠짐")
    if not s.tenkan_above_kijun:
        score += 12; hits.append("전환선 < 기준선 (데드크로스)")
    if not s.chikou_above_price_26d_ago:
        score += 8

    # 볼린저 상단 과열
    if s.bb_pctb >= 1.0:
        score += 15; hits.append("%B 1.0 이상 (상단 돌파)")
    elif s.bb_pctb >= 0.9:
        score += 8

    # 엔벨로프 상한 이탈
    if s.env_pos_pct >= 5:
        score += 15; hits.append(f"엔벨로프 {s.env_pos_pct:+.1f}% 상한 이탈")
    elif s.env_pos_pct >= 3:
        score += 8

    # RSI 과열
    if s.rsi14 is not None and s.rsi14 >= 80:
        score += 12; hits.append(f"RSI {s.rsi14:.0f} 과열")
    elif s.rsi14 is not None and s.rsi14 >= 75:
        score += 6

    # 20일 과속
    if s.ret_20d_pct is not None and s.ret_20d_pct >= 30:
        score += 10; hits.append(f"20일 +{s.ret_20d_pct:.0f}% 과속")

    score = max(0, min(100, score))

    if score >= 70:
        rank = ("청산 강력", "🚨")
    elif score >= 55:
        rank = ("부분 청산", "⚠️")
    elif score >= 40:
        rank = ("주의", "🟡")
    else:
        rank = ("보유", "")

    return {
        "score": score,
        "rank": rank[0],
        "rank_emoji": rank[1],
        "hits": hits,
    }


def trade_levels(s: IndicatorSnapshot) -> dict[str, float]:
    """매매가 자동 계산 — 백테스트 검증 -7%/+20%/+50% 룰."""
    entry = round(s.close, 2)
    return {
        "entry": entry,
        "stop":  round(entry * 0.93, 2),
        "tp1":   round(entry * 1.20, 2),
        "tp2":   round(entry * 1.50, 2),
        # 보조 정보
        "support_kijun": round(s.kijun, 2),
        "support_cloud_top": round(s.cloud_top, 2),
        "resistance_bb_upper": round(s.bb_upper, 2),
        "resistance_env_upper": round(s.env_upper, 2),
    }
