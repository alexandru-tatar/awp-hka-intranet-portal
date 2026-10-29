# 04 – Anmeldung

Zwei Betriebsarten, gewählt mit `auth_mode`:

| `auth_mode` | Anmeldung | Sessions |
|---|---|---|
| `dev` (nur mit `env: dev`) | Auswahl der Testpersonen aus `dev/users.yml` | Speicher, ohne `redis_url` |
| `oidc` | Keycloak (dev) bzw. Shibboleth-OIDC (prod), Authorization Code mit PKCE | Redis |

Wenn `redis_url` gesetzt ist, liegen auch im Dev-Modus die Sessions in Redis.

## Ablauf (`auth_mode: oidc`)

```text
GET /login?next=…            Transaktion oidc:{lid} in Redis (State, Nonce, PKCE-Verifier, next), Cookie login_cookie,
                             Redirect zum IdP
… Anmeldung beim IdP …
GET /oidc/callback?code&state   Cookie und State prüfen, Transaktion verbrauchen (GETDEL, also genau einmal),
                             Code gegen ID-Token tauschen, Token prüfen, Rollen mappen,
                             bisherige Session löschen, neue Session anlegen, Redirect auf next
```

- `next` ist nur `/` oder ein Pfad unter `/apps/`; alles andere wird zu `/` (`auth/redirects.py`).
- Jeder Fehler im Callback ergibt eine Fehlerseite (400) ohne Details; der Grund steht im Log
  (`login_failure reason=…`).
- Zugriffs- und Refresh-Token werden nicht gespeichert.

## Abmelden

`GET /logout` zeigt eine Bestätigung, `POST /logout` (mit CSRF-Token) beendet die Portal-Session. Bei `auth_mode: oidc` leitet
das Portal danach zum `end_session_endpoint` des IdP weiter (OIDC RP-initiated Logout) mit `client_id`,
`post_logout_redirect_uri` und `id_token_hint`; der IdP beendet seine Session und leitet zurück. Ohne diesen Schritt bliebe die
IdP-Session bestehen, und der nächste Login ginge ohne Passwort durch.

- Voraussetzung: `oidc.post_logout_redirect_uri` ist gesetzt und im IdP-Client erlaubt (Keycloak: `post.logout.redirect.uris`),
  und die Discovery des IdP enthält `end_session_endpoint`. Fehlt eines davon, wird nur die Portal-Session beendet.
- Das ID-Token wird deshalb in der Session gespeichert (`sess:{sid}`, Feld `id_token`) und nur hierfür benutzt; es erscheint
  nicht im Cookie und nicht in Templates. Zugriffs- und Refresh-Token werden weiterhin nicht gespeichert.
