import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { expect, test } from "vitest";
import { MAX_REVIEW_LENGTH, PRESET_REVIEWS } from "../src/constants";
import { ExplanationOption, ExplanationPanel, ModelPicker } from "../src/components/analysis/AnalysisWorkspace";
import { reviewLength, validReview } from "../src/lib/review";
import type { AnalysisResult, ModelInfo } from "../src/types";

const ids = ["tfidf_lr", "lstm", "klue_bert"];

function model(modelId: string, available = true, explanationAvailable = true): ModelInfo {
  return {
    modelId, displayName: modelId, version: "v1", available, explanationAvailable,
    metrics: { accuracy: 0.8, precision: 0.8, recall: 0.8, f1: 0.8 },
    evaluation: { dataset: "NSMC", testSet: "full", testCount: 50000, sampleSeed: null },
  };
}

function analysis(modelId: string, failed = false): AnalysisResult {
  return {
    analysisId: "analysis-1", status: "SUCCEEDED", modelId, modelVersion: "v1",
    label: "긍정", confidence: 0.8, durationMs: 12, explanationAvailable: true,
    explanation: failed
      ? { status: "FAILED", method: "LIME", errorCode: "EXPLANATION_FAILED" }
      : { status: "SUCCEEDED", method: "LIME", direction: "POSITIVE", sampleCount: 30, features: [{ token: "재미", weight: 0.2 }] },
    createdAt: "2026-09-23T00:00:00Z", completedAt: "2026-09-23T00:00:00Z", expiresAt: "2026-09-24T00:00:00Z",
  };
}

test("500 코드 포인트는 허용하고 501 코드 포인트는 거절한다", () => {
  expect(MAX_REVIEW_LENGTH).toBe(500);
  expect(reviewLength("😀".repeat(500))).toBe(500);
  expect(validReview("😀".repeat(500))).toBe(true);
  expect(validReview("😀".repeat(501))).toBe(false);
  expect(validReview(" ".repeat(500))).toBe(false);
  expect(PRESET_REVIEWS.every((item) => reviewLength(item.text) <= MAX_REVIEW_LENGTH)).toBe(true);
});

test("서버가 사용 가능하다고 표시한 세 모델만 선택할 수 있다", () => {
  const models = ids.map((id) => model(id));
  const enabled = renderToStaticMarkup(createElement(ModelPicker, { models, selected: "lstm", onSelect: () => {}, disabled: false }));
  expect((enabled.match(/type="radio"/g) ?? [])).toHaveLength(3);
  expect(enabled).not.toContain("사용 불가");
  const unavailable = renderToStaticMarkup(createElement(ModelPicker, { models: [model("tfidf_lr"), model("lstm", false), model("klue_bert", false)], selected: "tfidf_lr", onSelect: () => {}, disabled: false }));
  expect((unavailable.match(/type="radio"[^>]*disabled=""/g) ?? [])).toHaveLength(2);
  expect(unavailable).toContain("사용 불가");
});

test.each(ids)("%s 설명 선택과 설명 성공·실패 화면을 표시한다", (modelId) => {
  const option = renderToStaticMarkup(createElement(ExplanationOption, { model: model(modelId), checked: false, disabled: false, onChange: () => {} }));
  expect(option).toContain("단어별 예측 근거도 보기");
  expect(renderToStaticMarkup(createElement(ExplanationOption, { model: model(modelId, true, false), checked: false, disabled: false, onChange: () => {} }))).toBe("");
  const success = renderToStaticMarkup(createElement(ExplanationPanel, { result: analysis(modelId) }));
  expect(success).toContain("LIME");
  expect(success).toContain("재미");
  const failure = renderToStaticMarkup(createElement(ExplanationPanel, { result: analysis(modelId, true) }));
  expect(failure).toContain("감성 예측은 완료됐지만 설명을 생성하지 못했습니다");
});
