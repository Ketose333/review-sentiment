/** Single source for the public input policy. The API rejects anything longer. */
export const MAX_REVIEW_LENGTH = 500;

/**
 * Same starting points the Streamlit demo offered, so the migrated screen is familiar.
 * Every preset stays inside MAX_REVIEW_LENGTH; `presets-fit` in the web tests pins that.
 */
export const PRESET_REVIEWS: { label: string; text: string }[] = [
  { label: "직접 입력", text: "" },
  { label: "긍정 예시", text: "정말 재미있는 영화였어요. 배우들 연기와 연출이 훌륭했습니다." },
  { label: "부정 예시", text: "시간 낭비였다. 스토리도 엉성하고 연기도 별로였다." },
  { label: "애매한 예시", text: "그냥 그랬다. 기대했던 것보다는 평범했음." },
  { label: "짧은 입력 예시", text: "ㅎㅎ" },
];

export const STREAMLIT_URL = "https://nsmc-sentiment.streamlit.app";

export const NAV_ITEMS = [
  { href: "/", label: "리뷰 분석" },
  { href: "/dataset", label: "데이터 탐색" },
  { href: "/about", label: "프로젝트 소개" },
] as const;
