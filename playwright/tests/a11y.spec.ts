import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

test("axe checks home, plan, result, overview, and references", async ({ page }) => {
  for (const route of ["/#/home", "/#/new", "/#/result/plan-tomato-001", "/#/overview", "/#/references"]) {
    await page.goto(route);
    const results = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
      .analyze();
    const actionable = results.violations.filter(
      (violation) => violation.impact === "critical" || violation.impact === "serious",
    );
    expect(actionable, route + ": " + JSON.stringify(actionable.map(
      (violation) => ({ id: violation.id, nodes: violation.nodes.map((node) => node.target) }),
    ))).toEqual([]);
  }
});

test("keyboard reaches skip link and primary action with visible focus", async ({ page }) => {
  await page.goto("/#/home");
  await page.keyboard.press("Tab");
  await expect(page.getByRole("link", { name: "Skip to main content" })).toBeFocused();
  const firstOutline = await page.evaluate(() => getComputedStyle(document.activeElement as Element).outlineStyle);
  expect(firstOutline).not.toBe("none");
  await page.keyboard.press("Enter");
  await expect(page.getByRole("main")).toBeFocused();
  let reached = false;
  for (let i = 0; i < 16; i++) {
    await page.keyboard.press("Tab");
    reached = await page.getByRole("button", { name: "Create planting plan" }).evaluate(
      (button) => button === document.activeElement,
    );
    if (reached) break;
  }
  expect(reached).toBe(true);
  const outline = await page.evaluate(() => getComputedStyle(document.activeElement as Element).outlineStyle);
  expect(outline).not.toBe("none");
});

test("landmarks, headings, labels, error summary, and live feedback are accessible", async ({ page }) => {
  await page.goto("/#/new");
  await expect(page.getByRole("banner")).toBeVisible();
  await expect(page.getByRole("main")).toBeVisible();
  await expect(page.getByRole("contentinfo")).toBeVisible();
  expect(await page.getByRole("navigation").count()).toBeGreaterThanOrEqual(1);
  await expect(page.getByRole("heading", { level: 1, name: "TANIM" })).toBeVisible();
  await expect(page.getByRole("heading", { level: 2, name: "New planting plan" })).toBeVisible();
  for (const label of ["Crop", "Farm or location", "Planned area (ha)", "Planting date", "Expected harvest period"]) {
    await expect(page.getByLabel(label, { exact: true })).toBeVisible();
  }
  await page.getByLabel("Planned area (ha)").fill("0");
  await page.getByRole("button", { name: "Save plan" }).click();
  const summary = page.locator(".err-summary");
  await expect(summary).toHaveAttribute("role", "alert");
  await expect(summary).toBeFocused();
  await expect(page.getByLabel("Planned area (ha)")).toHaveAttribute("aria-invalid", "true");
  await expect(page.getByRole("main").locator("[aria-live]").first()).toBeAttached();
});

test("320px, 375px, and 200% page scale retain usable controls", async ({ page }) => {
  for (const width of [320, 375]) {
    await page.setViewportSize({ width, height: 800 });
    await page.goto("/#/new");
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    );
    expect(overflow, "overflow at " + width + "px").toBeLessThanOrEqual(1);
    await expect(page.getByRole("button", { name: "Save plan" })).toBeVisible();
  }
  await page.setViewportSize({ width: 640, height: 800 });
  await page.goto("/#/new");
  const cdp = await page.context().newCDPSession(page);
  await cdp.send("Emulation.setPageScaleFactor", { pageScaleFactor: 2 });
  await expect(page.getByRole("button", { name: "Save plan" })).toBeVisible();
  await cdp.send("Emulation.setPageScaleFactor", { pageScaleFactor: 1 });
  await cdp.detach();
});

test("visible links, controls, and disclosure targets meet 44px", async ({ page }) => {
  for (const route of ["/#/home", "/#/new", "/#/result/plan-tomato-001", "/#/references"]) {
    await page.goto(route);
    const small = await page.locator("a, button, input, select, summary").evaluateAll((elements) =>
      elements.flatMap((element) => {
        const rect = element.getBoundingClientRect();
        const visible = rect.width > 0 && rect.height > 0 && rect.right > 0 && rect.left < innerWidth;
        if (!visible || (rect.width >= 44 && rect.height >= 44)) return [];
        return [{ tag: element.tagName, text: element.textContent?.trim().slice(0, 40),
          width: rect.width, height: rect.height }];
      }),
    );
    expect(small, route + " undersized targets").toEqual([]);
  }
});
