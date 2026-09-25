export function contribution(weight: number): { label: string; tone: "positive" | "negative" | "neutral" } {
  if (weight > 0) return { label: "긍정 기여", tone: "positive" };
  if (weight < 0) return { label: "부정 기여", tone: "negative" };
  return { label: "중립", tone: "neutral" };
}

export function explanationRequested(explanationAvailable: boolean, checked: boolean): boolean {
  return explanationAvailable && checked;
}
