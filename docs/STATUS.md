# review-sentiment STATUS

마지막 갱신: 2026-09-26

> 완료된 기능의 전체 목록은 루트 [README.md](../README.md) "기능"을 정본으로 본다. 이 파일은 인프라 상태와 알려진 이슈를 추적한다.

## 인프라

| 항목 | 상태 |
| --- | --- |
| 모델 아티팩트 관리 | Hugging Face Hub 자산 저장소에서 런타임 로드 |
| Streamlit 초기 배포 | 2026-09-25 사용자가 삭제. 같은 날 공개 주소가 존재하지 않는 앱과 동일한 인증 리다이렉트로 응답함을 확인. 이를 깨우던 keep-alive workflow·전용 스크립트·자동 검증도 제거함 (이슈 #17). 현재 정식 진입 주소는 [Next.js 웹](https://review-sentiment-web.vercel.app) |
| Streamlit 초기 앱 재현 | 과거 배포 설정은 Python 3.11과 `packages.txt` JDK에 의존. 현재 Next.js/FastAPI 공개 서비스를 재현하는 설정이 아님 |
| Java/JVM (Okt) | 로컬 JDK 17. `packages.txt` 자동 설치는 과거 Streamlit 배포 전용 |
| 확장 스택 배포 형태 | ✅ 공개 배포됨 — [Next.js 웹](https://review-sentiment-web.vercel.app), [FastAPI 상태](https://ketose333--review-sentiment-api-api.ap-south.modal.run/healthz), Neon PostgreSQL Free. Vercel 프로젝트 `review-sentiment-web`, Vercel Hobby·Modal Starter·Neon Free 사용, PC와 무관하게 호스팅. Modal은 유휴 시 0개 컨테이너로 절전하고 첫 요청에 콜드 스타트가 있음. 웹은 정식 주소 하나만 연결하고 이전 Vercel 별칭과 API CORS 허용을 제거함. 2026-09-26 공개 운영 측정과 동시성 계약 확정으로 이관 완료 판정(이슈 #23). 월 크레딧 소진 위험은 알려진 이슈 참고. 비용·실측은 [공개 배포 기록](deployment-public.md) |
| 프론트 재현 배포 | PR #16 머지 후 Vercel 기존 프로젝트에 배포 `dpl_HSP7QbCZesudNh6MCPQZLkWkJLXG` 완료. Node 22.x, npm 10, `npm ci`, Production `NEXT_PUBLIC_API_URL`, 고정 Vercel CLI와 대상 확인 절차를 적용. 공개 세 화면 200 및 브라우저 모델 목록 확인. 세 모델 분석·LIME과 장기 무료 한도는 이번 배포에서 재측정하지 않음 |
| 확장 스택 비용 한도 | 결제 수단 없음. Modal Starter는 결제 수단 없이 월 $30 중 $1만 사용 가능(매월 1일 초기화). 2026-09-26 대시보드 잔여 $0.87, 이번 주기 사용 $0.13~0.14, 청구액 $0. 크레딧 소진 뒤 자동 유료 전환 없이 요청이 중단될 수 있음. Vercel Hobby와 Neon Free 사용량 한도도 적용됨. 유료 전환·결제 수단 추가 금지 |
| 확장 스택 속도 제한 | PostgreSQL 공통 고정 창 카운터(`rate_limit_counters`). 전역 예산은 허용된 요청만 청구(한 IP가 전체를 막지 못함), 원문 주소 미저장(소금값 HMAC 64자 + CHECK 제약), 전용 연결 풀과 트랜잭션 범위 서버 측 타임아웃, 카운터 장애 시 fail closed |

## 알려진 이슈

| 이슈 | 영향 | 대응 |
| --- | --- | --- |
| Windows에서 `pytest`·앱 첫 Okt 로드 시 faulthandler `access violation` 출력 | JVM 시작 시 JPype가 처리하는 시그널을 pytest faulthandler가 가로채 찍는 것. 테스트·앱·배포 동작에는 영향 없음 | Windows+JPype 특유의 무해한 현상, 무시 |
| `LimeTextExplainer`가 `random_state` 미고정 | 같은 모델·같은 텍스트라도 단어별 기여도 수치가 실행마다 소폭 다름(부호·순위는 안정적) | 버그 아님, LIME 고유 특성. `random_state` 고정은 개선 항목으로 남김 |
| (해결됨) self-contained 통합 직후 배포가 JVM SIGSEGV로 Aborted | `tensorflow`/`torch`/`transformers`를 모듈 최상단에서 즉시 import하면 Okt가 띄운 JVM과 PyTorch 네이티브 라이브러리가 같은 프로세스에 동시 적재되며 충돌 | 모델별 무거운 프레임워크 import는 각 로더 함수 안에서 지연 import로 유지 |
| Modal 월 무료 크레딧 소진 | 결제 수단 없이 월 $1만 사용 가능. 추정 월 약 85~250회 방문 뒤 다음 달 1일까지 API가 멈출 수 있음 | 월초·방문 증가 시 Modal Usage 확인. 유료 전환·결제 수단 추가 금지. 필요 시 방문 안내 또는 비용 구조 재검토 |
| NSMC 데이터 재배포 조건 | 원본 저장소에 라이선스 본문이 없고 Hugging Face 복제본 메타데이터와 기존 문서 표기가 달랐음 | CC0 단정을 제거함. 원제공자의 조건 확인 전 원문 데이터 재배포 금지 (`docs/model-audit.md`) |

## 다음 작업

- [x] **확장 초기 결정**: 결과 보존 24시간·로컬 구현 입력 상한 200자. 이관 완료 목표는 500자로 변경됨
- [x] **확장 단계 A 설계 초안**: `docs/api.md`·`docs/data-model.md`·`docs/architecture.md` 작성
- [x] **확장 단계 A·B 구현**: FastAPI 골격·PostgreSQL 마이그레이션·단건 분석을 로컬·Neon에서 검증하고 공개 API로 배포. `78132a3`에 구현 기록
- [x] **모델 공통 표본 평가**: 세 모델을 동일한 NSMC 테스트 5,000건에서 재평가하고 데이터·아티팩트 해시와 평가 조건을 기록 (`reports/README.md`)
- [x] **확장 단계 C 구현**: Next.js 웹 클라이언트 빌드·lint·실제 API 연결·데스크톱/모바일 브라우저 검증 완료. Vercel 프로덕션 배포. 기존 Streamlit 앱은 legacy로 유지. `f8bab82`에 구현 기록
- [x] **확장 단계 D 계약·측정**: TF-IDF 요청 시 LIME 생성만 지원하기로 결정하고 일회성 응답·원문 미저장 계약과 모델별 CPU 측정 기록 (`docs/lime-measurement.md`, 이슈 #13)
- [x] **확장 단계 D 구현**: TF-IDF·LSTM·KLUE-BERT 선택적 LIME API·웹 표시·설명 실패 분리·상태 전이 경합 수정. 실제 PostgreSQL·모델·브라우저 검증 완료. 공개 배포 포함. 해당 변경은 `main`에 반영됨
- [x] **확장 단계 D 실행 격리**: 멈춘 추론·LIME을 중단하는 하드 타임아웃 구현·검증. 전처리·추론·LIME을 워커 프로세스로 분리하고 기한 초과 시 종료. 실제 PostgreSQL·모델 파일로 백엔드 테스트 83건 통과, 공개 배포 환경에서 정상 분석·LIME 확인. 해당 변경은 `main`에 반영됨
- [x] **공개 배포 전 운영 점검**: 다중 프로세스 공통 속도 제한을 PostgreSQL 공통 카운터로 구현·검증(uvicorn 워커 2개에서 단일 예산 확인). 웹 Vercel · API 컨테이너 · 관리형 PostgreSQL로 분리하는 방향 결정. API 호스팅 사양·비용은 세 모델 실측 후 확정
- [x] **Streamlit 이관 1단계 화면**: `/dataset`·`/about` 신설, 예시 프리셋 추가, F1 최고 모델을 같은 평가 범위 안에서만 강조. 공개 웹 화면과 API 브라우저 연동 통과. 500자 상한 적용.
- [x] **이관 기능 동등성**: [완료 기준](migration-parity.md)에 따라 세 모델 분석·LIME, 500자 입력을 구현. 로컬 Docker·PostgreSQL과 공개 API에서 예측·설명 및 500/501자 경계를 확인.
- [x] **공개 배포 기능 검증**: 실제 웹/API 주소에서 세 모델 예측·LIME, 500/501자 경계, `/dataset`·`/about`, 브라우저 연동 확인. 공개 주소·실측은 [이관 완료 기준](migration-parity.md) 및 [공개 배포 계획](deployment-public.md) 참고
- [x] **무료 한도 사용자 알림**: API 오류에서 한도 소진 가능성과 잔액 확인 한계를 모달로 알림. PR #16; 테스트 28건·lint·로컬/원격 빌드, 로컬 모달 표시·닫기, 공개 배포 완료
- [x] **이관 운영 안정성 측정**: 콜드 스타트 약 11.5초, 세 모델 500자+LIME 6.4~17.6초, 최대 메모리 약 1.76GiB/8GiB, 동시 요청은 Modal 대기열 직렬 처리, Modal $1/월로 약 85~250회 방문 추정. 크레딧 약 $0.01 사용 (이슈 #19, [기록](deployment-public.md))
- [x] **Modal 메모리 요청 축소 검토**: 4GiB에서 메모리 부족은 없었으나(최대 2.06GiB) 첫 분석 추론이 1.6~2.5배 느려짐. 같은 이미지 8GiB 재측정으로 메모리가 원인임을 확인하고 8GiB 유지 (이슈 #21, [기록](deployment-public.md))
- [x] **동시성 계약 정리**: 공개 환경은 동시 요청을 거절 없이 Modal 대기열에서 순서대로 처리하는 것으로 API 계약 확정. 입력 동시성·컨테이너 수는 늘리지 않음 (이슈 #23)
- [x] **기존 Streamlit 배포 종료**: 사용자가 2026-09-25 삭제, 공개 주소 응답으로 확인. 이 저장소의 keep-alive workflow·스크립트·자동 검증 제거 (이슈 #17)
- [x] **이관 운영 게이트**: 세 모델 배포 메모리·지연·비용 측정, 공개 주소 안정성 확인, 동시성 계약 확정 → 2026-09-26 이관 완료 판정 ([기준](migration-parity.md)). 하루 측정 기반이므로 월 단위 사용량은 운영 중 관찰
- [ ] **이관 완료 후 이력서 스택 재평가**: 실제 구현·테스트·공개 배포 증거를 기준으로 이력서의 기술 공백이 채워졌는지 확인하고, 부족한 항목만 다음 작업으로 정한다. 이관 완료 전에는 충족으로 표시하지 않음
- [ ] LSTM 시드 고정 결과 재검증 및 Accuracy 0.85 목표 유지 여부 결정
- [ ] KLUE-BERT 전체 데이터/GPU 재학습 필요성은 공통 평가 결과 확인 후 결정
- [ ] TF-IDF·LIME 캡처를 self-contained 코드 기준으로 갱신
