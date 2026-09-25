"""Install the three immutable deployment artifacts and verify every model file.

The manifest is read as syntax from backend/app/artifacts.py so this build step does
not need to import the API or deserialize a model. A changed manifest, source file,
or downloaded weight makes the image build fail.
"""

import ast
import hashlib
import sys
import tempfile
import urllib.request
from pathlib import Path
from urllib.parse import quote


WEIGHTS = frozenset({"model.pkl", "vectorizer.pkl", "model.h5", "model.safetensors"})


def literal_with_names(node: ast.AST, values: dict) -> object:
    if isinstance(node, ast.Name):
        return values[node.id]
    if isinstance(node, ast.Dict):
        return {
            literal_with_names(key, values): literal_with_names(value, values)
            for key, value in zip(node.keys, node.values)
        }
    return ast.literal_eval(node)


def read_manifest(path: Path) -> tuple[str, str, dict[str, dict[str, str]]]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    values = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Name):
            continue
        if target.id in {"EXPECTED_REPO", "EXPECTED_REVISION", "EXPECTED_MANIFEST", "MODEL_MANIFESTS"}:
            values[target.id] = literal_with_names(node.value, values)
    return values["EXPECTED_REPO"], values["EXPECTED_REVISION"], values["MODEL_MANIFESTS"]


def verified_copy(source: Path, target: Path, expected: str) -> None:
    if source.is_symlink() or not source.is_file():
        raise ValueError(f"missing or linked source: {source}")
    content = source.read_bytes()
    if hashlib.sha256(content).hexdigest() != expected:
        # Git stores these JSON files with LF. A Windows checkout may expand
        # them to CRLF; deploy the verified Git bytes on either build host.
        content = content.replace(b"\r\n", b"\n")
    if hashlib.sha256(content).hexdigest() != expected:
        raise ValueError(f"SHA-256 mismatch: {source}")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)


def verified_download(url: str, target: Path, expected: str) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as temp:
        temporary = Path(temp.name)
        digest = hashlib.sha256()
        try:
            with urllib.request.urlopen(url, timeout=90) as response:
                for chunk in iter(lambda: response.read(1024 * 1024), b""):
                    digest.update(chunk)
                    temp.write(chunk)
            if digest.hexdigest() != expected:
                raise ValueError(f"SHA-256 mismatch: {url}")
            temporary.replace(target)
        finally:
            temporary.unlink(missing_ok=True)


def install(source_root: Path, destination: Path) -> None:
    repo, revision, manifests = read_manifest(source_root / "backend/app/artifacts.py")
    if set(manifests) != {"tfidf_lr", "lstm", "klue_bert"}:
        raise ValueError("model manifest must cover exactly the three deployment models")
    for model_id, manifest in manifests.items():
        for relative, expected in manifest.items():
            path = Path(relative)
            if path.parts[:2] != ("models", model_id) or len(path.parts) != 3:
                raise ValueError(f"unexpected artifact path: {relative}")
            if len(expected) != 64 or any(ch not in "0123456789abcdef" for ch in expected):
                raise ValueError(f"invalid SHA-256: {relative}")
            target = destination / relative
            if path.name in WEIGHTS:
                url = f"https://huggingface.co/datasets/{quote(repo, safe='/')}/resolve/{revision}/{quote(relative)}"
                verified_download(url, target, expected)
            else:
                verified_copy(source_root / relative, target, expected)
            print(f"verified {relative}", flush=True)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("usage: install_model_artifacts.py SOURCE_ROOT DESTINATION")
    install(Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve())
