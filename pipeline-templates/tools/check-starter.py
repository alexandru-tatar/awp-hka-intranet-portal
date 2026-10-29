#!/usr/bin/env python3
"""Prüft einen Starter gegen die Starter-Konvention (team-docs/entwicklung/starter-konvention.md).

Vier Prüfgruppen, je Prüfpunkt wird der gefundene Wert ausgegeben:
  structure  Pflichtordner und -dateien sind vorhanden
  make       die fünf Befehle (dev, start, test, lint, docker) sind im Makefile definiert
  pipeline   Lint und Test bestehen — mit denselben Befehlen wie in der Pipeline (ruft ci-local.py auf)
  container  das Abbild baut, hat HEALTHCHECK und Benutzer 10001, läuft gehärtet, /healthz liefert
             200 mit {"status":"ok"}, Schreiben ins Wurzel-Dateisystem scheitert, `docker stop` endet mit 0

Aufruf:  python3 tools/check-starter.py <starter-ordner> [--skip pipeline,container]
Exit:    0 = alle gewählten Prüfungen bestanden, 1 = mindestens eine fehlgeschlagen, 2 = Aufruffehler
Die Container-Prüfung braucht Docker (z. B. `colima start`); ohne Docker mit `--skip container`.
"""
import argparse
import json
import pathlib
import re
import subprocess
import sys
import time
import urllib.request
import uuid

REQUIRED_DIRS = ["src", "tests"]
REQUIRED_FILES = ["README.md", "Makefile", "Dockerfile", ".dockerignore", ".gitignore", ".editorconfig"]
TARGETS = ["dev", "start", "test", "lint", "docker"]
GROUPS = ["structure", "make", "pipeline", "container"]
HERE = pathlib.Path(__file__).resolve().parent
CI_LOCAL = HERE.parent / "ci-local.py"

results = []  # (group, check, ok, observed)


def record(group, check, ok, observed):
    results.append((group, check, bool(ok), str(observed)))
    return bool(ok)


def run(cmd, timeout=120, **kw):
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, **kw)
        return p.returncode, (p.stdout or "").strip(), (p.stderr or "").strip()
    except subprocess.TimeoutExpired:
        return 124, "", f"Zeitüberschreitung nach {timeout} s"
    except FileNotFoundError as err:
        return 127, "", str(err)


# --------------------------------------------------------------------------- structure
def check_structure(root):
    for d in REQUIRED_DIRS:
        record("structure", f"Ordner {d}/", (root / d).is_dir(), "vorhanden" if (root / d).is_dir() else "FEHLT")
    for f in REQUIRED_FILES:
        record("structure", f"Datei {f}", (root / f).is_file(), "vorhanden" if (root / f).is_file() else "FEHLT")


# --------------------------------------------------------------------------- make
def check_make(root):
    mk = root / "Makefile"
    if not mk.is_file():
        record("make", "Makefile lesbar", False, "Makefile fehlt")
        return
    text = mk.read_text(encoding="utf-8", errors="replace")
    defined = set(re.findall(r"^([A-Za-z0-9_.-]+)\s*:(?!=)", text, re.M))
    for t in TARGETS:
        record("make", f"Ziel make {t}", t in defined, "definiert" if t in defined else "FEHLT")
    runner = re.search(r"^RUNNER\s*:?=\s*(.+)$", text, re.M)
    record("make", "Zeile RUNNER (nur sie darf sich unterscheiden)", bool(runner), runner.group(1).strip() if runner else "FEHLT")


# --------------------------------------------------------------------------- pipeline
def check_pipeline(root):
    if not CI_LOCAL.is_file():
        record("pipeline", "ci-local.py gefunden", False, str(CI_LOCAL))
        return
    code, out, err = run([sys.executable, str(CI_LOCAL), str(root)], timeout=600)
    text = out + "\n" + err
    ran = {m.group(1): m.group(2) for m in re.finditer(r"^\s{2}(lint:\S+|test:\S+)\s+(bestanden|FEHLGESCHLAGEN[^\[]*)", text, re.M)}
    lint_ok = any(k.startswith("lint:") and v.startswith("bestanden") for k, v in ran.items())
    test_ok = any(k.startswith("test:") and v.startswith("bestanden") for k, v in ran.items())
    record("pipeline", "Lint-Job bestanden", lint_ok, next((f"{k}: {v.strip()}" for k, v in ran.items() if k.startswith("lint:")), "kein Lint-Job gelaufen (passende Datei fehlt?)"))
    record("pipeline", "Test-Job bestanden", test_ok, next((f"{k}: {v.strip()}" for k, v in ran.items() if k.startswith("test:")), "kein Test-Job gelaufen (passende Datei fehlt?)"))
    record("pipeline", "Gesamtergebnis ci-local.py", code == 0, f"Exit {code}")
    if code != 0:
        tail = [l for l in text.splitlines() if l.strip()][-6:]
        record("pipeline", "letzte Zeilen der Ausgabe", False, " | ".join(l.strip() for l in tail))


