"""The build privacy gate must refuse leaked values, not merely log them."""

import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "frontend/scripts/check-owner-grid-public.ts"


@pytest.mark.parametrize(
    ("name", "value", "message"),
    [
        ("data/index.html", '{"connected_load_kw":60}', "Private owner grid field"),
        ("analytics-data/README.txt", "owner_grid_revisions", "Private owner grid field"),
        ("assets/app.js", "PrivateOwnerGridCanary", "Private grid canary"),
    ],
)
def test_private_public_artifact_refused(tmp_path, name, value, message):
    path = tmp_path / name
    path.parent.mkdir(parents=True)
    path.write_text(value, encoding="utf-8")
    result = subprocess.run(["node", str(SCRIPT), str(tmp_path)], capture_output=True, text=True)
    assert result.returncode != 0
    assert message in result.stderr


def test_shared_spa_owner_form_code_is_allowed(tmp_path):
    (tmp_path / "app.js").write_text("const connected_load_kw = null;", encoding="utf-8")
    subprocess.run(["node", str(SCRIPT), str(tmp_path)], check=True, capture_output=True)
