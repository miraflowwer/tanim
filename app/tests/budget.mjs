// JS budget S31: compressed initial JS target < 250 KB. Run after build.
import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { existsSync, readdirSync, statSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const dist = join(dirname(fileURLToPath(import.meta.url)), "..", "dist", "assets");

describe("js budget (<250KB)", () => {
  it("fails when the build is missing and enforces the budget", () => {
    assert.ok(existsSync(dist), "app/dist/assets is missing; run npm run build before the budget test");
    const files = readdirSync(dist).filter((file) => file.endsWith(".js"));
    assert.ok(files.length > 0, "app/dist/assets contains no JavaScript bundle");
    const total = files.reduce((sum, file) => sum + statSync(join(dist, file)).size, 0);
    assert.ok(total < 250 * 1024, `JS total ${total} bytes exceeds 250KB`);
  });
});
