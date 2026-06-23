"""Shared helpers for training scripts."""

import os
import shutil


def mirror_to_submission(model_out_dir: str) -> None:
    """Copy a trained artifact directory into submission/ so both copies stay in sync.

    Training scripts update the root ``models/`` directory. After each run, this
    helper mirrors the same directory into ``submission/models/`` so the
    submission notebook / app can use the latest artifacts without a separate
    copy step.
    """
    src = model_out_dir
    dst = os.path.join("submission", model_out_dir)
    if os.path.isdir(dst):
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
    print(f"Mirrored {src}/ -> {dst}/")
