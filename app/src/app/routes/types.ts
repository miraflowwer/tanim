export type AppArea = "farmer" | "coordinator" | "reviewer" | "admin" | "platform";

export interface NavigationItem {
  id: string;
  label: string;
  area: AppArea;
  href: string;
  mobilePrimary?: boolean;
}
