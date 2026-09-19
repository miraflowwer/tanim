import importlib
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def test_vercel_config_points_to_web_build():
    config = json.loads((ROOT / "vercel.json").read_text(encoding="utf-8"))
    assert config["installCommand"] == "npm ci --prefix web"
    assert config["buildCommand"] == "npm run build --prefix web"
    assert config["outputDirectory"] == "web/dist"


def test_vercel_routes_reuse_service_handler():
    service = importlib.import_module("scripts.service")
    for module_name in ("api.health", "api.options", "api.grci"):
        module = importlib.import_module(module_name)
        assert issubclass(module.handler, service.GrciRequestHandler)


def test_deployment_docs_and_paths_exist():
    for path in (
        ROOT / "docs" / "DEPLOYMENT.md",
        ROOT / "docs" / "API_CONTRACT.md",
        ROOT / "docs" / "WEB_DESIGN.md",
        ROOT / "web" / "package-lock.json",
    ):
        assert path.exists(), path


if __name__ == "__main__":
    tests = [name for name in globals() if name.startswith("test_")]
    for name in sorted(tests):
        globals()[name]()
    print(f"OK: {len(tests)} deployment checks passed")
