import pytest
from gemmagraph.sandbox.patches import apply, validate

VALID = "--- a/src/calc.py\n+++ b/src/calc.py\n@@ -1 +1 @@\n-x = 1\n+x = 2\n"


def test_valid_unified_patch():
    assert validate(VALID, ["src/calc.py"])["valid"]


@pytest.mark.parametrize("diff", [
    VALID.replace("--- a/src/calc.py", "--- a/../../outside.py"),
    VALID.replace("--- a/src/calc.py", "--- a/tests/test_calc.py"),
    "old mode 100644\nnew mode 120000\n" + VALID,
    "rename from tests/test_calc.py\nrename to src/calc.py\n" + VALID,
    VALID.replace("+++ b/src/calc.py", "+++ b/src/../outside.py"),
    VALID.replace("src/calc.py", "tests/test_calc.py"),
    VALID.replace("@@ -1 +1 @@", "@@ -10,20 +1 @@"),
    VALID.replace("src/calc.py", "src/calc.py.evil"),
    VALID + "\n--- a/secret.py\n+++ b/secret.py\n@@ -1 +1 @@\n-x\n+y\n",
])
def test_rejects_paths_modes_and_malformed_hunks(diff):
    assert not validate(diff, ["src/calc.py"])["valid"]


async def test_real_git_apply_only_updates_private_workspace(tmp_path):
    root = tmp_path / "workspace"
    (root / "src").mkdir(parents=True)
    source = root / "src/calc.py"
    source.write_text("x = 1\n")
    patch = tmp_path / "candidate.diff"
    patch.write_text(VALID)
    assert (await apply(root, patch))["ok"]
    assert source.read_text() == "x = 2\n"
