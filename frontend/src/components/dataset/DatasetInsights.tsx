import { labelShares, lengthBins, meanLength, topWords } from "@/lib/eda";

const NUMBER = new Intl.NumberFormat("ko-KR");

function percent(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

function SummaryTile({ label, value, note }: { label: string; value: string; note?: string }) {
  return <div className="stat-tile">
    <span className="stat-label">{label}</span>
    <strong className="stat-value">{value}</strong>
    {note ? <span className="stat-note">{note}</span> : null}
  </div>;
}

/** Horizontal bars: the stats file keeps aggregates only, so no charting library is needed. */
function BarRow({ name, value, share, unit }: { name: string; value: number; share: number; unit: string }) {
  return <li className="bar-row">
    <span className="bar-name">{name}</span>
    <span className="bar-track" aria-hidden="true"><span style={{ width: `${Math.max(2, Math.round(share * 100))}%` }} /></span>
    <span className="bar-value">{NUMBER.format(value)}{unit}</span>
  </li>;
}

export function DatasetInsights() {
  const shares = labelShares();
  const total = shares.reduce((sum, entry) => sum + entry.count, 0);
  const peakLabelCount = Math.max(...shares.map((entry) => entry.count), 0);
  const bins = lengthBins();
  const average = meanLength();

  return <>
    <div className="page-intro">
      <h1>데이터 탐색</h1>
    </div>
    <section className="dataset-section" aria-labelledby="summary-heading">
      <h2 id="summary-heading">요약</h2>
      <div className="stat-grid">
        <SummaryTile label="총 학습 리뷰" value={`${NUMBER.format(total)}건`} />
        {shares.map((entry) => (
          <SummaryTile key={entry.label} label={`${entry.label} 비율`} value={percent(entry.share)} note={`${NUMBER.format(entry.count)}건`} />
        ))}
        <SummaryTile label="평균 길이" value={`약 ${Math.round(average)}자`} note="히스토그램 기준 근사" />
      </div>
    </section>

    <section className="dataset-section" aria-labelledby="label-heading">
      <h2 id="label-heading">레이블 분포</h2>
      <ul className="bar-list">
        {shares.map((entry) => (
          <BarRow key={entry.label} name={entry.label} value={entry.count} share={peakLabelCount > 0 ? entry.count / peakLabelCount : 0} unit="건" />
        ))}
      </ul>
    </section>

    <section className="dataset-section" aria-labelledby="length-heading">
      <h2 id="length-heading">리뷰 길이 분포</h2>
      <ul className="bar-list bar-list-dense">
        {bins.map((bin) => <BarRow key={bin.label} name={`${bin.label}자`} value={bin.count} share={bin.share} unit="건" />)}
      </ul>
    </section>

    <section className="dataset-section" aria-labelledby="words-heading">
      <h2 id="words-heading">레이블별 빈출 단어 TOP 20</h2>
      <div className="word-columns">
        {shares.map((entry) => (
          <div key={entry.label} className="word-column">
            <h3>{entry.label} 리뷰</h3>
            <ul className="bar-list">
              {topWords(entry.label).map((word) => <BarRow key={word.word} name={word.word} value={word.frequency} share={word.share} unit="회" />)}
            </ul>
          </div>
        ))}
      </div>
    </section>

  </>;
}
