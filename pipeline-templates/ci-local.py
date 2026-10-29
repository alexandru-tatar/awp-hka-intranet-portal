#!/usr/bin/env python3
"""Führt die Jobs einer GitLab-Pipeline-Datei lokal aus (ohne GitLab, ohne Container).

Zweck: Die Pipeline-Logik prüfen, bevor es ein GitLab-Repository gibt, und später lokal
nachvollziehen, warum eine Pipeline rot ist. Es werden **dieselben Befehle** ausgeführt, die in
app-pipeline.yml stehen (before_script + script) — die Datei bleibt die einzige Quelle.

Was dabei NICHT nachgebildet wird:
  - Container-Abbilder (`image:`): die Befehle laufen auf diesem Rechner (andere Python-/Node-Version möglich)
  - Cache, Artefakte, Regeln mit `if:`, Merge-Request-Pipelines, Berechtigungen
Jeder Job startet in einer frischen Kopie des Projekts (wie ein neuer Checkout ohne node_modules/.venv).

Aufruf:  python3 ci-local.py <projektordner> [--pipeline app-pipeline.yml] [--only job,job] [--verbose]
Exit:    0 = alle ausgeführten Jobs bestanden, 1 = mindestens ein Job fehlgeschlagen, 2 = Aufruf/Datei fehlerhaft
"""
import argparse
import os
import pathlib
import shutil
import stat
import subprocess
import sys
import tempfile
import time

try:
    import yaml
except ImportError:  # pragma: no cover
    sys.exit("PyYAML fehlt: pip install pyyaml")

RESERVED = {"workflow", "stages", "variables", "default", "include", "image", "cache",
            "before_script", "after_script"}
IGNORE = shutil.ignore_patterns("node_modules", ".venv", ".git", ".npm", "__pycache__",
                                ".pytest_cache", ".ruff_cache", "coverage")


def load_jobs(pipeline):
    data = yaml.safe_load(pipeline.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Pipeline-Datei ist kein YAML-Objekt")
    jobs = {k: v for k, v in data.items() if k not in RESERVED and isinstance(v, dict)}
    stages = data.get("stages") or ["test"]
    variables = {str(k): str(v) for k, v in (data.get("variables") or {}).items()}
    return jobs, stages, variables


def resolve(name, jobs, trail=()):
    """`extends` auflösen (flach: Werte des Jobs überschreiben die der Vorlage, wie bei GitLab für Skalare/Listen)."""
    if name in trail:
        raise ValueError(f"Zyklus in extends: {' -> '.join(trail + (name,))}")
    job = dict(jobs[name])
    parents = job.pop("extends", None)
    merged = {}
    for parent in ([parents] if isinstance(parents, str) else (parents or [])):
        if parent not in jobs:
            raise ValueError(f"{name}: extends verweist auf unbekannte Vorlage {parent!r}")
        merged.update(resolve(parent, jobs, trail + (name,)))
    merged.update(job)
    return merged


def applies(job, project):
    rules = job.get("rules")
    if rules is None:
        return True
    for rule in rules:
        files = rule.get("exists")
        if files is None:      # Regeln mit `if:` werden lokal als „trifft zu" behandelt
            return rule.get("when", "on_success") != "never"
        if any((project / f).exists() for f in files):
            return rule.get("when", "on_success") != "never"
    return False


def lines(value):
    if not value:
        return []
    return [value] if isinstance(value, str) else [str(v) for v in value]


def run_job(name, job, workdir, variables, bin_dir, verbose):
    exports = [f'export CI=true CI_LOCAL=true CI_PROJECT_DIR="{workdir}"']
    exports += [f'export {k}="{v}"' for k, v in variables.items()]
    body = ["set -eo pipefail", *exports, *lines(job.get("before_script")), *lines(job.get("script"))]
    env = dict(os.environ, PATH=f"{bin_dir}{os.pathsep}{os.environ['PATH']}")
    started = time.time()
    proc = subprocess.run(["bash", "-c", "\n".join(body)], cwd=workdir, env=env,
                          capture_output=True, text=True)
    seconds = time.time() - started
    if verbose or proc.returncode != 0:
        for stream in (proc.stdout, proc.stderr):
            for line in stream.rstrip().splitlines():
                print(f"    | {line}")
    return proc.returncode, seconds


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("project", help="Projektordner (z. B. ../starter-js)")
    ap.add_argument("--pipeline", default=str(pathlib.Path(__file__).with_name("app-pipeline.yml")))
    ap.add_argument("--only", help="nur diese Jobs (Komma-getrennt)")
    ap.add_argument("--verbose", action="store_true", help="Ausgabe auch bei bestandenen Jobs zeigen")
    args = ap.parse_args()

    project = pathlib.Path(args.project).resolve()
    if not project.is_dir():
        print(f"Projektordner nicht gefunden: {project}", file=sys.stderr)
        return 2
    try:
        jobs, stages, variables = load_jobs(pathlib.Path(args.pipeline))
        visible = [n for n in jobs if not n.startswith(".")]
        resolved = {n: resolve(n, jobs) for n in visible}
    except (OSError, ValueError, yaml.YAMLError) as err:
        print(f"Pipeline-Datei fehlerhaft: {err}", file=sys.stderr)
        return 2
    only = set(args.only.split(",")) if args.only else None
    unknown = (only or set()) - set(visible)
    if unknown:
        print(f"Unbekannte Jobs: {', '.join(sorted(unknown))}. Vorhanden: {', '.join(visible)}", file=sys.stderr)
        return 2

    tmp = pathlib.Path(tempfile.mkdtemp(prefix="ci-local-"))
    bin_dir = tmp / "bin"                      # macOS kennt nur `python3`; die Pipeline ruft `python` auf
    bin_dir.mkdir()
    shim = bin_dir / "python"
    shim.write_text(f'#!/bin/sh\nexec "{sys.executable}" "$@"\n')
    shim.chmod(shim.stat().st_mode | stat.S_IEXEC)

    print(f"Projekt:  {project}\nPipeline: {args.pipeline}\nHinweis:  Befehle laufen auf diesem Rechner, nicht im Container (image).\n")
    results = []
    for stage in stages:
        for name in visible:
            job = resolved[name]
            if job.get("stage", "test") != stage or (only and name not in only):
                continue
            if not applies(job, project):
                print(f"- {name:<14} übersprungen (keine passende Datei im Projekt)")
                results.append((name, stage, "übersprungen", 0.0))
                continue
            work = tmp / name.replace(":", "_")
            shutil.copytree(project, work, ignore=IGNORE)
            print(f"- {name:<14} läuft …", flush=True)
            code, seconds = run_job(name, job, work, variables, bin_dir, args.verbose)
            status = "bestanden" if code == 0 else f"FEHLGESCHLAGEN (Exit {code})"
            print(f"  {name:<14} {status}  [{seconds:.1f} s]")
            results.append((name, stage, status, seconds))

    shutil.rmtree(tmp, ignore_errors=True)
    failed = [r for r in results if r[2].startswith("FEHL")]
    print("\nErgebnis: " + ("ROT — mindestens ein Job ist fehlgeschlagen" if failed else "GRÜN — alle ausgeführten Jobs bestanden"))
    for name, stage, status, seconds in results:
        print(f"  {stage:<6} {name:<14} {status}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
