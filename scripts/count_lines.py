"""统计项目程序代码行数。

用法::

    python scripts/count_lines.py
    python scripts/count_lines.py --include-tests
    python scripts/count_lines.py --json

统计口径：
* 遍历源码目录，跳过虚拟环境、运行数据、构建产物与文档；
* 同时给出"物理行"与"有效代码行"（去掉空行与纯注释）；
* 默认包含 tests/，便于核对课程要求的 ≥15000 行。
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SKIP_DIRS = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "node_modules",
    "data",
    "build",
    "dist",
    "release",
    "docs",
    ".idea",
    ".vscode",
}

EXTENSIONS = {
    ".py": "Python",
    ".js": "JavaScript",
    ".css": "CSS",
    ".html": "HTML",
    ".ps1": "PowerShell",
    ".yml": "YAML",
    ".yaml": "YAML",
    ".toml": "TOML",
    ".sql": "SQL",
    ".md": "Markdown",
}

COMMENT_PREFIXES = {
    ".py": ("#",),
    ".js": ("//", "/*", "*", "*/"),
    ".css": ("/*", "*", "*/"),
    ".ps1": ("#",),
    ".yml": ("#",),
    ".yaml": ("#",),
    ".toml": ("#",),
    ".sql": ("--",),
}


def is_comment(line: str, suffix: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return True
    for prefix in COMMENT_PREFIXES.get(suffix, ()):
        if stripped.startswith(prefix):
            return True
    return False


def iter_files(include_tests: bool):
    for path in BASE_DIR.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.relative_to(BASE_DIR).parts):
            continue
        if not include_tests and path.parts and "tests" in path.relative_to(BASE_DIR).parts:
            continue
        if path.suffix.lower() not in EXTENSIONS:
            continue
        if path.name == "package-lock.json":
            continue
        yield path


def count() -> dict:
    per_language: dict[str, dict[str, int]] = defaultdict(lambda: {"files": 0, "lines": 0, "code": 0})
    files = 0

    for path in iter_files(include_tests=True):
        suffix = path.suffix.lower()
        language = EXTENSIONS[suffix]
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        lines = content.splitlines()
        code_lines = sum(1 for line in lines if not is_comment(line, suffix))
        per_language[language]["files"] += 1
        per_language[language]["lines"] += len(lines)
        per_language[language]["code"] += code_lines
        files += 1

    total_lines = sum(item["lines"] for item in per_language.values())
    total_code = sum(item["code"] for item in per_language.values())
    return {
        "files": files,
        "lines": total_lines,
        "code_lines": total_code,
        "languages": dict(sorted(per_language.items(), key=lambda item: item[1]["lines"], reverse=True)),
        "meets_target": total_lines >= 15000,
        "target": 15000,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="统计项目代码行数")
    parser.add_argument("--json", action="store_true", help="以 JSON 输出")
    parser.add_argument("--check", action="store_true", help="低于课程要求时以非零状态退出")
    args = parser.parse_args()

    result = count()
    if args.check and not result["meets_target"]:
        print(f"代码规模未达标：{result['lines']} < {result['target']}")
        return 1
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    print("=" * 62)
    print("识文台 InsightDesk · 代码规模统计")
    print("=" * 62)
    print(f"{'语言':<14}{'文件数':>8}{'物理行':>12}{'代码行':>12}")
    print("-" * 62)
    for language, item in result["languages"].items():
        print(f"{language:<14}{item['files']:>8}{item['lines']:>12}{item['code']:>12}")
    print("-" * 62)
    print(f"{'合计':<14}{result['files']:>8}{result['lines']:>12}{result['code_lines']:>12}")
    print("=" * 62)
    status = "达标" if result["meets_target"] else "未达标"
    print(f"课程要求：≥ {result['target']} 行　当前：{result['lines']} 行　{status}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
