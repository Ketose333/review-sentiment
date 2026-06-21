# review-sentiment PRD

## 0. 문서 메타데이터

| 항목 | 값 |
| --- | --- |
| 상태 | Draft |
| 마지막 업데이트 | 2026-06-18 |
| 목표 릴리즈 또는 마일스톤 | 2026-06-24 (MVP) |

### 변경 이력

| 날짜 | 변경 | 이유 |
| --- | --- | --- |
| 2026-06-18 | 최초 초안 | |
| 2026-06-19 | 트랜스포머 모델을 KLUE-BERT(`klue/bert-base`)로 확정 | SKT KoBERT는 커스텀 토크나이저·버전 호환성 이슈로 구현 리스크가 높고, KLUE-BERT는 표준 경로로 동급 이상 성능(NSMC) 확보 가능 (§2.1 참고) |
| 2026-06-21 | 모델 저장 포맷·로드 경로 명문화 | transformers 5.x `model.safetensors` 기본 포맷 대응 |

## 1. 문서 목적

이 PRD는 review-sentiment 프로젝트의 제품 요구사항과 의사결정 기준을 정의한다.

- **다루는 범위**: NSMC 데이터 기반 감성 분류 모델 개발, Streamlit 데모 앱, 모델 비교 평가, LIME 기반 예측 근거 시각화.
- **다루지 않는 범위**: 실시간 수집 파이프라인, 사용자 계정/인증, 모델 재학습 자동화, 모바일 앱, 장르 레이블 수집(NSMC에 장르 정보 없음).
- **이 문서로 내릴 결정**: 데이터셋 선정, 모델 후보와 평가 기준, MVP 시연 범위, 토크나이저 선택, 모델 해석 도구 선택.

## 2. 프로젝트 개요

NSMC(Naver Sentiment Movie Corpus) 20만 건의 영화 리뷰로 긍/부정 감성 분류 모델을 학습하고, Streamlit 대시보드에서 사용자 입력 리뷰의 감성을 예측하며 LIME으로 예측 근거 단어를 시각화하는 ML 프로젝트다. TF-IDF + LogisticRegression, LSTM, KLUE-BERT 3개 모델을 비교하여 성능 차이를 수치로 보여준다.

| 항목 | 값 |
| --- | --- |
| 스택 | Python 3.10 · scikit-learn · TensorFlow/Keras · Transformers · Streamlit |
| 데이터 | NSMC(Kaggle) — 200,000 reviews, 긍/부정 레이블 |
| 배포 | Streamlit Cloud (share.streamlit.io) |
| 모델 해석 | LIME (LimeTextExplainer) |

### 2.1 후보에서 승계한 결정

| 구분 | 내용 | 근거 |
| --- | --- | --- |
| 유지할 결정 | NSMC 데이터셋 사용 | Kaggle 공개 데이터, 즉시 다운로드 가능 |
| 유지할 결정 | Streamlit Cloud 배포 | 무료, 빠른 프로토타이핑 |
| 유지할 결정 | 3개 모델(TF-IDF/LSTM/KLUE-BERT) 비교 | 다양한 ML 스펙트럼 커버 |
| 다시 검증할 가정 | KLUE-BERT를 로컬에서 학습 가능한가 | Colab 또는 CPU fallback 확인 필요 |

### 2.1.1 트랜스포머 모델 결정 근거 (2026-06-19)

3개 모델 비교의 트랜스포머 슬롯은 **KLUE-BERT(`klue/bert-base`)**로 확정한다. SKT KoBERT(`skt/kobert-base-v1`)는 채택하지 않는다.

| 기준 | SKT KoBERT (`skt/kobert-base-v1`) | KLUE-BERT (`klue/bert-base`, 채택) |
| --- | --- | --- |
| 토크나이저 | 커스텀 `KoBERTTokenizer`(XLNetTokenizer 래퍼), git subdirectory로 별도 설치 필요 | 표준 `AutoTokenizer`로 즉시 로드, 추가 설치 불필요 |
| 버전 호환성 | transformers 버전 업그레이드 시 `position_ids` state_dict 누락, padding token 오설정 등 깨짐 이슈 다수 보고 | 표준 transformers 경로, 동일 이슈 보고 없음 |
| NSMC 정확도 | 약 89.0~89.6% | 동급 이상(개별 평가 약 90%+), PRD §19 목표(0.88) 충족 |
| 재현성 | 런타임 패키지 버전을 완전히 통제할 수 없는 환경에서 깨질 위험 | 표준 경로라 재현성 높음 |

## 3. 프로젝트 목표

### 3.1 문제 정의

