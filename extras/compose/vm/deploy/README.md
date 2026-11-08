# Registrierung und Verwaltung von Apps auf der Test-VM (HKA-53, HKA-56)

Apps werden von Hand registriert: Das Manifest wird per `scp` auf die VM kopiert und dort mit `portal-deploy` geprüft und abgelegt. Das
Portal übernimmt es nach wenigen Sekunden von selbst, prüft `/healthz` der App und zeigt sie im Menü. Wie das im Portal funktioniert,
steht in [`docs/07-registry-und-apps.md`](../../../../docs/07-registry-und-apps.md#registrierung-hka-53). Dieser Ordner enthält, was auf der
VM dafür eingerichtet wird.

```text
Mac:  scp manifest.json sadmin@VM:~/manifests/<slug>.json
VM:   sudo portal-deploy check|register --owner <owner/repo> < ~/manifests/<slug>.json
      sudo portal-deploy list | remove <slug> --owner <owner/repo>
        --> docker run --network none --read-only … hka/portal python -m portal.registry register
        --> /srv/portal/manifests/<slug>.json + /srv/portal/registry/owners.json
Portal (Container backend) liest /srv/portal/manifests schreibgeschützt, prüft alle 5 s auf Neues und /healthz der Apps
und schreibt den Status nach /srv/portal/status/status.json (liest "list").
```

| Datei | Zweck | Ziel auf der VM |
|---|---|---|
| `portal-deploy` | prüft (`check`), registriert (`register`), zeigt (`list`) oder legt still (`remove`), mit festen Docker-Argumenten | `/usr/local/sbin/portal-deploy` (root, 0755) |
| `deploy.env.example` | Image und Ordner für das Skript | `/etc/portal/deploy.env` |

Das Manifest wird nicht direkt nach `/srv/portal/manifests` kopiert: `portal-deploy` prüft es vorher (Schema, Rollen, Kategorien, Besitzer)
und schreibt atomar. Ein abgelehntes Manifest ändert nichts am Menü.

## Einrichtung (einmal, als `sadmin`)

1. **Neue Images einspielen.** Das Image enthält Prober und Befehl, die Konfiguration `dev/gateway.vm.yml` ist eingebaut. Ablauf wie in
   `compose.yml` (bauen auf dem eigenen Rechner, `docker save`, `scp`, `docker load`).
2. **Ordner anlegen**, bevor das Portal startet (sonst bricht es ab, weil `manifests_dir` fehlt). Die Nummer ist die Benutzer-ID im Image:
   ```bash
   UID_IMAGE=$(sudo docker run --rm --entrypoint python hka/portal:0.1.0-hardened -c "import os; print(os.getuid())")
   sudo install -d -m 0755 -o "$UID_IMAGE" -g "$UID_IMAGE" /srv/portal/manifests /srv/portal/registry /srv/portal/status
   install -d -m 0700 ~/manifests          # Ablage für die per scp kopierten Manifeste
   ```
3. **Portal neu starten:** `sudo docker compose -f ~/compose.yml up -d --no-build`. Das Menü ist danach leer, bis die erste App registriert ist.
4. **Skript und Einstellungen** (vorher `portal-deploy` und `deploy.env.example` per `scp` nach `~` kopieren):
   ```bash
   sudo install -m 0755 -o root -g root portal-deploy /usr/local/sbin/portal-deploy
   sudo install -d -m 0755 /etc/portal
   sudo install -m 0644 deploy.env.example /etc/portal/deploy.env      # Image und Ordner prüfen
   ```

## App registrieren (je App und Version)

Voraussetzung: Der Container `app-<slug>` läuft im Docker-Netz des Portals (Image ebenfalls per `docker save`/`scp`/`docker load`).

```bash
# Mac
scp manifest.json sadmin@iwi-hean-05.hs-karlsruhe.de:~/manifests/<slug>.json

# VM
sudo portal-deploy check    --owner <owner/repo> < ~/manifests/<slug>.json   # prüft nur, schreibt nichts
sudo portal-deploy register --owner <owner/repo> < ~/manifests/<slug>.json   # nach grünem Healthcheck der App
```

`--owner` ist das Repository der App (`owner/repo`). Der erste Besitzer eines Namens bleibt es (TOFU, 03 §6); dieselbe App immer mit
demselben `--owner` registrieren. Wird das Manifest abgelehnt, steht der Fehlerblock (`PF-104`, `PF-202`, `PF-204`) in der Ausgabe, der
Exit-Code ist 1, und nichts ändert sich. `sudo journalctl -t portal-deploy` zeigt jeden Aufruf mit Benutzer.

## Apps verwalten (HKA-56)

```bash
sudo portal-deploy list                                     # alle Apps: Slug, Besitzer, Version, Status, letzte Prüfung
sudo portal-deploy register --owner <owner/repo> < ~/manifests/<slug>.json   # geändertes Manifest: „Aktualisiert“
sudo portal-deploy remove <slug> --owner <owner/repo>       # App stilllegen, nach etwa 5 s aus dem Menü
```

Nach `remove` darf dasselbe Repository den Namen sofort wieder registrieren, ein anderes erst nach 90 Tagen (`PF-202`). Details:
[`docs/07-registry-und-apps.md`](../../../../docs/07-registry-und-apps.md#verwalten-hka-56).

**Umstellung einer bestehenden VM (einmal):** Ordner `/srv/portal/status` anlegen (Befehl oben in Schritt 2, nur dieser Ordner),
neues Image und neue `compose.yml` einspielen, Portal neu starten, `portal-deploy` neu installieren und in `/etc/portal/deploy.env`
die Zeile `STATUS_DIR=/srv/portal/status` ergänzen.

## Testanleitungen

**Aufruf:** falsche Befehle und Argumente scheitern mit Exit 2, ohne dass Docker startet:

```bash
sudo portal-deploy bash --owner a/b < manifest.json           # nur check, register, list oder remove erlaubt
sudo portal-deploy remove '../x' --owner a/b                  # ungültiger Name der App
sudo portal-deploy check --owner 'a/b;id' < manifest.json     # ungültiger Besitzer
sudo portal-deploy check --owner a/b                          # Manifest fehlt auf der Standardeingabe
```

**AK1, App erscheint im Menü:**

```bash
date +%T; sudo portal-deploy register --owner <owner/repo> < ~/manifests/<slug>.json; date +%T
```

Danach als Person mit der Rolle aus dem Manifest im Browser neu laden und die Zeit bis zum Menüeintrag messen. Ziel: höchstens 60 s,
erwartet etwa 10 s. Lokal (ohne VM) gemessen: 5 s.

**AK2, Status und Hinweis im Menü:**

```bash
sudo docker stop app-<slug>      # nach etwa einer Minute: Menüeintrag mit „nicht verfügbar“, /apps/<slug>/ zeigt die 503-Seite
sudo docker start app-<slug>     # nach etwa 30 s: Hinweis weg
sudo docker compose -f ~/compose.yml logs backend | grep registry_change
```

**AK3 und AK4, abgelehnte Manifeste:** `manifest.json` mit unbekannter Rolle (`"roles": ["dean"]`) oder Kategorie (`"category": "Freizeit"`)
registrieren: Der Aufruf endet mit `FEHLER PF-104` und nennt das Feld, das Menü bleibt gleich. Dasselbe Manifest mit einem anderen
`--owner` registrieren: `FEHLER PF-202`.

**HKA-56 AK1, Anzeigen:** `sudo portal-deploy list` zeigt jede registrierte App mit Besitzer und Status (`healthy` usw.) und darunter
„Status vom …“ mit einer Zeit von höchstens 30 s vorher. Portal stoppen (`sudo docker compose -f ~/compose.yml stop backend`), 2 Minuten
warten: `list` zeigt „unbekannt“ und den Hinweis „Läuft das Portal?“. Danach wieder starten.

**HKA-56 AK2, Aktualisieren:** Im Manifest `menu.label` ändern, per `scp` kopieren, `register` mit demselben `--owner`: Ausgabe
„Aktualisiert“. Im Browser neu laden: Der neue Text steht nach etwa 10 s im Menü, ohne Neustart des Portals.

**HKA-56 AK3, Entfernen:**

```bash
date +%T; sudo portal-deploy remove <slug> --owner <owner/repo>; date +%T
```

Im Browser neu laden und die Zeit messen, bis der Eintrag weg ist (Ziel höchstens 60 s, erwartet etwa 5 s). `list` zeigt
„stillgelegt seit …“. Danach `register` mit demselben `--owner`: erlaubt, die App kommt zurück. Mit einem anderen `--owner`: `PF-202`.

**HKA-56 AK4, unbekannter Name:** `sudo portal-deploy remove gibtsnicht --owner a/b; echo $?`: Meldung „ist nicht registriert“, Exit 1,
`list` unverändert.

## Lokal ohne VM ausprobieren

1. Kopie von `dev/gateway.apps.yml` anlegen, `state_file` streichen, `manifests_dir` auf einen leeren Ordner setzen und anhängen:
   `registry: { probe: true, owners_file: <Ordner>/owners.json, status_file: <Ordner>/status.json }`.
2. Portal: `PORTAL_CONFIG=<Kopie> uv run uvicorn portal.dev:app --port 8000`. App aus dem Golden Master auf Port 8080 (Anleitung in
   `docs/07-registry-und-apps.md`, Abschnitt „Prüfanleitung“).
3. `uv run python -m portal.registry register --config <Kopie> --owner me/test < manifest.json`, danach das Menü im Browser (Test-Login).
4. `uv run python -m portal.registry list --config <Kopie>` und `… remove <slug> --config <Kopie> --owner me/test`.

## Grenzen

- Registrieren kann nur, wer als `sadmin` (mit `sudo`) auf der VM ist. Den Wert von `--owner` prüft niemand gegen das Repository; er
  dient nur dazu, dass zwei Apps nicht denselben Namen bekommen.
- Die VM ist nur im Hochschulnetz erreichbar (VPN für `scp`).
- Der Signaturschlüssel des Gateways ist auf der VM flüchtig (`env: dev`); nach einem Neustart des Portals bekommen Apps neue Tokens.
- Nach einem Neustart des Portals beginnen alle Apps bei `registering` und sind nach etwa 5 s wieder im Menü.
- Nicht enthalten: Zurücksetzen auf eine alte Version, Prüfung auf Versionsrückschritt, Freigeben eines Namens vor Ablauf der 90 Tage
  (Phase 3, SQLite-Registry). Ein stillgelegter Name lässt sich bis dahin nur von Hand in `retired.json` und `owners.json` freigeben.
