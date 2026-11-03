#!/usr/bin/env bash
# Neue App aus dem Golden Master anlegen (HKA-54).
#
# Aufruf:  tools/neue-app.sh <slug> js|python [--pruefen]
#
# Legt mit einem Befehl ein fertig eingerichtetes GitHub-Repository "app-<slug>" an:
#   - Inhalt des Golden Master (Vorlage awp-hka-gold-js bzw. awp-hka-gold-python)
#   - Zweige main und develop, der Slug steht im manifest.json
#   - Ruleset "main-schutz" auf main: Pull Request mit 1 Freigabe, Pflicht-Check "check", keine Ausnahme
#   - Environment test-vm mit den Secrets DEPLOY_SSH_KEY, DEPLOY_HOST, DEPLOY_KNOWN_HOSTS
#   - Mitglieder des Portal-Repositories als Collaborators (Push-Recht)
#
# Voraussetzungen: gh (angemeldet als Konto-Inhaber) und jq.
# Nur der Konto-Inhaber (OWNER) kann Rulesets und Secrets setzen: Das Skript gilt für die Demo.
#
# Mit --pruefen läuft nur Teil A (alle Prüfungen vor dem Anlegen), es wird nichts angelegt.
#
# Umgebungsvariablen:
#   OWNER                    Konto der Repositories                (Standard: alexandru-tatar)
#   VORLAGE_OWNER            Konto der Golden Master               (Standard: $OWNER)
#   PORTAL_REPO              Portal-Repository (Slugs, Team)       (Standard: awp-hka-intranet-portal)
#   DEPLOY_SSH_KEY_FILE      Datei mit dem privaten Deploy-Schlüssel   (Pflicht)
#   DEPLOY_KNOWN_HOSTS_FILE  Datei mit dem known_hosts-Eintrag der VM  (Pflicht)
#   DEPLOY_HOST              Rechner der Test-VM                   (Standard: iwi-hean-05.hs-karlsruhe.de)
#   NEUE_APP_WARTEN          Sekunden zwischen Abfragen nach dem Anlegen (Standard: 2)
#
# Geheimnisse gehen nur über Dateien und Standardeingabe, nie als Argument und nie ins Log.

set -euo pipefail

OWNER="${OWNER:-alexandru-tatar}"
VORLAGE_OWNER="${VORLAGE_OWNER:-$OWNER}"
PORTAL_REPO="${PORTAL_REPO:-awp-hka-intranet-portal}"
DEPLOY_HOST="${DEPLOY_HOST:-iwi-hean-05.hs-karlsruhe.de}"
DEPLOY_SSH_KEY_FILE="${DEPLOY_SSH_KEY_FILE:-}"
DEPLOY_KNOWN_HOSTS_FILE="${DEPLOY_KNOWN_HOSTS_FILE:-}"
WARTEN="${NEUE_APP_WARTEN:-2}"

# Gleiche Liste wie RESERVED_SLUGS in src/portal/registry/models.py (ein Test prüft den Gleichlauf).
RESERVIERT="_portal admin api auth static apps portal adapters gateway traefik redis registry health healthz login logout oidc"
# Werte aus der Vorlage bzw. aus den Golden-Master-Tests: nicht als Slug einer echten App erlaubt.
GESPERRT="meine-app andere-app"
SLUG_MUSTER='^[a-z][a-z0-9-]{2,30}$' # wie schemas/manifest.schema.json
GITHUB_ACTIONS_ID=15368
UMGEBUNG="test-vm"
RULESET_NAME="main-schutz"

ANGELEGT=0
LETZTER="Prüfungen"
REPO=""

verwendung() {
  cat <<'TEXT'
Aufruf: tools/neue-app.sh <slug> js|python [--pruefen]

  <slug>     Kurzname der App: Kleinbuchstaben, Ziffern, Bindestrich; 3 bis 31 Zeichen; beginnt mit einem Buchstaben
  js|python  Golden Master als Vorlage
  --pruefen  nur prüfen, nichts anlegen

Pflicht: DEPLOY_SSH_KEY_FILE und DEPLOY_KNOWN_HOSTS_FILE (Dateien mit den Werten). Mehr in tools/README.md.
TEXT
}

fehler() {
  echo "FEHLER: $*" >&2
  exit 1
}

warnung() {
  echo "WARNUNG: $*" >&2
}

schritt() {
  LETZTER="$*"
  echo "==> $*"
}

