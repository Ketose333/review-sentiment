import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { ApiError, createAnalysis } from "../src/lib/api/client";
import { contribution, explanationRequested } from "../src/lib/explanation";

beforeEach(() => vi.stubEnv("NEXT_PUBLIC_API_URL", "http://localhost:8000"));
afterEach(() => { vi.unstubAllGlobals(); vi.unstubAllEnvs(); });

const result = {
  analysisId: "550e8400-e29b-41d4-a716-446655440000",
  status: "SUCCEEDED",
  modelId: "tfidf_lr",
  modelVersion: "artifact-version",
  label: "긍정",
  confidence: 0.8,
  durationMs: 12,
  explanationAvailable: true,
  createdAt: "2026-09-23T00:00:00Z",
  completedAt: "2026-09-23T00:00:00Z",
  expiresAt: "2026-09-24T00:00:00Z",
};

test.each(["tfidf_lr", "lstm", "klue_bert"])("%s 설명 선택 여부에 따라 요청 필드가 정확히 달라진다", async (modelId) => {
  const fetchMock = vi.fn(async (...args: [string, RequestInit?]) => {
    void args;
    return new Response(JSON.stringify(result), { status: 201, headers: { "X-Request-Id": "request-1" } });
  });
  vi.stubGlobal("fetch", fetchMock);
  await createAnalysis("영화가 재미있어요", modelId);
  await createAnalysis("영화가 재미있어요", modelId, true);
  const firstOptions = fetchMock.mock.calls[0][1] as RequestInit;
  const secondOptions = fetchMock.mock.calls[1][1] as RequestInit;
  expect(JSON.parse(firstOptions.body as string)).toEqual({ text: "영화가 재미있어요", modelId });
  expect(JSON.parse(secondOptions.body as string)).toEqual({ text: "영화가 재미있어요", modelId, includeExplanation: true });
  expect(firstOptions.cache).toBe("no-store");
});

test("422 설명 미지원 오류는 원문 없이 요청 ID만 전달한다", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ error: { code: "EXPLANATION_UNSUPPORTED", message: "원문을 담은 서버 메시지" } }), { status: 422, headers: { "X-Request-Id": "request-2" } })));
  await expect(createAnalysis("개인 입력", "tfidf_lr", true)).rejects.toMatchObject({ status: 422, code: "EXPLANATION_UNSUPPORTED", requestId: "request-2" });
  try { await createAnalysis("개인 입력", "tfidf_lr", true); } catch (error) {
    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).message).not.toContain("개인 입력");
    expect((error as ApiError).message).not.toContain("원문을 담은");
  }
});

test("긍정 방향의 부호와 서버가 반환한 설명 가용성을 구분한다", () => {
  expect(contribution(0.21)).toEqual({ label: "긍정 기여", tone: "positive" });
  expect(contribution(-0.12)).toEqual({ label: "부정 기여", tone: "negative" });
  expect(explanationRequested(true, true)).toBe(true);
  expect(explanationRequested(false, true)).toBe(false);
  expect(explanationRequested(true, false)).toBe(false);
});