- Der IdP lehnt einen `id_token_hint` mit ungültiger Signatur ab („Ungültiger Parameter: id_token_hint"). Das passiert, wenn der IdP
  seit der Anmeldung neu gestartet wurde (Keycloak im Dev-Modus erzeugt dann neue Schlüssel) oder seine Schlüssel gewechselt hat.
  Das Portal prüft den Hint deshalb vor dem Redirect gegen eine frisch geladene JWKS und lässt ihn sonst weg; der IdP fragt dann
  selbst nach, ob abgemeldet werden soll. Ein abgelaufenes Token mit gültiger Signatur bleibt als Hint erlaubt.
- Ob das Shibboleth-OP RP-initiated Logout anbietet, ist offen (02-open-questions §1).

## ID-Token-Prüfung (`auth/oidc.py`)

Signatur gegen JWKS (10 Minuten Cache, bei unbekannter `kid` einmal neu laden); Algorithmus nur aus `id_token_algs`
(kein `none`, kein HMAC); `iss` genau gleich dem konfigurierten `issuer`; `aud` enthält `client_id` (bei mehreren
Audiences `azp`); `exp`/`iat` mit `clock_leeway_seconds`; `nonce` gleich dem gespeicherten; `sub` nicht leer.
Token-Endpoint: `client_secret_basic`, Timeout 5 s, ein Retry bei 5xx.

## Sessions in Redis (`auth/redis_sessions.py`)

| Schlüssel | Typ | Inhalt |
|---|---|---|
| `sess:{sid}` | Hash | `sub`, `name`, `roles` (JSON), `csrf`, `created`, `last_seen`, `id_token` (nur für die Abmeldung beim IdP); läuft nach `idle_seconds` ab |
| `usr:{sha256(sub)}:sessions` | Set | alle Session-IDs eines Benutzers (für Sperrung) |
| `oidc:{lid}` | String (JSON) | Login-Transaktion, läuft nach `login_state_ttl_seconds` ab |

Die absolute Lebensdauer (`absolute_seconds`) wird beim Lesen geprüft; `last_seen` und das Idle-Ablaufdatum werden
höchstens alle `touch_min_interval_seconds` aktualisiert. Logout löscht Session und Eintrag im Set.

## Rollen

`dev/roles.yml` ordnet Claim-Werte des ID-Tokens Rollen zu, `dev/grants.yml` ergänzt Rollen je `sub`:

```yaml
sources:
  - claim: eduPersonAffiliation
    map: { student: student, employee: employee, faculty: professor, staff: employee }
  - claim: eduPersonEntitlement
    map: { "urn:hka:portal:admin": platform-admin }
default_roles: []
```

Nicht zugeordnete Werte ergeben keine Rolle (leeres Menü). Rollen werden bei der Anmeldung berechnet und in der
Session gespeichert; Änderungen gelten ab der nächsten Anmeldung. Manifeste dürfen nur Rollen aus `role_vocabulary`
(Konfiguration) verwenden. Die Claim-Namen sind Platzhalter, bis das Shibboleth-Attributschema feststeht (02 §8).

## Konfiguration (`dev/gateway.oidc.yml`)

```yaml
auth_mode: oidc
session_cookie: portal_sid
login_cookie: portal_login
cookie_secure: false
redis_url: redis://localhost:6379/0
idle_seconds: 1800
absolute_seconds: 28800
touch_min_interval_seconds: 60
login_state_ttl_seconds: 600
oidc:
  issuer: http://localhost:8180/realms/hka
  discovery_url: …            # optional; sonst <issuer>/.well-known/openid-configuration
  client_id: portal
  client_secret_file: keycloak/portal-client-secret
  redirect_uri: http://localhost:8000/oidc/callback
  post_logout_redirect_uri: http://localhost:8000/
  scopes: [openid, profile, email]
  id_token_algs: [RS256, ES256]
roles_file: roles.yml
grants_file: grants.yml
```

`discovery_url` ist nötig, wenn das Portal den IdP unter einer anderen Adresse erreicht als der Browser (Container,
siehe [05](05-compose.md)).

## Dev-IdP Keycloak

Realm `hka` (`extras/compose/keycloak/hka-realm.json`), Client `portal` (Secret `dev-portal-secret`, PKCE S256).
Keycloak-Konsole: http://localhost:8180, `admin` / `admin`. Benutzer, Passwort = Benutzername:

| Benutzer | Claims | Rollen im Portal |
|---|---|---|
| alexandru (Alexandru Tatar) | `eduPersonAffiliation: student` | student |
| antonio (Antonio Codrean) | `student` | student |
| david (David Coric) | `student` | student |
| neumann (Prof. Dr.-Ing. Rainer Neumann) | `faculty` | professor |
| max (Max Beispiel) | `employee` | employee |
| admin | `employee`, Entitlement `urn:hka:portal:admin` | employee, platform-admin |
| gast | – | keine |

Neuer Testbenutzer oder neue Attribute: Realm-Datei ändern, dann `make idp-down idp-up` (baut das Image neu).

### Login-Seite (Theme `hka`)

Die Anmeldeseite von Keycloak sieht aus wie das Portal: gleicher Kopf, gleiche Fußzeile, Felder, Fehlerhinweise und Buttons
aus dem Design-Kit. Der Ablauf ist unverändert (Weiterleitung zu Keycloak, Code, Callback); das Portal sieht kein Passwort.
In prod stellt Shibboleth seine eigene Seite dar, das Portal ändert sich dadurch nicht.

| Datei (`extras/compose/keycloak/theme/hka/login/`) | Inhalt |
|---|---|
| `theme.properties` | Elternthema `base`; bildet die Klassen der Basis-Templates auf Kit-Klassen ab |
| `template.ftl` | Seitenrahmen wie `base.html` des Portals (Kopf, Hauptbereich, Fußzeile), Meldungen als `.notice` |
| `login.ftl` | Formular mit `.field`, Fehlerübersicht (`.error-summary`), Button `.btn--primary` |
| `messages/messages_de.properties` | Texte; Sprache des Realms ist Deutsch (`defaultLocale: de`) |

`kit.css` und die Schriften entstehen beim Bauen des Keycloak-Images aus `kit/` und werden als Theme-Ressourcen abgelegt; sie
werden nicht eingecheckt. Andere Seiten (Passwort ändern, OTP, Fehler) nutzen die Basis-Templates mit den Kit-Klassen.
Aktiv ist das Theme über `loginTheme` im Realm. Änderungen an Theme oder Kit brauchen `make idp-up` bzw. `make server-up` (Neubau).

## Umstieg auf prod

- `env: prod`, `auth_mode: oidc`, `issuer`/`client_id` des Shibboleth-OP, `client_secret_file` aus einem Secret.
- Cookies mit `__Host-`-Präfix (`__Host-portal_sid`, `__Host-portal_login`) und `cookie_secure: true`; das setzt HTTPS voraus.
- `roles.yml` und `grants.yml` an die tatsächlich ausgelieferten Attribute anpassen.
- Redis-Passwort und Netz-Trennung (02 §1) – im Code noch nicht vorgesehen.
- Nicht vorhanden: Rate-Limit auf `/login`, `revoke-sessions`.

## Tests

`tests/test_oidc.py`: gefälschter IdP (`httpx.MockTransport`, eigener RSA-Schlüssel) und `fakeredis`. Abgedeckt sind
der Gesamtablauf, Spec-Tests G2 (Callback ohne Cookie), G4 (Replay), G6 (Session-ID wechselt), falscher State,
IdP-Fehler, falsche `nonce`/`aud`/`iss`, abgelaufenes Token, `alg none`, HMAC, Fehler am Token-Endpoint,
Rollen-Mapping, Logout (inklusive Weiterleitung zum IdP), `/readyz` und Redis-Ausfall sowie das Ablaufverhalten des Stores.
