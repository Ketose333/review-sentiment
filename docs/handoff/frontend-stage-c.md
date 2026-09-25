# 프론트엔드 단계 C 핸드오프

- 이슈: #11 `feat: Next.js 감성 분석 웹 클라이언트 분리`
- 사이클: Normal. 기존 Streamlit 유지와 입력 개인정보 경계를 별도 검수한다.
- 기준: `docs/prd.md` §26, `docs/api.md`, `docs/architecture.md`, 단계 B 구현 `E:/CAREER/repos/review-sentiment-backend-10-tfidf-analysis/backend/`.
- 작업 트리: 새 `frontend/11-next-client` 워크트리에서만 `frontend/`를 구현한다. main과 단계 A/B의 미커밋 변경을 보존한다. API 계약·모델 성능 수치는 main의 최신 문서를 읽고, 데이터는 실행 시 API에서 가져온다.
- 시각 기준: 데스크톱 `C:/Users/user/.codex/generated_images/01a0ce45-2919-7030-9beb-cde35f00f973/exec-b5a5bccb-6f04-497e-bf4b-6c46903b04ce.png`, 모바일 `C:/Users/user/.codex/generated_images/01a0ce45-2919-7030-9beb-cde35f00f973/exec-a03a9462-8409-4c4d-bcba-d21520804440.png`. 두 이미지는 레이아웃·색·간격 시안이다. 시안의 예시 결과·ID·버전·모바일의 전체 테스트 건수는 실제 데이터가 아니므로 UI에 고정하지 않는다.
- 디자인 토큰: 흰 배경, 진한 남색 본문, 절제된 청록색 행동 버튼·결과 강조, 연한 청회색 구분선, 넉넉한 여백. 데스크톱은 입력/결과 2열과 하단 성능 표, 모바일은 입력→결과→성능 순서의 세로 흐름. 과장된 히어로·순위·우승 표시를 만들지 않는다.
- 기능: `GET /v1/models`로 모델 ID·가용성·성능·평가 범위를 표시한다. 사용 가능한 한 모델만 선택해 최대 200 Unicode 코드 포인트의 리뷰를 `POST /v1/analyses`로 보낸다. 201 성공과 422/413/429/503/500 오류를 구별하고 요청 ID를 사용자에게 보여 준다. 결과에는 레이블·확률·분석 ID·모델 버전·24시간 보존 안내를 표시한다. 필요하면 분석 ID의 `GET /v1/analyses/{analysisId}` 재조회 흐름을 구현한다.
- 모델 비교: 기존 accuracy/F1을 API 값으로 표시하되 평가 데이터 범위(전체/5천 건 표본)를 함께 표기한다. 공통 테스트 집합 재평가 전에는 최고 모델·우열·정확한 순위를 주장하지 않는다.
- 개인정보: 원시 리뷰는 서버 저장·브라우저 localStorage/sessionStorage·URL·로그·분석 도구에 남기지 않는다. `fetch`는 `cache: 'no-store'`; 오류 텍스트에는 입력 원문을 포함하지 않는다. HTML 텍스트는 React 기본 이스케이프를 사용한다.
- 기술: Next.js 16 App Router, TypeScript, Tailwind 4. API 경로는 중앙 관리하고 `NEXT_PUBLIC_API_URL`을 사용한다. production build에서 URL 미설정이면 실패한다. 인증은 초기 범위 밖이며 불필요한 로컬 스토리지 키를 만들지 않는다.
- 검증: `npm run build`와 `npm run lint` 통과, 브라우저에서 데스크톱·모바일 렌더 및 폼/성공/오류/비가용 모델 동작을 확인한다. 테스트 후 개발 서버·브라우저 탭을 종료한다. 기존 Streamlit `app.py`는 유지한다.
- 작업 규칙: 커밋·push·PR 금지. reset/clean/pull/rebase 금지. `docs/STATUS.md` 수정 금지. 변경 파일 절대 경로·빌드·브라우저 검증·잔여 위험을 보고한다.
