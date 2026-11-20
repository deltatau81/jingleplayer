"""Package existing native PyInstaller output; never publish or create tags."""
import hashlib
import platform
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path
from jingleplayer_version import APP_VERSION


def main():
    root = Path(__file__).resolve().parent
    system = platform.system()
    arch = platform.machine().lower()
    arch = {"amd64": "x86_64", "aarch64": "arm64"}.get(arch, arch)
    out = root / "dist" / "release"
    out.mkdir(parents=True, exist_ok=True)
    stem = f"Jingleplayer-{APP_VERSION}-{system}-{arch}-unsigned"
    if system == "Windows":
        source = root / "dist" / "Jingleplayer.exe"
        if not source.is_file():
            raise FileNotFoundError(source)
        archive = out / (stem + ".zip")
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as z:
            z.write(source, source.name)
    elif system == "Darwin":
        source = root / "dist" / "macos" / arch / "Jingleplayer.app"
        if not source.is_dir():
            raise FileNotFoundError(source)
        archive = out / (stem + ".zip")
        subprocess.run(["ditto", "-c", "-k", "--sequesterRsrc", "--keepParent",
                        str(source), str(archive)], check=True)
        subprocess.run(["unzip", "-t", str(archive)], check=True)
    elif system == "Linux":
        source = root / "dist" / "linux" / "Jingleplayer"
        if not (source / "Jingleplayer").is_file():
            raise FileNotFoundError(source)
        archive = out / (stem + ".tar.gz")
        with tarfile.open(archive, "w:gz") as t:
            t.add(source, arcname=source.name)
        with tarfile.open(archive) as t:
            assert t.getmember("Jingleplayer/Jingleplayer").mode & 0o111
    else:
        raise RuntimeError(f"Unsupported platform: {system}")
    if archive.suffix == ".zip" and system == "Windows":
        with zipfile.ZipFile(archive) as z:
            assert z.testzip() is None
    with archive.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    archive.with_name(archive.name + ".sha256").write_text(
        f"{digest}  {archive.name}\n", encoding="ascii")
    print(archive)


if __name__ == "__main__":
    main()