abbruch() {
  local rc=$?
  if [ "$rc" -ne 0 ] && [ "$ANGELEGT" = 1 ]; then
    {
      echo ""
      echo "Abbruch im Schritt: $LETZTER"
      echo "Das Repository $REPO ist nur teilweise eingerichtet. Zum Wiederholen zuerst löschen:"
      echo "  gh repo delete $REPO"
    } >&2
  fi
}
trap abbruch EXIT

# Inhalt einer Datei im Rohformat
roh() {
  gh api -H "Accept: application/vnd.github.raw+json" "$1"
}

# 0: Endpunkt vorhanden, 1: 404, sonst Abbruch (kein Netz, keine Rechte)
existiert() {
  local ausgabe
  if ausgabe=$(gh api "$1" 2>&1); then
    return 0
  fi
  case "$ausgabe" in
    *"404"* | *"Not Found"*) return 1 ;;
  esac
  fehler "GitHub-Abfrage $1 fehlgeschlagen: $ausgabe"
}

# Slugs aus dev/manifests des Portals und aus den bisher angelegten Apps (Thema hka-app)
vergebene_slugs() {
  local liste pfad name inhalt
  liste=$(gh api "repos/$OWNER/$PORTAL_REPO/contents/dev/manifests" \
    --jq '.[] | select(.name | endswith(".json")) | .path') || return 1
  while IFS= read -r pfad; do
    [ -n "$pfad" ] || continue
    inhalt=$(roh "repos/$OWNER/$PORTAL_REPO/contents/$pfad") || return 1
    printf '%s\n' "$inhalt" | jq -r '.slug // empty' || return 1
  done <<EOF
$liste
EOF
  liste=$(gh api -X GET search/repositories -f q="user:$OWNER topic:hka-app" --jq '.items[].name') || return 1
  while IFS= read -r name; do
    [ -n "$name" ] || continue
    if inhalt=$(roh "repos/$OWNER/$name/contents/manifest.json" 2> /dev/null); then
      printf '%s\n' "$inhalt" | jq -r '.slug // empty' || true
    else
      warnung "Kein manifest.json in $OWNER/$name gelesen, der Slug dieser App fehlt in der Prüfung."
    fi
  done <<EOF
$liste
EOF
}

# --- Teil A: Prüfungen, bevor etwas angelegt wird -------------------------------------------------

pruefungen() {
  local login belegt

  command -v gh > /dev/null 2>&1 || fehler "gh (GitHub CLI) fehlt: https://cli.github.com"
  command -v jq > /dev/null 2>&1 || fehler "jq fehlt."
  gh auth status > /dev/null 2>&1 || fehler "gh ist nicht angemeldet: gh auth login"

  case "$SPRACHE" in
    js | python) ;;
    *) fehler "Sprache '$SPRACHE' unbekannt. Erlaubt: js oder python." ;;
  esac

  [[ "$SLUG" =~ $SLUG_MUSTER ]] \
    || fehler "Slug '$SLUG' ungültig: Kleinbuchstaben, Ziffern und Bindestrich, 3 bis 31 Zeichen, beginnt mit einem Buchstaben."
  for wort in $RESERVIERT; do
    [ "$SLUG" != "$wort" ] || fehler "Slug '$SLUG' ist für das Portal reserviert."
  done
  for wort in $GESPERRT; do
    [ "$SLUG" != "$wort" ] || fehler "Slug '$SLUG' ist ein Platzhalter aus der Vorlage oder den Tests. Bitte einen eigenen Namen wählen."
  done

  [ -n "$DEPLOY_SSH_KEY_FILE" ] && [ -s "$DEPLOY_SSH_KEY_FILE" ] \
    || fehler "DEPLOY_SSH_KEY_FILE fehlt oder die Datei ist leer."
  [ -n "$DEPLOY_KNOWN_HOSTS_FILE" ] && [ -s "$DEPLOY_KNOWN_HOSTS_FILE" ] \
    || fehler "DEPLOY_KNOWN_HOSTS_FILE fehlt oder die Datei ist leer."
  [ -n "$DEPLOY_HOST" ] || fehler "DEPLOY_HOST ist leer."

  login=$(gh api user --jq .login) || fehler "Angemeldeten gh-Benutzer nicht ermittelt."
  [ "$(printf '%s' "$login" | tr '[:upper:]' '[:lower:]')" = "$(printf '%s' "$OWNER" | tr '[:upper:]' '[:lower:]')" ] \
    || fehler "Angemeldet als '$login'. Rulesets und Secrets setzt nur der Konto-Inhaber '$OWNER' (gh auth switch)."

  local ist_vorlage
  ist_vorlage=$(gh api "repos/$VORLAGE_OWNER/$VORLAGE" --jq .is_template 2> /dev/null) \
    || fehler "Vorlage $VORLAGE_OWNER/$VORLAGE nicht gefunden."
  [ "$ist_vorlage" = "true" ] \
    || fehler "$VORLAGE_OWNER/$VORLAGE ist nicht als Vorlage markiert. Einmalig: gh repo edit $VORLAGE_OWNER/$VORLAGE --template"
  existiert "repos/$VORLAGE_OWNER/$VORLAGE/contents/.github/workflows/pruefung.yml" \
    || warnung "Die Vorlage enthält .github/workflows/pruefung.yml nicht (HKA-47 nicht gemergt). Der Pflicht-Check 'check' läuft dann nie, Pull Requests lassen sich nicht mergen."

  if existiert "repos/$OWNER/$REPO_NAME"; then
    fehler "Das Repository $OWNER/$REPO_NAME gibt es schon."
  fi

  belegt=$(vergebene_slugs) || fehler "Vergebene Slugs nicht gelesen (Portal $OWNER/$PORTAL_REPO, Apps mit Thema hka-app)."
  if printf '%s\n' "$belegt" | grep -qx -- "$SLUG"; then
    fehler "Der Slug '$SLUG' gehört schon zu einer anderen App."
  fi
}

