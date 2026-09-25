"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import { MAX_REVIEW_LENGTH, PRESET_REVIEWS } from "@/constants";
import { ApiError, createAnalysis, fetchModels } from "@/lib/api/client";
import { contribution, explanationRequested } from "@/lib/explanation";
import { bestByF1, excludedFromComparison } from "@/lib/performance";
import { reviewLength, validReview } from "@/lib/review";
import type { AnalysisResult, ModelInfo } from "@/types";

const MAX_LENGTH = MAX_REVIEW_LENGTH;

type Notice = { title: string; body: string; requestId: string | null; analysisId: string | null; quotaPossible?: boolean };

export function errorNotice(error: unknown): Notice {
  if (!(error instanceof ApiError)) {
    return { title: "연결할 수 없습니다", body: "잠시 후 다시 시도해 주세요.", requestId: null, analysisId: null };
  }
  const possibleQuotaNotice = {
    title: "현재 분석할 수 없습니다",
    body: "서버 한도 소진 또는 일시적인 서비스 장애일 수 있습니다. 현재 앱은 Modal 잔액을 실시간 조회하지 못합니다. 잠시 후 다시 시도해 주세요. 문제가 계속되면 월간 사용량 초기화 후 복구될 수 있습니다.",
    quotaPossible: true,
  };
  const messages: Record<number, { title: string; body: string }> = {
    413: { title: "요청 크기가 너무 큽니다", body: "입력 내용을 줄인 뒤 다시 시도해 주세요." },
    429: { title: "요청이 많습니다", body: "잠시 기다린 뒤 다시 시도해 주세요." },
    500: { title: "분석에 실패했습니다", body: "잠시 후 다시 시도해 주세요." },
  };
  let message: Pick<Notice, "title" | "body" | "quotaPossible"> | undefined = messages[error.status];
  if (error.status === 0 && error.code === "NETWORK_ERROR") {
    message = { ...possibleQuotaNotice, title: "서비스에 연결할 수 없습니다" };
  }
  if (error.status === 502 || error.status === 504) {
    message = possibleQuotaNotice;
  }
  if (error.status === 503) {
    if (error.code === "SERVICE_BUSY") {
      message = { title: "요청이 많습니다", body: "잠시 기다린 뒤 다시 시도해 주세요." };
    } else if (error.code === "REGISTRY_UNAVAILABLE") {
      message = { title: "서비스에 연결할 수 없습니다", body: "모델 목록 또는 분석 결과 저장소에 연결하지 못했습니다. 잠시 후 다시 시도해 주세요." };
    } else if (error.code === "MODEL_UNAVAILABLE") {
      message = { ...possibleQuotaNotice, title: "모델을 사용할 수 없습니다", body: `모델 서비스가 준비되지 않았습니다. ${possibleQuotaNotice.body}` };
    } else {
      message = possibleQuotaNotice;
    }
  }
  if (error.status === 422) {
    message = error.code === "EXPLANATION_UNSUPPORTED"
      ? { title: "설명을 제공하지 않습니다", body: "이 모델의 설명 기능을 사용할 수 없습니다. 모델 목록을 다시 확인해 주세요." }
      : error.code === "UNSUPPORTED_MODEL"
      ? { title: "모델을 선택해 주세요", body: "현재 사용할 수 있는 모델을 다시 선택해 주세요." }
      : { title: "입력을 확인해 주세요", body: `한국어 영화 리뷰를 1~${MAX_LENGTH}자 이내로 입력해 주세요.` };
  }
  if (!message) message = { title: "연결할 수 없습니다", body: "서비스 연결을 확인한 뒤 다시 시도해 주세요." };
  return { ...message, requestId: error.requestId, analysisId: error.analysisId };
}

function metric(value: number): string {
  return Number.isFinite(value) ? value.toFixed(4) : "—";
}

