# review-sentiment STATUS

마지막 갱신: 2026-06-24

> 완료된 기능의 전체 목록은 루트 [README.md](../README.md) "기능"을 정본으로 본다. 이 파일은 인프라 상태와 알려진 이슈를 추적한다.

## 인프라

| 항목 | 상태 |
| --- | --- |
| 모델 아티팩트 관리 | Git LFS (`*.pkl`, `*.h5`, `*.bin`, `*.safetensors`, `*.pt`, `*.onnx`) |
| Streamlit 배포 | ✅ 배포됨 — https://nsmc-sentiment.streamlit.app (Public) |
| Streamlit Python 버전 | **3.11 고정 필수** — 대시보드 ⋮ → Settings → Python version. 미고정 시 Python 3.14가 떠 tensorflow wheel 부재로 배포 크래시. `runtime.txt`(3.11)도 두지만 대시보드 설정이 확실함 |
| Java/JVM (Okt) | 로컬 JDK 17, Streamlit Cloud는 `packages.txt`(`default-jdk`)로 자동 설치 |

## 알려진 이슈

| 이슈 | 영향 | 대응 |
| --- | --- | --- |
| Windows에서 `pytest`·앱 첫 Okt 로드 시 faulthandler `access violation` 출력 | JVM 시작 시 JPype가 처리하는 시그널을 pytest faulthandler가 가로채 찍는 것. 테스트·앱·배포 동작에는 영향 없음 | Windows+JPype 특유의 무해한 현상, 무시 |
| `LimeTextExplainer`가 `random_state` 미고정 | 같은 모델·같은 텍스트라도 단어별 기여도 수치가 실행마다 소폭 다름(부호·순위는 안정적) | 버그 아님, LIME 고유 특성. `random_state` 고정은 개선 항목으로 남김 |
| (해결됨) self-contained 통합 직후 배포가 JVM SIGSEGV로 Aborted | `tensorflow`/`torch`/`transformers`를 모듈 최상단에서 즉시 import하면 Okt가 띄운 JVM과 PyTorch 네이티브 라이브러리가 같은 프로세스에 동시 적재되며 충돌 | 모델별 무거운 프레임워크 import는 각 로더 함수 안에서 지연 import로 유지 |

## 다음 작업

- [ ] LSTM 재학습 결과를 시드 고정 기준으로 재검증
- [ ] KLUE-BERT를 전체 데이터/GPU 환경에서 재학습해 성능 상한 확인
- [ ] TF-IDF·LIME 캡처를 self-contained 코드 기준으로 갱신
