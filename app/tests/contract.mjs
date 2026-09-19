// Static artifact checks. API contracts are exercised against FastAPI by Playwright.
import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const appRoot = join(dirname(fileURLToPath(import.meta.url)), "..");
const repoRoot = join(appRoot, "..");

describe("committed frontend artifacts", () => {
  it("labels the exact offline snapshot as synthetic", () => {
    const fixture = JSON.parse(readFileSync(
      join(appRoot, "src/fixtures/tomato_calabarzon_response.json"), "utf8",
    ));
    assert.equal(fixture.synthetic, true);
    assert.equal(fixture.provenance.verificationStatus, "synthetic_demo");
    assert.equal(fixture.provenance.referenceType, "demo_coordination_baseline");
    assert.match(fixture.provenance.evidenceNote, /synthetic demo/i);
  });

  it("does not ship a second browser calculation engine", () => {
    assert.equal(existsSync(join(appRoot, "src/lib/engine.ts")), false);
  });

  it("keeps the versioned calculate route in generated FastAPI OpenAPI", () => {
    const openapi = JSON.parse(readFileSync(join(repoRoot, "openapi/openapi.json"), "utf8"));
    assert.ok(openapi.paths["/api/v1/plans/{plan_id}/calculate"]?.post);
  });
});
