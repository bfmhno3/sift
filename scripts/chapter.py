"""Run the lab files of one chapter: chapter.py chNN."""

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TIMEOUT = 300
XVFB = ["xvfb-run", "-a", "-s", "-screen 0 1100x700x24"]


def command_for(path: Path, env: dict[str, str]) -> list[str]:
    """Return the argv for one lab file, adjusting env in place."""
    stem = path.stem
    if stem.endswith("_ft"):
        src = str(ROOT / "src")
        old = env.get("PYTHONPATH")
        env["PYTHONPATH"] = src + (os.pathsep + old if old else "")
        return ["python3.14t", str(path)]
    if stem.endswith("_gui"):
        return [*XVFB, "python3", str(path)]
    return ["python3", str(path)]


def should_fail(stem: str) -> bool:
    """Return True if the file is expected to exit non-zero."""
    return stem.endswith(("_fail", "_syntaxerror"))


def run_one(path: Path, out_dir: Path, env: dict[str, str]) -> bool:
    """Run one lab file; return True if its exit status is expected."""
    env = dict(env)
    argv = command_for(path, env)
    rel = path.relative_to(ROOT)
    try:
        proc = subprocess.run(
            argv,
            cwd=ROOT,
            env=env,
            capture_output=True,
            timeout=TIMEOUT,
        )
        code = proc.returncode
        stdout, stderr = proc.stdout, proc.stderr
    except subprocess.TimeoutExpired as exc:
        code = 124
        stdout, stderr = exc.stdout or b"", exc.stderr or b""
    (out_dir / f"{path.stem}.stdout").write_bytes(stdout)
    (out_dir / f"{path.stem}.stderr").write_bytes(stderr)
    ok = code != 0 if should_fail(path.stem) else code == 0
    if code == 124:
        ok = False
    print(
        f"{'ok  ' if ok else 'FAIL'} {rel}" + ("" if ok else f" (exit {code})")
    )
    return ok


def main() -> None:
    """Run the chapter named on the command line."""
    if len(sys.argv) != 2:
        sys.exit("usage: chapter.py chNN")
    chapter = sys.argv[1]
    lab = ROOT / "lab" / chapter
    if not lab.is_dir():
        sys.exit(f"chapter.py: no such directory: {lab}")
    out_dir = ROOT / "out" / chapter
    out_dir.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env.update(
        PYTHONHASHSEED="0",
        QT_QPA_PLATFORM="offscreen",
        MPLBACKEND="Agg",
    )
    failed = 0
    for path in sorted(lab.glob("*.py")):
        if not run_one(path, out_dir, env):
            failed += 1
    extra = lab / "extra.sh"
    if extra.exists():
        proc = subprocess.run(
            ["bash", str(extra)], cwd=ROOT, env=env, timeout=TIMEOUT
        )
        ok = proc.returncode == 0
        print(
            f"{'ok  ' if ok else 'FAIL'} {extra.relative_to(ROOT)}"
            + ("" if ok else f" (exit {proc.returncode})")
        )
        failed += not ok
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