- **사용자가 원하는 결과**: 한국어 영화 리뷰 텍스트를 입력하면 긍/부정 감성을 정확히 예측하고, 예측 근거를 이해할 수 있어야 한다.
- **그 결과를 원하는 이유**: 동일한 감성 분류 문제를 고전적 ML → 딥러닝 → 사전학습 언어모델 3단계로 풀어보고 성능·해석가능성 트레이드오프를 비교하기 위해.
- **현재 상태의 한계**: 텍스트 감정 분석 모델, 추천 알고리즘, 모델 평가 및 배포 경험이 필요함.
- **근거 출처 또는 확신 수준**: High — NSMC는 한국어 NLP 벤치마크 데이터로 검증된 데이터셋.

## 4. 목차

문서 메타데이터 · 문서 목적 · 프로젝트 개요 · 프로젝트 목표 · 타깃 사용자 · 대안과 차별점 · 핵심 가치 제안 · MVP 범위 · 사용자 흐름 · 상호작용 인터페이스 요구사항 · 제품 또는 시스템 요구사항 · 인수 조건 · 비기능 요구사항 · 엣지 케이스와 에러 처리 · 아키텍처 개요 · 프로토타입 범위 · 데이터 요구사항 · 개인정보와 보안 요구사항 · 성공 지표 · 우선순위 · 가정과 검증 · 주요 리스크 · 회고 · 열린 질문 · 참고 자료

## 5. 타깃 사용자

### 5.1 주요 사용자

- 포트폴리오 방문자 및 오픈소스 기여자.
- NLP/ML에 관심이 있는 개발자 및 리뷰어.

### 5.2 초기 집중 사용자

- Streamlit 링크로 직접 리뷰를 입력해보는 방문자.

### 5.3 비타깃 사용자

- 실시간 서비스가 필요한 일반 대중. 이 프로젝트는 ML 모델 비교와 시각화에 중점을 둔다.

### 5.4 사용자 문제

- 한국어 텍스트 감성 분류 모델을 엔드투엔드로 구현하고 비교한 경험이 부족하다.
- 모델 예측 결과를 "왜 그렇게 예측했는지" 시각적으로 설명할 방법이 필요하다.

## 6. 대안과 차별점

| 대안 | 한계 | review-sentiment의 차이 |
| --- | --- | --- |
| Kaggle Notebook 제출 | 외부에서 접근 불가, 인터랙션 부족 | Streamlit으로 누구나 리뷰 입력 가능 |
| 단일 모델만 구현 | 모델 선정 근거 부족 | TF-IDF/LSTM/KLUE-BERT 3종 비교 + 성능표 |
| 예측 결과만 출력 | 블랙박스 | LIME으로 근거 단어 하이라이트 |

차별 포인트: **3개 모델 비교 + 예측 근거 시각화**.

## 7. 핵심 가치 제안

한국어 영화 리뷰 한 줄을 입력하면 "이 리뷰는 92% 확률로 긍정입니다"라는 예측과 함께 예측에 가장 큰 영향을 준 단어 5개를 LIME으로 시각적으로 보여준다. TF-IDF → LSTM → KLUE-BERT로 갈수록 성능이 어떻게 달라지는지 한 화면에서 비교할 수 있다.

## 8. MVP 범위

| 포함 범위 | 제외 범위 | 이유 |
| --- | --- | --- |
| NSMC 데이터 전처리 및 EDA | 실시간 크롤링 | 과도한 범위, 데이터 안정성 확보 |
| TF-IDF + LogisticRegression 모델 | 앙상블 모델 | 3종 비교로 충분 |
| LSTM 모델 | Transformer 단독 | KLUE-BERT가 트랜스포머 기반으로 커버 |
| KLUE-BERT 모델 | LoRA/fine-tuning 가속 | 풀 파인튜닝으로 충분 |
| LIME 시각화 | Grad-CAM 등 다른 해석 기법 | LIME 1개로 충분, KLUE-BERT에도 적용 가능 |
| Streamlit 단일 페이지 | 다중 페이지 대시보드 | MVP 단순성 유지 |
| 긍/부정 이진 분류 | 다중 감정 분류(기쁨/슬픔 등) | NSMC는 이진 레이블 |

### 8.1 포함

1. NSMC 데이터 로드 및 전처리 (Okt 형태소 분석, 불용어 제거, 패딩)
2. EDA: 리뷰 길이 분포, 워드클라우드, 레이블 분포
3. TF-IDF + LogisticRegression 학습 및 평가
4. LSTM (Embedding + LSTM + Dense) 학습 및 평가
5. KLUE-BERT fine-tuning 및 평가
6. 모델 성능 비교표 (Accuracy, Precision, Recall, F1)
7. LIME(LimeTextExplainer)을 활용한 예측 근거 단어 시각화
8. Streamlit 앱: 리뷰 입력 → 모델 선택 → 예측 결과 + 근거 단어 출력

