import { useEffect, useMemo, useState } from "react";

const initial = {
  crop: "tomato",
  regionId: "IV-A",
  location: "Tanauan, Batangas",
  farmSizeHa: "2",
  farmSizeMarginHa: "0.2",
  plantingDate: "2026-09-01",
  harvestPeriod: "2026-12",
  comparisonAmount: "",
  comparisonType: "historical_production_baseline",
  comparisonGeography: "CALABARZON (IV-A)",
  comparisonPeriod: "2021-2025",
  sourceLabel: "",
};

export default function PlanForm({
  onSubmit,
  loading,
  preset,
  options,
  optionsError,
}) {
  const [form, setForm] = useState(initial);
  const [error, setError] = useState("");

  const crops = options?.crops ?? [];
  const regionLabels = useMemo(
    () => new Map((options?.regions ?? []).map((item) => [item.id, item.label])),
    [options]
  );
  const selectedCrop = crops.find((item) => item.id === form.crop);
  const availableRegions = selectedCrop?.regions ?? [];
  const referenceTypes = options?.reference_types ?? [];

  useEffect(() => {
    if (!preset) return;
    setForm((prev) => ({
      ...prev,
      crop: preset.crop,
      regionId: preset.regionId,
      location: preset.location,
      farmSizeHa: String(preset.farmSizeHa),
      farmSizeMarginHa: String(preset.farmSizeMarginHa),
      plantingDate: preset.plantingDate,
      harvestPeriod: preset.harvestPeriod,
      comparisonGeography:
        prev.comparisonType === "national_utilization_context"
          ? "Philippines"
          : regionLabels.get(preset.regionId) ?? preset.regionId,
    }));
    setError("");
  }, [preset, regionLabels]);

  useEffect(() => {
    if (!crops.length) return;
    if (!crops.some((item) => item.id === form.crop)) {
      const first = crops[0];
      const regionId = first.regions[0] ?? "";
      setForm((prev) => ({
        ...prev,
        crop: first.id,
        regionId,
        comparisonGeography:
          prev.comparisonType === "national_utilization_context"
            ? "Philippines"
            : regionLabels.get(regionId) ?? regionId,
      }));
      return;
    }
    if (availableRegions.length && !availableRegions.includes(form.regionId)) {
      const regionId = availableRegions[0];
      setForm((prev) => ({
        ...prev,
        regionId,
        comparisonGeography:
          prev.comparisonType === "national_utilization_context"
            ? "Philippines"
            : regionLabels.get(regionId) ?? regionId,
      }));
    }
  }, [crops, availableRegions, form.crop, form.regionId, regionLabels]);

  function set(key, value) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  function setCrop(cropId) {
    const crop = crops.find((item) => item.id === cropId);
    const regionId = crop?.regions?.includes(form.regionId)
      ? form.regionId
      : crop?.regions?.[0] ?? "";
    setForm((prev) => ({
      ...prev,
      crop: cropId,
      regionId,
      comparisonGeography:
          prev.comparisonType === "national_utilization_context"
            ? "Philippines"
            : regionLabels.get(regionId) ?? regionId,
    }));
  }

  function handleSubmit(event) {
    event.preventDefault();
    const farmSizeHa = Number(form.farmSizeHa);
    const farmSizeMarginHa = Number(form.farmSizeMarginHa);
    const amount = Number(form.comparisonAmount);

    if (!form.crop) return setError("Please select a crop. / Pumili ng pananim.");
    if (!form.regionId) return setError("Please select a Luzon region.");
    if (!form.location.trim())
      return setError("Please enter municipality or location.");
    if (!Number.isFinite(farmSizeHa) || farmSizeHa <= 0)
      return setError("Farm size must be a number greater than 0.");
    if (!Number.isFinite(farmSizeMarginHa) || farmSizeMarginHa < 0)
      return setError("Margin must be a number greater than or equal to 0.");
    if (!form.plantingDate) return setError("Please enter planting date.");
    if (!/^\d{4}-\d{2}$/.test(form.harvestPeriod))
      return setError("Harvest period must be YYYY-MM.");
    if (form.harvestPeriod < form.plantingDate.slice(0, 7))
      return setError("Harvest month cannot be before the planting month.");
    if (!Number.isFinite(amount) || amount <= 0)
      return setError("Comparison amount must be a number greater than 0 MT.");
    if (!form.comparisonType)
      return setError("Please select the comparison evidence type.");
    if (!form.comparisonGeography.trim())
      return setError("Please enter the comparison geography.");
    if (!form.comparisonPeriod.trim())
      return setError("Please enter the comparison period.");
    if (!form.sourceLabel.trim())
      return setError("Please enter the comparison source label.");
    const selectedReference = referenceTypes.find(
      (item) => item.id === form.comparisonType
    );
    const plan = {
      crop: form.crop,
      regionId: form.regionId,
      location: form.location.trim(),
      farmSizeHa,
      farmSizeMarginHa,
      plantingDate: form.plantingDate,
      harvestPeriod: form.harvestPeriod,
      comparison: {
        amount,
        unit: "MT",
        type: form.comparisonType,
        geography: form.comparisonGeography.trim(),
        period: form.comparisonPeriod.trim(),
        ...(selectedReference?.scope === "national"
          ? {}
          : { region_id: form.regionId }),
      },
      sourceLabels: [form.sourceLabel.trim()],
    };

    setError("");
    onSubmit(plan);
  }

  return (
    <form
      className="tanim-card"
      onSubmit={handleSubmit}
      aria-label="Planting plan form"
    >
      <h2>1. Your planting plan</h2>
      {optionsError && (
        <div className="tanim-error" role="alert">
          Could not load full crop options: {optionsError}
        </div>
      )}
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
          onChange={(e) => setCrop(e.target.value)}
        >
          {crops.map((crop) => (
            <option key={crop.id} value={crop.id}>
              {crop.label}
            </option>
          ))}
        </select>
      </div>

      <div className="tanim-field">
        <label htmlFor="region">Luzon region</label>
        <select
          id="region"
          value={form.regionId}
          onChange={(e) => {
            const regionId = e.target.value;
            setForm((prev) => ({
              ...prev,
              regionId,
              comparisonGeography:
                prev.comparisonType === "national_utilization_context"
                  ? "Philippines"
                  : regionLabels.get(regionId) ?? regionId,
            }));
          }}
        >
          {availableRegions.map((regionId) => (
            <option key={regionId} value={regionId}>
              {regionLabels.get(regionId) ?? regionId}
            </option>
          ))}
        </select>
        <span className="tanim-hint">
          Only crop-region pairs with a committed five-year yield reference are shown.
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
            min="0.1"
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
          <span className="tanim-hint">
            How unsure is the size? / Gaano kasigurado?
          </span>
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
            onChange={(e) => {
              const harvestPeriod = e.target.value;
              setForm((prev) => ({
                ...prev,
                harvestPeriod,
              }));
            }}
          />
        </div>
      </div>

      <fieldset className="tanim-comparison">
        <legend>Comparison evidence</legend>
        <p className="tanim-hint">
          Enter a reference from a named source. This form does not verify the
          amount or source label.
        </p>
        <div className="tanim-row-2">
          <div className="tanim-field">
            <label htmlFor="comparison-amount">Amount (MT)</label>
            <input
              id="comparison-amount"
              type="number"
              min="0.001"
              step="any"
              value={form.comparisonAmount}
              onChange={(e) => set("comparisonAmount", e.target.value)}
            />
          </div>
          <div className="tanim-field">
            <label htmlFor="comparison-type">Evidence type</label>
            <select
              id="comparison-type"
              value={form.comparisonType}
              onChange={(e) => {
                const comparisonType = e.target.value;
                setForm((prev) => ({
                  ...prev,
                  comparisonType,
                  comparisonGeography:
                    comparisonType === "national_utilization_context"
                      ? "Philippines"
                      : regionLabels.get(prev.regionId) ?? prev.regionId,
                }));
              }}
            >
              {referenceTypes.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.label}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div className="tanim-field">
          <label htmlFor="comparison-geography">Geography</label>
          <input
            id="comparison-geography"
            type="text"
            value={form.comparisonGeography}
            onChange={(e) => set("comparisonGeography", e.target.value)}
            placeholder="e.g. CALABARZON (IV-A)"
          />
        </div>

        <div className="tanim-row-2">
          <div className="tanim-field">
            <label htmlFor="comparison-period">Period</label>
            <input
              id="comparison-period"
              type="text"
              value={form.comparisonPeriod}
              onChange={(e) => set("comparisonPeriod", e.target.value)}
              placeholder="e.g. 2021-2025 or 2026-12"
            />
          </div>
          <div className="tanim-field">
            <label htmlFor="source-label">Source label</label>
            <input
              id="source-label"
              type="text"
            value={form.sourceLabel}
            onChange={(e) => set("sourceLabel", e.target.value)}
            placeholder="e.g. PSA OpenSTAT table or coop record"
          />
          </div>
        </div>
      </fieldset>

      <button
        className="tanim-btn tanim-btn-primary"
        type="submit"
        disabled={loading}
      >
        {loading ? "Computing…" : "Submit plan / Isumite"}
      </button>
    </form>
  );
}
