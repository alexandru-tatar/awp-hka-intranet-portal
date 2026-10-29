# 10 — Platform Operations

Implementation-level specification of how the platform is installed, started, backed up, upgraded and handed over. Overview: `../09-component-design.md` §10, §12. This is the technical basis of the **Betriebsanleitung** that the Angebot promises (§5.2, §9.3) and of the **Übergabetest** with a person from HKA-IT (§8.1, §9: "Plattform anhand der Betriebsanleitung starten und neu starten"). ⚑ = confirm against pinned versions / the HKA VM.

## 1. Environments on the one VM

Two Compose projects on the single contracted VM (P-08): `portal-prod` and `portal-stage`. Same files, different overlays and values.

| | prod | stage |
|---|---|---|
| Compose project | `portal-prod` | `portal-stage` |
| Host name | `portal.hka.example` | `portal-stage.hka.example` |
| Published ports | 80, 443 | 8080, 8443 (change via `HTTP_PORT`/`HTTPS_PORT` if HKA provides a second address) |
| IdP | Shibboleth OIDC (HKA) | Keycloak container (E-04), realm with three test users in three roles |
| Adapters | `live` (once delivered) | `mock` → `stage` |
| Subnets | `172.29.10.0/29` ingress, `172.29.11.0/24` apps, `172.29.12.0/29` core, `172.29.13.0/29` egress | `172.29.20.0/29`, `172.29.21.0/24`, `172.29.22.0/29`, `172.29.24.0/29` egress, `172.29.23.0/29` idp |
| Data | `/var/lib/portal/prod`, `/etc/portal/{secrets,apps}/prod` | `…/stage` |

⚑ The `172.29.x.x` ranges are placeholders; they must be checked against HKA's network plan and listed in Docker's `default-address-pools` exclusion (§3, `daemon.json`).

## 2. VM layout and permissions

```
/opt/portal/                       root:portal-admins 0750      git checkout of the platform repository
├── compose/{platform.yml, platform.stage.yml}
├── traefik/{traefik.yml, platform.yml}
├── config/{prod,stage}/{gateway.yml, adapters.yml, policy.yml, roles.yml, grants.yml}
├── keycloak/realm-portal-stage.json
├── releases/<x.y.z>.env           image digests of one platform release
└── scripts/{platform.sh, deploy.sh, bootstrap.sh}

/etc/portal/secrets/{prod,stage}/  root:portal-secrets 0750, files 0440   (group gid 10100)
/etc/portal/apps/{prod,stage}/     deployer:portal-admins 0750, <slug>.env 0600 deployer
/var/lib/portal/{prod,stage}/      gateway state: registry.db (10001), audit/ (10002), apps/<slug>/compose.yml (deployer)
/var/lib/portal/registry-images/   local image registry data
/var/backups/portal/{prod,stage}/  root:portal-admins 0750
/var/log/portal/{traefik,deploy}/  logrotate: daily, 30 days
```
**Why `0440` + group `10100`:** file-based Docker secrets keep the host file's ownership inside the container, and the services run as different uids (gateway 10001, adapters 10002, Redis 999). A common group with `group_add: ["10100"]` on exactly the services that mount a secret avoids world-readable files and avoids chown-ing per service ⚑ (confirm Compose's handling of `uid/gid/mode` for non-Swarm secrets; the group approach does not depend on it).

## 3. Host preparation — `bootstrap.sh` (idempotent)

| Step | Content |
|---|---|
| 1 Packages | Docker Engine + Compose plugin, Podman, skopeo, jq, sqlite3 (CLI for diagnostics), chrony, logrotate, openssl, apache2-utils (htpasswd) |
| 2 Users/groups | `deployer` (docker group), `ci` (no docker, subuid/subgid, linger), groups `portal-admins`, `portal-secrets` (gid 10100) |
| 3 Directories | as §2 with the listed modes |
| 4 `daemon.json` | see below |
| 5 Firewall | §3.2, persisted by a systemd unit that runs *after* Docker |
| 6 Time | chrony enabled; check `chronyc tracking` offset < 100 ms (assertions live 60 s) |
| 7 Generated secrets | per environment: `jwt_current` (RSA 3072), empty `jwt_next` and `jwt_previous`, `audit_hmac_key` (32 random bytes), `redis_password`, `registrar_token`; **never overwritten if present** |
| 8 TLS volume | `docker volume create portal_certs`; operator then runs `platform.sh renew-cert` |
| 9 Image registry | htpasswd file with `ci` and `deployer` users; start `registry:2` on `127.0.0.1:5000` |
| 10 Cron/systemd | nightly `platform.sh backup`, weekly `gc-images`, boot units (§3.3) |
| 11 Runners | print the registration commands for the two runners (manual, needs the Git platform token) |