### 8.2 제외

1. 사용자 계정/로그인
2. 리뷰 데이터 수집 자동화
3. 모델 재학습/자동 업데이트
4. 다국어 지원
5. 모바일 앱
6. 실시간 추천 시스템
7. 다중 감정 레이블 분류

## 9. 사용자 흐름

```mermaid
flowchart LR
  A[리뷰 텍스트 입력] --> B[전처리]
  B --> C[모델 선택]
  C --> D{TF-IDF / LSTM / KLUE-BERT}
    D --> E[감성 예측]
    E --> F[예측 확률 + 레이블]
    E --> G[LIME 단어 중요도]
  F --> H[결과 대시보드]
  G --> H
  H --> I[모델별 성능 비교표]
```

1. 사용자가 Streamlit 페이지에 접속한다.
2. 텍스트 영역에 영화 리뷰를 입력한다.
3. 분석할 모델(TF-IDF / LSTM / KLUE-BERT / 모두 비교)을 선택한다.
4. 시스템이 입력 텍스트를 전처리하고 선택한 모델로 예측한다.
5. 예측 결과(긍정/부정, 확률)를 출력한다.
6. 예측에 가장 큰 영향을 준 단어 TOP 5~10을 하이라이트하여 표시한다.
7. 하단에 3개 모델의 성능 비교표를 확인할 수 있다.

## 10. 상호작용 인터페이스 요구사항

### 10.1 Streamlit 웹 인터페이스

| 요소 | 설명 |
| --- | --- |
| 리뷰 입력 | `st.text_area` — 1~3문장 영화 리뷰 |
| 모델 선택 | `st.radio` 또는 `st.selectbox` — TF-IDF / LSTM / KLUE-BERT / 모두 |
| 예측 결과 | `st.metric` — 긍정/부정 레이블 + 신뢰도 확률 |
| 근거 단어 | `st.bar_chart` 또는 커스텀 시각화 — 단어별 기여도 |
| 성능 비교표 | `st.dataframe` — 모델별 Accuracy/Precision/Recall/F1 |

## 11. 제품 또는 시스템 요구사항

| 요구사항 ID | 요구사항 | 사용자 이야기 또는 시나리오 | 우선순위 | 비고 |
| --- | --- | --- | --- | --- |
| PR-001 | NSMC 데이터를 로드하고 학습/테스트 세트를 분리한다. | "데이터를 8:2로 나눠 학습한다" | P0 | |
| PR-002 | 한국어 형태소 분석으로 텍스트를 전처리한다. | "OKT 또는 Mecab으로 토크나이징한다" | P0 | |
| PR-003 | TF-IDF + LogisticRegression 모델을 학습하고 저장한다. | "pickle로 모델 저장, Streamlit에서 로드" | P0 | |
| PR-004 | LSTM 모델을 학습하고 `.h5`로 저장한다. | "Embedding → LSTM → Dense 구조" | P0 | |
| PR-005 | KLUE-BERT를 fine-tuning하고 저장한다. | "transformers 라이브러리 활용" | P0 | GPU 필수, Colab 권장 |
| PR-006 | 각 모델의 Accuracy/Precision/Recall/F1을 계산한다. | "classification_report로 출력" | P0 | |
| PR-007 | Streamlit 앱에서 모델을 로드하고 예측을 수행한다. | "pickle/h5/torch로 로드 → predict" | P0 | |
| PR-008 | LIME으로 예측 근거 단어를 시각화한다. | "LimeTextExplainer로 예측에 기여한 단어 TOP 5 표시" | P1 | |
| PR-009 | 3개 모델 성능을 하나의 비교표로 보여준다. | "st.dataframe으로 출력" | P1 | |
| PR-010 | EDA 결과(워드클라우드, 길이 분포 등)를 앱에 포함한다. | "데이터 탐색 결과 시각화" | P2 | |

## 12. 인수 조건

### PR-003: TF-IDF + LogisticRegression

```text
Given NSMC 학습 데이터
When TF-IDF 벡터라이저를 fit하고 LogisticRegression을 학습시킨 후
Then 테스트 Accuracy가 0.80 이상이어야 한다
```

### PR-004: LSTM

```text
Given 전처리된 NSMC 학습 데이터
When Embedding → LSTM → Dense 구조로 학습시킨 후
Then 테스트 Accuracy가 0.85 이상이어야 한다
```

