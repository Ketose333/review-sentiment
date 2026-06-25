"""review-sentiment Streamlit app — review input -> model select -> prediction.

Per PRD §18: review text is never persisted server-side (session-only widget state).
"""

import json
import os

import pandas as pd
import streamlit as st

import re


# >>> AUTO-SYNCED from src/preprocessing/stopwords.py (run scripts/sync_standalone_app.py) >>>
KOREAN_STOPWORDS: set[str] = {
    "의", "가", "이", "은", "들", "는", "좀", "잘", "걍", "과",
    "도", "를", "으로", "자", "에", "와", "한", "하다", "에서", "께서",
    "이다", "있다", "되다", "그", "저", "것", "수", "등", "들이", "에게",
    "보다", "만", "에는", "라서", "이라", "랑", "이랑", "거", "것을",
    "다", "을", "고", "지", "면", "게", "도요",
}
# <<< AUTO-SYNCED <<<


# >>> AUTO-SYNCED from src/preprocessing/tokenizer.py (run scripts/sync_standalone_app.py) >>>
import os


import re


def _register_jvm_dll_dir() -> None:
    """Windows: put the JDK's jvm.dll on the DLL search path before konlpy imports jpype.

    `_jpype.pyd` depends on jvm.dll at import time; konlpy/jpype don't register its
    directory, so standalone scripts (e.g. compute_eda.py) fail with
    "DLL load failed while importing _jpype". No-op on Linux/macOS — os.add_dll_directory
    doesn't exist there (Streamlit Cloud installs the JVM via packages.txt instead).
    """
    if not hasattr(os, "add_dll_directory"):
        return

    # Import TensorFlow (if installed) before the JDK's bin dir goes on the DLL
    # search path: the JDK ships an older msvcp140/vcruntime140 that, once on the
    # search path, gets picked up by TensorFlow's native module instead of the
    # system CRT, crashing with "DLL initialization routine could not be run"
    # (0x45A). Importing TF first lets it resolve its CRT deps cleanly, regardless
    # of which model the caller ends up loading later.
    try:
        import tensorflow  # noqa: F401
    except ImportError:
        pass

    java_home = os.environ.get("JAVA_HOME")
    if not java_home:
        return
    for sub in ("bin", os.path.join("bin", "server")):
        candidate = os.path.join(java_home, sub)
        if os.path.isdir(candidate):
            try:
                os.add_dll_directory(candidate)
            except OSError:
                pass


_register_jvm_dll_dir()


from konlpy.tag import Okt


_HANGUL_PATTERN = re.compile(r"[^ㄱ-ㅎㅏ-ㅣ가-힣\s]")


_okt = Okt()


def clean_text(text: str) -> str:
    """Strips text down to Korean syllables/jamo and whitespace only.

    Removes emoji, special characters, punctuation, digits, and Latin script.
    """
    return _HANGUL_PATTERN.sub("", text or "")


def tokenize(text: str, remove_stopwords: bool = True) -> list[str]:
    """Cleans, morphologically tokenizes (Okt, stemmed), and filters stopwords/empties.

    Returns [] for empty/whitespace-only/non-Korean input — callers must handle the
    empty-list case explicitly (PRD §14 edge cases: special chars / emoji-only input).
    """
    cleaned = clean_text(text).strip()
    if not cleaned:
        return []

    morphs = _okt.morphs(cleaned, stem=True)
    tokens = [m for m in morphs if m.strip()]
    if remove_stopwords:
        tokens = [t for t in tokens if t not in KOREAN_STOPWORDS]
    return tokens


def preprocess_for_vectorizer(text: str) -> str:
    """tokenize(text) joined with single spaces — the exact string consumed by
    the TF-IDF vectorizer at both train time and inference time."""
    return " ".join(tokenize(text))
# <<< AUTO-SYNCED <<<


import glob

# >>> AUTO-SYNCED from src/models/base.py (run scripts/sync_standalone_app.py) >>>
class ModelLoadError(Exception):
    """Raised when a model's artifacts cannot be loaded (missing/corrupt files)."""


