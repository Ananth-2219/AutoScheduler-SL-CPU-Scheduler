"""Shared launcher: find the repository and use its existing environment."""
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
project_python = ROOT / ".venv/bin/python"
if project_python.is_file() and Path(sys.prefix).resolve() != ROOT / ".venv":
    os.execv(str(project_python), [str(project_python), str(Path(sys.argv[0]).resolve()), *sys.argv[1:]])
sys.path.insert(0, str(ROOT))

from autoscheduler.review_metrics import run_cli
