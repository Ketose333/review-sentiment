# 로컬 통합 실행·운영 점검 (2026-09-24)

단계 A~D의 로컬 재현 경로다. 현재 공개 배포 절차가 아니다. 기존 Streamlit 라이브 앱은 계속 유지한다.

## 실행 순서

1. PostgreSQL 17을 로컬에서 실행하고 빈 데이터베이스를 만든다. 테스트에서는 Docker의 `postgres:17`을 `127.0.0.1:55432`에만 연결했다. DB 암호는 환경변수로 전달하고 저장소에 기록하지 않는다.
2. Python 3.10 이상·JDK 17 환경에서 `backend/requirements.txt`를 설치한다. TF-IDF 파일은 `backend/README.md`의 고정 자산 revision에서 받는다. API는 파일별 SHA-256을 확인한 뒤 로드한다.
3. `DATABASE_URL`, `TFIDF_ARTIFACT_DIR`, `CORS_ORIGINS=http://localhost:3000`, `RATE_LIMIT_SALT`(16자 이상)을 설정하고 `python -m alembic -c backend/alembic.ini upgrade head`를 실행한다.
4. 저장소 루트에서 `python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --no-access-log`로 API를 실행한다. 기본 요청 로그에 원문이 들어갈 여지를 막기 위해 접근 로그를 끈다.
5. `frontend/`에서 `npm ci` 후 `NEXT_PUBLIC_API_URL=http://127.0.0.1:8000`을 설정하고 `npm run dev`를 실행한다. 브라우저는 `http://localhost:3000`에서 연다.

실행 명령과 모델 사전 설치 예시는 [백엔드 안내](../backend/README.md), [웹 안내](../frontend/README.md)에 있다. 테스트는 루트 `python -m pytest -q`, 웹 `npm run lint`와 `npm run build`를 각각 실행한다. 실제 PostgreSQL 테스트에는 `TEST_DATABASE_URL`과 `TEST_TFIDF_ARTIFACT_DIR`을 지정한다. 검증 후 웹·API·DB 프로세스와 테스트 브라우저 탭을 종료한다.

## 현재 확인한 결과와 공개 배포 조건

- PostgreSQL과 실제 TF-IDF 파일을 연결한 전체 Python 테스트 156건이 통과했다. 공통 속도 제한은 별도 OS 프로세스를 띄워 예산이 실제로 공유되는지까지 확인한다. 생성·조회·422 입력 거절·모델 비가용·선택적 LIME 및 설명 실패 흐름을 확인했다.
- 웹 테스트 3건, lint·프로덕션 빌드와 데스크톱·모바일 실제 API 브라우저 흐름을 확인했다.
- 분석 실행 메타데이터의 24시간 보존, 원문 미저장, 입력 500 코드 포인트·본문 8,192바이트 제한을 구현·검증했다.
- 다중 프로세스 공통 속도 제한을 구현·검증했다. PostgreSQL의 고정 창 카운터를 모든 프로세스가 공유하므로 워커 수가 예산을 늘리지 않는다. `uvicorn --workers 2`에서 전역 예산을 초과한 요청이 429로 거절되는 것을 확인했다(프로세스별이라면 두 배까지 허용).
- 한 클라이언트의 폭주가 다른 사용자를 막지 못하는 것도 같은 구성에서 확인했다. 클라이언트별 한도 3·전역 6으로 두고 한 주소가 12건을 보냈을 때 그 주소는 3건만 허용되고 전역 카운터에는 허용된 건만 반영되어, 이어진 다른 주소 3개가 모두 정상 응답했다.
- 원문 주소는 저장하지 않고 소금값 HMAC 전체 64자 버킷만 기록한다. 마이그레이션 CHECK 제약이 점 표기 IPv4와 32자 16진수 IPv6를 모두 거부하는 것을 테스트로 고정했다.
- 공개 배포 형태를 [공개 배포 계획](deployment-public.md)으로 확정했다. 프록시 뒤에 둘 때는 `TRUSTED_PROXY_HOPS`를 실측해 설정해야 한다.
- 하드 타임아웃을 구현·검증했다. 전처리·추론·LIME은 별도 워커 프로세스에서 실행하고 기한이 지나면 워커를 종료한다. 기본값은 `ANALYSIS_HARD_TIMEOUT_SECONDS=20`, `ANALYSIS_WORKER_STARTUP_SECONDS=60`, `ANALYSIS_WORKER_SLOTS=2`이며 상세는 [백엔드 안내](../backend/README.md)에 있다. `ANALYSIS_TIMEOUT_SECONDS`는 그보다 큰 소프트 상한으로 남긴다. 하드 타임아웃은 프로세스 단위이므로, 공개 배포 전에 다중 프로세스 공통 속도 제한과 배포 형태는 여전히 결정해야 한다.
- LIME은 세 모델에서 명시적으로 요청한 경우에만 생성한다. API·웹 구현과 예측 성공 후 설명 실패 분리를 로컬에서 검증했다. 기한을 넘긴 실제 LIME이 종료되고 저장된 예측은 `SUCCEEDED`로 남는 것도 실행 중인 API에서 확인했다.