class EmptyInputError(Exception):
    """Raised when preprocessing yields no tokens for the given input (PRD §14 edge case)."""
# <<< AUTO-SYNCED <<<


# >>> AUTO-SYNCED from src/evaluation/metrics.py (run scripts/sync_standalone_app.py) >>>
def build_comparison_table(results: dict[str, dict]) -> pd.DataFrame:
    """results = {model_display_name: {"accuracy":..., "precision":..., "recall":..., "f1":...}}."""
    if not results:
        return pd.DataFrame(columns=["Accuracy", "Precision", "Recall", "F1"])

    df = pd.DataFrame(results).T
    df = df.rename(
        columns={
            "accuracy": "Accuracy",
            "precision": "Precision",
            "recall": "Recall",
            "f1": "F1",
        }
    )
    return df[["Accuracy", "Precision", "Recall", "F1"]]


def load_all_metrics(models_dir: str = "models") -> dict[str, dict]:
    """Scans models/*/metrics.json. Model display name comes from a "display_name" key
    inside each metrics.json (falls back to the directory name if absent)."""
    results: dict[str, dict] = {}
    for metrics_path in sorted(glob.glob(os.path.join(models_dir, "*", "metrics.json"))):
        with open(metrics_path, encoding="utf-8") as f:
            data = json.load(f)
        model_dir_name = os.path.basename(os.path.dirname(metrics_path))
        display_name = data.pop("display_name", model_dir_name)
        results[display_name] = data
    return results
# <<< AUTO-SYNCED <<<


# ----- 모델 1: TF-IDF + LogisticRegression -----
import joblib

LABEL_MAP = {0: "부정", 1: "긍정"}


def _tfidf_load(model_dir: str = "models/tfidf_lr"):
    vectorizer_path = os.path.join(model_dir, "vectorizer.pkl")
    model_path = os.path.join(model_dir, "model.pkl")
    if not os.path.exists(vectorizer_path) or not os.path.exists(model_path):
        raise ModelLoadError(f"TF-IDF model artifacts not found in {model_dir}")
    return joblib.load(vectorizer_path), joblib.load(model_path)


class TfidfLRModel:
    def __init__(self, vectorizer, model):
        self.vectorizer = vectorizer
        self.model = model

    def predict_proba(self, raw_text: str):
        processed = preprocess_for_vectorizer(raw_text)
        if not processed:
            raise EmptyInputError("No tokens remain after preprocessing")
        X = self.vectorizer.transform([processed])
        probabilities = self.model.predict_proba(X)[0]
        predicted_class = probabilities.argmax()
        return LABEL_MAP[predicted_class], float(probabilities[predicted_class])


# ----- 모델 2: LSTM (tensorflow는 이 모델이 실제로 선택됐을 때만 지연 import) -----
LSTM_MAX_LEN = 40


def _lstm_to_sequences(tokenizer, corpus):
    from tensorflow.keras.preprocessing.sequence import pad_sequences

    sequences = tokenizer.texts_to_sequences(corpus)
    return pad_sequences(sequences, maxlen=LSTM_MAX_LEN, padding="post", truncating="post")


def _lstm_load(model_dir: str = "models/lstm"):
    import tensorflow as tf

    model_path = os.path.join(model_dir, "model.h5")
    tokenizer_path = os.path.join(model_dir, "tokenizer.json")
    if not os.path.exists(model_path) or not os.path.exists(tokenizer_path):
        raise ModelLoadError(f"LSTM model artifacts not found in {model_dir}")
    model = tf.keras.models.load_model(model_path)
    with open(tokenizer_path, encoding="utf-8") as f:
        tokenizer = tf.keras.preprocessing.text.tokenizer_from_json(f.read())
    return tokenizer, model


