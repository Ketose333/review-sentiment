import { MAX_REVIEW_LENGTH } from "@/constants";

const DATASET_FACTS = [
  { label: "학습 데이터", value: "150,000건" },
  { label: "테스트 데이터", value: "50,000건" },
  { label: "레이블", value: "긍정 / 부정" },
];

const MODELS = [
  { name: "TF-IDF + LogisticRegression", trait: "전통적 통계 기반, 빠른 추론" },
  { name: "LSTM", trait: "Embedding → LSTM → Dense, 순차 문맥 학습" },
  { name: "KLUE-BERT", trait: "사전학습 트랜스포머 파인튜닝" },
];

export function ProjectAbout() {
  return <>
    <div className="page-intro">
      <h1>프로젝트 소개</h1>
    </div>
    <section className="about-section" aria-labelledby="about-heading">
      <h2 id="about-heading">무엇을 하는 프로젝트인가</h2>
      <p>
        Naver Sentiment Movie Corpus(NSMC) 20만 건의 영화 리뷰로 긍정·부정 감성 분류 모델을 학습하고,
        입력한 리뷰의 감성을 예측하며 LIME으로 예측 근거 단어를 보여주는 머신러닝 프로젝트입니다.
      </p>
      <div className="stat-grid">
        {DATASET_FACTS.map((fact) => <div key={fact.label} className="stat-tile">
          <span className="stat-label">{fact.label}</span>
          <strong className="stat-value">{fact.value}</strong>
        </div>)}
      </div>
    </section>

    <section className="about-section" aria-labelledby="models-heading">
      <h2 id="models-heading">비교 모델</h2>
      <div className="about-table-wrap">
        <table className="about-table">
          <thead><tr><th scope="col">모델</th><th scope="col">특징</th></tr></thead>
          <tbody>{MODELS.map((entry) => <tr key={entry.name}>
            <th scope="row">{entry.name}</th><td>{entry.trait}</td>
          </tr>)}</tbody>
        </table>
      </div>
    </section>

    <section className="about-section" aria-labelledby="privacy-heading">
      <h2 id="privacy-heading">입력과 보관</h2>
      <ul className="about-list">
        <li>한국어 리뷰 한 건, {MAX_REVIEW_LENGTH}자 이내만 분석합니다.</li>
        <li>리뷰 원문과 전처리 결과는 저장하지 않습니다. 분석 결과 메타데이터만 24시간 보관한 뒤 삭제합니다.</li>
        <li>LIME 설명 단어는 응답에만 담기고 저장하거나 다시 조회할 수 없습니다.</li>
      </ul>
    </section>
  </>;
}
