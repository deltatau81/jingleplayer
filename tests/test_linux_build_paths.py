"""Check Linux data paths using PyInstaller's actual spec generation/resolution."""
import ast
from pathlib import Path
import re

from PyInstaller.building import makespec
from PyInstaller.building.utils import format_binaries_and_datas


def test_linux_resources_resolve_from_nested_spec_and_foreign_cwd(tmp_path, monkeypatch):
    script = (Path(__file__).resolve().parents[1] / "build_linux.sh").read_text(
        encoding="utf-8"
    )
    assert 'project_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"' in script
    resources = re.findall(r'--add-data\s+"([^"\n]+)"', script)
    assert resources == [
        "$project_root/HELP.md:.",
        "$project_root/assets/jingleplayer.ico:assets",
    ]
    project = tmp_path / "project with spaces"
    (project / "assets").mkdir(parents=True)
    (project / "HELP.md").write_text("Bundled help", encoding="utf-8")
    (project / "assets/jingleplayer.ico").write_bytes(b"resource fixture")
    entry = project / "jingleplayer_app.py"
    entry.write_text("pass\n", encoding="utf-8")
    spec_dir = project / "build/linux/spec"
    foreign = tmp_path / "other working directory"
    foreign.mkdir()
    monkeypatch.chdir(foreign)
    datas = [
        (str(project / source.removeprefix("$project_root/")), destination)
        for source, destination in (resource.rsplit(":", 1) for resource in resources)
    ]
    spec = makespec.main(
        [str(entry)], name="Jingleplayer", specpath=str(spec_dir),
        datas=datas, shorthand_manifest=None,
    )
    tree = ast.parse(Path(spec).read_text(encoding="utf-8"))
    analysis = next(
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        and node.func.id == "Analysis"
    )
    spec_datas = ast.literal_eval(next(k.value for k in analysis.keywords if k.arg == "datas"))
    assert all(Path(source).is_absolute() for source, _ in spec_datas)
    resolved = format_binaries_and_datas(spec_datas, workingdir=str(spec_dir))
    assert resolved == {
        ("HELP.md", str(project / "HELP.md")),
        (str(Path("assets/jingleplayer.ico")), str(project / "assets/jingleplayer.ico")),
    }
