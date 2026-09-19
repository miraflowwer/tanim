export interface NoticeItem {
  id: string;
  title: string;
  reason: string;
  time: string;
  read: boolean;
  href: string;
  statusText: string;
}

// Typed notification fixtures. A live inbox needs API-M2-005. Fixtures are
// labeled synthetic and never presented as server deliveries.
export const NOTIFICATION_FIXTURE_NOTE =
  "Notification inbox is a typed fixture. Live delivery needs API-M2-005.";

export function seedNotifications(): NoticeItem[] {
  return [
    {
      id: "notice-seed-1",
      title: "Tomato plan result changed",
      reason: "A recalculation moved the Tomato 2026-Q4 comparison.",
      time: "2026-09-19",
      read: false,
      href: "#/crop/tomato",
      statusText: "Unread",
    },
    {
      id: "notice-seed-2",
      title: "Reference needs review",
      reason: "A candidate reference for Eggplant awaits a reviewer.",
      time: "2026-09-18",
      read: true,
      href: "#/review",
      statusText: "Read",
    },
    {
      id: "notice-seed-3",
      title: "Data source stale",
      reason: "PSA farmgate prices missed the expected refresh.",
      time: "2026-09-12",
      read: true,
      href: "#/data",
      statusText: "Read",
    },
  ];
}
