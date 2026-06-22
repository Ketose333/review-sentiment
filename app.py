"""review-sentiment Streamlit app — review input -> model select -> prediction.

Per PRD §18: review text is never persisted server-side (session-only widget state).
"""

import json
import os

import pandas as pd
import streamlit as st

from src.evaluation.metrics import build_comparison_table, load_all_metrics
from src.explainability.lime_explainer import explain
from src.models.base import EmptyInputError, ModelLoadError
from src.models.registry import get_available_models, load_model
from src.preprocessing.tokenizer import tokenize

st.set_page_config(page_title="review-sentiment", page_icon="🎬", layout="wide")

EDA_STATS_PATH = "models/eda/stats.json"
PRESET_REVIEWS = {
    "직접 입력": "",
    "👍 긍정 예시": "정말 재미있는 영화였어요. 배우들 연기와 연출이 훌륭했습니다.",
    "👎 부정 예시": "시간 낭비였다. 스토리도 엉성하고 연기도 별로였다.",
    "🤔 애매한 예시": "그냥 그랬다. 기대했던 것보다는 평범했음.",
    "✏️ 짧은 입력 예시": "ㅎㅎ",
}


@st.cache_resource(max_entries=1)
def _cached_load_model(display_name: str):
    return load_model(display_name)


@st.cache_data
def _load_eda_stats():
    if not os.path.exists(EDA_STATS_PATH):
        return None
    with open(EDA_STATS_PATH, encoding="utf-8") as f:
        return json.load(f)


with st.sidebar:
    st.title("🎬 영화 리뷰 감성 분석")
    st.caption("한국어 영화 리뷰 감성 분류 데모")
    model_name = st.selectbox("모델 선택", get_available_models())
    st.divider()
    st.markdown(
        "**데이터셋**: NSMC\n\n"
        "**전처리**: Okt + 불용어 제거\n\n"
        f"**현재 모델**: {model_name}"
    )

tab_predict, tab_compare, tab_eda, tab_about = st.tabs(
    ["🔍 예측", "📊 모델 성능 비교", "📈 데이터 탐색(EDA)", "ℹ️ 프로젝트 소개"]
)

with tab_predict:
    input_col, result_col = st.columns([3, 2])

    with input_col:
        preset_choice = st.selectbox("예시 리뷰 선택 (선택 시 자동 입력)", list(PRESET_REVIEWS.keys()))
        review_text = st.text_area(
            "영화 리뷰를 입력하세요",
            value=PRESET_REVIEWS[preset_choice],
            max_chars=500,
            height=160,
            key=f"review_input_{preset_choice}",
        )
        predict_clicked = st.button("예측하기", use_container_width=True)

    model = None
    label = confidence = None
    stripped = review_text.strip()

    with result_col:
        if not predict_clicked:
            st.info("왼쪽에 리뷰를 입력하고 예측하기를 눌러주세요.")
        elif not stripped:
            st.warning("리뷰 텍스트를 입력해주세요.")
        else:
            try:
                model = _cached_load_model(model_name)
            except ModelLoadError:
                st.error(f"{model_name} 모델을 불러올 수 없습니다. TF-IDF 모델을 사용해보세요.")
            else:
                if not tokenize(stripped):
                    st.warning("분석 가능한 텍스트가 없습니다. 한글 리뷰를 입력해주세요.")
                else:
                    try:
                        label, confidence = model.predict_proba(stripped)
                    except EmptyInputError:
                        st.warning("분석 가능한 텍스트가 없습니다. 한글 리뷰를 입력해주세요.")
                    else:
                        if len(stripped) <= 2:
                            st.warning("입력이 짧아 예측 신뢰도가 낮을 수 있습니다.")
                        emoji = "😊" if label == "긍정" else "😞"
                        positive_proba = confidence if label == "긍정" else 1 - confidence
                        with st.container(border=True):
                            st.metric(label=f"예측 결과 {emoji}", value=label, delta=f"{confidence:.0%} 신뢰도")
                            st.caption("긍정/부정 확률 분포")
                            st.progress(positive_proba, text=f"😊 긍정 {positive_proba:.0%}")
                            st.progress(1 - positive_proba, text=f"😞 부정 {1 - positive_proba:.0%}")

    if model is not None and label is not None:
        st.divider()
        with st.spinner("예측 근거 분석 중..."):
            try:
                word_weights = explain(model, stripped)
            except Exception:
                word_weights = []

        if word_weights:
            st.markdown("**단어별 예측 기여도** — 양수는 긍정 방향, 음수는 부정 방향으로 기여한 단어입니다.")
            weights_df = pd.DataFrame(word_weights, columns=["단어", "기여도"])
            weights_df = weights_df.set_index("단어").sort_values("기여도")
            st.bar_chart(weights_df)

