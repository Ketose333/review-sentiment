"""Stage submission/{review_sentiment.py, review_sentiment.ipynb} and zip them with the report.

소스(py)는 review_sentiment.py 1개만 포함한다(src/, scripts/는 zip에 넣지 않음). app.py는
src/ 코드를 인라인한 단일 파일이므로, 먼저 ``python scripts/sync_standalone_app.py``로
app.py를 최신 src/ 상태와 동기화한 뒤 이 스크립트를 실행할 것.

submission/ 폴더(레포 내부, 외부 절대경로 의존 없음)가 ipynb의 정본 위치다
(scripts/make_notebook.py가 거기에 직접 씀). app.py는 이 스크립트가
submission/review_sentiment.py로 복사해 보존하고, zip은 그 두 파일 + report로 만든다.

Usage:
  python scripts/sync_standalone_app.py
  python scripts/make_notebook.py
  python scripts/package_submission.py --name 김관영
  python scripts/package_submission.py --name 김관영 --report 김관영_머신러닝프로젝트_보고서.pdf
"""

from __future__ import annotations

import argparse
import os
import shutil
import zipfile


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--name", default="김관영", help="제출자 이름 (zip 파일명에 사용)")
    parser.add_argument("--notebook", default="submission/review_sentiment.ipynb")
    parser.add_argument("--report", default="김관영_머신러닝프로젝트_보고서.pdf")
    parser.add_argument("--app-py", default="app.py")
    parser.add_argument("--submission-dir", default="submission")
    parser.add_argument("--out", default=None, help="출력 zip 경로 (기본: {name}_머신러닝프로젝트.zip)")
    args = parser.parse_args()

    out = args.out or f"{args.name}_머신러닝프로젝트.zip"
    os.makedirs(args.submission_dir, exist_ok=True)
    files: list[tuple[str, str]] = []  # (arcname, source_path)

    if os.path.exists(args.notebook):
        files.append((os.path.basename(args.notebook), args.notebook))
    else:
        print(f"WARNING: notebook not found: {args.notebook}")

    if os.path.exists(args.app_py):
        dest = os.path.join(args.submission_dir, "review_sentiment.py")
        shutil.copyfile(args.app_py, dest)
        files.append((os.path.basename(dest), dest))
    else:
        print(f"WARNING: app.py not found: {args.app_py}")

    if os.path.exists(args.report):
        files.append((os.path.basename(args.report), args.report))
    else:
        print(f"WARNING: report not found: {args.report}")

    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for arc, src in files:
            z.write(src, arc)
            print(f"  added: {arc}")

    print(f"\nCreated {out} with {len(files)} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
