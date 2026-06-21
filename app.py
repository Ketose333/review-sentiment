"""review-sentiment Streamlit app — review input -> model select -> prediction.

Per PRD §18: review text is never persisted server-side (session-only widget state).
"""

import streamlit as st

from src.evaluation.metrics import build_comparison_table, load_all_metrics
from src.models.base import EmptyInputError, ModelLoadError
from src.models.registry import get_available_models, load_model
from src.preprocessing.tokenizer import tokenize

st.set_page_config(page_title="review-sentiment", page_icon="🎬")
st.title("영화 리뷰 감성 분석")


@st.cache_resource
def _cached_load_model(display_name: str):
    return load_model(display_name)


review_text = st.text_area("영화 리뷰를 입력하세요", max_chars=500)
model_name = st.selectbox("모델 선택", get_available_models())
predict_clicked = st.button("예측하기")

if predict_clicked:
    stripped = review_text.strip()
    if not stripped:
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
                        st.caption("입력이 짧아 예측 신뢰도가 낮을 수 있습니다.")
                    st.metric(label="예측 결과", value=label, delta=f"{confidence:.0%}")

st.divider()
st.subheader("모델 성능 비교")
comparison_df = build_comparison_table(load_all_metrics())
if comparison_df.empty:
    st.info("아직 학습된 모델 성능 데이터가 없습니다.")
else:
    st.dataframe(comparison_df)
