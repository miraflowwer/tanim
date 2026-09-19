export interface MapSummaryRow {
  geography: string;
  crop: string;
  plans: number;
  farmers: number;
  areaHa: number;
  productionMt: number | null;
  state: string;
}

// Map panel with an always-available list fallback. Coordinates are never
// fabricated: without a tile provider the panel shows aggregate summaries
// and states that the visual map layer is unavailable.
export function MapPanel({ title, rows, tilesAvailable = false }: {
  title: string;
  rows: MapSummaryRow[];
  tilesAvailable?: boolean;
}) {
  return (
    <section aria-labelledby="mappanel-h">
      <h3 id="mappanel-h">{title}</h3>
      {!tilesAvailable && (
        <p role="note" className="badge">
          Map tiles unavailable. Showing the aggregate list fallback. No locations are guessed.
        </p>
      )}
      {rows.length === 0 ? (
        <p role="status">No aggregate geography to show yet.</p>
      ) : (
        <ul className="cards">
          {rows.map((row, index) => (
            <li key={`${row.geography}-${row.crop}-${index}`}>
              <article className="card" aria-label={`${row.crop} in ${row.geography}`}>
                <h3>{row.crop} · {row.geography}</h3>
                <dl>
                  <dt>Plans</dt><dd>{row.plans}</dd>
                  <dt>Farmers</dt><dd>{row.farmers}</dd>
                  <dt>Planned area</dt><dd>{row.areaHa} ha</dd>
                  <dt>Estimated production</dt>
                  <dd>{row.productionMt === null ? "Yield unavailable" : `${row.productionMt} MT`}</dd>
                  <dt>State</dt><dd>{row.state}</dd>
                </dl>
              </article>
            </li>
          ))}
        </ul>
      )}
      <p className="hint">Aggregate geography only. Individual farm pins are never shown by default.</p>
    </section>
  );
}
