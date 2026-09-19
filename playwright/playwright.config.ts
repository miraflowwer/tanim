import { defineConfig, devices } from "@playwright/test";

const backend = {
  command: "python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000",
  cwd: "..",
  url: "http://127.0.0.1:8000/api/v1/health",
  reuseExistingServer: true,
  timeout: 30000,
  env: { ALLOW_DEV_AUTH: "true", TANIM_RUNTIME_MODE: "inmemory", PYTHONPATH: ".." },
};

const frontend = {
  command: "npm --prefix app run preview -- --host 127.0.0.1 --port 4173",
  cwd: "..",
  url: "http://127.0.0.1:4173",
  reuseExistingServer: true,
  timeout: 30000,
};

export default defineConfig({
  testDir: "./tests",
  fullyParallel: false,
  workers: 1,
  reporter: "list",
  use: { baseURL: "http://127.0.0.1:4173", trace: "on-first-retry" },
  webServer: [backend, frontend],
  projects: [
    { name: "mobile", use: { ...devices["Pixel 5"] } },
    { name: "desktop", use: { ...devices["Desktop Chrome"] } },
  ],
});