function evaluationScope(model: ModelInfo): string {
  const { dataset, testSet, testCount } = model.evaluation;
  const sampled = testSet.toLowerCase().includes("sampled");
  if (sampled) return `${dataset} 테스트${testCount !== null ? ` ${testCount.toLocaleString("ko-KR")}건` : ""} 표본`;
  return `${dataset} 테스트 전체 분할${testCount !== null ? ` (${testCount.toLocaleString("ko-KR")}건)` : ""}`;
}

function InfoIcon() {
  return <svg viewBox="0 0 20 20" aria-hidden="true" focusable="false"><circle cx="10" cy="10" r="8.5" fill="currentColor" /><path d="M10 8.4v5.1M10 6.3h.01" stroke="white" strokeWidth="1.8" strokeLinecap="round" /></svg>;
}

function QuotaNoticeDialog({ notice, onDismiss }: { notice: Notice; onDismiss: () => void }) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const dialog = dialogRef.current;
    if (dialog && !dialog.open) dialog.showModal();
    return () => { if (dialog?.open) dialog.close(); };
  }, []);
  return <dialog ref={dialogRef} className="quota-dialog" aria-labelledby="quota-dialog-title" onClose={onDismiss}>
    <div className="quota-dialog-content">
      <span className="quota-dialog-label">서비스 이용 안내</span>
      <h2 id="quota-dialog-title">{notice.title}</h2>
      <p>{notice.body}</p>
      {notice.requestId ? <p className="notice-id">요청 ID: {notice.requestId}</p> : null}
      {notice.analysisId ? <p className="notice-id">분석 ID: {notice.analysisId}</p> : null}
      <button type="button" className="quota-dialog-close" onClick={() => dialogRef.current?.close()}>확인</button>
    </div>
  </dialog>;
}

export function ModelPicker({ models, selected, onSelect, disabled }: { models: ModelInfo[]; selected: string; onSelect: (value: string) => void; disabled: boolean }) {
  const available = models.filter((model) => model.available);
  return <fieldset className="model-field">
    <legend className="field-label"><span className="desktop-only">분석 모델</span><span className="mobile-only">모델 선택</span></legend>
    <div className="model-options">
      {models.map((model) => <label key={model.modelId} className={`model-option ${selected === model.modelId ? "is-selected" : ""} ${model.available ? "" : "is-disabled"}`}>
        <input type="radio" name="model" value={model.modelId} checked={selected === model.modelId} disabled={!model.available || disabled} onChange={() => onSelect(model.modelId)} />
        <span className="radio-mark" aria-hidden="true" />
        <span className="model-option-content"><span className="model-option-name">{model.displayName}</span>
        {!model.available ? <span className="model-unavailable">사용 불가</span> : null}</span>
      </label>)}
    </div>
    <select className="model-select" value={selected} onChange={(event) => onSelect(event.target.value)} disabled={available.length === 0 || disabled} aria-label="분석 모델 선택">
      {available.length === 0 ? <option value="">사용 가능한 모델이 없습니다</option> : null}
      {models.map((model) => <option key={model.modelId} value={model.modelId} disabled={!model.available}>{model.displayName}{model.available ? "" : " (사용 불가)"}</option>)}
    </select>
    <div className="mobile-unavailable-list">
      {models.filter((model) => !model.available).map((model) => <div key={model.modelId}>{model.displayName}<span>선택 불가</span></div>)}
    </div>
  </fieldset>;
}

