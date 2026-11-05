# tools/

## neue-app.sh: neue App aus dem Golden Master anlegen (HKA-54)

Ein Befehl legt das GitHub-Repository `app-<slug>` an. Danach funktionieren Prüf-Pipeline und Review-Pflicht ohne eigene
Einrichtung. Das Deployment läuft von Hand per `scp` (HKA-50, HKA-53; Ablauf in Confluence „CI/CD und Deployment“): Das
Skript legt dafür keine Secrets und keine Environments an.

```sh
tools/neue-app.sh noten-uebersicht python --pruefen   # nur prüfen
tools/neue-app.sh noten-uebersicht python             # anlegen
tools/neue-app.sh test-abc js --ohne-team             # anlegen, ohne das Team einzuladen (Testlauf)
```

### Was entsteht

| Teil | Inhalt |
|---|---|
| Repository | `alexandru-tatar/app-<slug>`, öffentlich, Inhalt von `awp-hka-gold-js` bzw. `awp-hka-gold-python` |
| Zweige | `main` und `develop`; im `manifest.json` auf `main` steht der Slug |
| Ruleset `main-schutz` | Pull Request mit 1 Freigabe (die Autorin kann nicht selbst freigeben, der letzte Push zählt nicht), Pflicht-Check `check`, kein Löschen, kein Force-Push, **keine Ausnahme** (`bypass_actors: []`) |
| Collaborators | alle Mitglieder von `awp-hka-intranet-portal` mit Push-Recht (jede Person nimmt die Einladung an); mit `--ohne-team` entfällt dieser Schritt, es gehen keine Einladungen raus |
| Thema | `hka-app`; damit prüft das Skript später, ob ein Slug schon vergeben ist |

### Prüfungen vor dem Anlegen (Teil A, auch mit `--pruefen`)

Der Slug muss `^[a-z][a-z0-9-]{2,30}$` erfüllen (wie `schemas/manifest.schema.json`), darf nicht reserviert sein
(`RESERVED_SLUGS` in `src/portal/registry/models.py`) und nicht `meine-app` oder `andere-app` heißen. Er darf weder in
`dev/manifests/` des Portals noch im `manifest.json` einer anderen App mit dem Thema `hka-app` stehen. Das Repository
`app-<slug>` darf es nicht geben. Die Vorlage muss als Template markiert sein. Bei einem Fehler wird nichts angelegt.

### Umgebungsvariablen

`OWNER` (Standard `alexandru-tatar`), `VORLAGE_OWNER` (Standard `$OWNER`), `PORTAL_OWNER` (Konto des Portals,
Standard `$OWNER`), `PORTAL_REPO` (Standard `awp-hka-intranet-portal`), `NEUE_APP_WARTEN` (Sekunden zwischen Abfragen nach
dem Anlegen, Standard 2). Zugangsdaten braucht das Skript nicht; es liest nur die Anmeldung von `gh`.

### Voraussetzungen und Grenzen

- `gh` und `jq`, `gh` angemeldet als **Konto-Inhaber** (`alexandru-tatar`). Nur er kann Rulesets setzen. Das
  reicht für die Demo, nicht für den Betrieb (Organisation oder GitLab-Gruppe: Phase 3, HKA-23).
- Beide Golden Master einmalig als Vorlage markieren:
  `gh repo edit alexandru-tatar/awp-hka-gold-js --template` und `… awp-hka-gold-python --template`.
- Der Pflicht-Check `check` kommt aus `.github/workflows/pruefung.yml` der Vorlage (HKA-47). Fehlt die Datei, warnt das
  Skript, und Pull Requests lassen sich nicht mergen.
- Die Suche nach Apps mit dem Thema `hka-app` kann direkt nach dem Anlegen noch eine Weile hinterherhinken. Zwei Apps
  mit demselben Slug kurz hintereinander anlegen: vermeiden.
- Bei einem Abbruch nach dem Anlegen nennt das Skript den Schritt und den Befehl `gh repo delete …`. Es löscht nie selbst.

### Prüfanleitung (Akzeptanzkriterien HKA-54)

1. AK1: je ein Repository mit `js` und `python` anlegen; `gh api repos/alexandru-tatar/app-<slug>/branches --jq '.[].name'`
   zeigt `main` und `develop`, `manifest.json` trägt den Slug.
2. AK2: `gh api repos/alexandru-tatar/app-<slug>/rules/branches/main` zeigt Pull-Request-Pflicht mit 1 Freigabe und `check`.
3. AK3: `git push origin HEAD:main` wird abgelehnt; den eigenen Pull Request freigeben ist nicht möglich.
4. AK4: Gitleaks über das neue Repository und über das Log des Skripts: `git clone https://github.com/alexandru-tatar/app-<slug>.git`,
   darin `gitleaks git .` (ohne Fund); das Log mit `tools/neue-app.sh … 2>&1 | tee neue-app.log` aufnehmen und `gitleaks dir neue-app.log`
   prüfen. Automatisch für das Log: `uv run pytest tests/test_neue_app.py -k ak4` (braucht Docker; die Probe mit einem eingebauten
   Token muss anschlagen, sonst gilt die Prüfung als ungültig).
5. AK5: auf `develop` pushen und einen Pull Request nach `main` öffnen: die Pipeline `Prüfung` läuft ohne weitere Einrichtung
   (setzt HKA-47 in der Vorlage voraus).
6. AK6: `tools/neue-app.sh meine-app js --pruefen` und ein schon vergebener Slug brechen vor dem Anlegen ab.
   Automatisch: `uv run pytest tests/test_neue_app.py`.
7. Testlauf unter eigenem Konto, ohne Einladungen: Golden Master dort forken und als Vorlage markieren, dann
   `OWNER=<konto> VORLAGE_OWNER=<konto> PORTAL_OWNER=alexandru-tatar tools/neue-app.sh test-abc js --ohne-team`.
8. Testrepositories danach löschen: `gh repo delete alexandru-tatar/app-<slug>`.
