export interface LinePoint {
  label: string;
  value: number | null;
}

// Accessible line chart with a text table equivalent. Missing points are
// never drawn as zero; they stay missing in both the line and the table.
export function LineChart({ title, unit, points, emptyNote, contextNote }: {
  title: string;
  unit: string;
  points: LinePoint[];
  emptyNote: string;
  contextNote?: string;
}) {
  const drawn = points.filter((point) => point.value !== null);
  const values = drawn.map((point) => Number(point.value));
  const max = Math.max(1, ...values);
  const min = Math.min(0, ...values);
  const span = Math.max(1, max - min);
  const step = drawn.length > 1 ? 280 / (drawn.length - 1) : 0;
  const path = drawn
    .map((point, index) => `${index === 0 ? "M" : "L"}${20 + index * step},${190 - ((Number(point.value) - min) / span) * 170}`)
    .join(" ");
  return (
    <section aria-label={title}>
      <h3>{title} ({unit})</h3>
      {contextNote && <p className="hint">{contextNote}</p>}
      {drawn.length === 0 ? (
        <p role="status">{emptyNote}</p>
      ) : (
        <svg viewBox="0 0 320 240" role="img" aria-label={`${title} in ${unit}`}>
          {drawn.length > 1 && <path d={path} fill="none" stroke="currentColor" strokeWidth="2" />}
          {drawn.map((point, index) => (
            <g key={point.label}>
              <circle cx={20 + index * step} cy={190 - ((Number(point.value) - min) / span) * 170} r="4" fill="currentColor">
                <title>{point.label}: {point.value} {unit}</title>
              </circle>
              <text x={20 + index * step} y={216} fontSize="10" textAnchor="middle">{point.label}</text>
            </g>
          ))}
        </svg>
      )}
      <table className="responsive">
        <caption className="hint">{title} data table, values in {unit}.</caption>
        <thead><tr><th scope="col">Label</th><th scope="col">Value ({unit})</th></tr></thead>
        <tbody>
          {points.map((point) => (
            <tr key={point.label}>
              <td>{point.label}</td>
              <td>{point.value === null ? emptyNote : point.value}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