export function ExplanationPanel({ result }: { result: AnalysisResult }) {
  const explanation = result.explanation;
  if (!explanation || explanation.status === "FAILED") {
    return <div className="explanation-panel explanation-failed" role="status">
      <h3>예측 근거</h3><p>감성 예측은 완료됐지만 설명을 생성하지 못했습니다. 다시 분석해 주세요.</p>
    </div>;
  }
  const features = explanation.features.slice(0, 8);
  const maxWeight = Math.max(...features.map((feature) => Math.abs(feature.weight)), 0);
  return <div className="explanation-panel" aria-labelledby="explanation-heading">
    <h3 id="explanation-heading">예측 근거 <span>LIME</span></h3>
    <p className="explanation-caption">단어의 기여도를 긍정 방향 기준으로 표시합니다.</p>
    {features.length > 0 ? <ul className="feature-list">{features.map((feature, index) => {
      const direction = contribution(feature.weight);
      const width = maxWeight > 0 ? Math.max(4, Math.round(Math.abs(feature.weight) / maxWeight * 100)) : 4;
      return <li key={`${feature.token}-${index}`} className={`feature-item ${direction.tone}`}>
        <span className="feature-token">{feature.token}</span>
        <span className="feature-bar-track" aria-hidden="true"><span style={{ width: `${width}%` }} /></span>
        <span className="feature-value">{direction.label} {feature.weight > 0 ? "+" : ""}{feature.weight.toFixed(3)}</span>
      </li>;
    })}</ul> : <p className="explanation-caption">표시할 단어 기여도가 없습니다.</p>}
    <p className="explanation-privacy">설명 단어는 이 화면을 닫으면 사라집니다.</p>
  </div>;
}

export function ExplanationOption({ model, checked, disabled, onChange }: { model: ModelInfo | undefined; checked: boolean; disabled: boolean; onChange: (checked: boolean) => void }) {
  if (!model?.explanationAvailable) return null;
  return <label className="explanation-option"><input type="checkbox" checked={checked} disabled={disabled} onChange={(event) => onChange(event.target.checked)} /><span>단어별 예측 근거도 보기 <small>LIME 설명은 분석 시간이 더 걸릴 수 있습니다.</small></span></label>;
}

function ResultPanel({ result, requestId, notice, hasSubmitted, models, askedExplanation }: { result: AnalysisResult | null; requestId: string | null; notice: Notice | null; hasSubmitted: boolean; models: ModelInfo[]; askedExplanation: boolean }) {
  return <section className="result-section" aria-labelledby="result-heading" aria-live="polite">
    <h2 id="result-heading">분석 결과</h2>
    {result ? <div className="result-success">
      <div className="result-score">
        <div><span className="result-overline">감성 분류 결과</span><strong className={result.label === "긍정" ? "positive" : "negative"}>{result.label}</strong></div>
        <div className="confidence"><span>신뢰도</span><strong>{Math.round(result.confidence * 100)}%</strong></div>
      </div>
      <dl className="result-meta">
        <div><dt>분석 모델</dt><dd>{models.find((model) => model.modelId === result.modelId)?.displayName ?? result.modelId}</dd></div>
        <div><dt>분석 ID</dt><dd>{result.analysisId}</dd></div>
        <div><dt>모델 버전</dt><dd>{result.modelVersion}</dd></div>
        <div><dt>분석 일시</dt><dd>{new Intl.DateTimeFormat("ko-KR", { dateStyle: "medium", timeStyle: "short", timeZone: "Asia/Seoul" }).format(new Date(result.completedAt))}</dd></div>
        {requestId ? <div><dt>요청 ID</dt><dd>{requestId}</dd></div> : null}
      </dl>
      <p className="retention"><InfoIcon />리뷰 원문은 저장하지 않습니다. 분석 결과는 24시간 후 만료됩니다.</p>
    </div> : notice ? <div className="result-notice" role="alert">
      <strong>{notice.title}</strong><p>{notice.body}</p>
      {notice.analysisId ? <p className="notice-id">분석 ID: {notice.analysisId}</p> : null}
      {notice.requestId ? <p className="notice-id">요청 ID: {notice.requestId}</p> : null}
    </div> : <div className="result-empty">
      <div className="empty-heading"><InfoIcon /><strong>{hasSubmitted ? "분석을 준비하고 있습니다" : "리뷰를 입력한 후 분석하기를 눌러주세요."}</strong></div>
    </div>}
    {result && askedExplanation ? <ExplanationPanel result={result} /> : null}
  </section>;
}

