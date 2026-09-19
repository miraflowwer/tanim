export { FARMER_NAVIGATION } from "./farmer";
export { COORDINATOR_NAVIGATION } from "./coordinator";
export { REVIEWER_NAVIGATION } from "./reviewer";
export { ADMIN_NAVIGATION } from "./admin";
export { GLOBAL_NAVIGATION } from "./global";
export { PLATFORM_NAVIGATION } from "./platform";
export type { AppArea, NavigationItem } from "./types";

import { FARMER_NAVIGATION } from "./farmer";
import { COORDINATOR_NAVIGATION } from "./coordinator";
import { REVIEWER_NAVIGATION } from "./reviewer";
import { ADMIN_NAVIGATION } from "./admin";
import { GLOBAL_NAVIGATION } from "./global";
import { PLATFORM_NAVIGATION } from "./platform";

export const ALL_NAVIGATION = [
  ...FARMER_NAVIGATION,
  ...COORDINATOR_NAVIGATION,
  ...REVIEWER_NAVIGATION,
  ...ADMIN_NAVIGATION,
  ...GLOBAL_NAVIGATION,
  ...PLATFORM_NAVIGATION,
] as const;
