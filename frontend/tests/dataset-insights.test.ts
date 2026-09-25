import { expect, test } from "vitest";
import { MAX_REVIEW_LENGTH, PRESET_REVIEWS } from "../src/constants";
import { datasetStats, labelShares, lengthBins, meanLength, tokenizerLabel, topWords } from "../src/lib/eda";
import { bestByF1, excludedFromComparison, isSampled } from "../src/lib/performance";
import type { ModelInfo } from "../src/types";

function model(modelId: string, f1: number, testSet: string): ModelInfo {
  return {
    modelId,
    displayName: modelId,
    version: "v1",
    available: true,
    metrics: { accuracy: f1, precision: f1, recall: f1, f1 },
    evaluation: { dataset: "NSMC", testSet, testCount: 5000, sampleSeed: 42 },
    explanationAvailable: false,
  };
}

test("레이블 분포는 긍정·부정 순서와 비율을 함께 제공한다", () => {
  const shares = labelShares();
  expect(shares.map((entry) => entry.label)).toEqual(["긍정", "부정"]);
  expect(shares.reduce((sum, entry) => sum + entry.share, 0)).toBeCloseTo(1, 10);
  expect(shares.every((entry) => entry.count > 0)).toBe(true);
});

test("평균 길이는 히스토그램 빈 중앙값의 가중평균이다", () => {
  const source = {
    label_counts: { 긍정: 1, 부정: 1 },
    length_histogram: { bin_edges: [0, 10, 20], counts: [3, 1] },
    top_words_by_label: { 긍정: [], 부정: [] },
    word_tokenizer: "okt",
  };
  // (5 * 3 + 15 * 1) / 4
  expect(meanLength(source)).toBeCloseTo(7.5, 10);
  expect(meanLength({ ...source, length_histogram: { bin_edges: [0, 10], counts: [0] } })).toBe(0);
});

test("길이 구간 막대는 최다 구간 기준으로 정규화된다", () => {
  const bins = lengthBins();
  expect(bins).toHaveLength(datasetStats.length_histogram.counts.length);
  expect(bins[0].label).toMatch(/^\d+~\d+$/);
  expect(Math.max(...bins.map((bin) => bin.share))).toBe(1);
  expect(bins.every((bin) => bin.share >= 0 && bin.share <= 1)).toBe(true);
});

test("빈출 단어는 빈도 내림차순이고 없는 레이블은 빈 배열이다", () => {
  const words = topWords("긍정");
  expect(words).toHaveLength(20);
  expect(words.map((entry) => entry.frequency)).toEqual([...words.map((entry) => entry.frequency)].sort((a, b) => b - a));
  expect(words[0].share).toBe(1);
  expect(topWords("없는 레이블")).toEqual([]);
});

test("토크나이저 표기는 생성 조건을 그대로 반영한다", () => {
  expect(tokenizerLabel()).toBe("Okt 형태소 분석");
  expect(tokenizerLabel({ ...datasetStats, word_tokenizer: "simple" })).toBe("간이 토크나이저(공백 분리)");
});

test("예시 리뷰는 모두 공개 입력 상한 안에 있다", () => {
  expect(PRESET_REVIEWS[0].text).toBe("");
  expect(PRESET_REVIEWS.length).toBeGreaterThan(1);
  for (const preset of PRESET_REVIEWS) {
    expect(Array.from(preset.text).length).toBeLessThanOrEqual(MAX_REVIEW_LENGTH);
  }
});

test("F1 최고 모델은 같은 평가 범위끼리만 고른다", () => {
  const models = [
    model("tfidf_lr", 0.82, "full test split"),
    model("lstm", 0.84, "full test split"),
    model("klue_bert", 0.99, "sampled 5000"),
  ];
  expect(isSampled(models[2])).toBe(true);
  const best = bestByF1(models);
  expect(best?.model.modelId).toBe("lstm");
  expect(best?.comparedCount).toBe(2);
  expect(excludedFromComparison(models).map((entry) => entry.modelId)).toEqual(["klue_bert"]);
});

test("비교할 대상이 없으면 최고 모델을 표시하지 않는다", () => {
  expect(bestByF1([])).toBeNull();
  expect(bestByF1([model("tfidf_lr", 0.82, "full test split")])).toBeNull();
  const sampledOnly = [model("a", 0.7, "sampled 5000"), model("b", 0.9, "sampled 5000")];
  expect(bestByF1(sampledOnly)?.model.modelId).toBe("b");
  expect(excludedFromComparison(sampledOnly)).toEqual([]);
});
