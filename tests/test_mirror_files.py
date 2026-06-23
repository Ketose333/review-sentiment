"""Verify app.py and submission/*.py are byte-identical mirrors.

If this test fails, the deployment (app.py) and submission/submission.py have
diverged — recopy one to the other before merging.
"""

import hashlib
import os.path

_SUBMISSION_DIR = os.path.join(os.path.dirname(__file__), "..", "submission")
_APP_PATH = os.path.join(os.path.dirname(__file__), "..", "app.py")


def _sha256(path: str) -> str:
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def test_app_py_matches_submission_py():
    submission_files = [
        os.path.join(_SUBMISSION_DIR, f)
        for f in os.listdir(_SUBMISSION_DIR)
        if f.endswith(".py") and os.path.isfile(os.path.join(_SUBMISSION_DIR, f))
    ]
    assert len(submission_files) > 0, "No .py files found in submission/"

    app_hash = _sha256(_APP_PATH)
    for sub_path in submission_files:
        sub_name = os.path.basename(sub_path)
        sub_hash = _sha256(sub_path)
        assert (
            app_hash == sub_hash
        ), f"app.py hash ({app_hash}) != {sub_name} hash ({sub_hash}) — files have diverged"
