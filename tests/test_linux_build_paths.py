"""Check Linux data paths using PyInstaller's actual spec generation/resolution."""
import ast
import builtins
import importlib.util
from pathlib import Path
import re
import runpy
import sys
from types import SimpleNamespace

import PyInstaller
from PyInstaller.building import makespec
from PyInstaller.building.utils import format_binaries_and_datas
from PyInstaller.depend.analysis import PyiModuleGraph


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


def test_linux_exclusion_avoids_pkg_resources_runtime_hook(tmp_path):
    script = (Path(__file__).resolve().parents[1] / "build_linux.sh").read_text(
        encoding="utf-8"
    )
    excludes = re.findall(r"--exclude-module\s+([\w.]+)", script)
    assert excludes == ["pkg_resources"]
    entry = tmp_path / "optional_resources.py"
    entry.write_text("try:\n    import pkg_resources\nexcept ImportError:\n    pass\n")
    graph = PyiModuleGraph(PyInstaller.HOMEPATH, excludes=excludes)
    graph.add_script(str(entry))
    hooks = graph.analyze_runtime_hooks([])
    assert all(Path(node.filename).name != "pyi_rth_pkgres.py" for node in hooks)
    assert not any(name == "pkg_resources" for name, _, _ in graph.make_pure_toc())


def test_pygame_resource_fallback_without_pkg_resources(tmp_path, monkeypatch):
    """Exercise pygame's real optional-import path, not a replacement implementation."""
    spec = importlib.util.find_spec("pygame.pkgdata")
    original_import = builtins.__import__

    def without_pkg_resources(name, *args, **kwargs):
        if name == "pkg_resources" or name.startswith("pkg_resources."):
            raise ModuleNotFoundError("excluded from Linux bundle", name=name)
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", without_pkg_resources)
    namespace = runpy.run_path(spec.origin)
    assert namespace["resource_exists"]("unused", "unused") is False
    resource = tmp_path / "resource.dat"
    resource.write_bytes(b"bundled resource")
    monkeypatch.setitem(sys.modules, "resource_fixture", SimpleNamespace(__file__=str(tmp_path / "__init__.py")))
    with namespace["getResource"]("resource.dat", "resource_fixture") as stream:
        assert stream.read() == b"bundled resource"