with tab_compare:
    all_metrics = load_all_metrics()
    comparison_df = build_comparison_table(all_metrics)
    if comparison_df.empty:
        st.info("아직 학습된 모델 성능 데이터가 없습니다.")
    else:
        metric_cols = st.columns(len(comparison_df))
        for col, (model_display_name, row) in zip(metric_cols, comparison_df.iterrows()):
            col.metric(model_display_name, f"{row['Accuracy']:.1%}", help="Accuracy")

        st.divider()
        st.dataframe(comparison_df, use_container_width=True)
        st.bar_chart(comparison_df[["Accuracy", "F1"]])

        for model_display_name, metrics in all_metrics.items():
            note = metrics.get("note")
            if note:
                st.info(f"**{model_display_name}**: {note}")

with tab_eda:
    eda_stats = _load_eda_stats()
    if eda_stats is None:
        st.info("EDA 통계가 아직 생성되지 않았습니다. `python scripts/compute_eda.py`를 실행해주세요.")
    else:
        st.markdown("**레이블 분포** — 학습 데이터(150,000건) 기준")
        label_counts = eda_stats["label_counts"]
        label_df = pd.DataFrame({"건수": label_counts}, index=list(label_counts.keys()))
        st.bar_chart(label_df)

        st.divider()
        st.markdown("**리뷰 길이 분포** — 글자 수 기준 히스토그램")
        hist = eda_stats["length_histogram"]
        bin_edges = hist["bin_edges"]
        bin_labels = [f"{int(bin_edges[i])}~{int(bin_edges[i + 1])}" for i in range(len(bin_edges) - 1)]
        length_df = pd.DataFrame({"리뷰 수": hist["counts"]}, index=bin_labels)
        st.bar_chart(length_df)

        st.divider()
        st.markdown("**레이블별 빈출 단어 TOP 20** — Okt 형태소 분석 + 불용어 제거 후 집계")
        word_col_neg, word_col_pos = st.columns(2)
        for col, label_name in ((word_col_neg, "부정"), (word_col_pos, "긍정")):
            words_df = pd.DataFrame(eda_stats["top_words_by_label"][label_name], columns=["단어", "빈도"])
            words_df = words_df.set_index("단어").sort_values("빈도")
            col.caption(f"{label_name} 리뷰")
            col.bar_chart(words_df, horizontal=True)

with tab_about:
    st.subheader("NSMC 영화 리뷰 감성 분석")
    st.markdown(
        "Naver Sentiment Movie Corpus(NSMC) 20만 건의 영화 리뷰로 긍/부정 감성 분류 모델을 "
        "학습하고, 사용자 입력 리뷰의 감성을 예측하며 LIME으로 예측 근거 단어를 시각화하는 "
        "머신러닝 프로젝트입니다."
    )

    stat_cols = st.columns(3)
    stat_cols[0].metric("학습 데이터", "150,000건")
    stat_cols[1].metric("테스트 데이터", "50,000건")
    stat_cols[2].metric("레이블", "긍정 / 부정")

    st.divider()
    st.markdown("**비교 모델**")
    st.table(
        pd.DataFrame(
            [
                {"모델": "TF-IDF + LogisticRegression", "특징": "전통적 통계 기반, 빠른 추론"},
                {"모델": "LSTM", "특징": "Embedding → LSTM → Dense, 순차 문맥 학습"},
                {"모델": "KLUE-BERT", "특징": "사전학습 트랜스포머 파인튜닝"},
            ]
        )
    )
    st.caption("전처리: Okt 형태소 분석 + 불용어 제거 (KLUE-BERT는 서브워드 토크나이저 직접 사용)")
