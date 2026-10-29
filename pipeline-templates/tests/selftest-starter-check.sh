#!/usr/bin/env bash
# Selbsttest für tools/check-starter.py: Gute Starter müssen bestehen, jeder absichtlich kaputte Starter muss
# an der erwarteten Prüfung scheitern (nicht irgendwo anders). Braucht Docker (z. B. `colima start`).
# Aufruf: tests/selftest-starter-check.sh [pfad/zu/starter-js]
set -u
HERE="$(cd "$(dirname "$0")/.." && pwd)"
JS="${1:-$HERE/../starter-js}"
PY="$HERE/tests/fixtures/starter-python-example"
CHECK="python3 $HERE/tools/check-starter.py"
fail=0

variant() {  # variant <ziel-ordner-name>  -> Kopie von starter-js ohne node_modules
  d="$(mktemp -d)/$1"; mkdir -p "$d"; cp -R "$JS/." "$d/"; rm -rf "$d/node_modules"; echo "$d"
}
expect_pass() {  # expect_pass <name> <ordner>
  out=$($CHECK "$2" 2>&1); code=$?
  if [ $code -eq 0 ]; then echo "OK     $1 (alle Prüfpunkte bestanden)"; else echo "FEHLER $1 sollte bestehen (Exit $code)"; echo "$out" | grep FEHLER | head -5; fail=1; fi
}
expect_red() {  # expect_red <name> <erwartet-fehlgeschlagen: Teil des Prüfpunkt-Namens> <skip> <ordner>
  out=$($CHECK "$4" --skip "$3" 2>&1); code=$?
  if [ $code -ne 0 ] && echo "$out" | grep -q "FEHLER .*$2"; then
    echo "OK     $1 → rot wegen „$2“"
  else
    echo "FEHLER $1 (Exit $code, erwartet rot wegen „$2“)"; echo "$out" | grep -E "FEHLER|Ergebnis" | head -6; fail=1
  fi
}

expect_pass "JavaScript-Starter (starter-js)"        "$JS"
expect_pass "Python-Beispiel (Fixture)"              "$PY"

d=$(variant v1); python3 - "$d/Dockerfile" <<'PYEOF'
import re,sys; p=sys.argv[1]; s=open(p).read(); open(p,"w").write(re.sub(r"HEALTHCHECK[^\n]*\n(\s+CMD[^\n]*\n)?", "", s))
PYEOF
expect_red "ohne HEALTHCHECK"                         "HEALTHCHECK im Abbild"            structure,make,pipeline "$d"

d=$(variant v2); sed -i.bak 's/^USER 10001:10001/USER root/' "$d/Dockerfile"
expect_red "läuft als root"                           "Benutzer 10001 im Abbild"         structure,make,pipeline "$d"

d=$(variant v3); sed -i.bak '/^docker:/d' "$d/Makefile"
expect_red "Makefile ohne docker-Ziel"                "Ziel make docker"                 pipeline,container "$d"

d=$(variant v4); rm -rf "$d/tests"
expect_red "Ordner tests/ fehlt"                      "Ordner tests/"                    pipeline,container "$d"

d=$(variant v5); sed -i.bak 's/status: "ok"/status: "fine"/' "$d/src/app.js"
expect_red "falscher Health-Antworttext"              "GET /healthz"                     structure,make,pipeline "$d"

d=$(variant v6); python3 - "$d/Dockerfile" <<'PYEOF'
import re,sys; p=sys.argv[1]; s=open(p).read(); open(p,"w").write(re.sub(r'(HEALTHCHECK[^\n]*\n)\s+CMD[^\n]*\n', r'\1  CMD ["curl", "-f", "http://127.0.0.1:8080/healthz"]\n', s))
PYEOF
expect_red "HEALTHCHECK nutzt curl"                   "HEALTHCHECK ohne curl"            structure,make,pipeline "$d"

d=$(variant v7); sed -i.bak '/process.on/d' "$d/src/server.js"
expect_red "SIGTERM wird nicht behandelt"             "docker stop beendet mit Exit 0"   structure,make,pipeline "$d"

d=$(variant v8); printf 'const unused = 1;\n' >> "$d/src/app.js"
expect_red "Lint-Fehler im Code"                      "Lint-Job bestanden"               structure,make,container "$d"

[ $fail -eq 0 ] && echo "Selbsttest: alles wie erwartet" || echo "Selbsttest: ABWEICHUNGEN"
exit $fail