### 3.1 `/etc/docker/daemon.json`

```json
{
  "log-driver": "json-file",
  "log-opts": { "max-size": "10m", "max-file": "5" },
  "live-restore": true,
  "userland-proxy": false,
  "no-new-privileges": true,
  "default-address-pools": [ { "base": "172.30.0.0/16", "size": 24 } ],
  "features": { "containerd-snapshotter": false }
}
```
`live-restore` keeps containers running when the Docker daemon restarts. `default-address-pools` keeps dynamically created networks out of the `172.29.0.0/16` block reserved for the platform. (`no-new-privileges` as a daemon default is a belt-and-braces setting; the services also set it.)

### 3.2 Host firewall (`DOCKER-USER` chain) — what may leave the egress networks

Containers on `internal: true` networks have no route out at all. The two services that need to leave (gateway → IdP, adapters → legacy hosts) sit on the `egress` network with **fixed addresses** so rules can distinguish them:

```bash
# /opt/portal/scripts/firewall.sh  (applied after docker.service; values come from /etc/portal/firewall.conf)
set -euo pipefail
iptables -N PORTAL-EGRESS 2>/dev/null || iptables -F PORTAL-EGRESS
iptables -A PORTAL-EGRESS -m conntrack --ctstate ESTABLISHED,RELATED -j RETURN
# prod gateway (172.29.13.2) -> IdP
iptables -A PORTAL-EGRESS -s 172.29.13.2 -d "$IDP_ADDR"       -p tcp --dport 443 -j RETURN
# prod adapters (172.29.13.3) -> legacy systems
iptables -A PORTAL-EGRESS -s 172.29.13.3 -d "$EXCHANGE_ADDR"  -p tcp --dport 443 -j RETURN
iptables -A PORTAL-EGRESS -s 172.29.13.3 -d "$NOTEN_ADDR"     -p tcp --dport "$NOTEN_PORT" -j RETURN
# DNS for both (resolver address only)
iptables -A PORTAL-EGRESS -s 172.29.13.0/29 -d "$DNS_ADDR" -p udp --dport 53 -j RETURN
iptables -A PORTAL-EGRESS -s 172.29.13.0/29 -j DROP
iptables -C DOCKER-USER -s 172.29.13.0/29 -j PORTAL-EGRESS 2>/dev/null || iptables -I DOCKER-USER -s 172.29.13.0/29 -j PORTAL-EGRESS
```
(stage mirrors this with `172.29.24.0/29`.) Docker cannot allow-list by host name, so the addresses are filled in by HKA-IT into `firewall.conf`; this is a VM-level task and an HKA dependency (`../09-component-design.md` §10.3). Re-run on every boot by `portal-firewall.service`.

### 3.3 Boot units

```ini
# /etc/systemd/system/portal-firewall.service
[Unit]
Description=Portal egress firewall
After=docker.service
Requires=docker.service
[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/opt/portal/scripts/firewall.sh
[Install]
WantedBy=multi-user.target
```
```ini
# /etc/systemd/system/portal@.service     (instances: portal@prod, portal@stage)
[Unit]
Description=Portal platform (%i)
After=docker.service network-online.target portal-firewall.service
Requires=docker.service
[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/opt/portal/scripts/platform.sh up %i
ExecStop=/opt/portal/scripts/platform.sh down %i
TimeoutStartSec=300
[Install]
WantedBy=multi-user.target
```
Compose's `restart: unless-stopped` brings containers back after a Docker restart; the unit guarantees a **cold boot** converges without anyone logging in (tested in §10, item OP9).

## 4. The platform Compose project — `compose/platform.yml`

