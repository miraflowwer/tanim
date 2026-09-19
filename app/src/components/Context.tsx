// §28 price context + §29 climate context (separate from coordination signal).
import { CLIMATE_HEADING, CLIMATE_UNAVAILABLE, PRICE_NOTE } from "../lib/copy";
import type { ClimateCtx, PriceObs } from "../types";
import { Card } from "./Card";

export function PriceContext({ price }: { price: PriceObs | null }) {
  if (!price) return null;
  return (
    <Card title="Price context">
      <p>
        Latest: {price.latestPrice} {price.unit} · {price.date} · {price.geography}
      </p>
      <p className="hint">
        Source: {price.source} · Series {price.seriesId}
      </p>
      <p className="hint">Recent: {price.trend.join(" → ")} {price.unit}.</p>
      <p>{PRICE_NOTE}</p>
    </Card>
  );
}

export function ClimateContext({ climate }: { climate: ClimateCtx }) {
  return (
    <section aria-labelledby="climate-h">
      <h3 id="climate-h">{CLIMATE_HEADING}</h3>
      {!climate.available ? (
        <p role="status">{CLIMATE_UNAVAILABLE}</p>
      ) : (
        <Card title={`${climate.source} · ${climate.issuedAt}`}>
          <p>{climate.summary}</p>
          <p className="hint">Climate context only. It is not part of the coordination result.</p>
        </Card>
      )}
    </section>
  );
}
