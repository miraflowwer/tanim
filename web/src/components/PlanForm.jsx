import { useState } from "react";
import { CROPS, LUZON_REGIONS } from "../config.js";

const initial = {
  crop: "tomato",
  regionId: "IV-A",
  location: "Tanauan, Batangas",
  farmSizeHa: "2",
  farmSizeMarginHa: "0.2",
  plantingDate: "2026-09-01",
  harvestPeriod: "2026-12",
};

export default function PlanForm({ onSubmit, loading }) {
  const [form, setForm] = useState(initial);
  const [error, setError] = useState("");

  function set(key, value) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  function handleSubmit(event) {
    event.preventDefault();
    const farmSizeHa = Number(form.farmSizeHa);
    const farmSizeMarginHa = Number(form.farmSizeMarginHa);
    if (!form.crop) return setError("Please select a crop. / Pumili ng pananim.");
    if (!form.regionId) return setError("Please select a Luzon region.");
    if (!form.location.trim()) return setError("Please enter municipality or location.");
    if (!Number.isFinite(farmSizeHa) || farmSizeHa < 0)
      return setError("Farm size must be a number ≥ 0.");
    if (!Number.isFinite(farmSizeMarginHa) || farmSizeMarginHa < 0)
      return setError("Margin must be a number ≥ 0.");
    if (!form.plantingDate) return setError("Please enter planting date.");
    if (!/^\d{4}-\d{2}$/.test(form.harvestPeriod))
      return setError("Harvest period must be YYYY-MM.");
    setError("");
    onSubmit({
      crop: form.crop,
      regionId: form.regionId,
      location: form.location.trim(),
      farmSizeHa,
      farmSizeMarginHa,
      plantingDate: form.plantingDate,
      harvestPeriod: form.harvestPeriod,
    });
  }

  return (
    <form className="tanim-card" onSubmit={handleSubmit} aria-label="Planting plan form">
      <h2>1. Your planting plan</h2>
      {error && (
        <div className="tanim-error" role="alert">
          {error}
        </div>
      )}
      <div className="tanim-field">
        <label htmlFor="crop">Crop / Pananim</label>
        <select
          id="crop"
          value={form.crop}
          onChange={(e) => set("crop", e.target.value)}
        >
          {CROPS.map((c) => (
            <option key={c.id} value={c.id}>
              {c.label}
            </option>
          ))}
        </select>
      </div>
      <div className="tanim-field">
        <label htmlFor="region">Luzon region</label>
        <select
          id="region"
          value={form.regionId}
          onChange={(e) => set("regionId", e.target.value)}
        >
          {LUZON_REGIONS.map((r) => (
            <option key={r.id} value={r.id}>
              {r.label}
            </option>
          ))}
        </select>
        <span className="tanim-hint">
          Select directly — no map lookup in this MVP.
        </span>
      </div>
      <div className="tanim-field">
        <label htmlFor="location">Municipality / location</label>
        <input
          id="location"
          type="text"
          value={form.location}
          onChange={(e) => set("location", e.target.value)}
          placeholder="e.g. Tanauan, Batangas"
          autoComplete="off"
        />
      </div>
      <div className="tanim-row-2">
        <div className="tanim-field">
          <label htmlFor="area">Farm size (hectares)</label>
          <input
            id="area"
            type="number"
            min="0"
            step="0.1"
            value={form.farmSizeHa}
            onChange={(e) => set("farmSizeHa", e.target.value)}
          />
        </div>
        <div className="tanim-field">
          <label htmlFor="margin">± Margin (hectares)</label>
          <input
            id="margin"
            type="number"
            min="0"
            step="0.1"
            value={form.farmSizeMarginHa}
            onChange={(e) => set("farmSizeMarginHa", e.target.value)}
          />
          <span className="tanim-hint">How unsure is the size? / Gaano kasigurado?</span>
        </div>
      </div>
      <div className="tanim-row-2">
        <div className="tanim-field">
          <label htmlFor="planting">Planting date</label>
          <input
            id="planting"
            type="date"
            value={form.plantingDate}
            onChange={(e) => set("plantingDate", e.target.value)}
          />
        </div>
        <div className="tanim-field">
          <label htmlFor="harvest">Expected harvest (YYYY-MM)</label>
          <input
            id="harvest"
            type="month"
            value={form.harvestPeriod}
            onChange={(e) => set("harvestPeriod", e.target.value)}
          />
        </div>
      </div>
      <button className="tanim-btn tanim-btn-primary" type="submit" disabled={loading}>
        {loading ? "Computing…" : "Submit plan / Isumite"}
      </button>
    </form>
  );
}