```yaml
name: ${PORTAL_PROJECT:-portal-prod}

x-hardened: &hardened
  restart: unless-stopped
  init: true
  read_only: true
  cap_drop: [ALL]
  security_opt: ["no-new-privileges:true"]
  logging: { driver: json-file, options: { max-size: "10m", max-file: "5" } }

services:
  traefik:
    <<: *hardened
    image: ${TRAEFIK_IMAGE}                 # from releases/<x.y.z>.env, pinned by digest
    cap_add: [NET_BIND_SERVICE]
    mem_limit: 256m
    cpus: 0.5
    ports: ["${HTTP_PORT:-80}:80", "${HTTPS_PORT:-443}:443"]
    volumes:
      - /opt/portal/traefik/traefik.yml:/etc/traefik/traefik.yml:ro
      - /opt/portal/traefik/platform.yml:/etc/traefik/platform.yml:ro
      - portal_certs:/certs:ro
      - /var/log/portal/traefik:/var/log/traefik
    networks:
      edge: {}
      ingress: { ipv4_address: "${NET_INGRESS_PREFIX}.3" }
      apps:    { ipv4_address: "${NET_APPS_PREFIX}.4" }
    healthcheck: { test: ["CMD", "traefik", "healthcheck", "--ping"], interval: 15s, timeout: 3s, retries: 3 }
    depends_on: { gateway: { condition: service_healthy } }

  gateway:
    <<: *hardened
    image: ${GATEWAY_IMAGE}
    user: "10001:10001"
    group_add: ["10100"]
    mem_limit: 512m
    cpus: 1.0
    tmpfs: ["/tmp:size=32m,noexec,nosuid"]
    environment: { GATEWAY_CONFIG: /etc/portal/gateway.yml, TZ: UTC }
    volumes:
      - /opt/portal/config/${PORTAL_ENV_NAME}/gateway.yml:/etc/portal/gateway.yml:ro
      - /opt/portal/config/${PORTAL_ENV_NAME}/roles.yml:/etc/portal/roles.yml:ro
      - /opt/portal/config/${PORTAL_ENV_NAME}/grants.yml:/etc/portal/grants.yml:ro
      - /var/lib/portal/${PORTAL_ENV_NAME}:/var/lib/portal
    secrets:
      - oidc_client_secret
      - redis_password
      - { source: jwt_current,  target: jwt_current.pem }
      - { source: jwt_next,     target: jwt_next.pem }
      - { source: jwt_previous, target: jwt_previous.pem }
      - registrar_token
      - audit_hmac_key
    networks:
      ingress: { ipv4_address: "${NET_INGRESS_PREFIX}.2" }
      core:    { ipv4_address: "${NET_CORE_PREFIX}.3" }
      apps:    { ipv4_address: "${NET_APPS_PREFIX}.2", aliases: [portal-api] }
      egress:  { ipv4_address: "${NET_EGRESS_PREFIX}.2" }
    healthcheck: { test: ["CMD", "python", "-m", "portal_gateway.healthcheck"], interval: 10s, timeout: 3s, retries: 3, start_period: 15s }
    depends_on: { redis: { condition: service_healthy } }

  redis:
    <<: *hardened
    image: ${REDIS_IMAGE}
    user: "999:999"
    group_add: ["10100"]
    mem_limit: 192m
    cpus: 0.5
    command: ["sh", "-c", "exec redis-server --requirepass \"$$(cat /run/secrets/redis_password)\" --save '' --appendonly no --maxmemory 128mb --maxmemory-policy volatile-lru --dir /tmp"]
    tmpfs: ["/tmp:size=16m,noexec,nosuid"]
    secrets: [redis_password]
    networks: { core: { ipv4_address: "${NET_CORE_PREFIX}.2" } }
    healthcheck: { test: ["CMD-SHELL", "redis-cli -a \"$$(cat /run/secrets/redis_password)\" --no-auth-warning ping | grep -q PONG"], interval: 10s, timeout: 3s, retries: 3 }

  adapters:
    <<: *hardened
    image: ${ADAPTERS_IMAGE}
    user: "10002:10002"
    group_add: ["10100"]
    mem_limit: 256m
    cpus: 0.5
    tmpfs: ["/tmp:size=32m,noexec,nosuid"]
    volumes:
      - /opt/portal/config/${PORTAL_ENV_NAME}/adapters.yml:/etc/portal/adapters.yml:ro
      - /opt/portal/config/${PORTAL_ENV_NAME}/policy.yml:/etc/portal/policy.yml:ro
      - /var/lib/portal/${PORTAL_ENV_NAME}/audit:/var/lib/portal/audit
    secrets: [audit_hmac_key]               # plus adapter_<system>_credential entries as they exist
    networks:
      apps:   { ipv4_address: "${NET_APPS_PREFIX}.3", aliases: [portal-adapters] }
      egress: { ipv4_address: "${NET_EGRESS_PREFIX}.3" }
    healthcheck: { test: ["CMD", "python", "-m", "portal_adapters.healthcheck"], interval: 10s, timeout: 3s, retries: 3, start_period: 15s }

networks:
  edge:    { driver: bridge }
  ingress: { driver: bridge, internal: true, ipam: { config: [ { subnet: "${NET_INGRESS_PREFIX}.0/29" } ] } }
  apps:    { driver: bridge, internal: true, ipam: { config: [ { subnet: "${NET_APPS_PREFIX}.0/24", ip_range: "${NET_APPS_PREFIX}.128/25" } ] } }
  core:    { driver: bridge, internal: true, ipam: { config: [ { subnet: "${NET_CORE_PREFIX}.0/29" } ] } }
  egress:  { driver: bridge, ipam: { config: [ { subnet: "${NET_EGRESS_PREFIX}.0/29" } ] } }

volumes:
  portal_certs: { external: true }

secrets:
  oidc_client_secret: { file: "/etc/portal/secrets/${PORTAL_ENV_NAME}/oidc_client_secret" }
  redis_password:     { file: "/etc/portal/secrets/${PORTAL_ENV_NAME}/redis_password" }
  jwt_current:        { file: "/etc/portal/secrets/${PORTAL_ENV_NAME}/jwt_current" }
  jwt_next:           { file: "/etc/portal/secrets/${PORTAL_ENV_NAME}/jwt_next" }
  jwt_previous:       { file: "/etc/portal/secrets/${PORTAL_ENV_NAME}/jwt_previous" }
  registrar_token:    { file: "/etc/portal/secrets/${PORTAL_ENV_NAME}/registrar_token" }
  audit_hmac_key:     { file: "/etc/portal/secrets/${PORTAL_ENV_NAME}/audit_hmac_key" }
```
Environment values (`NET_*_PREFIX`, `PORTAL_ENV_NAME`, `PORTAL_PROJECT`, ports) come from `compose/prod.env` / `compose/stage.env`; image references from `releases/<x.y.z>.env`.