class LSTMModel:
    def __init__(self, tokenizer, model):
        self.tokenizer = tokenizer
        self.model = model

    def predict_proba(self, raw_text: str):
        processed = preprocess_for_vectorizer(raw_text)
        if not processed:
            raise EmptyInputError("No tokens remain after preprocessing")
        X = _lstm_to_sequences(self.tokenizer, pd.Series([processed]))
        positive_proba = float(self.model.predict(X, verbose=0).ravel()[0])
        predicted_class = 1 if positive_proba >= 0.5 else 0
        confidence = positive_proba if predicted_class == 1 else 1 - positive_proba
        return LABEL_MAP[predicted_class], confidence


# ----- 모델 3: KLUE-BERT (torch/transformers도 이 모델이 실제로 선택됐을 때만 지연 import) -----
BERT_MAX_LEN = 64


def _bert_load(model_dir: str = "models/klue_bert"):
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    has_weights = any(
        os.path.exists(os.path.join(model_dir, name))
        for name in ("model.safetensors", "pytorch_model.bin")
    )
    if not has_weights:
        raise ModelLoadError(f"KLUE-BERT model artifacts not found in {model_dir}")
    tokenizer = AutoTokenizer.from_pretrained(model_dir)
    model = AutoModelForSequenceClassification.from_pretrained(model_dir)
    model.eval()
    return tokenizer, model


class KlueBertModel:
    def __init__(self, tokenizer, model):
        self.tokenizer = tokenizer
        self.model = model

    def predict_proba(self, raw_text: str):
        import torch

        stripped = raw_text.strip()
        if not stripped:
            raise EmptyInputError("Empty input text")
        inputs = self.tokenizer(stripped, truncation=True, max_length=BERT_MAX_LEN, return_tensors="pt")
        with torch.no_grad():
            logits = self.model(**inputs).logits
        probabilities = torch.softmax(logits, dim=-1)[0]
        predicted_class = int(probabilities.argmax())
        return LABEL_MAP[predicted_class], float(probabilities[predicted_class])


# ----- 모델 레지스트리 -----
MODEL_REGISTRY = {
    "TF-IDF + LogisticRegression": {"loader": lambda: TfidfLRModel(*_tfidf_load())},
    "LSTM": {"loader": lambda: LSTMModel(*_lstm_load())},
    "KLUE-BERT": {"loader": lambda: KlueBertModel(*_bert_load())},
}


def get_available_models() -> list:
    return list(MODEL_REGISTRY.keys())


def load_model(display_name: str):
    entry = MODEL_REGISTRY.get(display_name)
    if entry is None:
        raise ModelLoadError(f"Unknown model: {display_name}")
    try:
        return entry["loader"]()
    except ModelLoadError:
        raise
    except Exception as exc:
        raise ModelLoadError(f"Failed to load model '{display_name}': {exc}") from exc


# ----- LIME 기반 예측 근거 -----
import numpy as np
from lime.lime_text import LimeTextExplainer

# >>> AUTO-SYNCED from src/explainability/lime_explainer.py (run scripts/sync_standalone_app.py) >>>
_CLASS_NAMES = ["부정", "긍정"]


_LABEL_TO_INDEX = {"부정": 0, "긍정": 1}


def _make_classifier_fn(model):
    def classifier_fn(texts: list[str]) -> np.ndarray:
        probs = np.full((len(texts), 2), 0.5)
        for i, text in enumerate(texts):
            try:
                label, confidence = model.predict_proba(text)
            except EmptyInputError:
                continue
            idx = _LABEL_TO_INDEX[label]
            probs[i, idx] = confidence
            probs[i, 1 - idx] = 1 - confidence
        return probs

    return classifier_fn


def explain(model, text: str, num_features: int = 8, num_samples: int = 300) -> list[tuple[str, float]]:
    """Returns [(word, weight), ...] for the predicted-긍정 direction.

    Positive weight pushes the prediction toward 긍정, negative toward 부정.
    """
    explainer = LimeTextExplainer(class_names=_CLASS_NAMES)
    exp = explainer.explain_instance(
        text,
        _make_classifier_fn(model),
        num_features=num_features,
        num_samples=num_samples,
        labels=(1,),
    )
    return exp.as_list(label=1)