function Performance({ models }: { models: ModelInfo[] }) {
  const best = bestByF1(models);
  const excluded = excludedFromComparison(models);
  return <section className="performance" aria-labelledby="performance-heading">
    <div className="performance-heading"><h2 id="performance-heading">모델 성능</h2></div>
    {best ? <p className="performance-best">
      <strong>F1 기준 최고 성능: {best.model.displayName}</strong> <span>F1 {metric(best.model.metrics.f1)}</span>
      <span className="performance-best-scope">같은 평가 범위의 {best.comparedCount}개 모델끼리 비교{excluded.length > 0 ? ` (${excluded.map((model) => model.displayName).join(", ")} 제외 — 표본 평가)` : ""}</span>
    </p> : null}
    {models.length > 0 ? <div className="performance-table-wrap"><table className="desktop-table">
      <thead><tr><th scope="col">모델</th><th scope="col">평가 데이터셋</th><th scope="col">Accuracy</th><th scope="col">F1</th></tr></thead>
      <tbody>{models.map((model) => <tr key={model.modelId}>
        <th scope="row">{model.displayName}</th><td>{evaluationScope(model)}</td><td>{metric(model.metrics.accuracy)}</td><td>{metric(model.metrics.f1)}</td>
      </tr>)}</tbody>
    </table><table className="mobile-table">
      <thead><tr><th scope="col">모델</th><th scope="col">Accuracy</th><th scope="col">F1</th><th scope="col">평가 데이터셋</th></tr></thead>
      <tbody>{models.map((model) => <tr key={model.modelId}>
        <th scope="row">{model.displayName}</th><td>{metric(model.metrics.accuracy)}</td><td>{metric(model.metrics.f1)}</td><td>{evaluationScope(model)}</td>
      </tr>)}</tbody>
    </table></div> : <p className="performance-unavailable">모델 성능 정보를 불러오지 못했습니다.</p>}
    <p className="evaluation-note"><InfoIcon /><span><strong>평가 범위를 확인해 주세요.</strong> 모델별 평가 조건이 다를 수 있으므로 수치를 단순 비교해 우열을 판단할 수 없습니다.</span></p>
  </section>;
}