**Stage overlay `compose/platform.stage.yml`** adds:
```yaml
x-hardened: &hardened      # YAML anchors do not cross files: repeated here
  restart: unless-stopped
  init: true
  read_only: true
  cap_drop: [ALL]
  security_opt: ["no-new-privileges:true"]
  logging: { driver: json-file, options: { max-size: "10m", max-file: "5" } }

services:
  keycloak:
    <<: *hardened
    image: ${KEYCLOAK_IMAGE}
    command: ["start", "--import-realm", "--http-enabled=true", "--hostname-strict=false", "--proxy-headers=xforwarded", "--http-relative-path=/idp"]
    mem_limit: 1g
    cpus: 1.0
    read_only: false                      # Keycloak writes its dev store; volume below
    volumes:
      - keycloak_data:/opt/keycloak/data
      - /opt/portal/keycloak/realm-portal-stage.json:/opt/keycloak/data/import/realm.json:ro
    networks: { idp: { ipv4_address: "${NET_IDP_PREFIX}.3" } }
  traefik:
    networks: { idp: { ipv4_address: "${NET_IDP_PREFIX}.4" } }
  gateway:
    networks: { idp: { ipv4_address: "${NET_IDP_PREFIX}.2" } }
networks:
  idp: { driver: bridge, internal: true, ipam: { config: [ { subnet: "${NET_IDP_PREFIX}.0/29" } ] } }
volumes:
  keycloak_data: {}
```
plus a stage-only router `/idp` → `http://keycloak:8080` in `traefik/platform.stage.yml`. ⚑ Keycloak flags and relative-path behaviour per the pinned version.

