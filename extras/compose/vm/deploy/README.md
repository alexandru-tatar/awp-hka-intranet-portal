# Registrierung von Apps auf der Test-VM (HKA-53)

Apps werden von Hand registriert: Das Manifest wird per `scp` auf die VM kopiert und dort mit `portal-deploy` geprüft und abgelegt. Das
Portal übernimmt es nach wenigen Sekunden von selbst, prüft `/healthz` der App und zeigt sie im Menü. Wie das im Portal funktioniert,
steht in [`docs/07-registry-und-apps.md`](../../../../docs/07-registry-und-apps.md#registrierung-hka-53). Dieser Ordner enthält, was auf der
VM dafür eingerichtet wird.

```text
Mac:  scp manifest.json sadmin@VM:~/manifests/<slug>.json
VM:   sudo portal-deploy check|register --owner <owner/repo> < ~/manifests/<slug>.json
        --> docker run --network none --read-only … hka/portal python -m portal.registry register
        --> /srv/portal/manifests/<slug>.json + /srv/portal/registry/owners.json
Portal (Container backend) liest /srv/portal/manifests schreibgeschützt, prüft alle 5 s auf Neues und /healthz der Apps.
```

| Datei | Zweck | Ziel auf der VM |
|---|---|---|
| `portal-deploy` | prüft (`check`) oder registriert (`register`) ein Manifest mit festen Docker-Argumenten | `/usr/local/sbin/portal-deploy` (root, 0755) |
| `deploy.env.example` | Image und Ordner für das Skript | `/etc/portal/deploy.env` |

Das Manifest wird nicht direkt nach `/srv/portal/manifests` kopiert: `portal-deploy` prüft es vorher (Schema, Rollen, Kategorien, Besitzer)
und schreibt atomar. Ein abgelehntes Manifest ändert nichts am Menü.

## Einrichtung (einmal, als `sadmin`)

1. **Neue Images einspielen.** Das Image enthält Prober und Befehl, die Konfiguration `dev/gateway.vm.yml` ist eingebaut. Ablauf wie in
   `compose.yml` (bauen auf dem eigenen Rechner, `docker save`, `scp`, `docker load`).
2. **Ordner anlegen**, bevor das Portal startet (sonst bricht es ab, weil `manifests_dir` fehlt). Die Nummer ist die Benutzer-ID im Image:
   ```bash
   UID_IMAGE=$(sudo docker run --rm --entrypoint python hka/portal:0.1.0-hardened -c "import os; print(os.getuid())")
   sudo install -d -m 0755 -o "$UID_IMAGE" -g "$UID_IMAGE" /srv/portal/manifests /srv/portal/registry
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

Voraussetzung: Der Container `app-<slug>` läuft im Docker-Netz `hka-portal-apps` (HKA-60). Am einfachsten mit `make deploy VM=<host>` im
App-Repository (Golden Master, HKA-50): Das erledigt Image, Container, `check` und `register` in einem Schritt. Von Hand geht es so:

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

## Testanleitungen

**Aufruf:** falsche Befehle und Argumente scheitern mit Exit 2, ohne dass Docker startet:

```bash
sudo portal-deploy bash --owner a/b < manifest.json           # nur check oder register erlaubt
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

**HKA-60, Netztrennung:** Das Portal-Image liegt auf der VM und dient als Prüf-Container im Netz der Apps.

```bash
P='sudo docker run --rm --network hka-portal-apps --entrypoint python hka/portal:0.1.0-hardened -c'
$P "import socket; socket.create_connection(('backend', 8000), 2); print('backend ok')"   # AK2: ok
$P "import socket; socket.create_connection(('redis', 6379), 2)"                          # AK3: Fehler (Name unbekannt)
$P "import socket; socket.create_connection(('keycloak', 8080), 2)"                       # AK3: Fehler (Name unbekannt)
```

**Umstellung auf HKA-60 (einmal):** `compose.yml` per `scp` kopieren, `sudo docker compose -f ~/compose.yml up -d --no-build`, danach jede
App einmal neu mit `make deploy` einspielen (sie hängen sonst noch im alten Netz `hka-portal-vm_default`).

## Lokal ohne VM ausprobieren

1. Kopie von `dev/gateway.apps.yml` anlegen, `state_file` streichen, `manifests_dir` auf einen leeren Ordner setzen und anhängen:
   `registry: { probe: true, owners_file: <Ordner>/owners.json }`.
2. Portal: `PORTAL_CONFIG=<Kopie> uv run uvicorn portal.dev:app --port 8000`. App aus dem Golden Master auf Port 8080 (Anleitung in
   `docs/07-registry-und-apps.md`, Abschnitt „Prüfanleitung“).
3. `uv run python -m portal.registry register --config <Kopie> --owner me/test < manifest.json`, danach das Menü im Browser (Test-Login).

## Grenzen

- Registrieren kann nur, wer als `sadmin` (mit `sudo`) auf der VM ist. Den Wert von `--owner` prüft niemand gegen das Repository; er
  dient nur dazu, dass zwei Apps nicht denselben Namen bekommen.
- Die VM ist nur im Hochschulnetz erreichbar (VPN für `scp`).
- Der Signaturschlüssel des Gateways ist auf der VM flüchtig (`env: dev`); nach einem Neustart des Portals bekommen Apps neue Tokens.
- Nach einem Neustart des Portals beginnen alle Apps bei `registering` und sind nach etwa 5 s wieder im Menü.
- Nicht enthalten: Abmelden einer App, Zurücksetzen auf eine alte Version, Prüfung auf Versionsrückschritt (Phase 3, SQLite-Registry).
