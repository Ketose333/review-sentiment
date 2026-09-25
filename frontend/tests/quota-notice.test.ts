import { expect, test } from "vitest";
import { errorNotice } from "../src/components/analysis/AnalysisWorkspace";
import { ApiError } from "../src/lib/api/client";

test.each([
  new ApiError(0, "NETWORK_ERROR", null, null),
  new ApiError(503, "UNKNOWN_ERROR", null, null),
  new ApiError(502, "UNKNOWN_ERROR", null, null),
  new ApiError(504, "UNKNOWN_ERROR", null, null),
])("$code 장애에는 서버 한도 가능성과 잔액 확인 한계를 알린다", (error) => {
  const notice = errorNotice(error);

  expect(notice.body).toContain("서버 한도 소진 또는 일시적인 서비스 장애일 수 있습니다");
  expect(notice.body).toContain("현재 앱은 Modal 잔액을 실시간 조회하지 못합니다");
  expect(notice.body).toContain("잠시 후 다시 시도해 주세요");
  expect(notice.body).toContain("월간 사용량 초기화 후 복구될 수 있습니다");
  expect(notice.quotaPossible).toBe(true);
  expect(notice.body).not.toContain("추가 요금은 발생하지 않습니다");
  expect(notice.body).not.toContain("다음 달에 다시 시도");
});

test("모델 사용 불가 503은 모델 상태와 무료 한도 가능성을 함께 안내한다", () => {
  const notice = errorNotice(new ApiError(503, "MODEL_UNAVAILABLE", "request-2", "analysis-2"));

  expect(notice.title).toBe("모델을 사용할 수 없습니다");
  expect(notice.body).toContain("모델 서비스가 준비되지 않았습니다");
  expect(notice.body).toContain("서버 한도 소진 또는 일시적인 서비스 장애일 수 있습니다");
  expect(notice.requestId).toBe("request-2");
  expect(notice.analysisId).toBe("analysis-2");
});

test.each([
  ["SERVICE_BUSY", "요청이 많습니다", "잠시 기다린 뒤 다시 시도해 주세요."],
  ["REGISTRY_UNAVAILABLE", "서비스에 연결할 수 없습니다", "모델 목록 또는 분석 결과 저장소에 연결하지 못했습니다."],
])("503 %s는 원인에 맞게 안내하고 quota 복구 시점을 추정하지 않는다", (code, title, body) => {
  const notice = errorNotice(new ApiError(503, code, null, null));

  expect(notice.title).toBe(title);
  expect(notice.body).toContain(body);
  expect(notice.body).not.toContain("Modal 잔액");
  expect(notice.body).not.toContain("월간 사용량 초기화");
  expect(notice.quotaPossible).not.toBe(true);
});

test.each([
  { status: 429, code: "RATE_LIMITED", title: "요청이 많습니다", excludedText: "무료 컴퓨트 한도" },
  { status: 422, code: "INVALID_TEXT", title: "입력을 확인해 주세요", excludedText: "무료 컴퓨트 한도" },
  { status: 500, code: "INFERENCE_FAILED", title: "분석에 실패했습니다", excludedText: "무료 컴퓨트 한도" },
])("HTTP $status $code는 원래 오류 안내를 유지한다", ({ status, code, title, excludedText }) => {
  const notice = errorNotice(new ApiError(status, code, null, null));

  expect(notice.title).toBe(title);
  expect(notice.body).not.toContain(excludedText);
});