# --- Teil B: Anlegen ------------------------------------------------------------------------------

anlegen() {
  local sha inhalt neu b64 pruefsumme i login fehlgeschlagen=""

  schritt "Repository $REPO aus $VORLAGE_OWNER/$VORLAGE anlegen"
  gh repo create "$REPO" --public --template "$VORLAGE_OWNER/$VORLAGE" \
    --description "HKA-Portal-App $SLUG (aus dem Golden Master)" > /dev/null
  ANGELEGT=1

  schritt "Warten, bis GitHub den Inhalt der Vorlage kopiert hat"
  for i in $(seq 1 30); do
    if gh api "repos/$REPO/contents/manifest.json" > /dev/null 2>&1; then
      break
    fi
    [ "$i" -lt 30 ] || fehler "manifest.json erscheint nach 30 Versuchen nicht in $REPO."
    sleep "$WARTEN"
  done

  # Vor dem Ruleset, denn danach ist kein direkter Push auf main mehr möglich.
  schritt "Slug '$SLUG' in manifest.json setzen"
  sha=$(gh api "repos/$REPO/contents/manifest.json" --jq .sha)
  inhalt=$(roh "repos/$REPO/contents/manifest.json")
  neu=$(printf '%s\n' "$inhalt" | sed -E 's/("slug"[[:space:]]*:[[:space:]]*")[^"]*(")/\1'"$SLUG"'\2/')
  [ "$(printf '%s' "$neu" | jq -r .slug)" = "$SLUG" ] || fehler "Der Slug ließ sich in manifest.json nicht ersetzen."
  b64=$(printf '%s\n' "$neu" | base64 | tr -d '\n')
  gh api -X PUT "repos/$REPO/contents/manifest.json" \
    -f message="Slug auf $SLUG gesetzt (neue-app.sh)" -f content="$b64" -f sha="$sha" -f branch=main > /dev/null

  schritt "Zweig develop anlegen"
  sha=$(gh api "repos/$REPO/git/ref/heads/main" --jq .object.sha)
  gh api -X POST "repos/$REPO/git/refs" -f ref=refs/heads/develop -f sha="$sha" > /dev/null

  schritt "Thema hka-app setzen"
  gh repo edit "$REPO" --add-topic hka-app > /dev/null

  schritt "Mitglieder des Portal-Repositories als Collaborators eintragen"
  local mitglieder
  mitglieder=$(gh api "repos/$OWNER/$PORTAL_REPO/collaborators" --paginate --jq '.[].login')
  while IFS= read -r login; do
    [ -n "$login" ] || continue
    [ "$(printf '%s' "$login" | tr '[:upper:]' '[:lower:]')" != "$(printf '%s' "$OWNER" | tr '[:upper:]' '[:lower:]')" ] || continue
    if gh api -X PUT "repos/$REPO/collaborators/$login" -f permission=push > /dev/null; then
      echo "    $login (muss die Einladung annehmen)"
    else
      warnung "$login konnte nicht eingetragen werden."
      fehlgeschlagen="$fehlgeschlagen $login"
    fi
  done <<EOF
$mitglieder
EOF

  schritt "Environment $UMGEBUNG anlegen"
  gh api -X PUT "repos/$REPO/environments/$UMGEBUNG" > /dev/null

  schritt "Secrets im Environment $UMGEBUNG setzen"
  gh secret set DEPLOY_SSH_KEY --env "$UMGEBUNG" --repo "$REPO" < "$DEPLOY_SSH_KEY_FILE" > /dev/null
  gh secret set DEPLOY_KNOWN_HOSTS --env "$UMGEBUNG" --repo "$REPO" < "$DEPLOY_KNOWN_HOSTS_FILE" > /dev/null
  printf '%s' "$DEPLOY_HOST" | gh secret set DEPLOY_HOST --env "$UMGEBUNG" --repo "$REPO" > /dev/null

  schritt "Ruleset $RULESET_NAME auf main setzen"
  gh api -X POST "repos/$REPO/rulesets" --input - > /dev/null <<JSON
{
  "name": "$RULESET_NAME",
  "target": "branch",
  "enforcement": "active",
  "bypass_actors": [],
  "conditions": { "ref_name": { "include": ["refs/heads/main"], "exclude": [] } },
  "rules": [
    { "type": "deletion" },
    { "type": "non_fast_forward" },
    {
      "type": "pull_request",
      "parameters": {
        "required_approving_review_count": 1,
        "dismiss_stale_reviews_on_push": true,
        "require_code_owner_review": false,
        "require_last_push_approval": true,
        "required_review_thread_resolution": false,
        "allowed_merge_methods": ["merge", "squash", "rebase"]
      }
    },
    {
      "type": "required_status_checks",
      "parameters": {
        "strict_required_status_checks_policy": false,
        "required_status_checks": [{ "context": "check", "integration_id": $GITHUB_ACTIONS_ID }]
      }
    }
  ]
}
JSON

  LETZTER="Fertig"
  echo ""
  echo "Fertig: https://github.com/$REPO"
  if [ -n "$fehlgeschlagen" ]; then
    warnung "Nicht eingetragen:$fehlgeschlagen. Von Hand: gh api -X PUT repos/$REPO/collaborators/<login> -f permission=push"
  fi
  echo "Prüfen:"
  echo "  gh api repos/$REPO/rules/branches/main"
  echo "  gh secret list --env $UMGEBUNG --repo $REPO"
  echo "  git clone https://github.com/$REPO.git && cd $REPO_NAME && git switch develop"
}