# <<< AUTO-SYNCED <<<


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
        if predict_clicked and not stripped:
            st.warning("리뷰 텍스트를 입력해주세요.")
        elif predict_clicked:
            try:
                model = _cached_load_model(model_name)
            except ModelLoadError:
                st.error(f"{model_name} 모델을 불러올 수 없습니다. TF-IDF 모델을 사용해보세요.")
            else:
                # 비한글(이모지·특수문자) 입력은 Okt 없이 값싼 clean_text로 사전 차단.
                # 토큰이 모두 불용어인 경우는 predict_proba가 EmptyInputError로 처리하므로
                # 여기서 Okt tokenize()를 또 호출하지 않는다(예측 1회당 Okt 1회로 축소).
                if not clean_text(stripped):
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
                            st.metric(label=f"예측 결과 {emoji}", value=label)
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

        best_model = comparison_df["F1"].idxmax()
        st.success(f"🏆 F1 기준 최고 성능 모델: **{best_model}** (F1 {comparison_df.loc[best_model, 'F1']:.4f})")

        st.divider()
        st.dataframe(comparison_df, use_container_width=True)
        # stack=False: Accuracy/F1을 누적이 아닌 그룹 막대로 표시(누적 시 ~1.7로 차올라 오해 소지)
        st.bar_chart(comparison_df[["Accuracy", "F1"]], stack=False)

        for model_display_name, metrics in all_metrics.items():
            note = metrics.get("note")
            if note:
                st.info(f"**{model_display_name}**: {note}")

with tab_eda:
    eda_stats = _load_eda_stats()
    if eda_stats is None:
        st.info("EDA 통계가 아직 생성되지 않았습니다. `python scripts/compute_eda.py`를 실행해주세요.")
    else:
        label_counts = eda_stats["label_counts"]
        total = sum(label_counts.values())
        hist = eda_stats["length_histogram"]
        bin_edges = hist["bin_edges"]
        # 히스토그램 빈 중앙값 가중평균으로 평균 길이 근사
        bin_centers = [(bin_edges[i] + bin_edges[i + 1]) / 2 for i in range(len(bin_edges) - 1)]
        mean_length = sum(c * n for c, n in zip(bin_centers, hist["counts"])) / total if total else 0

        sum_cols = st.columns(4)
        sum_cols[0].metric("총 학습 리뷰", f"{total:,}건")
        sum_cols[1].metric("긍정 비율", f"{label_counts.get('긍정', 0) / total:.1%}" if total else "-")
        sum_cols[2].metric("부정 비율", f"{label_counts.get('부정', 0) / total:.1%}" if total else "-")
        sum_cols[3].metric("평균 길이", f"약 {mean_length:.0f}자")
        st.caption("레이블이 거의 5:5로 균형 잡혀 있어 정확도(Accuracy)를 주요 지표로 써도 무방합니다.")

        st.divider()
        st.markdown("**레이블 분포** — 긍정/부정 리뷰 수")
        label_df = pd.DataFrame({"건수": label_counts}, index=list(label_counts.keys()))
        st.bar_chart(label_df)

        st.divider()
        st.markdown("**리뷰 길이 분포** — 글자 수 기준 히스토그램")
        bin_labels = [f"{int(bin_edges[i])}~{int(bin_edges[i + 1])}" for i in range(len(bin_edges) - 1)]
        length_df = pd.DataFrame({"리뷰 수": hist["counts"]}, index=bin_labels)
        st.bar_chart(length_df)

        st.divider()
        tokenizer_label = "Okt 형태소 분석" if eda_stats.get("word_tokenizer") == "okt" else "간이 토크나이저(공백 분리)"
        st.markdown(f"**레이블별 빈출 단어 TOP 20** — {tokenizer_label} + 불용어 제거 후 집계")
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