### PR-005: KLUE-BERT

```text
Given NSMC 학습 데이터
When KLUE-BERT를 fine-tuning한 후
Then 테스트 Accuracy가 0.88 이상이어야 한다
```

### PR-007: Streamlit 예측

```text
Given Streamlit 앱이 실행 중인 상태
When 사용자가 "정말 재미있는 영화였어요"를 입력하고 예측 버튼을 누르면
Then "긍정" 레이블과 0.8 이상의 확률이 출력되어야 한다
```

## 13. 비기능 요구사항

| 범주 | 요구사항 | 측정 기준 또는 표준 | 우선순위 |
| --- | --- | --- | --- |
| 성능 | TF-IDF 모델 예측이 1초 이내에 완료되어야 함 | `time` 측정 | P0 |
| 성능 | KLUE-BERT 모델 예측이 5초 이내에 완료되어야 함 | `time` 측정 | P1 |
| 신뢰성 | 동일 입력에 대해 동일 예측 결과를 반환해야 함 | 시드 고정 | P1 |
| 저장 | 모델 파일 크기가 Streamlit Cloud 무료 티어 제한을 초과하지 않아야 함 | GitHub 100MB | P1 |

## 14. 엣지 케이스와 에러 처리

| 상황 | 기대 동작 | 사용자 메시지 또는 복구 방법 | 우선순위 |
| --- | --- | --- | --- |
| 빈 리뷰 입력 | 예측 실행 차단 | "리뷰 텍스트를 입력해주세요." | P0 |
| 너무 짧은 리뷰(1~2글자) | 예측은 수행하나 신뢰도 낮음 표시 | "입력이 짧아 예측 신뢰도가 낮을 수 있습니다." | P1 |
| 모델 파일 로드 실패 | fallback 메시지와 함께 다른 모델 사용 유도 | "KLUE-BERT 모델을 불러올 수 없습니다. TF-IDF 모델을 사용해보세요." | P0 |
| Streamlit Cloud 메모리 부족 | KLUE-BERT 모델 로드 생략 | "KLUE-BERT는 로컬 또는 Colab에서만 지원됩니다." | P1 |
| 특수문자/이모지만 입력 | 전처리 후 빈 텍스트 처리 | "분석 가능한 텍스트가 없습니다. 한글 리뷰를 입력해주세요." | P1 |

## 15. 아키텍처 개요

```mermaid
flowchart TD
  subgraph "학습 환경 (Colab / Local)"
    A1[NSMC CSV 로드] --> A2[데이터 전처리]
    A2 --> A3[TF-IDF + LR 학습]
    A2 --> A4[LSTM 학습]
    A2 --> A5[KLUE-BERT Fine-tuning]
    A3 --> A6[(pickle 저장)]
    A4 --> A7[(h5 저장)]
    A5 --> A8[(pytorch_model.bin)]
  end

  subgraph "Streamlit Cloud"
    B1[리뷰 입력] --> B2[전처리]
    B2 --> B3[모델 선택]
    B3 --> B4{모델 로드}
    B4 --> B5[예측 실행]
    B5 --> B6[결과 출력]
    B5 --> B7[LIME 시각화]
  end

  A6 --> B4
  A7 --> B4
  A8 --> B4
```

## 16. 프로토타입 범위

프로토타입은 다음을 증명해야 한다:

- 서로 다른 복잡도의 모델(TF-IDF → LSTM → KLUE-BERT) 간 성능 차이를 수치로 비교 가능하다.
- 모델 예측 결과를 단어 단위로 해석하여 사용자에게 설명할 수 있다.
- Streamlit Cloud에서 모델 파일을 로드하고 실시간 예측이 동작한다.

프로토타입에서 시도하지 않을 것:

- 사용자 세션 관리, 데이터 영속성, A/B 테스트.

## 17. 데이터 요구사항

### 17.1 NSMC (Naver Sentiment Movie Corpus)

| 항목 | 값 |
| --- | --- |
| 출처 | https://github.com/e9t/nsmc — `ratings_train.txt` / `ratings_test.txt` |
| 크기 | 200,000개 리뷰 (train 150,000 / test 50,000) |
| 포맷 | Tab-separated `.txt` (id / document / label) |
| 레이블 | 0 (부정), 1 (긍정) |
| 라이선스 | CC0 1.0 Universal |
| 확인 | 2026-06-18 접속 확인, raw 파일 정상 응답 |

### 17.2 전처리 결과물