# --------------------------------------------------------------------------- container
def check_container(root):
    code, out, err = run(["docker", "info", "--format", "{{.ServerVersion}}"], timeout=30)
    if not record("container", "Docker erreichbar", code == 0, f"Server {out}" if code == 0 else (err or "docker nicht gefunden") + " (Colima gestartet?)"):
        return
    tag = f"check-starter-{uuid.uuid4().hex[:8]}"
    name = tag
    try:
        code, out, err = run(["docker", "build", "-q", "-t", tag, str(root)], timeout=900)
        if not record("container", "docker build", code == 0, "gebaut" if code == 0 else " | ".join((err or out).splitlines()[-3:])):
            return
        code, out, _ = run(["docker", "image", "inspect", "--format", "{{.Config.User}}|{{json .Config.Healthcheck}}", tag])
        user, _, hc = out.partition("|")
        record("container", "Benutzer 10001 im Abbild", user in ("10001", "10001:10001"), user or "(leer = Administrator)")
        hc_obj = json.loads(hc) if hc and hc != "null" else None
        has_hc = bool(hc_obj) and hc_obj.get("Test", ["NONE"])[0] != "NONE"
        record("container", "HEALTHCHECK im Abbild", has_hc, hc if has_hc else "FEHLT")
        record("container", "HEALTHCHECK ohne curl", has_hc and "curl" not in hc, "kein curl" if has_hc and "curl" not in hc else ("curl verwendet" if has_hc else "kein HEALTHCHECK"))

        code, cid, err = run(["docker", "run", "-d", "--name", name, "-p", "127.0.0.1::8080", "--read-only",
                              "--tmpfs", "/tmp:size=64m,noexec,nosuid", "--cap-drop", "ALL",
                              "--security-opt", "no-new-privileges:true", "--memory", "512m", "--cpus", "0.5",
                              "--pids-limit", "128", tag])
        if not record("container", "gehärteter Start (read-only, ohne Fähigkeiten)", code == 0, "gestartet" if code == 0 else err):
            return
        started = time.time()
        status = "starting"
        while time.time() - started < 60:
            _, status, _ = run(["docker", "inspect", "-f", "{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}", name])
            _, running, _ = run(["docker", "inspect", "-f", "{{.State.Running}}", name])
            if status in ("healthy", "unhealthy", "none") or running != "true":
                break
            time.sleep(1)
        record("container", "Gesundheitstest wird healthy (≤ 60 s)", status == "healthy", f"{status} nach {time.time() - started:.0f} s")
        if status != "healthy":
            _, logs, _ = run(["docker", "logs", "--tail", "5", name])
            record("container", "letzte Logzeilen", False, " | ".join(logs.splitlines()[-5:]) or "(leer)")

        _, port_line, _ = run(["docker", "port", name, "8080/tcp"])
        hostport = port_line.splitlines()[0] if port_line else ""
        try:
            with urllib.request.urlopen(f"http://{hostport}/healthz", timeout=5) as r:
                body, code_http = r.read().decode(), r.status
            ok = code_http == 200 and json.loads(body) == {"status": "ok"}
            record("container", "GET /healthz → 200 {\"status\":\"ok\"}", ok, f"HTTP {code_http} {body.strip()}")
        except Exception as err:  # noqa: BLE001 - jede Störung ist ein Prüfergebnis
            record("container", "GET /healthz → 200 {\"status\":\"ok\"}", False, f"{type(err).__name__}: {err}")

        code, out, err = run(["docker", "exec", name, "id", "-u"])
        record("container", "Prozess läuft als uid 10001", out == "10001", out or err)
        code, out, err = run(["docker", "exec", name, "sh", "-c", "touch /check-starter-rw 2>&1; echo exit=$?"])
        ro = "exit=0" not in out
        record("container", "Wurzel-Dateisystem ist schreibgeschützt", ro, "Schreiben scheitert" if ro else "Schreiben war möglich")
        t0 = time.time()
        run(["docker", "stop", "-t", "10", name], timeout=60)
        took = time.time() - t0
        _, exit_code, _ = run(["docker", "inspect", "-f", "{{.State.ExitCode}}", name])
        record("container", "docker stop beendet mit Exit 0 (≤ 10 s)", exit_code == "0" and took < 10, f"Exit {exit_code} nach {took:.1f} s")
    finally:
        run(["docker", "rm", "-f", name], timeout=30)
        run(["docker", "rmi", "-f", tag], timeout=30)


# --------------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("starter", help="Ordner des Starters (z. B. ../starter-js)")
    ap.add_argument("--skip", default="", help=f"Gruppen überspringen, Komma-getrennt ({', '.join(GROUPS)})")
    args = ap.parse_args()
    root = pathlib.Path(args.starter).resolve()
    if not root.is_dir():
        print(f"Ordner nicht gefunden: {root}", file=sys.stderr)
        return 2
    skip = {s.strip() for s in args.skip.split(",") if s.strip()}
    unknown = skip - set(GROUPS)
    if unknown:
        print(f"Unbekannte Gruppen: {', '.join(sorted(unknown))}", file=sys.stderr)
        return 2

    print(f"Starter: {root}\nKonvention: team-docs/entwicklung/starter-konvention.md\n")
    for group, fn in (("structure", check_structure), ("make", check_make), ("pipeline", check_pipeline), ("container", check_container)):
        if group in skip:
            print(f"- {group}: übersprungen")
            continue
        fn(root)
    width = max((len(c) for _, c, _, _ in results), default=10)
    last = None
    for group, check, ok, obs in results:
        if group != last:
            print(f"\n[{group}]")
            last = group
        print(f"  {'OK    ' if ok else 'FEHLER'} {check:<{width}}  {obs}")
    failed = [r for r in results if not r[2]]
    print(f"\nErgebnis: {len(results) - len(failed)} von {len(results)} Prüfpunkten bestanden"
          + ("" if not failed else f" — {len(failed)} fehlgeschlagen"))
    return 1 if failed or not results else 0


if __name__ == "__main__":
    sys.exit(main())
