# Registrierung von Apps auf der Test-VM (HKA-53)

Die Pipeline einer App legt nach dem Deployment das Manifest auf der VM ab. Das Portal übernimmt es nach wenigen Sekunden von selbst,
prüft `/healthz` der App und zeigt sie im Menü. Wie das im Portal funktioniert, steht in
[`docs/07-registry-und-apps.md`](../../../../docs/07-registry-und-apps.md#registrierung-durch-die-pipeline-hka-53). Dieser Ordner enthält,
was auf der VM dafür eingerichtet wird.

```text
GitHub Actions --ssh deploy@VM check|register < manifest.json-->  sshd (Benutzer deploy, Schlüssel mit festem Kommando)
   --> sudo portal-deploy --owner <owner/repo>  (nur check oder register, sonst Exit 2)
   --> docker run --network none --read-only … hka/portal python -m portal.registry register
   --> /srv/portal/manifests/<slug>.json + /srv/portal/registry/owners.json
Portal (Container backend) liest /srv/portal/manifests schreibgeschützt, prüft alle 5 s auf Neues und /healthz der Apps.
```

| Datei | Zweck | Ziel auf der VM |
|---|---|---|
| `portal-deploy` | festes Kommando: erlaubt nur `check` und `register` | `/usr/local/sbin/portal-deploy` (root, 0755) |
| `sudoers.portal-deploy` | `deploy` darf genau dieses Skript als root starten | `/etc/sudoers.d/portal-deploy` (0440) |
| `authorized_keys.example` | Schlüssel je App-Repository mit festem Kommando | `/home/deploy/.ssh/authorized_keys` (0600) |
| `deploy.env.example` | Image und Ordner für das Skript | `/etc/portal/deploy.env` |

Warum `sudo`: `docker` darf nur root und die Gruppe `docker` (gleichbedeutend mit root). `deploy` ist in keiner Gruppe und kann nur dieses
Skript mit festen Argumenten starten. Das Skript traut als root nichts aus der Umgebung außer `SSH_ORIGINAL_COMMAND`.

## Einrichtung (einmal, als `sadmin`)

1. **Neue Images einspielen.** Das Image enthält Prober und Befehl, die Konfiguration `dev/gateway.vm.yml` ist eingebaut. Ablauf wie in
   `compose.yml` (bauen auf dem eigenen Rechner, `docker save`, `scp`, `docker load`).
2. **Ordner anlegen**, bevor das Portal startet (sonst bricht es ab, weil `manifests_dir` fehlt). Die Nummer ist die Benutzer-ID im Image:
   ```bash
   UID_IMAGE=$(sudo docker run --rm --entrypoint python hka/portal:0.1.0-hardened -c "import os; print(os.getuid())")
   sudo install -d -m 0755 -o "$UID_IMAGE" -g "$UID_IMAGE" /srv/portal/manifests /srv/portal/registry
   ```
3. **Portal neu starten:** `sudo docker compose -f ~/compose.yml up -d --no-build`. Das Menü ist danach leer, bis die erste App registriert ist.
4. **Benutzer `deploy`** ohne Passwort und ohne Gruppen:
   ```bash
   sudo adduser --disabled-password --gecos "" deploy
   sudo install -d -m 0700 -o deploy -g deploy /home/deploy/.ssh
   ```
5. **Skript und Einstellungen:**
   ```bash
   sudo install -m 0755 -o root -g root portal-deploy /usr/local/sbin/portal-deploy
   sudo install -d -m 0755 /etc/portal
   sudo install -m 0644 deploy.env.example /etc/portal/deploy.env      # Image und Ordner prüfen
   sudo install -m 0440 sudoers.portal-deploy /etc/sudoers.d/portal-deploy
   sudo visudo -cf /etc/sudoers.d/portal-deploy
   ```
6. **Schlüssel je App-Repository.** Auf dem eigenen Rechner: `ssh-keygen -t ed25519 -N "" -C deploy-<repo> -f deploy-<repo>`. Den öffentlichen
   Teil mit dem Besitzer des Repositorys in `/home/deploy/.ssh/authorized_keys` eintragen (Muster in `authorized_keys.example`), den
   privaten Teil als Secret `DEPLOY_SSH_KEY` im Environment `test-vm` des App-Repositorys ablegen und danach lokal löschen. Der Besitzer
   (`owner/repo`) steht fest im Schlüssel. Eine Pipeline kann deshalb keinen Namen für ein fremdes Repository beanspruchen.

## Schritte im Workflow (kommen mit HKA-50 in die Golden Master)

```yaml
      - name: SSH vorbereiten
        run: |
          install -m 0700 -d ~/.ssh
          printf '%s\n' "${{ secrets.DEPLOY_SSH_KEY }}" > ~/.ssh/id_ed25519 && chmod 600 ~/.ssh/id_ed25519
          printf '%s\n' "${{ vars.DEPLOY_KNOWN_HOSTS }}" > ~/.ssh/known_hosts
      - name: Manifest prüfen (vor dem Deployment)
        run: ssh -T deploy@iwi-hean-05.hs-karlsruhe.de check < manifest.json
      # … Container bauen und einspielen (HKA-46), Healthcheck …
      - name: App registrieren (nach grünem Healthcheck)
        run: ssh -T deploy@iwi-hean-05.hs-karlsruhe.de register < manifest.json
```

Wird das Manifest abgelehnt, steht der Fehlerblock (`PF-104`, `PF-202`, `PF-204`) im Log, der Schritt ist rot, und nichts ändert sich.

## Testanleitungen

**AK5, kein Zugang zur Shell** (vom eigenen Rechner mit dem Schlüssel eines App-Repositorys):

```bash
ssh deploy@iwi-hean-05.hs-karlsruhe.de bash            # muss scheitern: portal-deploy: nur check oder register erlaubt (Exit 2)
ssh deploy@iwi-hean-05.hs-karlsruhe.de 'check; id'     # ebenso
ssh deploy@iwi-hean-05.hs-karlsruhe.de                 # ohne Befehl: ebenso, kein Terminal
ssh deploy@iwi-hean-05.hs-karlsruhe.de check < manifest.json         # erlaubt: prüft nur, schreibt nichts
```

Dazu Code-Review der `authorized_keys`: Jede Zeile beginnt mit `restrict,command="sudo -n /usr/local/sbin/portal-deploy --owner …"`. Auf
der VM zeigt `sudo journalctl -t portal-deploy` jeden Aufruf und jede Ablehnung.

**AK1, App erscheint im Menü** (braucht einen laufenden Container `app-<slug>` im Docker-Netz des Portals, HKA-46 und HKA-50):

```bash
date +%T; ssh -T deploy@iwi-hean-05.hs-karlsruhe.de register < manifest.json; date +%T
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
einspielen: Der Aufruf endet mit `FEHLER PF-104` und nennt das Feld, das Menü bleibt gleich. Dasselbe Manifest mit einem Schlüssel eines
anderen Repositorys einspielen: `FEHLER PF-202`.

## Lokal ohne VM ausprobieren

1. Kopie von `dev/gateway.apps.yml` anlegen, `state_file` streichen, `manifests_dir` auf einen leeren Ordner setzen und anhängen:
   `registry: { probe: true, owners_file: <Ordner>/owners.json }`.
2. Portal: `PORTAL_CONFIG=<Kopie> uv run uvicorn portal.dev:app --port 8000`. App aus dem Golden Master auf Port 8080 (Anleitung in
   `docs/07-registry-und-apps.md`, Abschnitt „Prüfanleitung“).
3. `uv run python -m portal.registry register --config <Kopie> --owner me/test < manifest.json`, danach das Menü im Browser (Test-Login).

## Grenzen

- Die VM ist nur im Hochschulnetz erreichbar. Wie die Pipeline sie erreicht (selbst gehosteter Runner o. Ä.), entscheidet HKA-46.
- Der Signaturschlüssel des Gateways ist auf der VM flüchtig (`env: dev`); nach einem Neustart des Portals bekommen Apps neue Tokens.
- Nach einem Neustart des Portals beginnen alle Apps bei `registering` und sind nach etwa 5 s wieder im Menü.
- Nicht enthalten: Abmelden einer App, Zurücksetzen auf eine alte Version, Prüfung auf Versionsrückschritt (Phase 3, SQLite-Registry).
