"""Run the fast checks expected before publishing or deploying."""

from __future__ import annotations

import argparse
import compileall
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def run(command: list[str]) -> None:
    print(f"$ {' '.join(command)}")
    subprocess.run(command, cwd=PROJECT_ROOT, check=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--with-app",
        action="store_true",
        help="Also run Streamlit's AppTest (downloads current release data if uncached).",
    )
    arguments = parser.parse_args()

    print("Compiling Python modules…")
    if not compileall.compile_dir(PROJECT_ROOT / "showdown_app", quiet=1):
        raise SystemExit("Application compilation failed.")
    if not compileall.compile_dir(PROJECT_ROOT / "showdown_pipeline", quiet=1):
        raise SystemExit("Pipeline compilation failed.")
    if not compileall.compile_dir(PROJECT_ROOT / "scripts", quiet=1):
        raise SystemExit("Script compilation failed.")

    run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"])

    if arguments.with_app:
        run([
            sys.executable,
            "-c",
            (
                "from streamlit.testing.v1 import AppTest; "
                "app=AppTest.from_file('app.py', default_timeout=180).run(); "
                "assert not app.exception, [str(item.value) for item in app.exception]; "
                "assert not app.error, [str(item.value) for item in app.error]; "
                "app.radio[0].set_value('First KO study').run(); "
                "assert not app.exception, [str(item.value) for item in app.exception]; "
                "assert not app.error, [str(item.value) for item in app.error]; "
                "assert any('Does getting the first KO predict the winner?' in item.value "
                "for item in app.markdown)"
            ),
        ])

    print("All requested checks passed.")


if __name__ == "__main__":
    main()
