import type { NavigationItem } from "./types";

// Farmer IA (§02): primary Home/Plans/Crops/Calendar/Map; secondary Farms,
// Notifications, Profile, Privacy & Consent. Bottom nav shows mobilePrimary
// items plus a More drawer — never more than five persistent destinations.
export const FARMER_NAVIGATION: NavigationItem[] = [
  { id: "home", label: "Home", area: "farmer", href: "#/home", mobilePrimary: true },
  { id: "plans", label: "Plans", area: "farmer", href: "#/plans", mobilePrimary: true },
  { id: "crops", label: "Crops", area: "farmer", href: "#/crops", mobilePrimary: true },
  { id: "calendar", label: "Calendar", area: "farmer", href: "#/calendar", mobilePrimary: true },
  { id: "map", label: "Map", area: "farmer", href: "#/map" },
  { id: "farms", label: "Farms", area: "farmer", href: "#/farms" },
  { id: "notifications", label: "Notifications", area: "farmer", href: "#/notifications" },
  { id: "profile", label: "Profile", area: "farmer", href: "#/profile" },
  { id: "privacy", label: "Privacy & Consent", area: "farmer", href: "#/privacy" },
];

// Legacy hashes from the P0 scaffold resolve to their canonical route.
export const FARMER_ROUTE_ALIASES: Record<string, string> = {
  my: "plans",
  new: "plans/new",
  crop: "crops",
};
