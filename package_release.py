"""Package portable binary, documentation, notices and maintainable source; no user settings."""
from pathlib import Path
import hashlib
import json
import shutil
import zipfile

BASE = Path(__file__).resolve().parent
OUT = BASE / "delivery"
MANUAL = '\u4f7f\u7528\u8bf4\u660e.md'


def main():
    shutil.copy2(BASE / "README.md", OUT / MANUAL)
    source = OUT / "GPUChecker-v5-source.zip"
    with zipfile.ZipFile(source, "w", zipfile.ZIP_DEFLATED) as archive:
        for folder in ("src", "tests", "assets"):
            for path in (BASE / folder).rglob("*"):
                if path.is_file() and "__pycache__" not in path.parts:
                    archive.write(path, path.relative_to(BASE))
        for name in ("README.md", "build.ps1", "package_release.py", "requirements.txt", "requirements-build.txt", "requirements-lock.txt", ".gitignore"):
            archive.write(BASE / name, name)
        for name in ("portable.flag.example", "THIRD_PARTY_NOTICES.md", "VALIDATION.md"):
            archive.write(OUT / name, "delivery/" + name)
        for path in (OUT / "licenses").rglob("*"):
            if path.is_file():
                archive.write(path, path.relative_to(BASE))
    bundle = OUT / "GPUChecker-v5-Windows-x64.zip"
    with zipfile.ZipFile(bundle, "w", zipfile.ZIP_DEFLATED) as archive:
        for name in ("GPUChecker-v5.exe", MANUAL, "GPUChecker-v5-source.zip", "portable.flag.example", "THIRD_PARTY_NOTICES.md", "VALIDATION.md", "preview.png", "config-editor.png", "host-editor.png", "preview-nogpu.png"):
            if (OUT/name).exists():
                archive.write(OUT / name, "GPUChecker/" + name)
        for path in (OUT / "licenses").rglob("*"):
            if path.is_file():
                archive.write(path, "GPUChecker/" + str(path.relative_to(OUT)))
    manifest = {p.name: {"bytes": p.stat().st_size, "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
                for p in (OUT / "GPUChecker-v5.exe", source, bundle)}
    (OUT / "SHA256-v5.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
