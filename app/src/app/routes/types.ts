export type AppArea = "farmer" | "coordinator" | "reviewer" | "admin" | "platform" | "global";

export interface NavigationItem {
  id: string;
  label: string;
  area: AppArea;
  href: string;
  mobilePrimary?: boolean;
}