# --- Hauptteil ------------------------------------------------------------------------------------

PRUEFEN=0
ARGUMENTE=()
for argument in "$@"; do
  case "$argument" in
    --pruefen) PRUEFEN=1 ;;
    -h | --help)
      verwendung
      exit 0
      ;;
    -*) fehler "Unbekannte Option: $argument" ;;
    *) ARGUMENTE+=("$argument") ;;
  esac
done
if [ "${#ARGUMENTE[@]}" -ne 2 ]; then
  verwendung >&2
  exit 1
fi

SLUG="${ARGUMENTE[0]}"
SPRACHE="${ARGUMENTE[1]}"
REPO_NAME="app-$SLUG"
REPO="$OWNER/$REPO_NAME"
VORLAGE="awp-hka-gold-$SPRACHE"

pruefungen

echo "Alle Prüfungen bestanden."
if [ "$PRUEFEN" = 1 ]; then
  echo "Geplant (mit --pruefen nicht ausgeführt):"
  echo "  Repository $REPO (öffentlich) aus $VORLAGE_OWNER/$VORLAGE, Slug '$SLUG', Zweige main und develop"
  echo "  Ruleset $RULESET_NAME: Pull Request mit 1 Freigabe, Pflicht-Check 'check', keine Ausnahme"
  echo "  Environment $UMGEBUNG mit DEPLOY_SSH_KEY, DEPLOY_KNOWN_HOSTS, DEPLOY_HOST"
  echo "  Collaborators aus $OWNER/$PORTAL_REPO"
  exit 0
fi

anlegen
