export interface BarDatum {
  label: string;
  value: number | null;
  note?: string;
}

// Accessible vertical bar chart. Every chart ships with a text table so the
// data never depends on vision alone. Units stay on the axis title.
export function BarChart({ title, unit, bars, emptyNote }: {
  title: string;
  unit: string;
  bars: BarDatum[];
  emptyNote: string;
}) {
  const values = bars.map((bar) => bar.value ?? 0);
  const max = Math.max(1, ...values);
  const drawn = bars.filter((bar) => bar.value !== null);
  return (
    <section aria-label={title}>
      <h3>{title} ({unit})</h3>
      {drawn.length === 0 ? (
        <p role="status">{emptyNote}</p>
      ) : (
        <svg viewBox="0 0 320 240" role="img" aria-label={`${title} in ${unit}`}>
          {drawn.map((bar, index) => {
            const height = Math.max(4, (Number(bar.value) / max) * 180);
            const x = 10 + index * (300 / drawn.length);
            const width = Math.max(8, 300 / drawn.length - 8);
            return (
              <g key={bar.label}>
                <rect x={x} y={200 - height} width={width} height={height} fill="currentColor" />
                <text x={x} y={216} fontSize="10">{bar.label}</text>
                <text x={x} y={196 - height} fontSize="10">{bar.value}{bar.note ? ` (${bar.note})` : ""}</text>
              </g>
            );
          })}
          <line x1="8" y1="200" x2="312" y2="200" stroke="currentColor" />
        </svg>
      )}
      <table className="responsive">
        <caption className="hint">{title} data table, values in {unit}.</caption>
        <thead><tr><th scope="col">Label</th><th scope="col">Value ({unit})</th></tr></thead>
        <tbody>
          {bars.map((bar) => (
            <tr key={bar.label}>
              <td>{bar.label}</td>
              <td>{bar.value === null ? emptyNote : `${bar.value}${bar.note ? ` (${bar.note})` : ""}`}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
