# 공개 배포 계획과 Streamlit 이관 (2026-09-24)

목표는 새 스택(FastAPI + Next.js)이 기존 Streamlit 데모를 **대체**하는 것이다. [이관 완료 기준](migration-parity.md)은 세 모델 예측·설명과 500자 입력이다. 로컬 컨테이너에서는 세 모델의 예측·설명과 500자 경계를 확인했다. 운영 안정성 게이트는 남아 있다. 사용자가 2026-09-25 기존 리뷰 감성 분석 Streamlit 배포를 삭제했고, 이 저장소의 전용 keep-alive도 제거했다(이슈 #17). 배포 삭제와 이관 완료 판정은 별개다.

## 기존 배포 상황 (이 계획의 전제)

| 대상 | 현재 | 이 프로젝트에 주는 제약 |
|---|---|---|
| review-sentiment Streamlit (legacy) | 2026-09-25 사용자가 삭제. 공식 웹 진입점은 https://review-sentiment-web.vercel.app | `app.py`는 과거 구현의 로컬 재현용으로만 남음 |
| music-mood-recs Streamlit | Streamlit Cloud Public | 같은 무료 티어를 공유하므로 새 비용을 만들지 않는 편이 일관적이다 |
| 슬립 대응 | music-mood-recs는 자체 Playwright keep-alive GitHub Actions를 유지. 이 저장소의 Streamlit keep-alive는 앱 삭제로 제거함 | 새 API·웹에는 자동 방문 작업을 두지 않는다 |
| web-portfolio | Vercel(`*.vercel.app`), 커스텀 부모 도메인 이전을 계획 중 | 웹은 Vercel이 기존 계정·경험과 맞는다 |
| 무거운 아티팩트 | Hugging Face Hub 데이터셋 저장소(`Ketose333/review-sentiment-assets`, `…music-mood-recs-assets`)에서 런타임 로드 | 이미 쓰는 계정이다. API도 같은 고정 revision을 쓴다 |
| 컨테이너·관리형 DB | **사용 이력 없음** | 새로 도입하는 유일한 요소이므로 가장 작은 선택을 한다 |

## 배포 형태 재검토 — 추가 요금 0원 제약

2026-09-25 사용자 지시: **가격이 발생해서는 안 된다.** 유료 시험·유료 인스턴스·결제 전환은 진행하지 않는다. 아래 A1·플랫폼 탐색 내용은 실제 Modal/Vercel/Neon 배포 전의 후보 검토 기록이다. 현재 배포와 무료 잔액은 `2026-09-25 실제 공개 배포` 절을 기준으로 한다.

- **웹(Next.js) → Vercel.** 기존 포트폴리오와 같은 계정·배포 흐름을 쓴다. `NEXT_PUBLIC_API_URL`만 환경변수로 넣는다.
- **API(FastAPI) → 무료 컴퓨트 후보 검증.** 세 모델 제공에는 JDK(Okt), TensorFlow, PyTorch·Transformers와 추론 워커가 필요하다. [Hugging Face의 새 Docker Space](https://huggingface.co/docs/hub/spaces-overview)는 CPU Basic의 시간당 요금이 0이어도 생성에 유료 계정이 필요하므로 제외한다. [Render Free](https://render.com/docs/compute-plans)는 메모리 512MB라 로컬 실측 3.089GiB를 담지 못한다.
- **PostgreSQL → 무료 관리형 인스턴스 또는 같은 무료 VM.** 모델 메타데이터·24시간 실행 기록·속도 제한 카운터만 저장한다. [Neon Free](https://neon.com/blog/neon-backend-is-ga)는 자동 절전되는 PostgreSQL 후보이지만 연결 재개와 무료 한도를 실제 API로 검증해야 한다. 같은 무료 VM에 PostgreSQL을 두는 경우에는 재시작 후 데이터·백업과 방화벽을 별도로 검증한다.
- **무료 VM 후보:** [Oracle Always Free A1](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm)은 현재 계정당 ARM 2 OCPU·12GB 메모리 상당을 허용한다. 계정 생성에는 카드 확인이 필요할 수 있으나 [Oracle 공식 안내](https://docs.oracle.com/iaas/Content/FreeTier/freetier.htm)는 유료 계정으로 업그레이드하지 않으면 카드를 청구하지 않는다고 명시한다. 무료 자원 부족·유휴 VM 회수 가능성이 있다. ARM64 API 이미지는 로컬에서 빌드했으나 실제 ARM VM에서 모델 실행은 아직 검증 전이다. 유료 계정 전환은 금지한다.
- **기존 TaeyulBot VM 실측(2026-09-25):** SSH·OCI 인스턴스 메타데이터로 확인한 `ca-toronto-1`의 `VM.Standard.E2.1.Micro`는 RAM 총 956MiB, 사용 가능 약 305MiB, swap 없음, 루트 파일시스템 45GiB 중 39GiB 여유다. TaeyulBot 서비스는 실행 중이고 약 180MB를 쓴다. 디스크에는 이미지가 들어갈 수 있어도 세 모델 실행 후 3.089GiB를 쓴 API를 이 VM에 함께 배치할 수 없다. CPU도 [공식 사양](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm)상 기본 1/8 OCPU라 LIME 실행에 부적합하다. OCI 콘솔에서 현재 계정이 Free Tier이고 토론토가 홈 리전이며, 실행 중인 E2 Micro 1대·47GB 부트 볼륨 1개·별도 블록 볼륨과 부트 볼륨 백업 0개임을 확인했다. A1 Flex는 `Always Free-eligible`로 표시된다. 따라서 기본 크기 A1 부트 볼륨을 추가해도 표시 용량 합계는 94GB로 무료 200GB 범위 안이다. 생성 화면의 월 비용 추정치 $21.27은 무료 티어 단가를 반영하지 않는다고 화면에 명시되어 있다. 기존 봇 VM이나 유료 계정 설정은 변경하지 않는다.
- **A1 생성 시도(2026-09-25):** 공용 인스턴스명 `shared-apps-a1`, A1 Flex 2 OCPU·12GB, Ubuntu 24.04, 기본 부트 볼륨, 기존 `free-arm` VCN의 공개 서브넷과 공인 IPv4로 생성 요청했다. OCI API가 `Out of capacity for shape VM.Standard.A1.Flex in availability domain AD-1`을 반환해 **인스턴스는 생성되지 않았다**. 토론토 홈 리전 생성 화면에는 AD-1만 표시됐고, A1 서비스 한도 사용량은 0/2 OCPU·0/12GB다. 한도 초과가 아니라 호스트 재고 부족이다. 추가 과금이나 기존 TaeyulBot 변경은 없으며, SSH 재확인 결과 `taeyulbot`은 `active`다.
- **A1 단 1회 재시도(2026-09-25):** 사용자가 명시적으로 요청해 생성 키 `C:\Users\user\.ssh\shared-apps-a1`를 만들고 공개 키만 제출했다. 같은 사양·기존 VCN·공개 서브넷·공인 IPv4·기본 46.6GB 부트 볼륨으로 한 번만 요청했다. 비용 패널은 $21.27/월을 표시하면서 tier 단가를 반영하지 않는다고 했고, 계정의 A1은 여전히 0/2 OCPU·0/12GB, 기존 47GB 볼륨을 합쳐 약 94GB로 Always Free 200GB 안이었다. OCI가 다시 `Out of capacity for shape VM.Standard.A1.Flex in availability domain AD-1`을 반환했다. 인스턴스 목록에는 기존 `free-arm` 하나만 남아 Running/Always Free이며 `shared-apps-a1`은 생성되지 않았다. **추가 재시도·유료 전환은 하지 않는다. 추가 요금 발생 없음.** PC 독립 24/7 공개 API를 위한 무료 컴퓨트가 확보되지 않아 공개 배포는 막혀 있다.
- **지역 변경 검토(2026-09-25):** 계정 지역 메뉴에는 토론토 홈 리전만 표시된다. [Oracle Always Free 안내](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm)는 무료 컴퓨트를 홈 리전에서만 생성할 수 있다고 명시하고, [지역 관리 문서](https://docs.oracle.com/en-us/iaas/Content/Identity/Tasks/managingregions.htm)는 홈 리전을 변경할 수 없다고 명시한다. 다른 지역에 구독하더라도 이 계정의 무료 A1 생성 문제를 해결하지 못한다. [무료 계정 등록 조건](https://signup.cloud.oracle.com/)상 한 사람의 무료 계정 중복 생성도 허용되지 않는다. 따라서 현 계정에서는 토론토 A1 재고가 돌아오기를 기다리거나 OCI 외부의 무료 실행 환경을 검토한다.
- **Streamlit Community Cloud 재사용 실험:** 로컬 Streamlit 1.57.0에서 `st.App`에 FastAPI를 연결해 기존 UI(`/`)와 GET·POST API(`/v1/*`)를 함께 제공했다. 다만 [공식 메모리 한도](https://docs.streamlit.io/deploy/streamlit-community-cloud/manage-your-app)는 가변적이며 약 690MB~2.7GB로 안내되어, 현재 세 모델 API의 3.089GiB 관측값보다 낮다. 공개 프록시·CORS·실제 메모리를 검증하기 전까지 배포 가능 경로로 간주하지 않는다. `st.App`는 [1.57 문서](https://docs.streamlit.io/1.57.0/develop/api-reference/server/st.app)에 있다.
- **기존 PC 공개 후보:** [Tailscale Personal·Funnel](https://tailscale.com/docs/features/tailscale-funnel)은 무료 플랜에서 로컬 서비스를 공개할 수 있다. 다만 PC가 켜져 있어야 하고, 베타 기능·대역폭 제한이 있어 상시 공개 서비스의 안정성은 별도로 검증해야 한다.

### 2026-09-25 무료 경로 재평가

추가 요금 없이 공개 API를 실제로 검증할 수 있는 후보를 다시 확인했다.

| 후보 | 확인 결과 | 판단 |
|---|---|---|
| 토론토 Always Free A1 | OCI 공식 [호스트 용량 오류 안내](https://docs.oracle.com/en-us/iaas/Content/Compute/Tasks/troubleshooting-out-of-host-capacity.htm)는 용량이 동적이며 잠시 기다렸다가 재시도하거나 Fault Domain을 지정하지 말라고 한다. [Capacity Reservation](https://docs.oracle.com/en-us/iaas/Content/Compute/Tasks/reserve-capacity.htm)은 Free Tier에서 쓸 수 없다. 현재 홈 리전 UI에는 AD-1 하나만 보였고 사용량은 0/2 OCPU·0/12GB였다. 승인된 단 1회 재시도도 같은 호스트 재고 오류로 실패했다. | A1은 재고가 나중에 풀릴 수 있으나 지금 예약·확정할 방법이 없고, 단 1회 재시도도 실패했다. 무작정 반복하지 않는다. 유료 전환·다른 계정·기존 E2 변경은 하지 않는다. |
| Hugging Face Docker Space | 현재 [공식 Spaces 안내](https://huggingface.co/docs/hub/spaces-overview)는 개인 계정에서 Docker/Gradio Space 생성에 PRO를 요구한다고 명시한다. | 무료 조건에서 제외. |
| 기존 Windows PC + Tailscale Funnel | [Funnel 공식 안내](https://tailscale.com/docs/features/tailscale-funnel)는 모든 플랜에서 사용할 수 있으나 베타이며, 공개 서비스는 해당 PC에서 동작해야 하고 대역폭 제한이 있다. 이 PC에는 Docker가 있으나 Tailscale은 설치되어 있지 않다. Windows는 61.75 GiB RAM이며 확인 시점 여유는 4.38 GiB였다. 컨테이너의 3.089 GiB는 단일 사후 관측치라 최대 사용량이나 반복 부하 여유를 보장하지 않는다. | 사용자가 24/7 및 PC 부팅과 무관한 실행을 요구했으므로 후보에서 제외한다. |
| Vercel Hobby + Modal Starter API + Neon Free PostgreSQL | Next.js를 Vercel에, scale-to-zero FastAPI를 Modal에, DB를 Neon에 배포했다. Vercel Hobby는 [개인·비상업 용도](https://vercel.com/legal/terms) 조건이며 각 서비스 무료 사용량 한도가 있다. | 실제 세 모델 API 분석·LIME과 웹/API 연결을 확인했다. 콜드 스타트·동시 부하·장기 한도는 추가 측정이 필요하다. 비용 기록은 아래 배포 기록을 따른다. |
| Google Cloud Run Free Tier | [공식 요금표](https://cloud.google.com/run/pricing)는 월 240,000 vCPU초와 450,000 GiB초를 무료로 제공하고 초과분은 청구한다고 명시한다. 요청 기반은 유휴 상태에서 비용을 피할 수 있지만 상시 최소 인스턴스는 추가 과금 대상이다. 관측 메모리 3.089 GiB를 계속 할당하면 RAM 무료량은 약 40.5시간 분량이며, 상시 공개를 위해 트래픽이나 최소 인스턴스를 유지하면 무료 한도를 넘을 수 있다. | 24/7·0원 보장 조건에 맞지 않아 제외한다. 과금 계정이나 서비스를 만들지 않는다. |
| Render Free Web Service | [공식 무료 플랜 안내](https://render.com/docs/free)에 따르면 512 MB RAM, 15분 유휴 후 sleep, 워크스페이스 월 750 무료 인스턴스 시간이다. 초과 대역폭은 결제 수단이 있으면 청구될 수 있다. | 메모리 부족·sleep·월 시간 제한으로 제외한다. |
| AWS Free Tier VM | [공식 무료 사용 안내](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-free-tier-usage.html)에 따르면 계정 개설 시기별 무료 기간·크레딧 제한이 있고, 한도를 넘으면 종량 과금이 발생할 수 있다. 대표 무료 인스턴스 메모리도 이 API 관측치보다 작다. | 지속적인 0원 보장에 맞지 않고 메모리도 부족해 제외한다. |

**당시 결론 (24/7·PC 부팅 무관, 실제 배포 전):** 토론토 A1의 할당량은 0/2 OCPU·0/12GB이나 AD-1 호스트 용량 부족으로 최초 요청과 사용자가 승인한 단 1회 재시도가 모두 실패했다. 두 번째 요청 뒤 OCI 인스턴스 목록에도 기존 `free-arm`만 있으며 새 인스턴스는 없다. 이 시점에는 세 모델을 올릴 무료 실행 환경을 확보하지 못했다. 이후 실제 공개 배포 내용은 아래 최신 배포 기록을 따른다.

> 위 결론은 당일 실제 배포 전 스냅샷이며, 아래 2026-09-25 배포 기록으로 갱신되었다.

### 2026-09-25 실제 공개 배포

- **웹:** Vercel Hobby 프로젝트를 `review-sentiment-web`로 정리하고 `frontend/`만 직접 업로드했다. Next.js 16.3.6 프로덕션 빌드 통과. 정식 공개 주소는 https://review-sentiment-web.vercel.app 하나만 Production 도메인으로 연결했다. 기존 `frontend-kappa-navy-gtn5mqhmrx.vercel.app` 및 `frontend-ketose333.vercel.app` 별칭은 프로젝트와 배포에서 제거했다. GitHub 자동 연결은 실패했지만 직접 업로드 배포는 성공했다. 다음 배포는 CLI에서 수동 실행해야 한다.
- **도메인·CORS 정리:** Vercel 프로젝트 이름을 `frontend`에서 `review-sentiment-web`로 변경했다. Modal Secret의 CORS 허용 목록에는 `https://review-sentiment-web.vercel.app`만 둔다. 새 도메인의 모델 목록 로딩과 CORS 응답을 확인했고, 이전 Vercel 주소는 더 이상 지원하지 않는다. 당시 기존 Streamlit 앱과 keep-alive는 legacy 상태로 남아 있었으며(2026-09-25 삭제·제거), 공식 진입 링크는 새 웹 주소 하나만 제공한다.
- **API:** Modal Starter에서 FastAPI 이미지 배포. https://ketose333--review-sentiment-api-api.ap-south.modal.run . `min_containers=0`, 유휴 60초 후 scale-to-zero, `max_containers=1`, 2 CPU·8 GiB. 컴퓨트는 PC와 무관하게 원격 실행되고 URL은 계속 공개되지만, 첫 요청에는 콜드 스타트가 있다. 화면에서 모델 목록 복귀까지 18초 이상 한 번 관측했다.
- **DB:** Neon Free (Singapore), 0001~0008 마이그레이션 완료. API가 쓰는 pooled endpoint는 IPv6 우선 경로와 연결 시작 `options` 제한이 있어 첫 공개 조회가 실패했다. 공유 카운터 타임아웃을 PostgreSQL 트랜잭션 범위 `set_config(..., true)`로 적용하도록 수정 후 조회가 정상화되었다. Neon PgBouncer의 transaction pooling은 세션 상태를 보존하지 않으므로 타임아웃 설정은 각 카운터 트랜잭션 안에서만 한다.
- **실제 공개 검증:** `GET /healthz`, `GET /v1/models` 통과. TF-IDF·LSTM·KLUE-BERT에서 예측과 LIME 설명 성공. 500자는 성공, 501자는 `422 INVALID_TEXT`. 브라우저에서 TF-IDF와 KLUE-BERT 분석·LIME 표시 성공. `/dataset`, `/about` 표시 확인. CORS는 최종 Vercel 프로덕션 origin으로 제한했다. LSTM 브라우저 표시 경로, 동시 부하·반복 콜드 스타트는 더 측정할 수 있다.
- **비용:** 계정 화면상 Vercel Hobby, Neon Free, Modal Starter이며 Modal 결제 화면에 결제 수단 추가 안내가 표시된다(카드 미등록). 2026-09-25 Usage & Billing 화면 확인값은 Modal 무료 크레딧 $1.00 중 $0.10 사용·$0.91 잔여, 이번 주기 청구 $0이다. 크레딧 소진 뒤에는 유료 전환 없이 요청이 중단될 수 있다. 무료 플랜 한도 초과나 정책 변경 가능성은 계속 모니터링해야 하며, 결제 수단·유료 플랜을 추가하지 않는다.
- **유지(당시 계획):** Streamlit과 기존 6시간 keep-alive를 계속 운영하기로 했다. 이후 사용자가 2026-09-25 Streamlit 배포를 삭제해 keep-alive도 제거했다. 아래 안정성 게이트는 이와 별개로 미완료다.

API 컨테이너에는 `GET /healthz`를 생존 확인 경로로 지정한다. 속도 제한과 DB 접근이 없으므로 부하 중에도 거절되지 않는다. 다만 생존 확인 전용이라 DB 도달 여부는 확인하지 않는다. 준비 확인이 필요해도 `/v1/models`는 쓰지 않는다 — 공개 예산을 소모해 부하 중에 재시작을 유발한다.

### 2026-09-25 프론트 재현 배포 (PR #16)

배포 전에는 로컬 Node 20.19.2/npm 10.8.2와 CI Node 22가 달랐고, 일회성 `NEXT_PUBLIC_API_URL` 주입과 임시 의존성 설치가 남아 있었다. `frontend/.codex-deps/partial-npm-node_modules` 안의 외부 테스트 두 개가 Vitest 기본 검색에 포함되어 앱 테스트 28건은 통과해도 전체 명령이 실패하는 현상을 재현했다. Vercel CLI의 이전 `@vercel/detect-agent` 로딩 실패는 원래 호출 경로의 로그를 확보하지 못했지만, 당시 임시 설치에는 해당 패키지와 CLI 실행 파일이 없었다. 따라서 CLI 자체 결함으로 단정하지 않는다. Windows 드라이브 간 `node_modules` 복사·이동을 없애고 프론트 디렉터리에서 잠금 파일로 `npm ci`를 실행한다. 첫 깨끗한 설치는 npm registry tarball 한 건에 233초가 걸렸고, 다시 실행한 `npm ci --include=dev --prefer-offline`은 11분 뒤 성공했다. 이 지연은 의존성 다운로드 계층이다.

재현 기준은 Node 22.16.0/npm 10.9.2, `frontend/package-lock.json`, `npm ci --include=dev`다. Vitest는 `frontend/tests/`만 검색하고 `.codex-deps`·npm 캐시·빌드 산출물은 테스트·lint·TypeScript·Git 범위에서 제외한다. `frontend/scripts/check-env.mjs`가 로컬 빌드와 Vercel 원격 빌드의 API origin을 같은 규칙으로 검사한다. Vercel 프로젝트 `review-sentiment-web`의 Root Directory를 `frontend`, Node.js를 22.x로 맞추고 Production `NEXT_PUBLIC_API_URL`을 공개 API HTTPS origin으로 등록했다. 로컬 Vercel CLI 60.0.1은 잠금 파일로 설치하며, 루트의 프로젝트 링크와 확인 기록이 일치하지 않으면 프로덕션 배포 명령을 실행하지 않는다. 새 PC 명령·대상 확인 순서는 [프론트 README](../frontend/README.md)에 있다. 인증 파일과 토큰은 Git에 추가하지 않는다.

| 검증 | 결과 |
| --- | --- |
| 깨끗한 설치 | Node 22.16.0/npm 10.9.2에서 `npm ci --include=dev` PASS, 651개 패키지 |
| 로컬 | `npm test` 4개 파일·28건 PASS, `npm run lint` PASS, 로컬 실패 URL과 공개 HTTPS URL 각각 `npm run build` PASS |
| 모달 브라우저 | 로컬 `http://127.0.0.1:9`로 실제 Modal API 호출 없이 네이티브 모달 표시·중앙 정렬·닫기 확인. 테스트 서버와 탭 종료 |
| CLI·CI | 고정 CLI 60.0.1 로딩 PASS; PR #16 Auto Review·Frontend CI PASS |
| 원격 | 배포 `dpl_HSP7QbCZesudNh6MCPQZLkWkJLXG` READY·정식 주소 연결. Vercel Node 22.23.2/npm 10.9.8에서 `npm ci`·공통 URL 검사·Next.js 빌드 PASS |
| 공개 주소 | `/`, `/dataset`, `/about` HEAD 200. 브라우저에서 세 모델 목록 로딩 확인; 분석 POST·LIME은 이번 검증에서 반복하지 않음 |
| 의존성 감사 | 원격 전체 설치 경고 29건. 로컬 `npm audit --omit=dev`에서 프로덕션 의존성 0건 |

이 배포는 화면·연결 확인이다. 공개 환경의 분석·설명 실패 처리, 반복 콜드 스타트, 동시 부하, 최대 메모리와 장기 무료 한도는 아직 이관 완료 게이트에 남아 있다. 기존 Streamlit 앱과 keep-alive는 이 배포 뒤 삭제·제거했으며(이슈 #17), 그 사실이 위 게이트 통과를 뜻하지는 않는다.

### 2026-09-26 공개 운영 안정성 측정 (이슈 #19)

사용자가 승인한 Modal 크레딧 한도 $0.20 안에서 진행했다. 먼저 Modal·Neon·Vercel 대시보드의 과거 기록을 무료로 읽고, 공개 환경에서 아직 확인하지 않은 항목만 컨테이너 한 번 기동(약 155초)으로 측정했다. 요청 8건, 추정 비용 약 $0.01이다. 측정 스크립트는 상태 코드·시간·오류 코드만 기록하고 입력 원문과 설명 단어는 기록하지 않았다.

| 항목 | 결과 | 근거 |
| --- | --- | --- |
| 콜드 스타트 | 클라이언트 기준 `/healthz` 11.5초(Modal 대기 약 11초, 컨테이너 시작 3.3초, 실행 0.25초). 과거 기록의 컨테이너 시작은 3.1~12.2초 | 이번 측정 + Modal 호출 기록(9/25~26) |
| 첫 DB 조회 | 웜 컨테이너·Neon 절전 상태에서 `/v1/models` 6.3초(서버 실행 5.9초), 직후 2.3초(서버 2.1초). 과거 콜드 직후 첫 `/v1/models` 서버 실행 5.7~25.4초 | 이번 측정 + Modal 호출 기록 |
| 500자 + LIME | TF-IDF 6.4초, LSTM 17.6초(추론 11.4초), KLUE-BERT 16.2초(추론 9.1초). 세 모델 설명 모두 `SUCCEEDED`, 함수 제한 240초 안 | 이번 측정 |
| 최대 메모리 | 세 모델 적재·설명 후 1.74GiB, 9/25 기능 검증 구간 1.76GiB. 요청량 8GiB의 약 22%. 분 단위 샘플이라 순간 최대치는 조금 더 높을 수 있음 | Modal 메트릭 |
| 동시 요청 | 같은 클라이언트의 POST 2건 동시 전송이 둘 다 201. Modal 기록상 둘 다 02:11:20 대기열 진입, 한 건은 10초 대기 후 시작 | 이번 측정 + Modal 호출 기록 |
| 무료 사용량 | Modal $0.13/$1(9/26 반영분, 월 초기화 10/1), Neon 컴퓨트 0.37/100 CU-시간·저장 0.03/0.5GB, Vercel 전송 10.8MB/100GB·요청 1.3천/100만 | 각 대시보드 |

**동시 요청 처리 방식:** Modal은 이 함수에 컨테이너당 입력 한 건만 넣고 `max_containers=1`이다. 그래서 공개 환경에서는 동시 요청이 앱의 입장 제한(프로세스당 4건, 주소당 1건 → 503 `SERVICE_BUSY`)에 닿기 전에 Modal 대기열에서 순서대로 처리된다. 거절은 없지만 앞선 LIME 요청 시간(최대 약 17초)만큼 뒤 요청이 기다리고, `/healthz`·`/v1/models`도 같은 대기열을 탄다. 이번 측정으로 공개 환경의 `TRUSTED_PROXY_HOPS` 주소 식별은 검증되지 않았다.

**무료 운영 용량(추정):** 2코어·8GiB 기준 초당 약 $0.000044이며, 리전 할증 1.15~1.75배를 적용하면 $0.00005~0.00008다. `cpu=2`가 과금상 물리 코어 2개인지는 확인하지 못해 상한 쪽으로 계산했다. 월 $1 크레딧은 컨테이너 가동 약 3.6~6.3시간이다. 방문 한 번에 콜드 스타트·사용·유휴 60초로 90~155초가 걸리면 월 약 85~250회 방문 뒤 다음 달 1일까지 API가 멈출 수 있다. 메모리는 요청량과 사용량 중 큰 값으로 과금되므로, 실제 사용이 2GiB 미만이어도 8GiB 요청이 비용의 약 40%를 차지한다.

**판정:** 단일 사용자 기준으로 기능·지연·메모리는 무료 한도 안에서 동작한다. 다만 월 방문 용량이 작고 동시 요청이 대기열로 처리되므로, 아래 후속 조치를 결정하기 전까지 이관 완료로 표시하지 않는다.

- 메모리 요청 축소 검토: 관측 최대 1.76GiB 대비 8GiB. 4GiB로 줄이면 초당 비용이 약 20% 감소한다. 줄인 뒤 세 모델 LIME 최대치를 재확인해야 한다.
- 동시성 계약 정리: 공개 환경의 대기열 동작을 API 계약에 맞출지(문서화), Modal 입력 동시성을 늘려 앱 입장 제한을 쓰게 할지 결정한다.

### 로컬 실측을 반영한 공개 시험 사양

최종 로컬 컨테이너는 세 모델과 웹 테스트를 실행한 뒤 3.089GiB를 사용했다. 단일 시점 값이므로 최대 메모리는 아니다. Modal 2 CPU·8 GiB에서 짧은 입력의 예측·설명은 모두 성공했으나 최대 메모리와 동시 부하를 측정하지 않았다.

- **유료 호스팅은 제외:** Fly.io·Render 유료 사양을 쓰지 않는다. 무료 자원으로 세 모델이 통과하지 못하면 이관을 완료로 표시하지 않는다.
- **DB 대안:** [Supabase Free](https://supabase.com/pricing)는 1주일간 활동이 낮으면 프로젝트가 일시정지될 수 있으므로 상시 안정성 게이트를 별도로 확인해야 한다.
- **웹:** Vercel Hobby 프로덕션에 직접 업로드 완료. GitHub 자동 연결은 실패해 다음 배포는 CLI 수동 업로드가 필요하다.

공개 기능 배포는 완료했지만, 운영 안정성 및 장기 무료 한도 검증은 남아 있다. **추가 요금 0원** 조건을 유지하면서 반복 콜드 스타트·부하·Neon 절전 복귀와 무료 사용량 한도를 점검한다.

배포의 `TRUSTED_PROXY_HOPS=1`은 실제 브라우저 요청에서의 제한 버킷을 별도 확인할 예정이다. 이 값이 맞지 않으면 사용자가 프록시 주소 하나를 공유해 같은 예산에 묶일 수 있다.

모든 프로세스가 같은 `RATE_LIMIT_SALT`를 써야 하며, 시작 로그의 소금값 지문(`rate_limit_salt_fingerprint`)이 프로세스마다 같은지로 확인한다. 이 지문과 요청 로그는 `INFO` 수준이라 로깅을 `WARNING`으로 올리면 확인할 수 없다.

추가 운영 측정: 공유 카운터의 단일 `global` 행 부하, 503 `REGISTRY_UNAVAILABLE` 비율, 300ms lock timeout, 콜드 스타트와 최대 메모리. 공개 첫 연결 실패는 Neon 풀러의 startup `options` 거부였고, 타임아웃을 트랜잭션 로컬 설정으로 옮겨 해결했다.

## 마이그레이션 `0007` 이력과 새 DB 확인

`0007`은 최초 커밋 전에 버킷 CHECK를 16진수 32자에서 64자로 고쳤다. 당시 수정 전 revision은 삭제한 로컬 임시 DB에만 적용했다. 현재 저장소의 `0007`은 {64} 제약을 생성하고, 별도 목적의 `0008`은 신경망 모델 등록을 갱신한다. 공개 Neon DB에는 `0001`~`0008`을 적용했다. 새 DB는 순서대로 마이그레이션하면 된다. 기존 DB를 재사용한다면 revision 번호만 믿지 말고 `rate_limit_counters_bucket_opaque`가 64자 HMAC 버킷을 허용하는지 먼저 확인한다. 불일치가 발견되면 이미 사용 중인 `0008`을 재사용하거나 기존 마이그레이션을 고치지 말고 새 revision에서 제약을 수정한다.

## 이관 단계

### 1단계 — 화면 이관 (분석은 TF-IDF 유지) — 완료

Streamlit의 네 탭 중 분석 외 화면을 웹으로 옮겼다. 새 추론 경로를 늘리지 않으므로 메모리·지연 리스크가 없다.

- **데이터 탐색** `/dataset` — 레이블 분포·길이 히스토그램·레이블별 빈출 단어 TOP 20. `models/eda/stats.json`을 `frontend/src/data/eda-stats.json`으로 번들한다. API를 거치지 않으므로 API가 잠든 상태에서도 열리고 공개 예산도 쓰지 않는다. 두 파일이 어긋나면 `tests/test_eda_sync.py`가 실패한다.
- **프로젝트 소개** `/about` — 데이터셋·비교 모델·전처리 설명에 입력과 보관 정책을 더했다.
- **예시 리뷰 프리셋** — Streamlit과 같은 4종을 분석 화면에 두고, 고르면 입력란을 채운다.
- **입력 상한** — 로컬 웹·API를 Streamlit과 동일한 500자로 수정하고 경계 테스트를 통과했다.
- **모델 성능** — F1 최고 모델을 강조하되 **같은 평가 범위끼리만** 비교한다. Streamlit은 전체 분할 평가와 5,000건 표본 평가를 한데 놓고 최고를 뽑았는데, 이는 이 저장소가 명시한 '평가 조건이 다르면 단순 비교 불가' 원칙과 어긋난다. 제외한 모델과 이유를 함께 표시한다.
- 화면이 셋이 되어 헤더·푸터를 레이아웃으로 올리고 내비게이션을 추가했다.

### 2단계 — 세 모델 기능과 배포 환경 검증 (미완료)

LSTM·KLUE-BERT 예측과 세 모델의 LIME 설명, 500자 입력을 공개 환경에서 검증했다. 공개 API의 `durationMs`(추론 시간, LIME 제외)는 짧은 입력 1회에서 TF-IDF 2.586초·LSTM 12.307초·KLUE-BERT 11.009초였다. 같은 요청의 클라이언트 측 전체 경과 시간은 각각 약 8.9초·15.1초·13.6초였다. 첫 호출·직전 모델 호출·콜드 스타트의 영향을 받는 단일 관측이다. 로컬 컨테이너 사용량 3.089GiB·이미지 1,859,760,902바이트다. 반복 지연·동시 부하와 최대 메모리는 추가 측정해야 한다.

### 3단계 — 운영 게이트와 기존 배포 정리 (게이트 미완료)

세 모델의 기능 동등성과 새 주소의 안정성을 확인해 이관 완료 여부를 기록한다. 기존 리뷰 감성 분석 Streamlit 배포는 사용자가 2026-09-25 삭제했다. 같은 날 공개 주소가 존재하지 않는 앱과 동일한 인증 리다이렉트로 응답함을 확인하고 이 저장소의 전용 keep-alive workflow·스크립트·자동 검증을 제거했다(이슈 #17). 새 주소를 깨우는 자동 방문 작업은 계획하지 않는다. 기존 배포 정리는 끝났지만 새 웹/API의 장기 안정성·무료 운영 검증은 남아 있다.

Windows 로컬 측정에서 KLUE-BERT LIME은 30샘플 약 62초였으나, Linux 컨테이너 로컬 짧은 입력은 7.78초, 공개 API 짧은 입력은 11.009초였다([측정 기록](lime-measurement.md)). 입력 길이·CPU 할당·동시 부하에 따른 편차와 공개 프록시 기한, 강제 설명 실패 동작을 추가 검증해야 한다. 장기 무료 운영·안정성을 확인하기 전에는 이관 완료로 표시하지 않는다.
