import { expect, test } from "@playwright/test";
import { existsSync, readdirSync, statSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

test("LCP under 2.5s on seeded home", async ({ page }) => {
  await page.goto("/#/home");
  const lcp = await page.evaluate(
    () => new Promise<number>((resolve) => {
      let done = false;
      const finish = (value: number) => { if (!done) { done = true; resolve(value); } };
      try {
        new PerformanceObserver((list) => {
          const last = list.getEntries().pop() as PerformanceEntry & { renderTime?: number; loadTime?: number };
          if (last) finish(last.renderTime ?? last.loadTime ?? performance.now());
        }).observe({ type: "largest-contentful-paint", buffered: true });
      } catch { finish(performance.now()); }
      setTimeout(() => finish(performance.now()), 3000);
    }),
  );
  expect(lcp).toBeLessThan(2500);
});

test("JS budget fails when dist is missing and enforces 250KB", async () => {
  const dir = join(dirname(fileURLToPath(import.meta.url)), "..", "..", "app", "dist", "assets");
  expect(existsSync(dir)).toBeTruthy();
  const files = readdirSync(dir).filter((file) => file.endsWith(".js"));
  expect(files.length).toBeGreaterThan(0);
  const total = files.reduce((sum, file) => sum + statSync(join(dir, file)).size, 0);
  expect(total).toBeLessThan(250 * 1024);
});
