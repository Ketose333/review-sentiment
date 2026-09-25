# 분석 API — 단계 B·D

FastAPI는 TF-IDF·LSTM·KLUE-BERT의 동기 예측과 선택적 LIME 설명을 제공합니다. 세 모델은 서로 다른 워커 풀에서 로드됩니다. [이관 완료 기준](../docs/migration-parity.md)은 공개 환경에서 세 모델의 예측·설명과 500자 입력을 검증하는 것입니다. PostgreSQL에는 모델 메타데이터와 분석 실행 상태·결과만 저장합니다. 원문과 전처리 결과는 저장하지 않습니다.

## 준비와 실행

저장소 루트에서 Python 3.10 이상과 Java 17을 준비합니다. `JAVA_HOME`이 필요합니다. 모델 가중치는 `Ketose333/review-sentiment-assets`의 고정 revision `915d7784e3c81333d6812913b0a80eda37fdbd41`에서, LSTM·BERT의 JSON 파일은 이 Git 체크아웃에서 설치합니다. 설치 과정은 8개 필수 파일의 SHA-256을 검증해야 합니다. Windows의 BERT JSON 파일은 CRLF를 LF로 정규화한 뒤 Git blob 해시와 대조합니다.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
.\.venv\Scripts\python.exe scripts/install_model_artifacts.py . .artifacts
$env:TFIDF_ARTIFACT_DIR = (Resolve-Path .artifacts/models/tfidf_lr).Path
$env:LSTM_ARTIFACT_DIR = (Resolve-Path .artifacts/models/lstm).Path
$env:KLUE_BERT_ARTIFACT_DIR = (Resolve-Path .artifacts/models/klue_bert).Path
$env:DATABASE_URL = 'postgresql+psycopg://USER:PASSWORD@HOST:PORT/DATABASE'
$env:CORS_ORIGINS = 'http://localhost:3000'
$env:ANALYSIS_TIMEOUT_SECONDS = '120'
$env:ANALYSIS_HARD_TIMEOUT_SECONDS = '20'
$env:TFIDF_LR_EXPLANATION_TIMEOUT_SECONDS = '20'
$env:LSTM_EXPLANATION_TIMEOUT_SECONDS = '45'
$env:KLUE_BERT_EXPLANATION_TIMEOUT_SECONDS = '180'
$env:ANALYSIS_WORKER_STARTUP_SECONDS = '60'
$env:ANALYSIS_WORKER_SLOTS = '2'
$env:ANALYSIS_REQUEST_SLOTS = '4'
$env:ANALYSIS_PER_CLIENT_SLOTS = '1'
$env:RATE_LIMIT_SALT = '<16자 이상 비밀값 — 모든 프로세스 공통>'
$env:TRUSTED_PROXY_HOPS = '0'
.\.venv\Scripts\python.exe -m alembic -c backend/alembic.ini upgrade head
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --no-access-log
```

가중치는 Git 추적 대상이 아닙니다. API는 레지스트리의 고정 저장소·revision과 모델별 필수 파일의 SHA-256을 확인한 뒤에만 로드합니다. 파일이 누락·변조되면 `available=false`이며 분석은 503 `MODEL_UNAVAILABLE`로 기록됩니다. 모델 목록은 파일 검증만 수행하고 역직렬화하지 않습니다. 파일의 장치·inode·크기·수정/변경 시각·권한이 같으면 검증된 해시를 프로세스 메모리에서 재사용하고, 하나라도 바뀌면 다시 계산합니다. Windows에서는 파일 생성 시각인 `st_ctime` 대신 Win32 `ChangeTime`을 사용하며 파일 시스템이 이를 제공하지 않으면 캐시하지 않습니다. 이는 읽기 전용 배포 아티팩트를 전제로 BERT 가중치 442MB를 요청마다 다시 읽지 않기 위한 방식입니다. 분석 시 로드된 모델은 모델별 워커 프로세스 메모리에 캐시합니다. 파일은 읽기 전용 위치에 설치하세요. 해시가 맞아도 런타임 의존성 문제로 로드에 실패하면 분석은 503으로 기록됩니다.

`POST /v1/analyses`는 성공 시 201과 `Location`을 돌려줍니다. 요청 본문은 JSON 파싱 전에 실제 수신 바이트를 세어 8192바이트를 초과하면 실행 행 없이 413으로 거절합니다. 이는 500개 비BMP 문자가 JSON escape로 표현된 경우도 수용합니다. JSON 형식·필드 타입·미등록 모델은 실행 전 422, 등록 모델의 빈 입력·500자 초과·TF-IDF/LSTM 전처리 후 빈 입력은 `REJECTED`와 422입니다. 비활성·로드 실패는 `FAILED`와 503, 추론·결과 검증 실패는 `FAILED`와 500입니다. 저장 실패는 성공으로 응답하지 않습니다. `GET /v1/analyses/{analysisId}`는 생성 후 24시간이 지나면 404입니다.

선택 필드 `includeExplanation: true`는 세 모델 모두 허용합니다. TF-IDF 설명은 300샘플, LSTM·KLUE-BERT는 30샘플이며 최대 8개 특징을 생성합니다. 신경망 30샘플은 현재 CPU 측정치를 바탕으로 한 초기 설정이며 설명 안정성·응답 시간은 공개 환경에서 재측정해야 합니다. 예측 성공은 LIME 실행 전에 `SUCCEEDED`로 저장합니다. 설명은 모델별 별도 기한(TF-IDF 20초, LSTM 45초, KLUE-BERT 180초, 첫 워커 기동 시 추가 60초)으로 실행합니다. KLUE-BERT 30샘플의 로컬 CPU 측정값은 약 62초였고, 장시간 동기 연결을 허용하는 프록시 설정도 공개 환경에서 검증해야 합니다. 설명 중 워커가 종료되거나 실패하면 저장된 예측은 `SUCCEEDED`로 유지하고 생성 응답에 `explanation.status=FAILED`, `errorCode=EXPLANATION_FAILED`를 반환합니다. 단어·가중치·원문은 DB·로그·결과 조회에 저장하거나 재노출하지 않습니다. `durationMs`는 예측 완료까지의 시간이며 설명을 포함한 전체 HTTP 시간은 안전한 요청 로그의 `elapsedMs`로 측정합니다.

동기 분석 요청은 API 프로세스당 최대 `ANALYSIS_REQUEST_SLOTS`건(기본 4), 클라이언트 주소당 최대 `ANALYSIS_PER_CLIENT_SLOTS`건(기본 1)만 처리합니다. 입구에서 빈 슬롯을 50ms 안에 얻지 못하면 실행 행을 만들기 전에 503 `SERVICE_BUSY`, `Retry-After: 1`을 반환합니다. 이 한도는 한 프로세스의 전체 모델 요청에 적용하며 uvicorn 프로세스·인스턴스마다 따로 생깁니다. 다른 클라이언트의 요청과 GET은 남은 API 스레드에서 처리합니다. 설명 워커의 빈 슬롯은 50ms만 기다리고 확보하지 못하면 예측은 이미 저장된 `SUCCEEDED`로 두고 설명만 `FAILED/EXPLANATION_FAILED`로 반환합니다. 실제 프록시와 인스턴스 수에서 동시성·응답 지연을 측정해야 합니다.

## 속도 제한

`GET /healthz`는 속도 제한도 DB 접근도 없는 생존 확인 전용입니다. 준비 확인 요청을 공개 예산에 청구하면 가장 바쁠 때 거절되어 제한기 자체가 재시작을 유발합니다.

`GET /v1/models`, `POST /v1/analyses`, `GET /v1/analyses/{analysisId}`는 두 단계로 제한합니다. 먼저 프로세스 내 제한기가 명백한 폭주를 걸러 공통 카운터와 DB를 보호하고(공통 예산보다 4배 느슨하게 둡니다 — 같은 값으로 맞추면 어느 워커가 처리했는지가 결과를 바꿉니다), 그다음 **PostgreSQL에 저장된 공통 고정 창 카운터**가 전체 예산을 판정합니다. 초과 시 모델 파일 해시·실행 행 생성·분석 결과 조회 전에 429 `RATE_LIMITED`를 반환합니다. 공통 카운터가 프로세스 밖에 있으므로 uvicorn 워커 수나 인스턴스 수를 늘려도 공개 예산은 늘어나지 않습니다. Redis·큐는 도입하지 않습니다.

| 환경변수 | 기본값 | 의미 |
|---|---|---|
| `RATE_LIMIT_SHARED` | `true` | 공통 카운터 사용 여부. `false`는 단일 프로세스 로컬 개발 전용입니다. |
| `RATE_LIMIT_SALT` | (필수) | 주소를 카운터 키로 바꾸는 비밀값. 16자 이상이며 **모든 프로세스가 같은 값**을 써야 합니다. |
| `RATE_LIMIT_PER_IP` | 30 | 창당 클라이언트별 허용 건수(1~10000). |
| `RATE_LIMIT_GLOBAL` | 300 | 창당 전체 허용 건수(1~100000, `RATE_LIMIT_PER_IP` 이상). |
| `RATE_LIMIT_WINDOW_SECONDS` | 60 | 고정 창 길이(1~3600). |
| `TRUSTED_PROXY_HOPS` | 0 | 우리가 통제하는 프록시가 `X-Forwarded-For`에 덧붙이는 항목 수(0~8). |

전역 예산에는 **허용된 요청만** 청구합니다. 자기 한도를 넘긴 요청까지 전역 카운터에 더하면 한 클라이언트가 분당 300건만 보내도 전체 사용자를 429로 막을 수 있어, 공통 카운터가 오히려 서비스 거부 수단이 됩니다. 클라이언트 행을 먼저 증가시키고, 한도 안일 때만 같은 문장에서 전역 행을 증가시킵니다. 클라이언트 버킷은 `global`과 같아질 수 없으므로 모든 트랜잭션이 같은 순서로 잠금을 잡고 교착이 생기지 않습니다.

카운터 테이블 `rate_limit_counters`의 `bucket`은 `global` 또는 `ip:` + 소금값 HMAC-SHA256 **전체 64자**입니다. 주소 원문은 저장하지 않으며, 마이그레이션의 CHECK 제약이 점 표기 IPv4와 32자 16진수 IPv6를 포함한 모든 주소 형식을 거부합니다(32자로 잘랐다면 IPv6 주소가 그대로 통과했습니다). 만료된 창은 창 길이에 맞춘 주기로 삭제합니다 — 시간당 1회로 정리하면 보존 창 수가 실제 보존 기간과 달라집니다.

클라이언트 주소는 버킷을 만들기 전에 정규화합니다. IPv4 매핑 IPv6·대괄호 IPv6·대문자 16진수·`주소:포트` 형태는 한 버킷으로 모으고, 주소가 아닌 값은 신뢰하지 않고 미식별 버킷으로 보냅니다. IPv6는 **/64 단위**로 한 예산을 씁니다. 주소 단위로 두면 가입자 한 명이 2^64개 버킷을 갖게 되어 클라이언트별 한도가 사실상 없어집니다.

`TRUSTED_PROXY_HOPS`가 0이면 `X-Forwarded-For`를 완전히 무시하고 peer 주소로 판정합니다. 값이 1 이상이면 헤더 **여러 줄을 모두 이어붙인 뒤** 오른쪽에서 셉니다. 프록시가 클라이언트가 보낸 헤더를 자기 줄로 남기는 경우, 한 줄만 읽으면 신뢰해야 할 위치가 클라이언트 입력 안으로 들어가기 때문입니다. 값을 너무 크게 잡으면 클라이언트가 보낸 값을 신뢰하게 되고, 너무 작게 잡으면 모든 사용자가 프록시 주소 하나에 묶입니다. 배포 후 실측으로 확인하세요. 프록시 뒤에 두면서 이 값을 설정하지 않으면 **모든 사용자가 프록시 주소 하나를 공유해 한 예산에 묶입니다**. 값을 설정하면 헤더의 오른쪽에서 그만큼 떨어진 항목을 클라이언트로 봅니다. 항목 수가 부족한 요청은 프록시 주소로 대체하지 않고 미식별(`unknown`) 버킷으로 처리합니다.

카운터 경로는 자체 연결 풀과 서버 측 제한(`statement_timeout` 500ms, `lock_timeout` 300ms, 풀 대기 2초)을 씁니다. 모든 공개 요청이 공유 카운터 한 행에서 직렬화되므로, 제한이 없으면 fail closed가 먼저 멈춘 뒤 전체를 거절하는 동작이 되고 엔드포인트가 쓸 연결까지 고갈됩니다. 카운터를 읽을 수 없거나 예상한 계수가 돌아오지 않으면 요청을 통과시키지 않고 503 `REGISTRY_UNAVAILABLE`로 거절합니다(fail closed). 429 응답에는 창이 끝나기까지의 초를 `Retry-After`로 넣습니다. 고정 창이므로 창 경계 직전·직후에 몰린 요청은 최대 두 배까지 허용될 수 있습니다. 더 촘촘한 평탄화가 필요하면 공개 배포 시 edge 제한을 함께 둡니다. 창을 넘긴 초과 요청도 카운터에 기록하므로, 한도를 계속 두드려도 새 여유를 얻지 못합니다.

`ANALYSIS_TIMEOUT_SECONDS` 기본값은 120초입니다. 이는 추론이 반환한 뒤 소요 시간을 확인하는 **소프트 처리 한계**이며, 하드 타임아웃(아래)보다 큰 상한으로 남겨 둡니다. 초과하면 성공을 저장하지 않고 `FAILED/INFERENCE_FAILED`로 종료합니다. 앱 프로세스의 유지 관리 루프는 시작 직후와 이후 매시간 만료 행을 삭제하고, 소프트 한계의 2배 이상 경과한 `RUNNING` 행을 `FAILED`로 복구합니다. 추론이 이 유예시간까지 계속되는 경우 복구와 완료가 경합할 수 있으며, 완료 경로는 저장된 실패를 다시 읽어 실패로 반환합니다. 유지 관리 실패는 원문·예외 전문 없이 고정 이벤트 `analysis_maintenance_failed`로 기록하고 다음 주기에 재시도합니다. 모든 프로세스가 중단된 동안에는 유지 관리도 멈추므로 재시작 시 다시 실행됩니다.

## 하드 타임아웃

전처리(Okt·JVM)·추론·LIME은 API 프로세스가 아니라 **별도 워커 프로세스**에서 실행합니다. Python 스레드에서는 실행 중인 JVM 호출이나 LIME을 안전하게 중단할 수 없으므로, 기한이 지나면 워커 프로세스를 `terminate` 후 필요 시 `kill`로 종료합니다. 종료된 워커는 다음 요청에서 다시 생성됩니다.

| 환경변수 | 기본값 | 의미 |
|---|---|---|
| `ANALYSIS_HARD_TIMEOUT_SECONDS` | 20 | 작업 1건의 실제 기한. 빈 워커 슬롯을 기다리는 시간도 이 예산에 포함됩니다(1~600이며 `ANALYSIS_TIMEOUT_SECONDS` 이하). |
| `ANALYSIS_WORKER_STARTUP_SECONDS` | 60 | 새로 생성된 워커의 **첫 호출에만** 더해지는 기동 여유. 프레임워크 import와 JVM 시작에 필요합니다(15~600). |
| `ANALYSIS_WORKER_SLOTS` | 2 | 프로세스당 동시 실행 워커 수. 워커마다 모델·JVM 사본을 따로 적재합니다(1~8). |

값이 범위를 벗어나거나 하드 기한이 소프트 한계보다 크면 앱이 시작되지 않습니다. 기동 여유 하한 15초는 실측 콜드 스타트(9~11초)보다 커서, 너무 낮은 값으로 워커가 영구히 재생성되는 상태를 막습니다.

슬롯을 얻은 시점에 남은 예산이 최소 배정량(기한의 25%, 최대 1초) 미만이면 작업을 보내지 않고 503 `MODEL_UNAVAILABLE`로 반환합니다. 이는 워커가 멈춘 상태가 아니라 프로세스가 포화된 상태이므로, 예열된 워커를 종료하지 않습니다. 선택 기능인 LIME은 슬롯이 2개 이상일 때 마지막 슬롯을 쓰지 않으므로, 설명 요청이 감성 분석 경로를 굶기지 않습니다(슬롯이 1개면 기존과 같이 공유합니다).

작업별 기한은 각각 따로 적용합니다. 전처리·추론이 기한을 넘기면 실행 행은 각각 `FAILED/MODEL_UNAVAILABLE`(503)과 `FAILED/INFERENCE_FAILED`(500)로 끝나며, 오류 코드 체계는 바뀌지 않습니다. 모든 슬롯이 사용 중이어서 기한 안에 워커를 얻지 못하면 503 `MODEL_UNAVAILABLE`입니다. 예측이 이미 `SUCCEEDED`로 저장된 뒤 LIME이 기한을 넘기거나 슬롯이 없으면 감성 분석 결과는 그대로 유지하고 `explanation.status=FAILED`, `errorCode=EXPLANATION_FAILED`만 반환합니다.

워커에는 레지스트리의 검증 대상 필드(`model_id`, `enabled`, `artifact_repo`, `artifact_revision`, `artifact_manifest`)와 입력 텍스트만 전달하고, 워커는 `ok`·`unavailable`·`failed` 세 가지 결과만 돌려줍니다. 예외 전문은 프로세스 경계를 넘지 않으므로 원문이 부모 프로세스의 로그·응답에 섞일 여지가 없습니다. pickle 역직렬화도 워커에서만 수행합니다. 앱 종료 시 lifespan이 워커를 정리하므로 남는 프로세스가 없습니다.

한 요청은 전처리·추론·설명 세 작업을 순차로 수행합니다. 설명 기한은 예측 기한과 독립적이며, KLUE-BERT 설명의 최악 경로를 포함해 유지 관리 복구 창을 계산합니다. 예측은 설명 전에 `SUCCEEDED`로 저장되므로 설명 실패가 예측 상태를 바꾸지 않습니다.

워커는 `spawn`으로 생성합니다. 즉 워커가 부모의 `__main__`을 다시 import하므로, 직접 작성한 실행 스크립트로 앱을 띄울 때는 `if __name__ == "__main__":` 보호가 필요합니다(`python -m uvicorn`·`python -m pytest`는 해당 없음).

모델별 워커 풀은 무거운 프레임워크를 별도 프로세스에서 로드합니다. TF-IDF와 LSTM은 Okt/JVM을 사용하고 KLUE-BERT는 PyTorch/Transformers를 사용합니다. LSTM·KLUE-BERT의 전체 아티팩트 적재와 500자 입력의 지연 시간·메모리는 공개 배포 환경에서 측정해야 합니다. 워커 풀은 모델마다 `ANALYSIS_WORKER_SLOTS`개까지 생성되며, uvicorn 워커를 늘리면 다시 곱해지므로 메모리 한계를 고려해 설정하세요.

요청 로그는 `backend.api`에 `requestId`, 경로 템플릿, HTTP 상태, 전체 요청 소요시간, 검증된 모델 ID, 오류 코드만 JSON으로 남깁니다. 원문·설명 토큰·LIME 예외 전문은 로깅하지 않습니다. 설명 실패 시에도 로그 오류 코드는 고정된 `EXPLANATION_FAILED`입니다.

테스트는 `python -m pytest backend/tests -q`입니다. 실제 PostgreSQL 통합 테스트는 격리된 DB에 마이그레이션을 적용하고 `TEST_DATABASE_URL`을 지정하면 실행됩니다. 실제 아티팩트 추론 테스트는 `TEST_TFIDF_ARTIFACT_DIR`, `TEST_LSTM_ARTIFACT_DIR`, `TEST_KLUE_BERT_ARTIFACT_DIR`을 각각 지정하면 실행됩니다. 기존 프로젝트 테스트는 `python -m pytest tests -q`로 실행합니다.
