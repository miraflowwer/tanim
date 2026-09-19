import type { NavigationItem } from "./types";

export const FARMER_NAVIGATION: NavigationItem[] = [
  { id: "home", label: "Home", area: "farmer", href: "#/home", mobilePrimary: true },
  { id: "my", label: "My Plans", area: "farmer", href: "#/my", mobilePrimary: true },
  { id: "new", label: "New Plan", area: "farmer", href: "#/new" },
  { id: "profile", label: "Profile", area: "farmer", href: "#/profile" },
];