export function AnalysisWorkspace() {
  const [models, setModels] = useState<ModelInfo[]>([]);
  const [selected, setSelected] = useState("");
  const [text, setText] = useState("");
  const [includeExplanation, setIncludeExplanation] = useState(false);
  const [loadingModels, setLoadingModels] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [resultRequestId, setResultRequestId] = useState<string | null>(null);
  const [notice, setNotice] = useState<Notice | null>(null);
  const [modelsNotice, setModelsNotice] = useState<Notice | null>(null);
  const [quotaDialogDismissed, setQuotaDialogDismissed] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);
  const [hasSubmitted, setHasSubmitted] = useState(false);
  const [askedExplanation, setAskedExplanation] = useState(false);
  const [preset, setPreset] = useState(PRESET_REVIEWS[0].label);
  const length = reviewLength(text);
  const selectedModel = models.find((model) => model.modelId === selected && model.available);

  function clearPreviousResult() {
    setResult(null);
    setNotice(null);
    setResultRequestId(null);
    setHasSubmitted(false);
    setAskedExplanation(false);
  }

  useEffect(() => {
    let active = true;
    fetchModels().then((items) => {
      if (!active) return;
      setModels(items);
      setSelected((current) => items.some((item) => item.modelId === current && item.available) ? current : items.find((item) => item.available)?.modelId ?? "");
      setModelsNotice(null);
    }).catch((error: unknown) => {
      if (!active) return;
      setModels([]);
      setSelected("");
      setQuotaDialogDismissed(false);
      setModelsNotice(errorNotice(error));
    }).finally(() => { if (active) setLoadingModels(false); });
    return () => { active = false; };
  }, [reloadKey]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (submitting) return;
    setHasSubmitted(true);
    setResult(null);
    setNotice(null);
    setQuotaDialogDismissed(false);
    setResultRequestId(null);
    if (!selectedModel) {
      setNotice({ title: "모델을 선택해 주세요", body: "현재 사용할 수 있는 모델이 없습니다.", requestId: null, analysisId: null });
      return;
    }
    if (!validReview(text)) {
      setNotice({ title: "입력을 확인해 주세요", body: `한국어 영화 리뷰를 1~${MAX_LENGTH}자 이내로 입력해 주세요.`, requestId: null, analysisId: null });
      return;
    }
    setSubmitting(true);
    const askExplanation = explanationRequested(selectedModel.explanationAvailable, includeExplanation);
    setAskedExplanation(askExplanation);
    try {
      const response = await createAnalysis(text, selectedModel.modelId, askExplanation);
      setResult(response.result);
      setResultRequestId(response.requestId);
    } catch (error) {
      setNotice(errorNotice(error));
    } finally {
      setSubmitting(false);
    }
  }

  const quotaNotice = notice?.quotaPossible ? notice : modelsNotice;

  return <>
    {quotaNotice && !quotaDialogDismissed ? <QuotaNoticeDialog notice={quotaNotice} onDismiss={() => setQuotaDialogDismissed(true)} /> : null}
    <div className="page-intro"><h1>영화 리뷰 감성 분석</h1></div>
      <div className="workspace-grid"><section className="form-section" aria-labelledby="form-heading"><h2 id="form-heading">리뷰 분석하기</h2>
        {modelsNotice ? <div className="models-alert" role="alert"><strong>{modelsNotice.title}</strong><p>{modelsNotice.body}</p>{modelsNotice.requestId ? <p>요청 ID: {modelsNotice.requestId}</p> : null}<button type="button" onClick={() => { setLoadingModels(true); setReloadKey((value) => value + 1); }}>다시 불러오기</button></div> : null}
        <form onSubmit={submit} noValidate>
          <ModelPicker models={models} selected={selected} disabled={submitting} onSelect={(value) => { setSelected(value); setIncludeExplanation(false); clearPreviousResult(); }} />
          {loadingModels ? <p className="loading-text">모델 목록을 불러오는 중입니다.</p> : null}
          <div className="preset-field">
            <label className="field-label" htmlFor="preset-review">예시 리뷰</label>
            <select id="preset-review" className="preset-select" value={preset} disabled={submitting}
              onChange={(event) => {
                const chosen = PRESET_REVIEWS.find((item) => item.label === event.target.value);
                setPreset(event.target.value);
                if (chosen) setText(chosen.text);
                clearPreviousResult();
              }}>
              {PRESET_REVIEWS.map((item) => <option key={item.label} value={item.label}>{item.label}</option>)}
            </select>
          </div>
          <div className="text-field"><label className="field-label" htmlFor="review-text">리뷰 입력</label><textarea id="review-text" value={text} onChange={(event) => { setText(event.target.value); setPreset(PRESET_REVIEWS[0].label); clearPreviousResult(); }} disabled={submitting} placeholder={`영화에 대한 생각을 ${MAX_LENGTH}자 이내로 입력해 주세요.`} rows={4} aria-describedby="text-count" /><div id="text-count" className={`char-count ${length > MAX_LENGTH ? "over-limit" : ""}`}>{length} / {MAX_LENGTH}</div></div>
          <ExplanationOption model={selectedModel} checked={includeExplanation} disabled={submitting} onChange={(checked) => { setIncludeExplanation(checked); clearPreviousResult(); }} />
          <button className="submit-button" type="submit" disabled={submitting || loadingModels || !selectedModel}>{submitting ? "분석 중입니다…" : "분석하기"}</button>
        </form>
      </section><ResultPanel result={result} requestId={resultRequestId} notice={notice} hasSubmitted={hasSubmitted} models={models} askedExplanation={askedExplanation} /></div>
    <Performance models={models} />
  </>;
}
