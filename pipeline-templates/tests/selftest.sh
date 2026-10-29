#!/usr/bin/env bash
# Selbsttest der Pipeline-Vorlage: grüne Fälle müssen Exit 0, rote Fälle Exit != 0 liefern.
# Das ist der „rote Prüfung sperrt den Merge"-Beweis im Kleinen, bevor es GitLab gibt.
# Aufruf: tests/selftest.sh [pfad/zu/starter-js]
set -u
HERE="$(cd "$(dirname "$0")/.." && pwd)"
JS="${1:-$HERE/../starter-js}"
RUN="python3 $HERE/ci-local.py"
fail=0
expect() {  # expect <erwartet: 0|nonzero> <name> <befehl...>
  want="$1"; name="$2"; shift 2
  "$@" >/tmp/selftest.out 2>&1; code=$?
  if { [ "$want" = 0 ] && [ $code -eq 0 ]; } || { [ "$want" = nonzero ] && [ $code -ne 0 ]; }; then
    echo "OK     $name (Exit $code, erwartet $want)"
  else
    echo "FEHLER $name (Exit $code, erwartet $want)"; tail -15 /tmp/selftest.out; fail=1
  fi
}
expect 0       "python grün"            $RUN "$HERE/tests/fixtures/python-ok"
expect nonzero "python lint rot"        $RUN "$HERE/tests/fixtures/python-lint-error"
expect nonzero "python test rot"        $RUN "$HERE/tests/fixtures/python-test-fail"
if [ -d "$JS" ]; then
  expect 0     "javascript grün"        $RUN "$JS"
  TMP="$(mktemp -d)"
  cp -R "$JS/." "$TMP/lint" 2>/dev/null; rm -rf "$TMP/lint/node_modules"; printf 'const unused = 1;\n' >> "$TMP/lint/src/app.js"
  expect nonzero "javascript lint rot"  $RUN "$TMP/lint"
  cp -R "$JS/." "$TMP/test" 2>/dev/null; rm -rf "$TMP/test/node_modules"; sed -i.bak 's/toBe(200)/toBe(500)/' "$TMP/test/tests/health.test.js"
  expect nonzero "javascript test rot"  $RUN "$TMP/test"
  rm -rf "$TMP"
else
  echo "ÜBERSPRUNGEN javascript (Ordner $JS nicht gefunden)"
fi
[ $fail -eq 0 ] && echo "Selbsttest: alles wie erwartet" || echo "Selbsttest: ABWEICHUNGEN"
exit $fail
