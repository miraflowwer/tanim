import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

function record(value: unknown): Record<string, unknown> {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    throw new Error("Expected an API object.");
  }
  return value as Record<string, unknown>;
}

function idFrom(value: unknown): string {
  const id = record(value).id;
  if (typeof id !== "string" || !id) throw new Error("API response has no ID.");
  return id;
}

async function tokenFor(request: APIRequestContext, userId: string): Promise<string> {
  const response = await request.post("/api/v1/auth/session", { data: { user_id: userId } });
  expect(response.status()).toBe(200);
  const token = record(await response.json()).access_token;
  if (typeof token !== "string" || !token) throw new Error("Development session returned no token.");
  return token;
}

async function signIn(page: Page, who: "farmer" | "reviewer" = "farmer"): Promise<void> {
  await page.goto("/#/profile");
  await page.getByRole("button", { name: "Sign in as demo " + who }).click();
  await expect(page.getByRole("status")).toContainText("Signed in as " + who + "-1");
}

async function createFromForm(page: Page, crop = "tomato", area = "2"): Promise<string> {
  await page.goto("/#/new");
  await page.getByLabel("Crop", { exact: true }).selectOption(crop);
  await page.getByLabel(/farm or location/i).fill("San Isidro field");
  await page.getByLabel(/planned area/i).fill(area);
  await page.getByRole("button", { name: "Save plan" }).click();
  await expect(page).toHaveURL(/#\/result\/plan-/);
  const id = new URL(page.url()).hash.split("/").pop();
  if (!id) throw new Error("Created plan URL has no ID.");
  return id;
}

test("FastAPI contract serializes farm, plan, revision, and calculation", async ({ request }) => {
  const headers = { authorization: "Bearer " + await tokenFor(request, "farmer-1") };
  const farmResponse = await request.post("/api/v1/farms", {
    headers, data: { organization_id: "org-1", name: "Contract farm" },
  });
  expect(farmResponse.status()).toBe(201);
  const farmId = idFrom(await farmResponse.json());
  const created = await request.post("/api/v1/plans", {
    headers,
    data: {
      crop_code: "tomato", organization_id: "org-1", farm_id: farmId,
      area_ha: 1, area_margin_ha: 0, planting_date: "2026-09-20",
      harvest_period: "2026-10-01",
    },
  });
  expect(created.status()).toBe(201);
  const plan = record(await created.json());
  const planId = idFrom(plan);
  expect(plan.farm_id).toBe(farmId);
  expect(record(plan.revision).area_ha).toBe(1);

  const calculated = await request.post("/api/v1/plans/" + planId + "/calculate", {
    headers, data: {},
  });
  expect(calculated.status()).toBe(200);
  const result = record(await calculated.json());
  expect(record(result.primary).planned_area_ha).toBe(1);
  expect(record(result.secondary)).toHaveProperty("estimated_range_mt");
  expect(result).toHaveProperty("detailed_evidence");

  const updated = await request.patch("/api/v1/plans/" + planId, {
    headers, data: { area_ha: 1.5 },
  });
  expect(updated.status()).toBe(200);
  const revised = record(await updated.json());
  expect(record(revised.revision).revision_number).toBe(2);
  expect(record(revised.revision).area_ha).toBe(1.5);
});

test("development sign-in is an actual API session", async ({ page, request }) => {
  await signIn(page);
  const token = await page.evaluate(() => window.localStorage.getItem("tanim.access_token"));
  expect(token).toBeTruthy();
  const me = await request.get("/api/v1/me", {
    headers: { authorization: "Bearer " + token },
  });
  expect(me.status()).toBe(200);
  expect(record(await me.json()).user_id).toBe("farmer-1");
});

test("form creates linked farm and plan and renders the returned calculation", async ({ page, request }) => {
  await signIn(page);
  await page.goto("/#/new");
  await page.getByLabel(/farm or location/i).fill("San Isidro field");
  await page.getByLabel(/planned area/i).fill("2");
  const sent = page.waitForRequest((req) => req.url().endsWith("/api/v1/plans") && req.method() === "POST");
  await page.getByRole("button", { name: "Save plan" }).click();
  const planRequest = await sent;
  expect(planRequest.postDataJSON()).toMatchObject({
    crop_code: "tomato", organization_id: "org-1", area_ha: 2,
    harvest_period: "2026-10-01",
  });
  const farmId = planRequest.postDataJSON().farm_id;
  expect(typeof farmId).toBe("string");
  const token = await page.evaluate(() => window.localStorage.getItem("tanim.access_token"));
  const farm = await request.get("/api/v1/farms/" + farmId, {
    headers: { authorization: "Bearer " + token },
  });
  expect(farm.status()).toBe(200);
  expect(record(await farm.json()).name).toBe("San Isidro field");
  await expect(page).toHaveURL(/#\/result\/plan-/);
  await expect(page.getByRole("heading", { name: "Coordination result" })).toBeVisible();
  await expect(page.getByText("Synthetic demo", { exact: false })).toHaveCount(0);
  await expect(page.getByText("2 ha", { exact: true })).toBeVisible();
});

test("invalid plan has a focused accessible error summary", async ({ page }) => {
  await signIn(page);
  await page.goto("/#/new");
  await page.getByLabel(/farm or location/i).fill("San Isidro field");
  await page.getByLabel(/planned area/i).fill("0");
  await page.getByRole("button", { name: "Save plan" }).click();
  const summary = page.locator(".err-summary");
  await expect(summary).toContainText("Planned area must be more than 0 ha");
  await expect(summary).toBeFocused();
  await expect(page.getByLabel(/planned area/i)).toHaveAttribute("aria-invalid", "true");
});

test("missing comparison evidence stays incomplete in the browser", async ({ page }) => {
  await signIn(page);
  await createFromForm(page, "eggplant");
  await expect(page.getByText(/no reviewed reference/i).first()).toBeVisible();
  await page.getByText("Comparison detail").click();
  await expect(page.locator("details.card").getByText(/does not have a reviewed comparison reference/i)).toBeVisible();
  await expect(page.getByText(/synthetic offline/i)).toHaveCount(0);
});

test("adjustment PATCH creates a revision and recalculates from FastAPI", async ({ page, request }) => {
  await signIn(page);
  const planId = await createFromForm(page);
  await page.getByRole("link", { name: "Adjust this plan" }).click();
  await page.getByLabel(/planned area/i).fill("3");
  const sent = page.waitForRequest((req) => req.url().endsWith("/api/v1/plans/" + planId) && req.method() === "PATCH");
  await page.getByRole("button", { name: "Save changes" }).click();
  expect((await sent).postDataJSON()).toMatchObject({ area_ha: 3 });
  await expect(page).toHaveURL(/#\/result\/plan-/);
  await expect(page.getByText("3 ha", { exact: true })).toBeVisible();
  const token = await page.evaluate(() => window.localStorage.getItem("tanim.access_token"));
  const revisions = await request.get("/api/v1/plans/" + planId + "/revisions", {
    headers: { authorization: "Bearer " + token },
  });
  expect(revisions.status()).toBe(200);
  expect(record(await revisions.json()).revisions).toHaveLength(2);
});

test("overview displays the server aggregate after plan creation", async ({ page }) => {
  await signIn(page);
  await createFromForm(page);
  await page.goto("/#/overview");
  await expect(page.getByRole("heading", { name: /planning to produce/i })).toBeVisible();
  await expect(page.getByText(/Synthetic offline aggregate snapshot/)).toHaveCount(0);
  await expect(page.getByRole("table")).toContainText("2026-10-01");
  await expect(page.getByRole("table")).toContainText("tomato");
});

test("reference submission and reviewer verification use real transitions", async ({ page, request }) => {
  const farmerHeaders = { authorization: "Bearer " + await tokenFor(request, "farmer-1") };
  const source = "Playwright review " + test.info().project.name + " " + Date.now();
  const created = await request.post("/api/v1/references", {
    headers: farmerHeaders,
    data: {
      crop_code: "tomato", organization_id: "org-1", amount_mt: 18,
      reference_type: "local_committed_demand", geography: "CALABARZON",
      period: "2026-H2", source,
    },
  });
  expect(created.status()).toBe(201);
  const refId = idFrom(await created.json());
  const submitted = await request.post("/api/v1/references/" + refId + "/submit", {
    headers: farmerHeaders, data: {},
  });
  expect(submitted.status()).toBe(200);
  expect(record(await submitted.json()).review).toBe("under_review");
  await signIn(page, "reviewer");
  await page.goto("/#/references");
  const card = page.getByRole("article").filter({ hasText: source });
  await expect(card).toBeVisible();
  await card.getByRole("button", { name: "Mark verified" }).click();
  await expect(card).toContainText("Review state: verified");
  const reviewerHeaders = { authorization: "Bearer " + await tokenFor(request, "reviewer-1") };
  const reviewed = await request.get("/api/v1/references/" + refId, { headers: reviewerHeaders });
  expect(record(await reviewed.json()).verification_status).toBe("reviewed_verified");
  const invalid = await request.post("/api/v1/references/" + refId + "/verify", {
    headers: reviewerHeaders, data: {},
  });
  expect(invalid.status()).toBe(409);
});

test("same-organization farmer-specific API resources reject another farmer", async ({ page, request }) => {
  const admin = { authorization: "Bearer " + await tokenFor(request, "admin-1") };
  const member = await request.put("/api/v1/organizations/org-1/members/farmer-2", {
    headers: admin, data: { role: "farmer" },
  });
  expect(member.status()).toBe(200);
  const other = { authorization: "Bearer " + await tokenFor(request, "farmer-2") };
  const farm = await request.post("/api/v1/farms", {
    headers: other, data: { organization_id: "org-1", name: "Other farmer field" },
  });
  expect(farm.status()).toBe(201);
  const farmId = idFrom(await farm.json());
  const plan = await request.post("/api/v1/plans", {
    headers: other,
    data: {
      crop_code: "tomato", organization_id: "org-1", farm_id: farmId,
      area_ha: 1, planting_date: "2026-09-20", harvest_period: "2026-10-01",
    },
  });
  expect(plan.status()).toBe(201);
  const planId = idFrom(await plan.json());
  await signIn(page);
  const denied = await page.evaluate(async ({ farmId, planId }) => {
    const authorization = "Bearer " + window.localStorage.getItem("tanim.access_token");
    const farmResponse = await fetch("/api/v1/farms/" + farmId, { headers: { authorization } });
    const planResponse = await fetch("/api/v1/plans/" + planId, { headers: { authorization } });
    const revisionResponse = await fetch("/api/v1/plans/" + planId + "/revisions", { headers: { authorization } });
    const calculationResponse = await fetch("/api/v1/plans/" + planId + "/calculate", {
      method: "POST", headers: { authorization, "content-type": "application/json" }, body: "{}",
    });
    return [farmResponse.status, planResponse.status, revisionResponse.status, calculationResponse.status];
  }, { farmId, planId });
  expect(denied).toEqual([403, 403, 403, 403]);
});

test("320px and common mobile width have no document overflow", async ({ page }) => {
  for (const width of [320, 375]) {
    await page.setViewportSize({ width, height: 800 });
    await page.goto("/#/new");
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(overflow).toBeLessThanOrEqual(1);
    await expect(page.getByRole("button", { name: "Save plan" })).toBeVisible();
  }
});

test("desktop layout shows the organization table", async ({ page }) => {
  await signIn(page);
  await page.setViewportSize({ width: 1280, height: 800 });
  await page.goto("/#/overview");
  await expect(page.getByRole("table")).toBeVisible();
  await expect(page.getByRole("table")).toContainText("Crop");
});
