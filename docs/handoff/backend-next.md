# 백엔드 단계 A 핸드오프

- 이슈: #9 `feat: FastAPI 분석 API 단계 A 기반 구축`
- 사이클: Normal. API 입력과 저장 경계는 보안 검수를 추가한다.
- 기준: `docs/prd.md` §26, `docs/api.md`, `docs/data-model.md`, `docs/architecture.md`.
- 범위: FastAPI 프로젝트와 의존성, PostgreSQL 모델 레지스트리·분석 실행 테이블 마이그레이션 및 초기 모델 메타데이터, `GET /v1/models`, 입력 검증 구성과 계약 테스트.
- 제외: 실제 추론과 `POST /v1/analyses` 성공 처리(B단계), Next.js, LIME, 기존 Streamlit 제거.
- 필수 제약: 원시 입력·입력 해시·LIME 입력 전문은 DB·로그·오류 응답에 저장하거나 노출하지 않는다. 모든 응답에 요청 ID를 제공한다. 모델 목록은 추론 가중치를 로드하지 않는다.
- 완료 기준: 모델 목록·입력 검증 계약 테스트 통과, 기존 pytest 회귀 통과, 마이그레이션 경로 확인, 변경 파일과 테스트 결과 보고.
- 작업 규칙: 별도 `backend/9-api-foundation` 워크트리에서 구현한다. 커밋·push·PR 생성은 하지 않고 `docs/STATUS.md`도 수정하지 않는다.
