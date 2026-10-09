"""
HogShade: the comparison framework's command: validate the case table anywhere, run the oracle cases where a GPU is.
Package: tools/compare

    uv run tools/compare.py validate             # CI step "Comparison": exit 1 with the findings listed
    uv run tools/compare.py list                 # the cases, controls marked
    uv run tools/compare.py run                  # render the cases on the wgpu host; write captures/report.json
    uv run tools/compare.py run --only texel-roughness --out captures/quick

``validate`` needs no GPU. It loads every case under ``verification/cases/`` against the check registry (a missing
or non-positive data range, a threshold on a metric the check does not report, an unknown check), confirms every
request is one the wgpu host can honour, reads ``verification/accepted.json`` and refuses an acceptance that names
no case, and, with ``--report``, checks a stored report against its schema.

``run`` captures each distinct request once (the controls share their twin's), measures, judges and writes
``report.json``. Exit codes: 0 every case passed and every control failed as it should; 1 a case failed or needs
review, or a control passed, or the table is invalid; 2 a table this command cannot run (an unknown ``--only``, or
a regression or parity case before the increment that runs it); 3 no GPU adapter (0 with ``--allow-skips``, for a
headless runner). Captures go to ``captures/``, which git ignores: the EXRs are large, and only chosen pictures
are committed.

Design: ``Docs/design/2026-10-08-comparison-framework.md``; spec: ``Docs/superpowers/specs/c2-comparison-core.md``.
"""

from __future__ import annotations

import argparse
import logging as _logging
import sys
from collections.abc import Callable, Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hogshade.compare import cases as cases_mod
from hogshade.compare import oracles, runner
from hogshade.compare.adapters import wgpu as wgpu_adapter
from hogshade.compare.report import Report, ReportError
from hogshade.compare.verdict import AcceptedDifferences, VerdictError

_MODULE_NAME = "tools.compare"
__version__ = "0.1.0"
__updated__ = "2026-10-08"
_LOGGER = _logging.getLogger(_MODULE_NAME)

CASES_DIR = ROOT / "verification" / "cases"
ACCEPTED = ROOT / "verification" / "accepted.json"
OUT_DIR = ROOT / "captures"

EXIT_OK, EXIT_FINDINGS, EXIT_REFUSED, EXIT_NO_ADAPTER = 0, 1, 2, 3


def load_table(cases_dir: Path, accepted_path: Path) -> tuple[list[cases_mod.Case], AcceptedDifferences, list[str]]:
    """The cases and acceptances, and the findings (strings) from validating them; cases are empty on a finding."""
    findings: list[str] = []
    table: list[cases_mod.Case] = []
    accepted = AcceptedDifferences()
    try:
        table = cases_mod.load(cases_dir, oracles.CHECKS)
    except cases_mod.CaseError as e:
        findings.append(str(e))
    try:
        accepted = AcceptedDifferences.load(accepted_path)
    except VerdictError as e:
        findings.append(str(e))
    if not table and not findings:
        findings.append(f"{cases_dir}: no cases; an empty table proves nothing")
    for case in table:
        try:
            wgpu_adapter.check_supported(case.request)
        except wgpu_adapter.UnsupportedRequest as e:
            findings.append(f"case {case.id!r}: the wgpu host cannot honour its request: {e}")
    ids = {c.id for c in table}
    for cid in accepted.entries:
        if table and cid not in ids:
            findings.append(f"{accepted_path}: {cid!r} is accepted but no case has that id")
    return table, accepted, findings


def cmd_validate(args: argparse.Namespace) -> int:
    table, _accepted, findings = load_table(args.cases, args.accepted)
    for stored in args.report or []:
        try:
            Report.from_json(Path(stored).read_text(encoding="utf-8"))
        except (ReportError, OSError) as e:
            findings.append(f"{stored}: {e}")
    for finding in findings:
        _LOGGER.error(finding)
    if findings:
        _LOGGER.error(f"comparison check: {len(findings)} finding(s)")
        return EXIT_FINDINGS
    controls = sum(c.is_control for c in table)
    _LOGGER.info(f"comparison check: {len(table)} case(s) ({controls} control(s)) valid under {args.cases}")
    return EXIT_OK


