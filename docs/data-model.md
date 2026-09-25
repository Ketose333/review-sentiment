# 확장 데이터 모델 (Draft)

기준: [PRD §26](prd.md)와 [API 계약](api.md). PostgreSQL은 모델 레지스트리와 분석 실행 메타데이터만 저장한다.

## `model_registry`

| 열 | 타입·제약 | 의미 |
| --- | --- | --- |
| `model_id` | `text` PK | `tfidf_lr`, `lstm`, `klue_bert` |
| `display_name` | `text not null` | 화면 표시명 |
| `artifact_repo` | `text not null` | 가중치 저장소 식별자 |
| `artifact_revision` | `text not null` | 배포 자산의 고정 커밋 SHA |
| `artifact_manifest` | `jsonb not null` | 파일 경로별 SHA-256. 모델 바이너리는 저장하지 않음 |
| `enabled` | `boolean not null` | 운영자가 분석 허용 여부를 전환 |
| `metrics` | `jsonb not null` | 사전 계산 `accuracy`, `precision`, `recall`, `f1` |
| `evaluation_scope` | `jsonb not null` | 평가 데이터 원천·분할·표본 수·표본 시드. 모델 간 비교 조건 표시용 |
| `explanation_available` | `boolean not null` | API 설명 지원 여부. A·B단계는 `false` |
| `updated_at` | `timestamptz not null` | 레지스트리 변경 시각 |

초기 행은 저장된 `models/*/metrics.json`과 검증된 자산 해시에서 생성한다. `metrics` 값만으로 동일한 평가 조건을 가정하지 않는다. 현재 KLUE-BERT는 NSMC 테스트 분할의 5천 건 표본, TF-IDF·LSTM은 전체 테스트 분할로 기록한다. 학습 코드와 배포 자산의 정확한 대응을 증명하는 실행 기록은 아직 없으므로, 확인하지 않은 학습 시드나 학습 시각은 채우지 않는다.

## `analysis_runs`

| 열 | 타입·제약 | 의미 |
| --- | --- | --- |
| `analysis_id` | `uuid` PK | 추측하기 어려운 공개 조회 ID |
| `model_id` | `text not null`, `model_registry` FK | 등록된 모델만 실행 기록 생성 |
| `model_version` | `text not null` | 실행 당시 `artifact_revision` 스냅샷 |
| `status` | `text not null`, 허용값 제약 | `RECEIVED`, `RUNNING`, `SUCCEEDED`, `FAILED`, `REJECTED` |
| `label` | `text null` | 성공 시 `긍정` 또는 `부정` |
| `confidence` | `double precision null` | 성공 시 반환 레이블의 확률, 0~1 |
| `explanation_available` | `boolean not null` | 실행 당시 API 설명 지원 여부. A·B단계는 `false` |
| `duration_ms` | `integer null` | 실행 소요 시간, 음수 금지 |
| `error_code` | `text null` | 실패·거절 원인 코드 |
| `request_id` | `uuid not null` | 원문 없이 로그와 연결 |
| `created_at` | `timestamptz not null` | 생성 시각 |
| `completed_at` | `timestamptz null` | 종료 상태 전환 시각 |
| `expires_at` | `timestamptz not null` | `created_at + 24시간` |

성공 상태에서만 `label`·`confidence`가 존재하고 `error_code`는 비어 있어야 한다. 실패·거절 상태에서는 성공 예측값이 없어야 한다. 종료 상태는 `completed_at`이 있어야 하며 다시 변경하지 않는다. 상태 전환은 현재 상태를 조건으로 건 원자적 UPDATE로 수행한다.

원시 리뷰 텍스트, 텍스트 해시, LIME 입력 전문, 설명 단어·기여도는 저장하지 않는다. 설명 단어도 원문의 일부를 드러낼 수 있으므로 D단계의 표시·재조회 요구를 별도로 검토한다.

## 생성·조회·삭제

1. JSON 형식·타입·모델 ID를 확인한다. 이 단계에서 거절한 요청은 실행 행을 만들지 않는다.
2. 등록 모델의 요청은 `RECEIVED` 행을 만든다. 텍스트 검증 실패는 원문 없이 `REJECTED`로 전환하고 422를 반환한다.
3. 유효한 요청은 `RUNNING`으로 전환한 뒤 모델을 로드·추론한다. 저장이 완료된 성공만 `SUCCEEDED`와 201로 반환한다. 모델 미가용·추론 실패는 `FAILED`로 저장한다.
4. `GET /v1/analyses/{analysisId}`는 ID와 `expires_at > now()`를 함께 검사한다. 만료된 행은 삭제 전에도 404다.
5. 하루에 한 번 이상 `expires_at <= now()`인 행을 묶음 삭제한다. 프로세스 중단으로 남은 `RUNNING` 행은 설정된 동기 분석 처리 한계의 2배 이상 경과한 뒤 `FAILED`로 복구한다. 이는 HTTP 연결을 강제 종료하는 한계가 아니며, 복구와 늦은 완료가 겹치면 조건부 상태 전환으로 저장된 실패를 유지한다. 원문이 없으므로 자동 재시도하지 않는다.

기본 인덱스는 두 테이블의 PK와 `analysis_runs(expires_at)`만 둔다. 분석 목록 API가 없으므로 상태·시각 복합 인덱스는 선행 추가하지 않는다.

## 마이그레이션 순서

1. 모델 레지스트리 생성과 ID·평가 범위 제약.
2. 분석 실행 테이블 생성, FK·상태·결과 제약.
3. 만료 삭제 인덱스와 초기 모델 행 등록.

스키마 변경은 번호가 있는 새 마이그레이션으로만 추가하고 적용된 파일은 수정하지 않는다. 마이그레이션 도구와 실제 SQL은 FastAPI 기반 구현 시 결정한다.
