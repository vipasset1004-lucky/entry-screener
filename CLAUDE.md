# CLAUDE.md — 타점 스크리너

AI 협업 가이드.

## 목적

일목균형표 + 볼린저밴드 + 엔벨로프 3중 지표만으로 **정밀 타점**을 잡는 단독 스크리너.
진짜갈놈(`jjingalnom-screener`)과 별개 — 그건 "갈 종목 찾기", 이건 "언제 살까".

## 원칙

1. **pykrx 단일 데이터 소스**. 외부 API 추가 금지 (의존성 최소화).
2. **계산은 모두 로컬** — KRX OHLCV → pandas vectorize → 결과 JSON.
3. **출력 필터링 필수** — 매수 35+ 또는 매도 55+ 만 저장 (JSON 용량 절감).
4. **인라인 데이터** — index.html에 results.json 임베드 (외부 fetch 0).
5. **새 의존성 추가 시 신중** — requirements.txt 3줄 유지.

## 자동화

- KST 16:30 cron (장 마감 30분 후 일봉 확정 반영)
- 약 1,000종목 × 200일 OHLCV → 4~6분 페치 + 1분 계산 = 약 5~7분
- GitHub Actions 무료 한도 내 (월 ~150분 사용)

## 수정 시 주의

- `signals.py`의 가중치 변경 시 결과 분포 크게 변함. 변경 전후 분포 비교 필수.
- pykrx 페치 실패율이 높아지면 KRX 서버 변경 가능 — 재시도 로직 점검.
- `MIN_BUY_KEEP` / `MIN_SELL_KEEP`를 낮추면 JSON 급증 — 모바일 로딩 영향.

## 디버깅

```powershell
# 유니버스만 확인
python -c "from src.ohlcv_fetcher import get_universe; u=get_universe(); print(len(u), u[:10])"

# 단일 종목 지표 확인
python -c "
from src.ohlcv_fetcher import _fetch_one
from src.indicators import snapshot
from src.signals import buy_score
t, df = _fetch_one('005930')
snap = snapshot(t, '삼성전자', 'KOSPI', df)
print(buy_score(snap))
"

# 전체 파이프라인
python -m src.main
```

## 향후 확장 후보

- 일봉 외 주봉/월봉 추가 (장기 추세 확인)
- 시장 레짐 필터 (BULL일 때만 황금 타점 매수)
- 알림 (황금 타점 신규 등장 시)
- 진짜갈놈과 교차 (양쪽 동시 점등 종목 = 최강 픽)
- 백테스트 추가 (가중치 검증)
