function toPlanRecord(plan) {
  return {
    crop: plan.crop,
    region_id: plan.regionId,
    location: plan.location,
    farm_size_ha: plan.farmSizeHa,
    farm_size_margin_ha: plan.farmSizeMarginHa,
    planting_date: plan.plantingDate,
    harvest_period: plan.harvestPeriod,
  };
}

export function toBackendPayload(planInput) {
  const payload = {
    use_demo_reference: planInput.useDemoReference === true,
  };

  if (Array.isArray(planInput.plans)) {
    payload.plans = planInput.plans.map(toPlanRecord);
  } else {
    payload.plan = toPlanRecord(planInput);
  }

  if (!payload.use_demo_reference && planInput.comparison) {
    payload.comparison = { ...planInput.comparison };
    payload.source_labels = planInput.sourceLabels ?? [];
  }
  return payload;
}
