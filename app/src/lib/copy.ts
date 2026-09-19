// Central calibrated copy (§41). Plain B1 language, no certainty claims.
export const ORG_NAME = "Coop Demo Org";
export const ORG_SCOPE = "CALABARZON";

export const EMPTY_HOME =
  "You have no planting plans yet. Add one to see how your plan fits with other plans in your group.";

export const STALE_BANNER =
  "This source has not been refreshed as expected. TANIM is using the last verified version.";

export const ALT_HEADING = "Other crops with available coordination evidence";
export const ALT_LABEL = "Coordination alternative";

export const PRICE_NOTE = "Past prices do not decide future profit. Prices are context only.";
export const CLIMATE_HEADING = "Weather and climate context";
export const CLIMATE_UNAVAILABLE = "Weather context is not available right now. Your coordination result does not depend on it.";
export const SYNTHETIC_BADGE = "Synthetic demo — not market demand.";
export const IDENTITIES_HIDDEN = "Farmer names are hidden for this role. Totals are shown for the group.";
export const REVIEWER_ONLY = "Only reviewers can mark a reference verified.";

export const STATUS_LABEL: Record<string, string> = {
  low_coordination_load: "Low coordination load",
  elevated_coordination_load: "Elevated coordination load",
  high_coordination_load: "High coordination load",
  historical_baseline_only: "Historical baseline only",
  more_evidence_needed: "More evidence needed",
};

export const STATUS_HEADLINE: Record<string, string> = {
  low_coordination_load:
    "Planned production is below the comparison reference for this crop and harvest period.",
  high_coordination_load:
    "Planned production is above the reviewed reference for this crop and harvest period.",
  historical_baseline_only:
    "This compares your group's planned production with past production. It does not measure market demand.",
  more_evidence_needed:
    "TANIM can estimate production, but no reviewed local demand reference is available for this crop and period.",
};

export function altCopy(crop: string, period: string): string {
  return `Fewer planned hectares are currently registered for ${crop} for this harvest period (${period}).`;
}
