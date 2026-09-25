# 프런트엔드 다음 작업 — 이슈 #14

- 사이클: Normal
- 기준: [이관 완료 기준](../migration-parity.md), 현재 [API 계약](../api.md)
- 작업 워크트리: `E:\CAREER\repos\review-sentiment-frontend-11-next-client`

## 범위

1. 공개 입력 상한을 500 코드 포인트로 바꾸고 입력·문구·테스트를 맞춘다. 500자와 501자 경계를 검증한다.
2. API가 `available=true`로 돌려주는 TF-IDF·LSTM·KLUE-BERT를 선택할 수 있게 한다. 설명은 모델별 `explanationAvailable`과 사용자 선택으로 요청한다. 세 모델 예측 성공, 설명 성공/실패 UI를 검증한다.
3. 현재 선택 불가 상태는 API 가용성에 따라 유지한다. 백엔드가 아직 활성화되지 않은 모델을 클라이언트에서 임의로 선택 가능하게 만들지 않는다.
4. `npm test`, `npm run lint`, `npm run build`를 실행하고 결과를 보고한다.

## 책임과 금지

- 이 워크트리의 `frontend/` 파일만 수정한다. `backend/`·`src/`·`docs/STATUS.md`는 수정하지 않는다.
- 기존 미커밋 파일을 삭제하거나 재설정하지 않는다. 별도 지시 전에는 커밋·push·PR·머지를 하지 않는다. 새 브랜치/워크트리를 만들지 않는다. 현재 분리된 워크트리를 사용한다.
- 구현 후 변경 파일 절대경로, 설계 이유, 테스트 결과, 남은 제한을 메인에 보고한다. 코드 리뷰는 메인이 별도 에이전트에 요청한다.