### 4.1 Network plan (final, R20)

| Network | Internal | Members (fixed address) | Purpose |
|---|---|---|---|
| `edge` | no | traefik | only network with published ports |
| `ingress` | yes | gateway `.2` (listener :8000), traefik `.3` | forward-auth and config polling; **apps are not here** |
| `core` | yes | redis `.2`, gateway `.3` | session store; **no one else** |
| `apps` | yes | gateway `.2` (listener :8001 only), adapters `.3` (:8002), traefik `.4`, all apps (dynamic, ≥ .128) | app traffic, JWKS/nav, adapter calls |
| `egress` | no (firewalled) | gateway `.2`, adapters `.3` | IdP and legacy-system access only |
| `idp` (stage) | yes | gateway, traefik, keycloak | Keycloak back-channel |

Reading the table as a security argument: an app can reach exactly four addresses — Traefik (cannot initiate anything), gateway :8001, adapters :8002, and other apps on `apps` (blocked by `aud` verification, confirmed at deploy by the conformance probe). It cannot reach Redis, the registry API, or the internet.

## 5. `platform.sh` — operator commands

```text
platform.sh bootstrap
platform.sh up        <prod|stage>                # compose up -d --wait, then `check`
platform.sh down      <prod|stage>                # compose down (volumes and secrets untouched); apps are NOT stopped
platform.sh restart   <prod|stage> [service]
platform.sh status    <prod|stage>                # compose ps + registry list + traefik ping
platform.sh logs      <prod|stage> <service> [-f]
platform.sh check     <prod|stage>                # self-test: §9 security/network assertions + smoke requests
platform.sh backup    <prod|stage>                # §6
platform.sh restore   <prod|stage> <backup-file>
platform.sh rotate-key <prod|stage> <stage1|promote|finish>     # 02-gateway §7
platform.sh renew-cert <prod|stage> <fullchain.pem> <privkey.pem>
platform.sh gc-images
platform.sh volume-backup  <prod|stage> <slug> [dest]
platform.sh volume-restore <prod|stage> <slug> <file>
platform.sh upgrade   <prod|stage> <release>      # §7
```
Behaviours worth fixing: `up` is idempotent and waits for health (`--wait`); `down` must not remove app containers (apps are separate Compose projects and keep running; only the portal in front of them is unavailable); after `up` the registry re-publishes routes to Traefik within one poll (≤ 5 s) because routing is derived from the database. Every command prints what it is about to do in German and requires `--yes` for destructive actions (`restore`, `volume-restore`, `gc-images`).

## 6. Backup and restore

The Angebot excludes automatic backup of app data (§5.2); the platform's own state is small and cheap to protect.

| Data | Where | Backup | Frequency | Restore |
|---|---|---|---|---|
| Registry DB | `/var/lib/portal/<env>/registry.db` | `gateway-cli registry backup` (consistent online copy) | nightly 02:30, 14 kept | stop gateway → copy file back → start → `registry verify` |
| Secrets and keys | `/etc/portal/secrets/<env>/` | encrypted archive (`age`/`gpg` to the admin key) | after every change + weekly | decrypt and copy; permissions per §2 |
| Adapter audit | `/var/lib/portal/<env>/audit/` | `rsync -a` | nightly | copy back |
| App volumes | Docker volumes `<project>_data_<slug>` | `platform.sh volume-backup` (tar through a throw-away container), **on demand** | not automatic (§5.2) | `volume-restore` with the app stopped |
| Platform config | `/opt/portal` | it is a Git checkout | — | `git clone` |
| Redis | none | — | — | none (ephemeral, R7) |
| Image registry | `/var/lib/portal/registry-images` | not backed up | — | images are reproducible from Git; digests in the registry DB tell what to rebuild |
| TLS certificate | volume `portal_certs` | the source files held by HKA-IT | on change | `renew-cert` |

**Honest limit:** backups on the same VM do not protect against loss of the VM. The real disaster-recovery mechanism is the **Proxmox VM backup/snapshot schedule** run by HKA-IT — to be requested together with the VM (open point, §11). Backup copies should additionally go to a network share if HKA offers one.

