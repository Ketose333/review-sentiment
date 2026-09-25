export type ModelInfo = {
  modelId: string;
  displayName: string;
  version: string;
  available: boolean;
  metrics: { accuracy: number; precision: number; recall: number; f1: number };
  evaluation: { dataset: string; testSet: string; testCount: number | null; sampleSeed: number | null };
  explanationAvailable: boolean;
};

export type Explanation =
  | { status: "SUCCEEDED"; method: "LIME"; direction: "POSITIVE"; sampleCount: number; features: { token: string; weight: number }[] }
  | { status: "FAILED"; method: "LIME"; errorCode: "EXPLANATION_FAILED" };

export type AnalysisResult = {
  analysisId: string;
  status: "SUCCEEDED";
  modelId: string;
  modelVersion: string;
  label: "긍정" | "부정";
  confidence: number;
  durationMs: number;
  explanationAvailable: boolean;
  explanation?: Explanation;
  createdAt: string;
  completedAt: string;
  expiresAt: string;
};

export type ApiErrorBody = {
  analysisId?: string;
  error?: { code?: string; message?: string; requestId?: string };
};

export type DatasetStats = {
  label_counts: Record<string, number>;
  length_histogram: { bin_edges: number[]; counts: number[] };
  top_words_by_label: Record<string, [string, number][]>;
  word_tokenizer: string;
};

export type LabelShare = { label: string; count: number; share: number };
export type LengthBin = { label: string; count: number; share: number };
export type WordFrequency = { word: string; frequency: number; share: number };
