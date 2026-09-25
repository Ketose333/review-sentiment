# NSMC 공통 표본 재평가 (2026-09-24)

세 저장 모델을 같은 NSMC 테스트 표본 5,000건과 같은 순서로 평가했다. 결과 원본 메타데이터는 `common_nsmc_5000.json`에 있다. 리뷰 원문과 개별 예측값은 결과 파일에 저장하지 않았다.

| 모델 | Accuracy | Precision | Recall | F1 |
| --- | ---: | ---: | ---: | ---: |
| TF-IDF + LogisticRegression | 0.8282 | 0.8288 | 0.8245 | 0.8266 |
| LSTM | 0.8082 | 0.8512 | 0.7440 | 0.7940 |
| KLUE-BERT | 0.8780 | 0.8539 | 0.9102 | 0.8811 |

## 재현 방법

원본 `e9t/nsmc`의 `ratings_test.txt`를 고정 revision `eafdd77e310f399a4d0083a58ade40b55a5a308d`에서 받는다. 파일 SHA-256은 `8ac9f64052f11dbf6ae0acb5e038f03d90a76f0eda7820cfb3a92d02edfcebda`이다. pandas로 읽고 `dropna(subset=["document"]).reset_index(drop=True)`를 적용하면 49,997건이다. 여기서 `sample(n=5000, random_state=42).reset_index(drop=True)`를 적용했다. 행 ID, 리뷰, 레이블을 순서대로 UTF-8 JSONL 인코딩한 표본 SHA-256은 `277576170352d11980616d54858a15fb9f73741c7598e16bd27f3fff9f36a30b`이다. 입력 내용은 해시 계산에만 사용했다.

```powershell
python scripts/evaluate_common_nsmc.py --all --models-root E:\CAREER\repos\review-sentiment\models --timeout-seconds 1800
```

각 모델은 별도 Python 프로세스에서 기존 `load()` 및 `evaluate()`로 실행했다. 모델 아티팩트의 SHA-256을 고정값과 비교한 뒤 로드한다. 실행 환경 버전과 모델별 소요 시간은 JSON 결과에 있다. Python 3.10.6, Windows, CPU에서 완료했고, KLUE-BERT는 약 203초가 걸렸다.

## 해석 범위

이 표본에서 KLUE-BERT의 Accuracy와 F1이 가장 높다. KLUE-BERT의 0.8780/0.8811은 기존 `metrics.json`과 일치한다. TF-IDF와 LSTM의 과거 지표는 전체 NSMC 테스트 집합 기준이므로 이 표본 지표와 직접 차이를 성능 변화로 해석할 수 없다.

세 모델의 **저장된 가중치**를 비교했으며 재학습, 독립 반복 실험, 신뢰구간 검정은 하지 않았다. KLUE-BERT는 1만 8천 건의 훈련 표본으로 학습됐고 학습 실행 시드 기록이 완전하지 않다. 따라서 이 결과는 이 고정 표본에서의 관측 결과이며 일반적인 우열이나 훈련 재현성을 입증하지 않는다. NSMC 레이블은 영화 평점에서 유도되어 다른 도메인 리뷰의 성능을 보장하지 않는다.