| 항목 | 형식 | 비고 |
| --- | --- | --- |
| TF-IDF 벡터라이저 | `.pkl` | vocab size 10,000 |
| TF-IDF + LR 모델 | `.pkl` | |
| LSTM 토크나이저 | `.pkl` | |
| LSTM 모델 | `.h5` | vocab size 20,000, embedding 100, lstm 128 |
| KLUE-BERT 모델 | `model.safetensors` (442MB, transformers 5.x 기본) | klue/bert-base, CPU 서브셋 fine-tune |

## 18. 개인정보와 보안 요구사항

- NSMC는 공개 데이터셋으로 개인정보를 포함하지 않는다.
- Streamlit 앱에서 입력받는 리뷰 텍스트는 서버에 저장되지 않는다 (세션 휘발).
- 모델 파일은 GitHub LFS 또는 Git Annex로 관리하며, `.gitignore`로 대용량 파일의 일반 커밋을 방지한다.
- API 키, 토큰 등 민감 정보는 `.env` 또는 `st.secrets`로 관리한다.

## 19. 성공 지표

| 지표 | 목표 | 측정 방법 |
| --- | --- | --- |
| KLUE-BERT 테스트 Accuracy | 0.88 이상 | `sklearn.metrics.accuracy_score` |
| TF-IDF vs LSTM vs KLUE-BERT 성능 차이 | 단계적 향상 확인 가능 | 비교표 출력 |
| Streamlit 예측 응답 시간 | 5초 이내 | 실측 |

## 20. 우선순위

### P0

반드시 출시: NSMC 데이터 전처리, TF-IDF + LogisticRegression, Streamlit 기본 앱, 예측 결과 출력, 모델 성능 비교표.

### P1

다음으로 중요: LSTM 모델, KLUE-BERT 모델, LIME 시각화.

### P2

유용한 개선: EDA 시각화 포함, 워드클라우드, 다양한 예시 리뷰 프리셋.

### Future

장기 확장: 다중 감정 분류(7-class), 실시간 리뷰 크롤링, 추천 시스템 연동.

## 21. 가정과 검증

| 가정 | 근거 수준 | 틀렸을 때의 위험 | 검증 계획 |
| --- | --- | --- | --- |
| KLUE-BERT를 Google Colab에서 fine-tuning 가능 | High (표준 transformers 경로) | Colab GPU 메모리 부족 시 CPU fallback 또는 LSTM만 데모 | Colab GPU 확인 후 대체 계획 수립 |
| Streamlit Cloud 무료 티어로 모델 3개 로드 가능 | Medium | 메모리 초과로 KLUE-BERT 로드 실패 가능 | 모델 경량화 또는 조건부 로드 구현 |
| 발표 청중이 모델 비교표를 이해 | High | 표가 너무 복잡하면 전달력 하락 | 시각적 계층 구성으로 가독성 확보 |

## 22. 주요 리스크

| 리스크 | 영향 | 확률 | 대응 |
| --- | --- | --- | --- |
| KLUE-BERT 학습에 GPU 시간 부족 | KLUE-BERT 누락, 2개 모델만 비교 | 중 | CPU 경량 모델 fallback |
| 모델 파일이 GitHub 100MB 초과 | 배포 실패 | 중 | Git LFS 또는 모델 경량화 |
| Streamlit Cloud에서 KLUE-BERT OOM | 모델 3개 동시 로드 불가 | 중 | 조건부 로드: 사용자가 선택한 모델만 HuggingFace Hub에서 로드, `st.cache_resource`로 캐싱 |
| 배포 환경 네트워크 장애 | 시연 불가 | 저 | 로컬 Streamlit fallback |

## 23. 회고

(프로젝트 완료 후 작성)

## 24. 열린 질문

1. KLUE-BERT를 CPU-only 환경에서 어느 정도까지 최적화할 수 있을까? → ONNX 변환 또는 양자화 검토 필요.
2. Streamlit Cloud에서 Hugging Face Hub 모델 다운로드 시간이 수용 가능한가? → 첫 로드 시 1~2분, 이후 `st.cache_resource`로 즉시 제공 예정.

## 25. 참고 자료

- NSMC GitHub 저장소: https://github.com/e9t/nsmc (raw 파일 정상, 2026-06-18 확인)
- KLUE-BERT Hugging Face: https://huggingface.co/klue/bert-base (채택 모델, 표준 `AutoTokenizer` 경로)
- KLUE Benchmark 논문 (Park et al., 2021): https://arxiv.org/abs/2105.09680
- 한국어 PLM 비교 서베이: https://arxiv.org/pdf/2112.03014
- LIME: https://github.com/marcotcr/lime
- konlpy (Okt 토크나이저): https://github.com/konlpy/konlpy
- Streamlit: https://streamlit.io