def cmd_list(args: argparse.Namespace) -> int:
    table, _accepted, findings = load_table(args.cases, args.accepted)
    for finding in findings:
        _LOGGER.error(finding)
    for case in table:
        print(
            f"{case.id}\t{case.kind}\t{'control' if case.is_control else 'case'}\t{case.check.name}\t{case.request.id}"
        )
    return EXIT_FINDINGS if findings else EXIT_OK


def make_adapter() -> wgpu_adapter.WgpuAdapter:
    """The wgpu adapter on the machine's GPU. Raises on no adapter; a seam so tests can stand in a fake."""
    return wgpu_adapter.WgpuAdapter()


def cmd_run(args: argparse.Namespace, adapter_factory: Callable[[], wgpu_adapter.WgpuAdapter] | None = None) -> int:
    table, accepted, findings = load_table(args.cases, args.accepted)
    if findings:
        for finding in findings:
            _LOGGER.error(finding)
        return EXIT_FINDINGS
    if args.only:
        unknown = sorted(set(args.only) - {c.id for c in table})
        if unknown:
            _LOGGER.error(f"--only names no case: {unknown}")
            return EXIT_REFUSED
        table = [c for c in table if c.id in set(args.only)]
    try:
        runner.check_runnable(table)
    except runner.RunnerError as e:
        _LOGGER.error(str(e))
        return EXIT_REFUSED
    try:
        adapter = (adapter_factory or make_adapter)()
    except Exception as e:  # noqa: BLE001 - any adapter failure (no wgpu, no GPU) is the same answer: nothing to run on
        _LOGGER.warning(f"no wgpu adapter ({type(e).__name__}: {e}); the oracle cases need a GPU")
        return EXIT_OK if args.allow_skips else EXIT_NO_ADAPTER
    report = runner.run(
        table,
        adapter.capture,
        args.out,
        wgpu_adapter.HOST,
        wgpu_adapter.LEVEL,
        adapter.versions(),
        accepted,
    )
    args.out.mkdir(parents=True, exist_ok=True)
    path = args.out / "report.json"
    path.write_text(report.to_json(), encoding="utf-8", newline="\n")
    s = report.summary
    _LOGGER.info(
        f"wrote {path}: {s['pass']} pass, {s['needs-review']} needs-review, {s['fail']} fail of {s['cases']} case(s); "
        f"{s['controls_ok']} of {s['controls']} control(s) failed as they should"
    )
    for result in report.cases:
        if result.is_control and not result.control_ok:
            _LOGGER.error(f"control {result.id} did not fail as it should: the instrument cannot tell right from wrong")
        elif not result.is_control and result.verdict.value != "pass":
            _LOGGER.error(f"case {result.id}: {result.verdict.value}: {'; '.join(result.notes) or result.error}")
    return EXIT_OK if report.ok else EXIT_FINDINGS


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    for name, helptext in (
        ("validate", "check the case table, the acceptances and any stored report (no GPU)"),
        ("list", "print the cases"),
        ("run", "render the oracle cases on the wgpu host and write report.json"),
    ):
        p = sub.add_parser(name, help=helptext)
        p.add_argument(
            "--cases", type=Path, default=CASES_DIR, help="directory of case files (default verification/cases)"
        )
        p.add_argument(
            "--accepted", type=Path, default=ACCEPTED, help="accepted differences (default verification/accepted.json)"
        )
        if name == "validate":
            p.add_argument("--report", action="append", help="a stored report.json to check against the schema")
        if name == "run":
            p.add_argument(
                "--out", type=Path, default=OUT_DIR, help="where captures and report.json go (default captures/)"
            )
            p.add_argument("--only", action="append", help="run only this case id (repeatable)")
            p.add_argument(
                "--allow-skips", action="store_true", help="exit 0 when there is no GPU adapter (a headless runner)"
            )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return {"validate": cmd_validate, "list": cmd_list, "run": cmd_run}[args.command](args)


if __name__ == "__main__":
    _logging.basicConfig(level=_logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    sys.exit(main())
