# 백엔드 단계 B 핸드오프

- 이슈: #10 `feat: TF-IDF 단일 분석 API와 실행 상태 저장`
- 사이클: Critical. 상태 전환·DB 기록·민감 입력 경계가 있어 별도 코드·보안 검수를 수행한다.
- 기준: `docs/prd.md` §14·§26, `docs/api.md`, `docs/data-model.md`, `docs/architecture.md`와 단계 A 구현.
- 시작점: 단계 A의 미커밋 `backend/` 전체를 새 `backend/10-tfidf-analysis` 워크트리에 복사한다. 단계 A 워크트리와 main의 기존 미커밋 변경은 건드리지 않는다.
- 범위: `POST /v1/analyses`, `GET /v1/analyses/{analysisId}`, TF-IDF 기존 모델 추론 재사용, 아티팩트 고정 revision·SHA-256 검증, `RECEIVED → RUNNING → SUCCEEDED/FAILED` 및 `RECEIVED → REJECTED` 원자적 전환, 24시간 만료 조회, 단계 A 회귀 테스트.
- 오류: 형식·타입·미등록 모델은 실행 전 422, 등록 모델의 텍스트 오류는 REJECTED와 422, 비활성·로드 오류는 FAILED와 503, 추론·결과 오류는 FAILED와 500. 저장 실패를 성공으로 반환하지 않는다.
- 필수 제약: 원문·해시·전처리 결과·LIME 내용은 DB·운영 로그·오류 응답·추적에 저장하지 않는다. `analysisId`는 UUID, 요청 ID는 응답 헤더와 오류 본문에서 일치한다. 분석 응답은 `Cache-Control: no-store`다.
- 검증: 성공·입력 거절·모델 미가용·추론 실패·만료 조회를 독립 테스트로 확인한다. 가능하면 실제 PostgreSQL에 마이그레이션을 적용하고 상태 전환·제약을 검증한다. 기존 테스트도 실행한다.
- 제외: LSTM/KLUE-BERT 추론, LIME, Next.js, 외부 배포, Streamlit 제거. 만료 삭제 작업은 계약에 맞게 최소 하루 한 번 실행되는 방식을 이번 단계에서 구현한다.
- 작업 규칙: 커밋·push·PR 생성 금지. reset/clean/pull/rebase 금지. `docs/STATUS.md` 수정 금지. 완료 시 파일 절대 경로·테스트 결과·남은 위험을 보고하고 대기한다.
