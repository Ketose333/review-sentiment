# 세 모델 API 컨테이너 준비

루트 `Dockerfile`은 Python 3.11, OpenJDK 17, CPU 전용 PyTorch, TensorFlow, Transformers와 API를 포함한다. AMD64에서는 `tensorflow-cpu==2.21.0`, ARM64에서는 ARM wheel이 있는 `tensorflow==2.21.0`을 설치한다. TF-IDF 저장 모델의 학습 버전에 맞춰 scikit-learn 1.7.2를 고정한다. 이미지 빌드 중 고정 Hugging Face dataset revision `915d7784e3c81333d6812913b0a80eda37fdbd41`에서 가중치 네 파일을 받고, Git에 있는 토크나이저·설정 파일 네 개와 함께 파일별 SHA-256을 확인한다. 검증 실패 시 빌드가 실패한다. 가중치 합계는 458,744,889바이트(약 437.5MiB)이며, 의존성과 빌드 캐시 때문에 최초 빌드에는 수 GiB 다운로드와 최소 10~15GiB의 여유 디스크를 예상한다.

KLUE-BERT JSON 세 파일은 Git blob이 LF인데 Windows 체크아웃에서는 CRLF로 확장된다. 설치 스크립트는 CRLF를 Git의 LF 바이트로 되돌린 뒤 해시를 검증하고 이미지에 복사한다. LSTM JSON은 체크아웃과 Git blob의 해시가 같다. 매니페스트에는 Git blob 기준 SHA-256을 기록해야 Linux 체크아웃에서도 같은 결과가 나온다.

```bash
docker build -t review-sentiment-api:local .
```

2026-09-25 ARM64 조사: 로컬 Docker Desktop의 `--platform linux/arm64 --target runtime-deps`에서 Python 3.11과 OpenJDK 17 설치, PyTorch 2.12.1+cpu ARM64 wheel 설치, TensorFlow 2.21.0 ARM64 wheel을 포함한 모든 API 의존성 해결·다운로드와 LIME wheel 빌드가 성공했다. QEMU에서 마지막 pip 설치가 장시간 진행되어 빌드를 중단했다. **ARM64 이미지 완성, 모델 로드·예측, 12GiB 인스턴스 내 메모리와 지연은 아직 검증되지 않았다.** 이 조사는 로컬 Docker만 사용했고 클라우드 자원은 만들지 않았다.

이미지에는 DB 접속 정보나 비밀값을 넣지 않는다. 실행 시 `DATABASE_URL`, `RATE_LIMIT_SALT`(16자 이상), `CORS_ORIGINS`를 환경변수로 주입한다. 프록시 뒤에 배포하면 실제 `X-Forwarded-For` 구성에 맞는 `TRUSTED_PROXY_HOPS`도 설정한다. `DATABASE_URL`이 접근하는 PostgreSQL에는 API 시작 전에 마이그레이션을 적용해야 한다. 예를 들어 배포 환경의 비밀값을 담은 Git 비추적 env 파일을 사용한다.

```bash
docker run --rm --env-file /path/outside/repository/api.env review-sentiment-api:local python -m alembic -c backend/alembic.ini upgrade head
docker run --rm --env-file /path/outside/repository/api.env -p 8000:8000 review-sentiment-api:local
```

모델 디렉터리 변수 `TFIDF_ARTIFACT_DIR`, `LSTM_ARTIFACT_DIR`, `KLUE_BERT_ARTIFACT_DIR`는 이미지에 설정되어 있다. 컨테이너의 `GET /healthz`는 생존 확인용이다. 최종 이미지에서 로컬 PostgreSQL 연결, 세 모델 예측·LIME 설명, 500/501자 경계가 통과했다. Next.js 화면에서도 세 모델 설명을 확인했고, 390px 화면에서 가로 넘침이 없었다. 세 모델과 웹 테스트 호출 뒤 메모리는 3.089GiB, 이미지 크기는 1,859,760,902바이트였다. 콜드 스타트·동시 부하·메모리 최대치와 공개 주소 검증은 남아 있으므로 공개 이관 완료는 아니다.
