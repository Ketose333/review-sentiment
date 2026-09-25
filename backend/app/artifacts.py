"""Verify every file used by a model before loading executable model data."""

import hashlib
import os
from functools import lru_cache
from pathlib import Path
from threading import Lock

from backend.app.tables import ModelRegistry

TFIDF_FILES = ("model.pkl", "vectorizer.pkl")
EXPECTED_REPO = "Ketose333/review-sentiment-assets"
EXPECTED_REVISION = "915d7784e3c81333d6812913b0a80eda37fdbd41"
EXPECTED_MANIFEST = {
    "models/tfidf_lr/model.pkl": "8eb8571babaf37d452b3b894281fde6997c6b2aaf8533efdfb85aa6f28bbe611",
    "models/tfidf_lr/vectorizer.pkl": "69df406990335fa9ba1e2d1411ad2a56a41ecba40abded1781cafff404727118",
}
MODEL_FILES = {
    "tfidf_lr": TFIDF_FILES,
    "lstm": ("model.h5", "tokenizer.json"),
    "klue_bert": ("model.safetensors", "config.json", "tokenizer.json", "tokenizer_config.json"),
}
MODEL_MANIFESTS = {
    "tfidf_lr": {
        "models/tfidf_lr/model.pkl": "8eb8571babaf37d452b3b894281fde6997c6b2aaf8533efdfb85aa6f28bbe611",
        "models/tfidf_lr/vectorizer.pkl": "69df406990335fa9ba1e2d1411ad2a56a41ecba40abded1781cafff404727118",
    },
    "lstm": {
        "models/lstm/model.h5": "aa87bac234a46daebda568a79000cb656dc781df39cbe28152200935a2f9f60b",
        "models/lstm/tokenizer.json": "ec62e121240daf19b5b206db0e91c4f108b740a7dd041173d5bfaa46c79da451",
    },
    "klue_bert": {
        "models/klue_bert/model.safetensors": "8a2e7480a194c64ffe0b22a35a3a0ecd9e4cc5cd5e68cb73436b399956f28423",
        "models/klue_bert/config.json": "a1a6b6ae0ce34fa89b53ddca458929c10c794f5394d68bbe727723f1fc8f94dd",
        "models/klue_bert/tokenizer.json": "f9d6539cd3f6972070d5531342d87ab67faa2bc7d0570fe454715031e893191a",
        "models/klue_bert/tokenizer_config.json": "3cfbb173107c0d1668eb08657cddba58563c9daa94f7229006d08c40e5e75bb3",
    },
}


class ArtifactUnavailable(Exception):
    pass


_hash_lock = Lock()


@lru_cache(maxsize=32)
def _digest_file(path: str, identity: tuple[int, ...], normalize_json: bool) -> str:
    """Hash once per immutable file identity; changed metadata forces revalidation."""
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        if normalize_json:
            digest.update(stream.read().replace(b"\r\n", b"\n"))
        else:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
    return digest.hexdigest()


def _verified_digest(path: Path, normalize_json: bool) -> str:
    try:
        stat = path.stat(follow_symlinks=False)
        if os.name == "nt":
            try:
                change_time = _windows_change_time(path)
            except OSError:
                # An unsupported Win32 query must disable the cache, not the model.
                change_time = 0
        else:
            change_time = stat.st_ctime_ns
        identity = (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, change_time, stat.st_mode)
        # lru_cache alone permits duplicate misses from concurrent requests.
        with _hash_lock:
            if change_time == 0:
                # Some Windows filesystems/providers do not expose ChangeTime.
                # Without it a same-size overwrite plus restored mtime could
                # reuse a stale digest, so fail closed to an uncached hash.
                return _digest_file.__wrapped__(str(path), identity, normalize_json)
            return _digest_file(str(path), identity, normalize_json)
    except OSError:
        raise ArtifactUnavailable() from None


def _windows_change_time(path: Path) -> int:
    """Return NTFS ChangeTime; Python <=3.11 st_ctime is file creation time."""
    import ctypes
    import msvcrt

    class FileBasicInfo(ctypes.Structure):
        _fields_ = [
            ("CreationTime", ctypes.c_longlong),
            ("LastAccessTime", ctypes.c_longlong),
            ("LastWriteTime", ctypes.c_longlong),
            ("ChangeTime", ctypes.c_longlong),
            ("FileAttributes", ctypes.c_ulong),
        ]

    api = ctypes.WinDLL("kernel32", use_last_error=True).GetFileInformationByHandleEx
    api.argtypes = (ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_ulong)
    api.restype = ctypes.c_bool
    info = FileBasicInfo()
    with path.open("rb") as stream:
        handle = msvcrt.get_osfhandle(stream.fileno())
        if not api(handle, 0, ctypes.byref(info), ctypes.sizeof(info)):
            raise OSError(ctypes.get_last_error(), "GetFileInformationByHandleEx failed")
    return info.ChangeTime


def artifact_directory(model_id: str = "tfidf_lr") -> Path:
    variable = "TFIDF_ARTIFACT_DIR" if model_id == "tfidf_lr" else f"{model_id.upper()}_ARTIFACT_DIR"
    configured = os.environ.get(variable)
    if not configured:
        raise ArtifactUnavailable()
    return Path(configured).resolve()


def verified_directory(row: ModelRegistry) -> Path:
    if row.model_id not in MODEL_FILES or row.artifact_repo != EXPECTED_REPO or row.artifact_revision != EXPECTED_REVISION:
        raise ArtifactUnavailable()
    directory = artifact_directory(row.model_id)
    if not directory.is_dir():
        raise ArtifactUnavailable()
    manifest = row.artifact_manifest
    expected_manifest = EXPECTED_MANIFEST if row.model_id == "tfidf_lr" else MODEL_MANIFESTS[row.model_id]
    if not isinstance(manifest, dict) or manifest != expected_manifest:
        raise ArtifactUnavailable()
    for name in MODEL_FILES[row.model_id]:
        expected = manifest[f"models/{row.model_id}/{name}"]
        if not isinstance(expected, str) or len(expected) != 64:
            raise ArtifactUnavailable()
        path = directory / name
        if not path.is_file() or path.is_symlink():
            raise ArtifactUnavailable()
        # Git checkouts on Windows may contain CRLF while image builds use LF.
        normalize_json = row.model_id == "klue_bert" and name.endswith(".json")
        if _verified_digest(path, normalize_json) != expected:
            raise ArtifactUnavailable()
    return directory


def is_available(row: ModelRegistry) -> bool:
    if not row.enabled or row.model_id not in MODEL_FILES:
        return False
    try:
        verified_directory(row)
        return True
    except ArtifactUnavailable:
        return False
