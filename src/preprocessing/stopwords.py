"""Static Korean stopword list for NSMC review tokenization (particles, conjunctions, fillers)."""

KOREAN_STOPWORDS: set[str] = {
    "의", "가", "이", "은", "들", "는", "좀", "잘", "걍", "과",
    "도", "를", "으로", "자", "에", "와", "한", "하다", "에서", "께서",
    "이다", "있다", "되다", "그", "저", "것", "수", "등", "들이", "에게",
    "보다", "만", "에는", "라서", "이라", "랑", "이랑", "거", "것을",
    "다", "을", "고", "지", "면", "게", "도요",
}
