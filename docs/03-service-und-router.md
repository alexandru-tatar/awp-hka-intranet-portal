# 03 – Service und Router

## Zusammenspiel

```text
Handler (router/)  →  Service (service/)  →  Repository (Registry, SessionStore)
   │                       │
   └ rendert über web/views └ gibt DTOs zurück, wirft fachliche Exceptions
```

`context.py` erzeugt die Services einmal pro App und hängt sie an `Portal`. Handler bekommen sie über `Depends`
(`AppServiceDep`, `SessionWriteServiceDep`, `LoginServiceDep` in `web/deps.py`) und den Kontext über `PortalDep`.

## Router

```python
router: Final = APIRouter(tags=["Seiten"])

@router.get("/", response_class=HTMLResponse)
def home(request: Request, portal: PortalDep, service: AppServiceDep, session: CurrentSession) -> Response:
    """Startseite … (:param / :return / :rtype / :raises)"""
    logger.debug("sub={}", session.sub)
    groups: Final = service.find_nav_groups(session.roles)
    return portal.views.page(request, "pages/home.html", title=portal.t("home.title"), session=session, groups=groups)
```

- Eine Datei pro Thema (`<thema>_router.py`), ein `router` pro Datei, Export in `router/__init__.py`, Einhängen in `app.py`.
- Handler sind Funktionen mit Rückgabetyp `Response`; keine Fachlogik, kein Zugriff auf Registry oder Store.
- Private Hilfsfunktionen stehen mit `_` am Dateiende. HTTP-Konstanten (Header-Namen, Cache-Werte) in `router/constants.py`.
- Wer angemeldet sein muss, nimmt `CurrentSession`; optional `OptionalSession`; nur `platform-admin`: `AdminSession`.

## Service

Pro Entity ein Lese-Service (`<Entity>Service`) und ein Schreib-Service (`<Entity>WriteService`); das Repository kommt
per Konstruktor als `self.repo`.

| Service | Repository | Methoden |
|---|---|---|
| `AppService` | `Registry` | `find_nav_groups(roles)`, `find_all()`, `find_authorized(slug, session)` |
| `SessionService` | `SessionStore` | `find_by_id(sid)` |
| `SessionWriteService` | `SessionStore`, Testpersonen | `create(user_id)`, `create_for_subject(sub, name, roles)`, `delete(sid, csrf)`, `discard(sid)` |
| `LoginService` | `OidcClient`, `RedisLoginStore`, `RoleMapper`, `SessionWriteService` | `start(next)`, `finish(...)` |

- **Rückgabe nur als DTO** (`AppDTO`, `NavGroupDTO`, `SessionDTO`): `@dataclass(eq=False, slots=True, kw_only=True)` mit
  eigenem `__init__(self, <entity>)`, nur primitive Felder. Entities aus `registry/` und `auth/` verlassen `service/` nicht.
- **Nicht gefunden** → `NotFoundError` im Service, nie `None` zurückgeben.
- **Keine HTTP-Klassen** (`HTTPException`) in `service/`.
- Neue Klassen und Funktionen in `service/__init__.py` exportieren.

## Zugriffsentscheidung für Apps

`AppService.find_authorized(slug, session)` entscheidet in dieser Reihenfolge (wie `/auth/verify`, 02 §6):

1. App unbekannt oder Status `registering`, `failed`, `retired` → `NotFoundError` (404)
2. keine Session → `LoginRequiredError` (Redirect auf `/login?next=…`)
3. keine passende Rolle → `ForbiddenError` (403)
4. Status nicht `healthy` → `UnavailableError` (503)

Rolle wird vor Status geprüft, damit Fremde nichts über den Status erfahren.

## Fehlerbehandlung

`web/errors.py` übersetzt Exceptions in Portal-Fehlerseiten mit Fehlernummer (`request_id`):

| Exception | HTTP |
|---|---|
| `NotFoundError` | 404 |
| `ForbiddenError` | 403 |
| `UnavailableError` | 503 |
| `InvalidCsrfError`, `UnknownUserError`, `LoginFailedError` | 400 |
| `LoginRequiredError` | 302 auf `/login` |
| `RedisError` | 503 (Zugriff wird verweigert, wenn Redis nicht antwortet) |
| `HTTPException` (Routing, Dependencies) | der jeweilige Status; Header wie `Allow` bei 405 bleiben erhalten |
| `RequestValidationError` | 422 |
| alles andere | 500 |

**Alle Fehler erscheinen als HTML-Seite des Portals, nie als JSON.** Eigene Texte gibt es für 400, 401, 403, 404, 405, 408,
409, 410, 413, 414, 415, 422, 429, 501, 502, 503 und 504 (`error.<status>.title` und `.body` in `messages.de.yml`); jeder andere
Status nutzt `error.4xx` bzw. `error.5xx`. Jede Seite zeigt Titel, Text, Link zur Startseite und die Fehlernummer (`request_id`),
bei 401 zusätzlich einen Link zur Anmeldung. `/_portal/error/{code}` liefert dieselben Seiten für die `errors`-Middleware von
Traefik. Ausnahmen, die absichtlich maschinenlesbar bleiben: `/nav` (401 als `application/problem+json`, 02/04 §8), `/readyz`
(JSON) und Static-Dateien (nur Status, kein Body).

Neuen Status mit eigenem Text ergänzen: Schlüssel in `messages.de.yml` und Status in `_ERRORS_WITH_TEXT` (`web/views.py`).

Neue fachliche Exception: Klasse in `service/exceptions.py` und Eintrag in `SERVICE_ERROR_STATUS`.

## Feature hinzufügen (Beispiel: neue Seite mit Daten)

1. Methode im passenden Service, die ein DTO liefert (Test in `tests/test_service.py`).
2. Handler in `router/<thema>_router.py`, Template unter `templates/pages/`, Texte in `messages.de.yml`.
3. Router in `router/__init__.py` exportieren und in `app.py` einhängen.
4. Test über `TestClient` (`client`-Fixture, `login(client, "alexandru")` aus `conftest.py`).
