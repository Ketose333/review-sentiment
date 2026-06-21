# review-sentiment

NSMC(Naver Sentiment Movie Corpus) 기반 한국어 영화 리뷰 감성 분석 웹앱. TF-IDF·LSTM·KLUE-BERT 3개 모델을 비교하고, LIME으로 예측 근거 단어를 시각화한다. 머신러닝 수업 과제로 시작한 프로젝트이며, Streamlit Cloud에 배포되어 있다.

[![Live Demo](https://img.shields.io/badge/Live_Demo-Streamlit-FF4B4B?style=flat-square&logo=streamlit&logoColor=white)](https://nsmc-sentiment.streamlit.app)
![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=flat-square&logo=python&logoColor=white)
![scikit--learn](https://img.shields.io/badge/scikit--learn-F7931E?style=flat-square&logo=scikitlearn&logoColor=white)
![PyTorch](https://img.shields.io/badge/PyTorch-EE4C2C?style=flat-square&logo=pytorch&logoColor=white)

## 목차

1. [배경](#배경)
2. [데이터](#데이터)
3. [파이프라인](#파이프라인)
4. [진행 현황](#진행-현황)
5. [모델 비교](#모델-비교)
6. [기능](#기능)
7. [프로젝트 현황](#프로젝트-현황)
8. [디렉터리 구조](#디렉터리-구조)
9. [로컬 환경 셋업](#로컬-환경-셋업)
10. [모델 학습](#모델-학습-이미-학습된-아티팩트가-models에-있으면-건너뛰어도-됨)
11. [앱 실행](#앱-실행)
12. [배포 (Streamlit Cloud)](#배포-streamlit-cloud)

## 배경

영화 리뷰의 평점과 실제 리뷰 텍스트 감성이 항상 일치하지 않는 경우가 많아(예: 평점은 높지만 비판적인 리뷰), 텍스트 자체에서 감성을 직접 분류하는 모델이 필요하다. 이 프로젝트는 머신러닝 수업 과제로 시작했으며, 동일한 한국어 감성 분류 문제를 **고전적 ML(TF-IDF+LogisticRegression) → 딥러닝(LSTM) → 사전학습 언어모델(KLUE-BERT)** 3단계로 풀어보고 성능·해석가능성 트레이드오프를 비교하는 데 목적을 둔다.


## 데이터

| 항목 | 값 |
| --- | --- |
| 데이터셋 | NSMC (Naver Sentiment Movie Corpus) |
| 출처 | [github.com/e9t/nsmc](https://github.com/e9t/nsmc) — `ratings_train.txt` / `ratings_test.txt` |
| 규모 | 200,000개 리뷰 (train 150,000 / test 50,000) |
| 포맷 | Tab-separated `.txt` (`id` / `document` / `label`) |
| 라이선스 | CC0 1.0 Universal |

**종속변수(label) 정의**

| 값 | 의미 | 기준 |
| --- | --- | --- |
| `0` | 부정 | 네이버 영화 평점 1~4점 리뷰 |
| `1` | 긍정 | 네이버 영화 평점 9~10점 리뷰 |

> NSMC는 평점 5~8점(중립권) 리뷰를 원천 제외하고 구성된 데이터셋이라, label은 "평점이 아니라 리뷰 텍스트의 감성 자체"를 학습하도록 설계되어 있다.

## 파이프라인

```
NSMC 원본(.txt)
  └─ src/data/load_nsmc.py        다운로드 + 로드 (data/, gitignore)
       └─ src/preprocessing/      Okt 형태소 분석 + 불용어 제거
            └─ src/models/        모델별 학습 (tfidf_lr / lstm / klue_bert)
                 ├─ models/{model}/         학습된 아티팩트 저장 (Git LFS)
                 ├─ src/evaluation/metrics.py   Accuracy/Precision/Recall/F1 계산
                 └─ src/explainability/lime_explainer.py   예측 근거 단어 추출
                      └─ app.py (Streamlit)  모델 선택 → 예측/비교/EDA 탭 → 배포
```

## 진행 현황

- [x] NSMC 로드·전처리 (Okt 형태소 분석 + 불용어 제거)
- [x] TF-IDF·LSTM·KLUE-BERT 3개 모델 학습·평가
- [x] 모델 성능 비교 (Accuracy/Precision/Recall/F1)
- [x] LIME 예측 근거 단어 시각화
- [x] EDA (레이블/리뷰 길이/빈출 단어 분포)
- [x] Streamlit Cloud 배포
- [ ] LSTM 시드 고정 기준 재검증
- [ ] KLUE-BERT 전체 데이터/GPU 재학습으로 성능 상한 확인

> 상세 항목·비고는 [기능](#기능) 표, 인프라·이슈는 [docs/STATUS.md](docs/STATUS.md) 참고.

## 모델 비교

| 모델 | Accuracy | F1 | 특징 / 채택 이유 |
| --- | --- | --- | --- |
| TF-IDF + LogisticRegression | 0.837 | 0.836 | 가장 가볍고 빠름, LIME 근거가 단어 단위로 가장 직관적 — 해석용 베이스라인 |
| LSTM (Embedding→LSTM→Dense) | 0.842 | 0.842 | TF-IDF와 KLUE-BERT 사이 절충안, CPU로 전체 15만 행 학습(단 train acc 0.904로 약간 과적합) |
| **KLUE-BERT (fine-tuned)** | **0.870** | **0.873** | 3개 중 최고 성능. CPU 제약으로 서브셋(train 1.8만/test 5천, 2 epoch) 학습했음에도 사전학습 언어모델 이점이 뚜렷함 — **최종 채택** |

> 성능 수치는 모두 **로컬/CPU 실측치**. KLUE-BERT는 GPU·풀데이터 환경에서 0.90+ 기대(상세 근거는 보고서·`docs/prd.md` 참고).

## 기능

| 기능 | 상태 | 비고 |
| --- | --- | --- |
| NSMC 로드·전처리 (Okt 형태소 분석 + 불용어 제거) | ✅ | `src/data/load_nsmc.py`, `src/preprocessing/` |
| TF-IDF + LogisticRegression 학습·평가 | ✅ | **Acc 0.837 / F1 0.836** (`models/tfidf_lr/`) |
| LSTM (Embedding→LSTM→Dense) 학습·평가 | ✅ | **Acc 0.842 / F1 0.842**, CPU 전체데이터 15만 행 |
| KLUE-BERT fine-tuning 학습·평가 | ✅ | **Acc 0.870 / F1 0.873**, CPU 서브셋(train 1.8만/test 5천, 2 epoch) |
| 모델 성능 비교 (Accuracy/Precision/Recall/F1) | ✅ | 앱 "모델 성능 비교" 탭, 그룹 막대그래프 + F1 기준 최고 모델 강조 |
| LIME 예측 근거 단어 시각화 | ✅ | `src/explainability/lime_explainer.py`, 예측 탭 막대그래프 |
| EDA (레이블 분포·리뷰 길이 분포·레이블별 빈출 단어 TOP20) | ✅ | 앱 "데이터 탐색(EDA)" 탭, `scripts/compute_eda.py`로 사전계산 → `models/eda/stats.json` |
| 예시 리뷰 프리셋 (긍정/부정/애매/짧은 입력) | ✅ | 예측 탭 셀렉트박스 |
| 모델 선택 메모리 최적화 | ✅ | 모델별 지연 import + `st.cache_resource(max_entries=1)` (무료 티어 OOM 방지) |
| Streamlit Cloud 배포 | ✅ | Python 3.11 고정 필요 (아래 "배포" 참고) |

> 모델별 성능 수치·채택 이유는 [모델 비교](#모델-비교) 참고.

## 프로젝트 현황

→ **[docs/STATUS.md](docs/STATUS.md)** — 인프라 상태, 모델별 학습 완료 여부, 다음 작업, 알려진 이슈를 추적하는 작업 로그.

## 디렉터리 구조

```
app.py                      Streamlit 데모 앱 (entry point)
requirements.txt            의존성 (streamlit, scikit-learn, tensorflow, torch, transformers, konlpy, lime ...)
packages.txt                Streamlit Cloud용 apt 패키지 (default-jdk — konlpy/Okt 구동에 필요)

src/
  data/load_nsmc.py         NSMC 다운로드 + 로드 (최초 실행 시 data/에 캐싱, data/는 gitignore)
  preprocessing/            Okt 형태소 분석 + 불용어 제거 (tokenizer.py, stopwords.py)
  models/                   모델별 train/evaluate/save/load + 추론 래퍼
    base.py                 모델 공통 인터페이스(Protocol)
    tfidf_lr.py / lstm.py / klue_bert.py
  explainability/           LIME 예측 근거 시각화
  evaluation/metrics.py     정확도/정밀도/재현율/F1 계산 + 모델 비교 표

scripts/                    학습 CLI 진입점 (python scripts/train_xxx.py)
  train_tfidf_lr.py / train_lstm.py / train_klue_bert.py
  compute_eda.py            EDA 통계 사전계산 → models/eda/stats.json (Okt 우선, 미가용 시 경량 토크나이저 폴백)
models/                     학습된 아티팩트 (Git LFS로 .pkl/.h5/.safetensors 추적, .gitattributes 참고)
  tfidf_lr/ / lstm/ / klue_bert/
  eda/stats.json            EDA 사전계산 통계 (앱 "데이터 탐색" 탭이 로드)
runtime.txt                 Streamlit Cloud용 Python 버전 힌트 (3.11)
tests/                      pytest 단위 테스트

docs/
  STATUS.md                 인프라/진행상황/다음작업 작업 로그
  prd.md                    제품 요구사항 (데이터셋/모델/배포/제출 경로 결정 기준)
```

## 로컬 환경 셋업

```bash
git clone https://github.com/Ketose333/review-sentiment.git && cd review-sentiment
pip install -r requirements.txt   # tensorflow/torch/transformers 포함, 용량 큼(수 GB)
```

**konlpy(Okt) 의존성**: JVM 필요. 로컬은 JDK 설치 + `JAVA_HOME` 설정 필요. Streamlit Cloud는 `packages.txt`(`default-jdk`)로 자동 설치됨.

## 모델 학습 (이미 학습된 아티팩트가 models/에 있으면 건너뛰어도 됨)

```bash
python scripts/train_tfidf_lr.py    # 완료됨 — models/tfidf_lr/
python scripts/train_lstm.py        # 완료됨 — models/lstm/ (Acc 0.8417, CPU 전체데이터)
python scripts/train_klue_bert.py   # 완료됨 — models/klue_bert/ (Acc 0.87 / F1 0.8733, CPU 서브셋)
python scripts/compute_eda.py       # EDA 통계 생성 → models/eda/stats.json (앱 "데이터 탐색" 탭이 로드)
```

`compute_eda.py`는 단어 빈도 집계에 Okt를 쓴다(`stats.json`의 `word_tokenizer` 필드에 실제 사용 토크나이저 기록 — 현재 `"okt"`). `tokenizer.py`가 Windows에서 `JAVA_HOME`의 JVM DLL 경로를 자동 등록하므로 단발성 실행에서도 Okt가 동작한다. JVM/konlpy를 못 띄우는 환경에서는 경량 토크나이저로 자동 폴백해 어떤 머신에서도 완전한 `stats.json`을 생성한다.

각 스크립트는 첫 실행 시 NSMC를 `data/`에 자동 다운로드한다(.gitignore 처리됨, 매번 다시 받을 필요 없음).

## 앱 실행

```bash
streamlit run app.py
```

사이드바에서 모델 선택(TF-IDF+LR / LSTM / KLUE-BERT) → "🔍 예측" 탭에서 리뷰 입력 → 예측 결과 + LIME 단어별 기여도 시각화. "📊 모델 성능 비교" 탭에서 학습된 모델들의 정확도/F1 비교.

## 배포 (Streamlit Cloud)

1. 레포를 GitHub에 push (모델 아티팩트는 Git LFS로 추적됨, `.gitattributes` 참고)
2. [share.streamlit.io](https://share.streamlit.io)에서 레포 연결, entry point = `app.py`
3. `packages.txt`로 JDK 자동 설치됨
4. **⚠️ Python 버전 고정 필수**: Streamlit Cloud는 기본적으로 최신 Python(예: 3.14)을 띄우는데, `tensorflow`는 해당 버전용 wheel이 아직 없어 `pip install`이 통째로 실패한다(`No matching distribution found for tensorflow`). 앱 대시보드 **⋮ → Settings → Python version**에서 **3.11**을 선택할 것. (`runtime.txt`도 3.11로 두지만, 확실한 적용은 대시보드 설정이다.)
5. 로컬 Streamlit fallback이 필요하면 `streamlit run app.py`로 실행한다.
