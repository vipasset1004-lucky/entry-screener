# 🎯 타점 스크리너 (entry-screener)

**일목균형표 + 볼린저밴드 + 엔벨로프** 3중 정렬로 정밀한 매수·매도 타점을 잡는 스크리너.

라이브: https://vipasset1004-lucky.github.io/entry-screener/

## 알고리즘

매수 타점 점수 (0~100):

- **A. 일목균형표 (40점)**: 구름 위 + 전환>기준 + 후행스팬 양호 + 두꺼운 구름
- **B. 볼린저밴드 (30점)**: 중간선 위 + 하단 근접 (눌림 매수) + 스퀴즈 확장
- **C. 엔벨로프 ±5% (30점)**: 0~-3% 저점 + 하한 반등 또는 상한 돌파 직후
- 페널티: RSI 80+ 과열, 20일 +35%+ 과속

3중 정렬 (구름 위 + BB 중간 위 + ENV 중심권) = ✨ 보너스

### 등급

| 점수 | 등급 |
|---|---|
| 🏆 80+ | 황금 타점 |
| 💎 65+ | 강한 매수 |
| 🎯 50+ | 매수 |
| 🔍 35+ | 관찰 |

### 매매룰 (백테스트 기반)

- 손절: −7%
- 익절1: +20% (1/3)
- 익절2: +50% (1/3)
- 잔여: 트레일링

## 흐름

```
KST 16:30 cron
  ↓
pykrx로 거래대금 5억+ KOSPI/KOSDAQ 유니버스 수집
  ↓
ThreadPoolExecutor(12)로 200일 OHLCV 병렬 페치 (~4분)
  ↓
종목별 일목/볼린저/엔벨로프 + 매수·매도 점수
  ↓
점수 35+ 또는 매도 55+ 종목만 results.json 저장
  ↓
index.html에 데이터 inline 임베드
  ↓
main 브랜치 푸시 → GitHub Pages 자동 배포
```

## 로컬 실행

```powershell
cd "G:\내 드라이브\entry-screener"
pip install -r requirements.txt
python -m src.main
```

## 파일 구조

```
.
├── src/
│   ├── ohlcv_fetcher.py    # pykrx 유니버스 + OHLCV 수집
│   ├── indicators.py        # 일목/볼린저/엔벨로프 계산
│   ├── signals.py           # 매수·매도 타점 점수 + 매매가
│   ├── main.py              # 파이프라인
│   └── template.html        # 빌드 소스 (마커 치환)
├── .github/workflows/scan.yml
├── index.html               # 자동 생성 (데이터 inline)
├── results.json
├── last_update.json
├── requirements.txt
└── README.md
```

## 주의

투자 자문 아님. 모든 매매 판단·책임은 사용자.