## 7. Upgrade and rollback of the platform itself

A platform release is a file `releases/<x.y.z>.env` with the image digests of Traefik, gateway, Redis, adapters (+ Keycloak on stage), built and tested by the team.

1. `platform.sh backup prod` (and stage).
2. `platform.sh upgrade stage <release>` → `up`, then the **Durchstich E2E** (`../09-component-design.md` §11) and `platform.sh check stage` must be green.
3. Announce a short window (the user-visible effect is a few seconds of 5xx while the gateway restarts; Traefik keeps its routes meanwhile ⚑ HTTP-provider last-good behaviour).
4. `platform.sh upgrade prod <release>`: Redis and adapters first, gateway, Traefik last; each step waits for health.
5. Smoke test: log in, open both reference apps, `platform.sh check prod`.
6. **Rollback:** `platform.sh upgrade prod <previous-release>`; if the registry schema was migrated, restore the pre-upgrade `registry.db` backup (the service refuses to start on a newer schema, `03` §2.1, so a wrong combination fails loudly rather than corrupting data).

SDK/kit/starter releases are separate from platform releases (`06`, `04`, `07`); the only coupling is the assertion version `v` and the kit's major version.

## 8. Operational runbooks (short forms; each becomes a Betriebsanleitung chapter)

| Situation | Steps |
|---|---|
| **Renew the TLS certificate** | `platform.sh renew-cert prod fullchain.pem privkey.pem` (copies into `portal_certs` via a throw-away container; Traefik's file provider reloads); verify with `openssl s_client` expiry date |
| **Rotate the signing key** | `rotate-key prod stage1` → wait ≥ 10 min → `promote` → wait 24 h → `finish` (`02-gateway.md` §7); users stay logged in |
| **Lock out a user / revoke sessions** | `docker compose exec gateway gateway-cli revoke-sessions --sub <sub>` |
| **An app misbehaves** | `deploy.sh rollback --env prod --slug <slug> --by <name>`; if that is not enough `deploy.sh retire …` (route disappears within 5 s) |
| **Disk filling** | `df -h`; `docker system df`; `platform.sh gc-images`; check `/var/lib/docker/containers/*/*-json.log` sizes (rotation limits them) |
| **Gateway will not start** | `platform.sh logs prod gateway`; common causes: missing secret file, listen address not on an interface (network changed), registry DB newer than code |
| **IdP certificate/metadata changed** | gateway re-reads IdP discovery on restart; restart gateway |
| **VM reboot** | nothing to do; `portal@prod.service` and Compose restart policies bring everything up (verify with `status`) |
| **Add a legacy-system credential** | place file in `/etc/portal/secrets/<env>/adapter_<system>_credential` (root:10100 0440), add to the `secrets:` list of the adapters service, switch the backend mode in `adapters.yml`, `restart adapters` |

## 9. `platform.sh check` — the security regression suite

Run after every `up`, upgrade and by HKA-IT during handover. Each assertion prints `OK`/`FEHLER` with a German explanation.

| # | Assertion | How |
|---|---|---|
| K1 | Only 80/443 (stage 8080/8443) listen on the host | `ss -ltn` |
| K2 | No container mounts `docker.sock` | `docker inspect` over the project's containers |
| K3 | Every platform container: non-root user, `ReadonlyRootfs`, `CapDrop=ALL`, `no-new-privileges` | `docker inspect` |
| K4 | From a throw-away container on `apps`: Redis host name does not resolve; `172.29.12.2:6379` unreachable | `nc`/`getent` |
| K5 | From `apps`: gateway `:8000` refused, `:8001` open, adapters `:8002` open | `nc` |
| K6 | From `apps`: no route to the internet (`curl --max-time 3 https://example.org` fails) | `curl` |
| K7 | From `ingress`: Traefik reaches gateway :8000; nothing else listens | `nc` |
| K8 | `GET https://<host>/auth/verify`, `/registry/apps`, `/internal/traefik-config` return 404 from outside | `curl -k` |
| K9 | Secrets files: owner/group/mode as §2; no secret file world-readable | `stat` |
| K10 | `jwks.json` lists the expected `kid`s; signing key matches `jwt_current` | `curl` + `openssl` |
| K11 | NTP offset < 100 ms | `chronyc tracking` |
| K12 | Disk usage < 80 %, memory available > 1 GB | `df`, `free` |
| K13 | Egress rules present (`PORTAL-EGRESS` chain) | `iptables -S` |
| K14 | Smoke: unauthenticated `GET /apps/<slug>/` for every registered app → 302 to login | `curl` |
| K15 | Smoke: registry lists no app in `failed` state | `gateway-cli registry list` |

## 10. Platform tests (CI for the platform repository, run against stage)

| # | Case |
|---|---|
| OP1 | `platform.sh up stage` from a clean VM (after `bootstrap`) converges and `check stage` is green |
| OP2 | `down` then `up`: apps keep running during `down`; menu and routes return within 10 s of `up` |
| OP3 | `restart gateway`: in-flight page loads recover; sessions survive (Redis untouched) |
| OP4 | `restart redis`: users must log in again; no app can be reached without a session in between |
| OP5 | Kill `traefik`: Compose restarts it; portal reachable again < 30 s |
| OP6 | Backup then restore the registry on a scratch copy: identical Traefik payload |
| OP7 | Key rotation: assertions signed with the old key verify throughout stages 1–4 (fixtures F16) |
| OP8 | Upgrade stage from release N to N+1 and back |
| OP9 | **Cold boot test:** reboot the VM; without any login, `status` shows all healthy within 5 minutes |
| OP10 | Firewall: from the gateway container, `IDP_ADDR:443` reachable, an arbitrary public address not; from adapters only the configured legacy hosts |
| OP11 | `renew-cert` replaces the served certificate without dropping connections ⚑ |
| OP12 | Disk-full simulation on `/var/log`: platform keeps serving (logs are rotated and bounded) |
| OP13 | Durchstich E2E (`../09-component-design.md` §11) passes on stage after each release |

## 11. Übergabetest für die HKA-IT (Checkliste, Deutsch)

Grundlage: Angebot §8.1/§9 — *„Eine Person der HKA-IT für den Übergabetest (Plattform anhand der Betriebsanleitung starten und neu starten)"*, Termin 28.01.2027. Die Person arbeitet **nur mit der Betriebsanleitung**; das Projektteam schaut zu und greift nicht ein. Ziel: Die Person kann die Plattform ohne Hilfe stoppen, starten, neu starten und eine App zurücksetzen.

| Nr. | Aufgabe | Erwartetes Ergebnis | Ergebnis |
|---|---|---|---|
| 1 | Per SSH anmelden, in `/opt/portal` wechseln, `./scripts/platform.sh status prod` ausführen | Alle Dienste „healthy"; Liste der Apps mit Status „in Betrieb" | ☐ ok |
| 2 | Portal im Browser öffnen und mit dem Testkonto anmelden | Startseite mit Menü; beide Referenz-Apps sichtbar | ☐ ok |
| 3 | `./scripts/platform.sh down prod` ausführen | Dienste gestoppt; Portal-Adresse nicht erreichbar | ☐ ok |
| 4 | `./scripts/platform.sh up prod` ausführen | Nach höchstens 2 Minuten alles „healthy"; Anmeldung funktioniert wieder | ☐ ok |
| 5 | Nur das Gateway neu starten: `./scripts/platform.sh restart prod gateway` | Portal ist nach wenigen Sekunden wieder da; Sie bleiben angemeldet | ☐ ok |
| 6 | Redis neu starten: `./scripts/platform.sh restart prod redis` | Portal erreichbar; Sie müssen sich neu anmelden (das ist richtig) | ☐ ok |
| 7 | Logs ansehen: `./scripts/platform.sh logs prod gateway` | Es erscheinen Meldungen im JSON-Format; keine Passwörter oder Anmeldedaten | ☐ ok |
| 8 | Eine App zurücksetzen: `./scripts/deploy.sh rollback --env prod --slug noten --by <Ihr Name>` | App läuft in der vorherigen Version; Menüpunkt bleibt | ☐ ok |
| 9 | Eine Demo-App beenden: `./scripts/deploy.sh retire --env prod --slug demo --by <Ihr Name>` | Menüpunkt verschwindet innerhalb weniger Sekunden | ☐ ok |
| 10 | Sicherung der Registry erstellen: `./scripts/platform.sh backup prod` | Datei in `/var/backups/portal/prod/` | ☐ ok |
| 11 | Selbsttest: `./scripts/platform.sh check prod` | Alle Zeilen „OK" | ☐ ok |
| 12 | Die VM neu starten (`sudo reboot`) und danach `status` ausführen | Nach höchstens 5 Minuten alles „healthy", ohne dass jemand etwas starten musste | ☐ ok |
| 13 | Zertifikat tauschen (Probelauf auf stage): `./scripts/platform.sh renew-cert stage …` | Browser zeigt das neue Zertifikat | ☐ ok |

Abnahme: alle Punkte „ok" → das Ergebnis wird mit Datum und Name der IT-Person im Abnahmeprotokoll festgehalten (Angebot §9.3, Phase 4).

## 12. Failure matrix with detection commands (extends `../09-component-design.md` §12)

| Component down | User impact | Detection | Recovery |
|---|---|---|---|
| Traefik | portal and all apps unreachable | `docker compose ps`; browser error; `curl -k https://host/` | automatic restart; `platform.sh restart prod traefik` |
| Gateway | portal pages and all `/apps/*` give errors (fail closed); Traefik keeps routes | `platform.sh status`; `logs gateway`; `/readyz` via `docker compose exec` | restart; check secrets/config in logs |
| Redis | all users must log in again; 503 until up | `status`; gateway `redis_unavailable` events | `restart redis` |
| Registry DB corrupt | menu empty/stale; routes remain from last poll until gateway restarts | `gateway-cli registry verify` | `restore` latest backup |
| One app | its menu entry disappears; URL → 503 page | `status` (registry list: unhealthy); app logs | `deploy.sh rollback` or `restart` via compose project `app-<env>-<slug>` |
| Adapters | apps that need legacy data show a German error | `logs adapters`; audit gaps | `restart adapters` |
| IdP | no new logins; sessions continue | login errors in gateway log | contact IdP owner |
| Disk full | gradual failure | K12; `df -h` | gc, log rotation, extend disk |
| Clock drift | assertions rejected (`Expired`), login `exp` errors | K11 | fix chrony |
| Egress rule missing after boot | gateway cannot reach IdP / adapters cannot reach legacy | K13; login failures | `systemctl restart portal-firewall` |

## 13. Resource budget (basis for the VM size request)

| Consumer | RAM | CPU |
|---|---|---|
| OS + Docker + runners idle | 1.0 GB | — |
| prod platform (traefik 256 + gateway 512 + redis 192 + adapters 256 MB limits) | ≤ 1.2 GB | ≤ 2.5 |
| prod apps (10 × 512 MB limit; typical use ≪ limit) | ≤ 5.0 GB | ≤ 5 (limits; shared) |
| stage platform incl. Keycloak (1 GB) | ≤ 2.2 GB | ≤ 3.5 |
| stage apps (4 × 512 MB) | ≤ 2.0 GB | ≤ 2 |
| image registry | 0.15 GB | — |
| build jobs (2 concurrent, rootless, peak) | ≈ 3.0 GB | 2–4 |
| **Sum of limits** | **≈ 14.5 GB** | |

Limits are caps, not typical use; with realistic usage 12 GB is workable, **16 GB RAM, 6 vCPU, ≥ 100 GB disk** is the comfortable request. If builds move to HKA shared runners, subtract ≈ 3 GB. Disk: images (≈ 200 MB × 10 apps × 5 versions ≈ 10 GB), registry, volumes, logs.

## 14. Open points

- VM size and Proxmox backup schedule (§6, §13) — request from HKA-IT with the VM (before 05.11).
- Network ranges and egress allow-list addresses (§1, §3.2) — HKA network team and the owners of the IdP, Exchange and Noten systems.
- Real client IP / front proxy (R21); certificate source and renewal owner.
- Keycloak production-mode settings are irrelevant (stage only); if HKA wants Keycloak as a long-term test IdP it needs its own review.
- Whether the Übergabetest person has `portal-admins` membership (needed for the commands above) — yes by design; confirm the account exists before 28.01.2027.
