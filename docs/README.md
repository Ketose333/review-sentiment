# review-sentiment 문서 인덱스

## 문서 목록

| 문서 | 상태 | 역할 |
| --- | --- | --- |
| `STATUS.md` | 항상 최신 | 인프라/진행상황/다음작업/알려진 이슈 — 작업 시작 전 먼저 읽을 것 |
| `prd.md` | MVP·확장 구현 완료, 운영 검증 중 | 제품 요구사항과 의사결정 기준선. §26은 배포된 API·저장·웹 확장 범위다. |
| `api.md` | 구현·공개 배포 계약 | §26 확장의 HTTP 요청·응답·오류 계약. 장기 운영 안정성 검증은 남았다. |
| `data-model.md` | 구현됨 | 모델 레지스트리·분석 실행 메타데이터·24시간 만료 정책 |
| `architecture.md` | 구현됨 | 기존 Streamlit과 FastAPI·PostgreSQL·Next.js의 경계 |
| `migration-parity.md` | 확정된 완료 기준 | 세 모델 예측·설명, 500자 입력, 공개 배포 검증과 Streamlit 종료 조건 |
| `model-audit.md` | 검토 기록 | 재학습 필요성·평가 범위·모델 출처 확인 |
| `lime-measurement.md` | 측정 기록 | D단계 LIME 지연 시간·지원 범위·개인정보 경계 |
| `deployment-local.md` | 실행 기록 | A~D 로컬 통합 재현 순서와 공개 배포 전 조건 |
| `deployment-public.md` | 공개 배포 기록 | 공개 웹·API·DB 구성과 비용 위험, Streamlit 이관 단계 |
| `../reports/README.md` | 재평가 결과 | 세 저장 모델의 동일 NSMC 5,000건 표본 평가와 재현 조건 |

## 해당 없음

- `backend.md`: **현재 구현에는 해당 없음**. FastAPI 구현 시 실제 모듈·운영 절차를 문서화한다.
