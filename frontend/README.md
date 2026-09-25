# 감성 분석 웹 클라이언트

Next.js 16 · TypeScript · Tailwind CSS 4 기반 웹 클라이언트입니다. 모델 목록과 성능 지표는 FastAPI의 `GET /v1/models`에서 읽습니다. 분석은 현재 사용 가능한 모델만 선택해 `POST /v1/analyses`로 요청합니다.

## 로컬 실행

검증 기준 버전은 **Node.js 22.16.0 + npm 10.9.2**입니다. `package.json`의 지원 범위는 Node.js `>=22.16.0 <23`, npm `>=10 <11`이며 `check:toolchain`이 실제 버전을 검사합니다. `.nvmrc`와 `packageManager`는 재현 기준 patch를 고정합니다. Windows에서는 `nvm install 22.16.0`과 `nvm use 22.16.0`을 실행합니다. `frontend/`가 있는 드라이브에서 직접 설치하고, 다른 드라이브의 `node_modules`를 복사하거나 `NODE_PATH`로 연결하지 않습니다. 잠금 파일을 기준으로 `npm ci`를 사용합니다.

```powershell
cd frontend
npm run check:toolchain
npm ci --include=dev
$env:NEXT_PUBLIC_API_URL = "http://127.0.0.1:8000"
npm run check:env
npm run dev
```

API는 웹 출처(`http://localhost:3000`)를 CORS 허용 목록에 포함해야 합니다. `NEXT_PUBLIC_API_URL`은 브라우저에서 접근 가능한 API **origin**으로 설정합니다. 공개 주소는 HTTPS여야 하고, 로컬 개발의 `localhost`/`127.0.0.1`/`[::1]`에는 HTTP를 허용합니다. 경로·쿼리·인증 정보가 포함된 URL은 거절합니다. `npm run build`와 Vercel 원격 빌드 모두 같은 `check:env`를 실행합니다. 연결 실패 화면을 검증할 때는 `http://127.0.0.1:9`처럼 응답하지 않는 로컬 주소를 쓸 수 있으며 실제 분석 API를 호출하지 않습니다.

```powershell
npm run lint
npm test
npm run build
```

`npm ci --include=dev` → `npm test` → `npm run lint` → `npm run build` 순서가 CI 검증 순서입니다. `.codex-deps/`, `.npm-cache/`, `node_modules/`, `.next/`는 생성물로 제외하고 Vitest는 `frontend/tests/`만 검색합니다.

## API 비용 없이 모달 브라우저 확인

개발 서버에서 응답하지 않는 로컬 포트를 사용합니다. 이 검증은 Modal 분석 API를 호출하지 않습니다.

```powershell
cd frontend
$env:NEXT_PUBLIC_API_URL = "http://127.0.0.1:9"
npm run dev
```

브라우저에서 `http://localhost:3000`을 열고 모델 목록 요청 실패 후 개발자 도구 콘솔에서 아래를 순서대로 실행합니다. 첫 식이 `true`이고 제목에 서비스 이용 안내가 표시되면 모달 표시가 통과한 것입니다. `확인`을 누르거나 두 번째 식으로 버튼을 클릭한 뒤 마지막 식이 `true`이면 닫기가 통과한 것입니다.

```javascript
document.querySelector("dialog.quota-dialog")?.open === true
document.querySelector("dialog.quota-dialog .quota-dialog-close")?.click()
document.querySelector("dialog.quota-dialog") === null
```

검증 후 개발 서버를 `Ctrl+C`로 종료하고 연 브라우저 탭을 닫습니다.

## 공개 웹 배포

Vercel 모노레포 CLI는 **저장소 루트**에서 프로젝트를 연결하고 배포합니다. 실제 원격 `review-sentiment-web` 프로젝트의 Project ID와 Project Settings → Build and Deployment → Root Directory가 `frontend`인지 확인하십시오. 프로젝트 Node.js 버전도 22.x인지 확인합니다. Root Directory는 원격 프로젝트 설정이며, `frontend/vercel.json`은 그 안에서 `npm ci --include=dev`와 `npm run build`를 지정합니다. Production 환경변수 `NEXT_PUBLIC_API_URL`에는 공개 API의 HTTPS origin을 설정합니다. [Vercel 모노레포 CLI 안내](https://vercel.com/docs/monorepos#add-a-monorepo-through-vercel-cli)와 [Root Directory 안내](https://vercel.com/docs/builds/configure-a-build#root-directory)를 따릅니다.

먼저 저장소 루트에서 로컬 CLI로 **기존 프로젝트**에 연결하고 대상 정보를 확인합니다. 인증은 Vercel CLI가 관리하며 토큰을 명령이나 저장소에 기록하지 않습니다.

```powershell
# 저장소 루트에서 실행
./frontend/node_modules/.bin/vercel.cmd link --project review-sentiment-web
./frontend/node_modules/.bin/vercel.cmd project inspect review-sentiment-web
Get-Content .vercel/project.json
```

원격 Project ID·Org ID와 로컬 `.vercel/project.json`이 일치하고 Root Directory `frontend`가 확인된 뒤에만, 저장소 루트의 Git 제외 경로 `.vercel/deployment-target.json`에 다음 형식으로 확인 기록을 만듭니다. 값은 실제 확인한 ID로 치환합니다. 이 파일은 배포 안전장치이며 시크릿이 아닙니다.

```json
{
  "projectId": "<확인한 프로젝트 ID>",
  "orgId": "<확인한 조직 ID>",
  "projectName": "review-sentiment-web",
  "rootDirectory": "frontend"
}
```

배포 전 `frontend/`에서 깨끗한 설치·테스트·lint·빌드를 순서대로 마친 뒤 `npm run deploy`를 실행합니다. 스크립트는 연결 ID와 확인 기록이 일치하지 않으면 `--prod`를 호출하지 않습니다. 조건이 맞으면 잠금 파일에 고정된 Vercel CLI를 **저장소 루트 cwd**로 실행합니다. 원격 빌드에서도 같은 `check:env`가 실행됩니다.

```powershell
cd frontend
npm ci --include=dev
$env:NEXT_PUBLIC_API_URL = "https://<공개-API-호스트>"
npm test
npm run lint
npm run build
npm run deploy
```

배포 후 공개 주소의 화면·CORS·이관 완료 조건을 확인합니다. 사용자가 기존 리뷰 감성 분석 Streamlit 배포를 직접 삭제할 예정이며, 배포 삭제만으로 이관 완료로 판정하지 않습니다.

선택한 모델의 `explanationAvailable`이 `true`일 때 LIME 설명을 선택할 수 있습니다. 설명 선택은 기본으로 꺼져 있으며, 실패해도 감성 예측 결과는 유지됩니다. 현재 웹은 500 코드 포인트 입력을 받지만, 세 모델 제공은 백엔드의 가용성 응답에 따릅니다. 리뷰 원문과 설명 단어는 브라우저 저장소와 URL에 저장하지 않습니다. 남은 운영 검증은 [이관 완료 기준](../docs/migration-parity.md)을 따릅니다.
