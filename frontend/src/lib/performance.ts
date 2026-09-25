import type { ModelInfo } from "@/types";

/** A sampled evaluation is not comparable with a full test split. */
export function isSampled(model: ModelInfo): boolean {
  return model.evaluation.testSet.toLowerCase().includes("sampled");
}

/**
 * Highest F1 among the models that share the widest comparable evaluation scope.
 *
 * The Streamlit tab named one best model across all rows, which the project's own
 * guidance contradicts: one model is scored on a 5,000-row sample and the others on the
 * full split. Comparing only inside one scope keeps the highlight honest, and it returns
 * null when there is nothing to compare.
 */
export function bestByF1(models: ModelInfo[]): { model: ModelInfo; comparedCount: number } | null {
  const full = models.filter((model) => !isSampled(model));
  const group = full.length > 1 ? full : models.length > 1 ? models : [];
  if (group.length === 0) return null;
  const best = group.reduce((leader, model) => (model.metrics.f1 > leader.metrics.f1 ? model : leader));
  if (!Number.isFinite(best.metrics.f1)) return null;
  return { model: best, comparedCount: group.length };
}

/** Models left out of the highlight because their evaluation scope differs. */
export function excludedFromComparison(models: ModelInfo[]): ModelInfo[] {
  const full = models.filter((model) => !isSampled(model));
  return full.length > 1 ? models.filter(isSampled) : [];
}
