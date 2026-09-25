import { MAX_REVIEW_LENGTH } from "@/constants";

export function reviewLength(text: string): number {
  return Array.from(text).length;
}

export function validReview(text: string): boolean {
  const length = reviewLength(text);
  return length >= 1 && length <= MAX_REVIEW_LENGTH && text.trim().length > 0;
}
