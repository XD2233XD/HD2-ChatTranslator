"""构建水印/签名发布包。

  python tools/watermark.py --folder release/HD2ChatTranslator-1.0.0 --version 1.0.0
      --author XD2233XD --watermark-id HD2CT-XD2233XD-xxxx --key keys/hd2ct_ed25519
      --out release/HD2ChatTranslator-1.0.0-win64.zip

做四件事：
  1. 给发布目录写 WATERMARK.json（作者、稳定 ID、build_id、每个文件的 SHA256）
  2. 写 SHA256SUMS.txt，并用 ssh-keygen -Y sign 签名（ed25519）
  3. 把公钥、签名、验证说明放进包
  4. 打 ZIP（归档注释里再写一遍作者/ID/build），并给外层 ZIP 生成 SHA256SUMS + 签名
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import time
import zipfile
from pathlib import Path

GENERATED = {
    "WATERMARK.json", "SHA256SUMS.txt", "SHA256SUMS.txt.sig",
    "hd2ct_ed25519.pub", "README-SIGNATURE.txt",
}


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def ssh_keygen() -> str:
    for p in (r"C:\Windows\System32\OpenSSH\ssh-keygen.exe", shutil.which("ssh-keygen")):
        if p and Path(p).is_file():
            return p
    raise SystemExit("ssh-keygen not found")


def sign(path: Path, key: Path, namespace: str) -> Path:
    sig = Path(str(path) + ".sig")
    if sig.exists():
        sig.unlink()
    subprocess.run([ssh_keygen(), "-Y", "sign", "-f", str(key), "-n", namespace, str(path)],
                   check=True)
    if not sig.is_file():
        raise SystemExit("signature not produced: " + str(sig))
    return sig


def files_in(folder: Path) -> list[Path]:
    out = []
    for p in sorted(folder.rglob("*")):
        if p.is_file() and str(p.relative_to(folder)).replace("\\", "/") not in GENERATED:
            out.append(p)
    return out


def write_checksums(folder: Path) -> Path:
    lines = []
    for p in files_in(folder):
        rel = str(p.relative_to(folder)).replace("\\", "/")
        lines.append(f"{sha256_file(p)}  {rel}")
    path = folder / "SHA256SUMS.txt"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return path


def make_zip(folder: Path, out: Path, comment: str) -> str:
    if out.exists():
        out.unlink()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(folder.rglob("*")):
            if p.is_file():
                rel = str(p.relative_to(folder)).replace("\\", "/")
                z.write(p, f"{folder.name}/{rel}")
        z.comment = comment.encode("utf-8")
    return sha256_file(out)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--folder", required=True)
    ap.add_argument("--version", required=True)
    ap.add_argument("--author", required=True)
    ap.add_argument("--watermark-id", required=True)
    ap.add_argument("--key", required=True)
    ap.add_argument("--namespace", default="hd2ct")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    folder = Path(a.folder).resolve()
    out = Path(a.out).resolve()
    key = Path(a.key).resolve()
    pub = Path(str(key) + ".pub")
    if not folder.is_dir():
        raise SystemExit("folder not found: " + str(folder))
    if not key.is_file() or not pub.is_file():
        raise SystemExit("signing key pair missing: " + str(key))

    for name in GENERATED:
        p = folder / name
        if p.exists():
            p.unlink()

    tree = "\n".join(f"{p.relative_to(folder).as_posix()}:{sha256_file(p)}" for p in files_in(folder))
    tree_hash = hashlib.sha256(tree.encode("utf-8")).hexdigest()
    built_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    build_id = f"{a.version}-{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}-{tree_hash[:8]}"

    shutil.copyfile(pub, folder / "hd2ct_ed25519.pub")
    wm = {
        "schema": 1,
        "author": a.author,
        "watermark_id": a.watermark_id,
        "build_id": build_id,
        "version": a.version,
        "built_at": built_at,
        "namespace": a.namespace,
        "tree_sha256": tree_hash,
        "public_key": "hd2ct_ed25519.pub",
        "public_key_sha256": hashlib.sha256(pub.read_bytes()).hexdigest(),
        "files": {
            p.relative_to(folder).as_posix(): sha256_file(p) for p in files_in(folder)
        },
    }
    (folder / "WATERMARK.json").write_text(
        json.dumps(wm, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    sums = write_checksums(folder)
    sig = sign(sums, key, a.namespace)

    fingerprint = subprocess.run([ssh_keygen(), "-lf", str(pub)], capture_output=True, text=True,
                                 check=True).stdout.strip()
    verify = f"""HD2 Chat Translator - signature
author      : {a.author}
watermark   : {a.watermark_id}
build       : {build_id}
public key  : {fingerprint}

Verify this package:
  1. ssh-keygen -Y check-novalidate -n {a.namespace} -s SHA256SUMS.txt.sig < SHA256SUMS.txt
     -> should print: Good "{a.namespace}" signature with ED25519 key {fingerprint.split()[1]}
  2. Compare that key with hd2ct_ed25519.pub (same file in this package).
  3. Check file hashes in SHA256SUMS.txt (PowerShell):
       Get-FileHash <file> -Algorithm SHA256

This proves the package was signed by the holder of the private key.
It cannot prevent someone from removing the watermark and repacking.
"""
    (folder / "README-SIGNATURE.txt").write_text(verify, encoding="utf-8", newline="\n")

    comment = f"HD2CT|author={a.author}|watermark={a.watermark_id}|build={build_id}"
    zip_sha = make_zip(folder, out, comment)

    outer = out.parent / "SHA256SUMS.txt"
    outer.write_text(f"{zip_sha}  {out.name}\n", encoding="utf-8", newline="\n")
    outer_sig = sign(outer, key, a.namespace)
    shutil.copyfile(pub, out.parent / pub.name)

    print("watermark  :", a.watermark_id)
    print("build      :", build_id)
    print("zip        :", out)
    print("zip sha256 :", zip_sha)
    print("signature  :", outer_sig)
    print("fingerprint:", fingerprint)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
