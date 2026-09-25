# 감성 분석 웹 클라이언트

Next.js 16 · TypeScript · Tailwind CSS 4 기반 웹 클라이언트입니다. 모델 목록과 성능 지표는 FastAPI의 `GET /v1/models`에서 읽습니다. 분석은 현재 사용 가능한 모델만 선택해 `POST /v1/analyses`로 요청합니다.

## 로컬 실행

```powershell
cd frontend
npm install
$env:NEXT_PUBLIC_API_URL = "http://localhost:8000"
npm run dev
```

API는 웹 출처(`http://localhost:3000`)를 CORS 허용 목록에 포함해야 합니다. 프로덕션 빌드는 `NEXT_PUBLIC_API_URL`이 없으면 실패합니다. 이 값은 브라우저에서 접근 가능한 FastAPI 주소여야 합니다.

```powershell
npm run lint
npm test
npm run build
```

선택한 모델의 `explanationAvailable`이 `true`일 때 LIME 설명을 선택할 수 있습니다. 설명 선택은 기본으로 꺼져 있으며, 실패해도 감성 예측 결과는 유지됩니다. 현재 웹은 500 코드 포인트 입력을 받지만, 세 모델 제공은 백엔드의 가용성 응답에 따릅니다. 리뷰 원문과 설명 단어는 브라우저 저장소와 URL에 저장하지 않습니다. 기존 Streamlit 데모는 [이관 완료 기준](../docs/migration-parity.md)을 충족할 때까지 계속 이용할 수 있습니다.
