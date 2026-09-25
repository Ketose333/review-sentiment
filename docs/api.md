# 감성 분석 API 계약

기준: [PRD §26](prd.md#26-확장-마일스톤--분석-api와-검토-웹-분리-draft). 단계 A~D의 구현·공개 배포에 쓰는 HTTP 요청·응답 계약이다. 기능 동등성과 운영 종료 조건은 [이관 완료 기준](migration-parity.md)을 따른다.

## 공통 규칙

- 기본 경로는 `/v1`이다. JSON 필드는 `camelCase`, 시각은 UTC ISO 8601, 분석 ID는 UUID 문자열이다.
- 초기 버전은 인증 없는 공개 데모이며, 분석 목록 API는 제공하지 않는다. 조회는 분석 ID를 아는 요청에만 허용한다.
- 분석 결과는 생성 시각부터 24시간 보존한다. 만료 즉시 조회는 404이고, 만료 레코드는 최소 하루 한 번 삭제한다.
- 요청의 `text`는 원문 Unicode 코드 포인트 수 기준 1~500자다. 공백만 있는 입력과 500자 초과 입력은 422로 거절하며, 서버가 입력을 자르지 않는다. TF-IDF·LSTM 전처리 후 토큰이 남지 않는 입력도 422로 거절한다. 모델 내부의 LSTM 40토큰·KLUE-BERT 64토큰 제한은 별개다.
- 원시 `text`와 LIME 입력 전문은 DB·운영 로그·오류 추적에 남기지 않는다. 응답에도 입력 원문을 되돌려주지 않는다.
- `confidence`는 반환된 `label`에 대한 모델 확률이다. 분류 레이블은 `긍정` 또는 `부정`이다. 모델의 사전 계산 성능과 요청별 예측 확률을 구분해 표시한다.
- 모든 응답은 `X-Request-Id` 헤더를 포함한다. 오류 응답은 동일한 값을 `error.requestId`에도 담는다.
- 호환 가능한 선택 필드 추가는 `v1` 안에서 처리한다. 필수 필드 변경, 타입 변경, 경로 변경은 새 버전에서 처리한다.

## 모델 목록

`GET /v1/models` → 200

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `models` | 배열 | `tfidf_lr`, `lstm`, `klue_bert` 순서의 모델 정보 |
| `models[].modelId` | 문자열 | 요청에 사용하는 고정 식별자 |
| `models[].displayName` | 문자열 | 화면 표시명 |
| `models[].version` | 문자열 | 배포된 모델 아티팩트의 버전 또는 해시 |
| `models[].available` | 불리언 | 현재 분석 요청을 받을 수 있는지 여부 |
| `models[].metrics` | 객체 | `accuracy`, `precision`, `recall`, `f1`; 각 값은 0~1 |
| `models[].evaluation` | 객체 | `dataset`, `testSet`, `testCount`, `sampleSeed`. 정확한 평가 건수가 확인되지 않은 경우 `testCount`는 `null`, 전체 테스트 사용 시 `sampleSeed`는 `null` |
| `models[].explanationAvailable` | 불리언 | 해당 모델의 API 설명 지원 여부 |

레지스트리를 읽을 수 없으면 503 `REGISTRY_UNAVAILABLE`을 반환한다. 속도 제한을 넘으면 DB·모델 파일 조회 전에 429 `RATE_LIMITED`를 반환하며, 창이 끝나기까지의 초를 `Retry-After` 헤더로 함께 보낸다. `GET /healthz`는 속도 제한과 DB 접근이 없는 생존 확인 전용 경로이며 `{"status": "ok"}`를 반환한다. 세 모델의 `explanationAvailable`은 설명 구현과 아티팩트가 사용 가능할 때 `true`다. 현재 KLUE-BERT 지표는 5천 건 표본 평가이므로 클라이언트는 평가 범위를 함께 표시한다.

## 분석 생성

`POST /v1/analyses` — `Content-Type: application/json`

```json
{"text":"정말 재미있는 영화였어요","modelId":"tfidf_lr"}
```

기본 요청은 위 두 필드만 보낸다. `modelId`는 모델 목록의 고정 식별자 중 하나여야 한다. 입력 원문 길이를 먼저 검증하고, 공백을 제거한 결과가 비어 있는지도 검증한다. 길이 초과를 조용히 자르지 않는다. 선택적 `includeExplanation` 필드는 아래에서 정의한다.

성공 시 201과 `Location: /v1/analyses/{analysisId}`를 반환한다.

```json
{
  "analysisId":"550e8400-e29b-41d4-a716-446655440000",
  "status":"SUCCEEDED",
  "modelId":"tfidf_lr",
  "modelVersion":"artifact-version",
  "label":"긍정",
  "confidence":0.92,
  "durationMs":42,
  "explanationAvailable":false,
  "createdAt":"2026-09-23T00:00:00Z",
  "completedAt":"2026-09-23T00:00:00Z",
  "expiresAt":"2026-09-24T00:00:00Z"
}
```

`modelVersion`은 실제 배포 아티팩트 값으로 채운다. `durationMs`는 예측 완료까지의 소요 시간이며, 선택적 LIME 설명 시간은 포함하지 않는다. 설명을 포함한 전체 HTTP 처리 시간은 안전한 구조화 로그의 `elapsedMs`로 측정한다. 예시의 확률·시간·버전은 계약 형식 설명용이다. LIME 설명은 D단계 확장 계약에 따른다.

### 거절·실패

| 상황 | HTTP | 오류 코드 | 실행 기록 |
| --- | --- | --- | --- |
| JSON 형식 또는 필드 타입 오류 | 422 | `INVALID_REQUEST` | 생성하지 않음 |
| JSON 본문 8,192바이트 초과 | 413 | `PAYLOAD_TOO_LARGE` | 생성하지 않음 |
| 알 수 없는 `modelId` | 422 | `UNSUPPORTED_MODEL` | 생성하지 않음 |
| 빈 입력·공백 입력·500자 초과·TF-IDF 또는 LSTM 전처리 후 빈 입력 | 422 | `INVALID_TEXT` | `RECEIVED → REJECTED` 기록 |
| 등록 모델의 비활성·로드 실패 | 503 | `MODEL_UNAVAILABLE` | `RECEIVED → RUNNING → FAILED` 기록 |
| 추론·결과 검증 실패 | 500 | `INFERENCE_FAILED` | `RECEIVED → RUNNING → FAILED` 기록 |
| 분석 요청 속도 초과 | 429 | `RATE_LIMITED` | 생성하지 않음 |
| 동시 분석 처리 슬롯 초과 | 503 | `SERVICE_BUSY` | 생성하지 않음 |

오류 형식은 다음과 같다. 실행 기록이 생성된 경우에만 최상위 `analysisId`를 포함한다. `requestId`는 모든 응답과 구조화 로그를 연결하며 요청 원문을 포함하지 않는다.

```json
{
  "analysisId":"550e8400-e29b-41d4-a716-446655440000",
  "error":{
    "code":"INVALID_TEXT",
    "message":"입력 텍스트를 확인해 주세요.",
    "requestId":"9f3d9f55-11ef-40d7-a7f6-9cb857813a5e"
  }
}
```

내부 예외·모델 파일 경로·요청 원문은 오류 메시지나 추적 이벤트에 넣지 않는다.

`GET /v1/models`, `GET /v1/analyses/{analysisId}`, `POST /v1/analyses`는 PostgreSQL 공유 속도 제한을 사용한다. 기본 한도는 클라이언트 IP당 분당 30건, 전체 분당 300건이다. 한도를 넘으면 DB 조회·파일 검사·실행 기록 생성 전에 429 `RATE_LIMITED`를 반환한다. POST 동시 처리는 API 프로세스당 4건, 클라이언트 주소당 1건으로 제한하며 50ms 안에 입장하지 못하면 503 `SERVICE_BUSY`와 `Retry-After: 1`을 반환한다.

**공개 배포의 동시성 계약(2026-09-26 확정):** 공개 Modal 배포는 컨테이너 한 개(`max_containers=1`)에 입력을 한 건씩만 전달한다. 따라서 공개 API는 동시 요청을 거절하지 않고 대기열에서 차례로 처리한다. 앞선 요청이 끝날 때까지 뒤 요청은 대기하며, 세 모델 500자 설명 요청 한 건은 운영 설정(8GiB)에서 약 6~18초 걸린다([측정 기록](deployment-public.md)). `GET` 요청도 같은 대기열을 쓴다. 공개 환경에서 `503 SERVICE_BUSY`는 정상 흐름에서 기대하지 않는다. 위 앱 입장 제한과 웹의 `SERVICE_BUSY` 안내는 로컬·다중 워커 배포를 위한 방어로 유지한다. 방문이 많아져 대기가 문제되면 Modal 입력 동시성과 컨테이너 수를 조정하되, 월 무료 크레딧 소모와 함께 다시 측정한다.

## 분석 결과 조회

`GET /v1/analyses/{analysisId}` → 200

성공한 실행은 분석 생성의 기본 성공 응답과 같은 필드를 반환한다. D단계의 일회성 LIME 설명은 조회 응답에 포함하지 않는다. `FAILED` 또는 `REJECTED` 실행은 `analysisId`, `status`, `modelId`, `modelVersion`, `errorCode`, `createdAt`, `completedAt`, `expiresAt`을 반환하고 성공 예측값은 포함하지 않는다. UUID 형식 오류, 없는 ID, 만료된 ID는 모두 404 `ANALYSIS_NOT_FOUND`로 응답한다.

분석 생성·조회 응답은 `Cache-Control: no-store`를 사용한다.

동기 HTTP 처리이므로 초기 버전에서는 `RECEIVED`와 `RUNNING`을 정상 조회 결과로 기대하지 않는다. 워커·큐·폴링 API는 지연 시간과 동시성 측정 이후에 검토한다.

## D단계 선택적 LIME 확장 계약

`POST /v1/analyses`는 선택적 불리언 `includeExplanation`을 받는다. 생략하거나 `false`이면 기존 응답과 처리 경로를 유지한다. `true`는 TF-IDF(`tfidf_lr`), LSTM(`lstm`), KLUE-BERT(`klue_bert`)에 허용하며, 설명 기능이 비활성인 모델에 요청하면 실행 기록을 만들기 전에 422 `EXPLANATION_UNSUPPORTED`를 반환한다. 해당 모델의 설명 기능을 사용할 수 있으면 `explanationAvailable`을 `true`로 반환한다.

설명을 요청해 예측이 성공하면 생성 응답에만 아래 객체를 추가한다. `features[].weight`는 **긍정 방향** 기여도이며 음수는 부정 방향 기여도다. LIME은 TF-IDF 300개, LSTM·KLUE-BERT 각각 30개 샘플과 최대 8개 특징을 사용한다. 사용자가 제출한 원문은 기본 응답과 마찬가지로 되돌려주지 않는다.

```json
{
  "explanation": {
    "status": "SUCCEEDED",
    "method": "LIME",
    "direction": "POSITIVE",
    "sampleCount": 300,
    "features": [{"token": "재미", "weight": 0.21}]
  }
}
```

설명 생성만 실패하면 감성 분석은 `SUCCEEDED`로 유지하고 201 응답의 `explanation`을 `{ "status": "FAILED", "method": "LIME", "errorCode": "EXPLANATION_FAILED" }`로 표시한다. 내부 예외 전문·입력·부분 설명은 보내지 않는다. 설명은 DB, 운영 로그, 오류 추적, `GET /v1/analyses/{analysisId}`에 저장하거나 포함하지 않는다. 짧은 리뷰의 경우 설명 토큰만으로 입력을 추정할 수 있으므로 생성 응답은 `Cache-Control: no-store`를 유지한다. 설명은 별도 워커 프로세스에서 실행하고 하드 타임아웃으로 강제 종료한다. 기한을 넘기면 설명만 실패하며 감성 분석 결과와 오류 코드 체계는 바뀌지 않는다.
