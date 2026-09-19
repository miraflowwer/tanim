// Member 2 static contract checks: route wiring, shared primitives, API use,
// accessibility markers, and copy rules. Browser behavior is covered by Playwright.
import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { existsSync, readFileSync, readdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const appRoot = join(dirname(fileURLToPath(import.meta.url)), "..");
const repoRoot = join(appRoot, "..");

function src(relative) {
  return readFileSync(join(appRoot, relative), "utf8");
}

function walk(dir, suffixes) {
  const found = [];
  for (const entry of readdirSync(join(appRoot, dir), { withFileTypes: true })) {
    const relative = join(dir, entry.name);
    if (entry.isDirectory()) found.push(...walk(relative, suffixes));
    else if (suffixes.some((suffix) => entry.name.endsWith(suffix))) found.push(relative);
  }
  return found;
}

const viewFiles = walk("src/features", [".views.tsx"]);
const apiFiles = walk("src/features", [".api.ts"]);

describe("member 2 route wiring", () => {
  it("fills reviewer, admin, global, and coordinator navigation", () => {
    const reviewer = src("src/app/routes/reviewer.ts");
    assert.ok(reviewer.includes('"review"'));
    assert.ok(reviewer.includes('"refnew"'));
    const admin = src("src/app/routes/admin.ts");
    for (const id of ["admin", "members", "invitations", "organization", "audit", "exports", "policy", "consent"]) {
      assert.ok(admin.includes(`"${id}"`), `admin nav is missing ${id}`);
    }
    const global = src("src/app/routes/global.ts");
    assert.ok(global.includes('"notifications"'));
    assert.ok(global.includes('"search"'));
    const coordinator = src("src/app/routes/coordinator.ts");
    for (const id of ["attention", "map", "timeline"]) {
      assert.ok(coordinator.includes(`"${id}"`), `coordinator nav is missing ${id}`);
    }
  });

  it("registers detail routes without breaking the shared router", () => {
    const router = src("src/app/router.ts");
    for (const id of ["cplan", "ref", "history"]) {
      assert.ok(router.includes(`"${id}"`), `router is missing detail route ${id}`);
    }
  });

  it("renders every new route id from App", () => {
    const app = src("src/App.tsx");
    for (const id of ["attention", "cplan", "map", "timeline", "review", "ref", "refnew",
      "admin", "members", "invitations", "organization", "audit", "exports", "policy",
      "consent", "notifications", "search", "history"]) {
      assert.ok(app.includes(`"${id}"`), `App does not render route ${id}`);
    }
  });
});

describe("member 2 shared primitives", () => {
  it("keeps views on shared components with no local design system", () => {
    for (const file of viewFiles) {
      const text = src(file);
      assert.ok(
        text.includes("../../components/"),
        `${file} does not reuse shared components`,
      );
      for (const name of ["Button", "Card", "DataTable", "Alert", "Status"]) {
        assert.ok(!new RegExp(`function ${name}\\b`).test(text), `${file} redefines ${name}`);
        assert.ok(!new RegExp(`const ${name} =`).test(text), `${file} redefines ${name}`);
      }
    }
  });

  it("keeps network calls inside feature api modules, never in views", () => {
    for (const file of viewFiles) {
      assert.ok(!/fetch\s*\(/.test(src(file)), `${file} calls fetch directly`);
    }
    assert.ok(apiFiles.length > 0);
  });

  it("does not duplicate trusted calculations in the browser", () => {
    assert.equal(existsSync(join(appRoot, "src/lib/engine.ts")), false);
    const forbidden = ["plannedSupplyRange", "supplyLoadRange", "collectiveAreaRange", "compute_grci"];
    for (const file of [...viewFiles, ...apiFiles]) {
      for (const name of forbidden) {
        assert.ok(!src(file).includes(name), `${file} duplicates engine logic ${name}`);
      }
    }
  });
});

describe("member 2 api contracts", () => {
  it("calls only versioned endpoints present in generated OpenAPI", () => {
    const openapi = JSON.parse(readFileSync(join(repoRoot, "openapi/openapi.json"), "utf8"));
    const paths = openapi.paths;
    const missing = [];
    for (const file of apiFiles) {
      const text = src(file);
      const calls = [...text.matchAll(/request\("([A-Z]+)",\s*`([^`]+)`/g)];
      for (const [, method, raw] of calls) {
        let key = raw.replace(/\$\{[^}]*\}/g, "{id}").split("?")[0];
        if (raw.includes("${query}")) key = key.replace(/\{id\}$/, "");
        const action = key.match(/^\/api\/v1\/references\/\{ref_id\}\/([^/]+)$/)?.[1];
        if (action) {
          const valid = [
            "submit", "verify", "reject", "reopen", "expire", "supersede", "flag",
          ].includes(action) && paths[`/api/v1/references/{ref_id}/${action}`]?.[method.toLowerCase()];
          if (!valid) missing.push(`${file}: ${method} ${key}`);
          continue;
        }
        key = key
          .replace("/references/{id}/", "/references/{ref_id}/")
          .replace(/\/references\/\{id\}$/, "/references/{ref_id}")
          .replace("/plans/{id}", "/plans/{plan_id}")
          .replace("/crops/{id}/yield", "/crops/{code}/yield")
          .replace("/exports/{id}", "/exports/{export_id}")
          .replace("/data-sources/{id}/", "/data-sources/{key}/")
          .replace("/calculations/{id}", "/calculations/{calculation_id}");
        const operation = paths[key]?.[method.toLowerCase()];
        if (!operation) missing.push(`${file}: ${method} ${key}`);
      }
    }
    assert.deepEqual(missing, []);
  });

  it("records missing backend contracts instead of inventing behavior", () => {
    const requests = readFileSync(join(repoRoot, "docs/implementation/API_REQUESTS.md"), "utf8");
    for (const id of ["API-M2-001", "API-M2-002", "API-M2-003", "API-M2-004", "API-M2-005", "API-M2-006"]) {
      assert.ok(requests.includes(id), `API_REQUESTS.md is missing ${id}`);
    }
  });
});

describe("member 2 accessibility and copy", () => {
  it("marks every view with accessible names", () => {
    for (const file of viewFiles) {
      assert.ok(/aria-(label|labelledby)/.test(src(file)), `${file} has no accessible name`);
    }
  });

  it("gives charts and maps nonvisual equivalents", () => {
    assert.ok(src("src/components/charts/BarChart.tsx").includes("<table"));
    assert.ok(src("src/components/charts/LineChart.tsx").includes("<table"));
    assert.ok(src("src/components/map/MapPanel.tsx").toLowerCase().includes("fallback"));
  });

  it("avoids banned wording and labels synthetic fixtures", () => {
    for (const file of [...viewFiles, ...walk("src/features", [".fixtures.ts"] )]) {
      const text = src(file).toLowerCase();
      assert.ok(!text.includes("confidence interval"), `${file} uses banned wording`);
      assert.ok(!text.includes("ai recommendation"), `${file} uses banned wording`);
    }
    assert.ok(src("src/features/organization/organization.fixtures.ts").includes("synthetic"));
    assert.ok(src("src/features/notifications/notifications.fixtures.ts").includes("synthetic"));
  });
});
