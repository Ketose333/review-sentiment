"""KLUE-BERT fine-tuning sentiment model: train/evaluate/save/load + inference wrapper.

CPU-only environment: trains/evaluates on a subset of NSMC (see scripts/train_klue_bert.py)
rather than the full 200k rows, since full fine-tuning needs a GPU (PRD §2.1, §22 risk).
Unlike TF-IDF/LSTM, raw text is fed straight to the BERT subword tokenizer (no Okt
morphological preprocessing) — that is how klue/bert-base's pretrained vocabulary expects input.
"""

import os

import torch
from torch.utils.data import DataLoader, Dataset
from transformers import AutoModelForSequenceClassification, AutoTokenizer

from src.evaluation.metrics import compute_metrics
from src.models.base import EmptyInputError, ModelLoadError

MODEL_NAME = "klue/bert-base"
LABEL_MAP = {0: "부정", 1: "긍정"}
MAX_LEN = 64


class _NSMCDataset(Dataset):
    def __init__(self, texts, labels, tokenizer):
        self.encodings = tokenizer(
            list(texts), truncation=True, padding=True, max_length=MAX_LEN, return_tensors="pt"
        )
        self.labels = torch.tensor(labels.to_numpy(), dtype=torch.long)

    def __len__(self):
        return len(self.labels)

    def __getitem__(self, idx):
        item = {key: val[idx] for key, val in self.encodings.items()}
        item["labels"] = self.labels[idx]
        return item


def train(train_df, epochs: int = 2, batch_size: int = 16, lr: float = 2e-5):
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    model = AutoModelForSequenceClassification.from_pretrained(MODEL_NAME, num_labels=2)

    dataset = _NSMCDataset(train_df["document"], train_df["label"], tokenizer)
    loader = DataLoader(dataset, batch_size=batch_size, shuffle=True)

    optimizer = torch.optim.AdamW(model.parameters(), lr=lr)
    model.train()
    for epoch in range(epochs):
        total_loss = 0.0
        for step, batch in enumerate(loader):
            optimizer.zero_grad()
            outputs = model(**batch)
            outputs.loss.backward()
            optimizer.step()
            total_loss += outputs.loss.item()
            if step % 100 == 0:
                print(f"epoch={epoch} step={step}/{len(loader)} loss={outputs.loss.item():.4f}")
        print(f"epoch={epoch} done, avg_loss={total_loss / len(loader):.4f}")

    return tokenizer, model


def evaluate(tokenizer, model, test_df, batch_size: int = 16) -> dict:
    dataset = _NSMCDataset(test_df["document"], test_df["label"], tokenizer)
    loader = DataLoader(dataset, batch_size=batch_size, shuffle=False)

    model.eval()
    all_preds = []
    with torch.no_grad():
        for batch in loader:
            labels = batch.pop("labels")
            outputs = model(**batch)
            preds = outputs.logits.argmax(dim=-1)
            all_preds.extend(preds.tolist())

    return compute_metrics(test_df["label"].to_numpy(), all_preds)


def save(tokenizer, model, out_dir: str = "models/klue_bert") -> None:
    os.makedirs(out_dir, exist_ok=True)
    model.save_pretrained(out_dir, safe_serialization=False)
    tokenizer.save_pretrained(out_dir)


def load(model_dir: str = "models/klue_bert"):
    if not os.path.exists(os.path.join(model_dir, "pytorch_model.bin")):
        raise ModelLoadError(f"KLUE-BERT model artifacts not found in {model_dir}")
    tokenizer = AutoTokenizer.from_pretrained(model_dir)
    model = AutoModelForSequenceClassification.from_pretrained(model_dir)
    model.eval()
    return tokenizer, model


class KlueBertModel:
    def __init__(self, tokenizer, model):
        self.tokenizer = tokenizer
        self.model = model

    def predict_proba(self, raw_text: str) -> tuple[str, float]:
        stripped = raw_text.strip()
        if not stripped:
            raise EmptyInputError("Empty input text")

        inputs = self.tokenizer(stripped, truncation=True, max_length=MAX_LEN, return_tensors="pt")
        with torch.no_grad():
            logits = self.model(**inputs).logits
        probabilities = torch.softmax(logits, dim=-1)[0]
        predicted_class = int(probabilities.argmax())
        confidence = float(probabilities[predicted_class])
        return LABEL_MAP[predicted_class], confidence
