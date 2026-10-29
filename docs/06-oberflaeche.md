# 06 – Oberfläche: Templates, Texte und Design-Kit

Die Oberfläche ist serverseitig gerendertes HTML (Jinja2) ohne JavaScript-Framework. Das Aussehen kommt aus dem Design-Kit in
`kit/`; die Regeln und das exakte Markup der Muster stehen im Skill `hka-design` und in
`claude-proposal/04-portal-ui-and-design-kit.md`.

## Templates (`src/portal/templates/`)

| Ordner | Inhalt |
|---|---|
| `base.html` | Rahmen: „Zum Inhalt springen", Entwicklungsbanner (nur `env: dev`), Kopf, Menü (nur angemeldet), Hauptbereich, Fußzeile |
| `partials/` | `header.html`, `footer.html`, `nav.html` (Menübaum; auch Body von `GET /nav`) |
| `pages/` | `home`, `status`, `connections`, `logout`, `error`, `dev_login`, `dev_app` |
| `macros/` | Wiederverwendbare Muster: `fields.html`, `dialog.html`, `table.html` |

Seiten erben von `base.html` und füllen `{% block content %}`. Gerendert wird immer über `Views.page(...)` (`web/views.py`); das
Template bekommt `user` (die Session oder `None`), `request_id`, `nav_html` und die übergebenen Werte. Global verfügbar sind `t`
(Texte), `kit` und `cfg`.

### Makros

```jinja
{% from "macros/fields.html" import field, error_summary %}
{{ field("subject", t("dev.app.subject"), hint="…", error=None, required=True) }}
{{ error_summary(t("dev.app.error_summary"), [("subject", t("dev.app.subject_error"))]) }}

{% from "macros/dialog.html" import dialog %}
{{ dialog("confirm-send", "Titel", "Text", "Senden", submit_form="send-form") }}

{% from "macros/table.html" import table %}
{{ table("Beschriftung", ["Modul", "Note"], [["Mathe", "1,7"]], num_cols=(1,)) }}
```

- `field(id, label, name, type, value, hint, error, required, textarea)`: Label, Hinweis, Eingabe und Fehlertext; `aria-describedby`
  und `aria-invalid` werden gesetzt.
- `error_summary(title, errors)`: Fehlerübersicht über dem Formular, `errors = [(feld_id, meldung)]`.
- `dialog(id, title, body, confirm_label, submit_form)`: Dialog mit genau zwei Buttons; ein Button mit
  `data-dialog-open="<id>"` öffnet ihn, die Bestätigung sendet das Formular mit der ID `submit_form`.
- `table(caption, columns, rows, num_cols, id)`: Tabelle mit Beschriftung; die erste Zelle jeder Zeile ist Zeilenkopf,
  `num_cols` richtet Spalten rechts aus.

## Texte (`src/portal/locales/messages.de.yml`)

Alle sichtbaren Texte stehen in dieser Datei (Anrede „Sie", kurze Sätze, einfache Sprache), nicht in Templates oder Code.
Aufruf im Template `{{ t('home.title') }}`, im Code `portal.t("home.title")`. Platzhalter in `{geschweiften Klammern}`;
`{kontakt}` kommt aus der Konfiguration. Ein unbekannter Schlüssel löst einen Fehler (`KeyError`) aus, ein fehlender Platzhalter
bleibt als `{name}` stehen. Neue Seite: Schlüssel anlegen, dann im Template verwenden.

## Fehlerseiten

Jeder Fehler erscheint als Portal-Seite (`pages/error.html`). Texte `error.<status>.title` und `.body`; Fallback `error.4xx` und
`error.5xx`. Siehe [03 Service und Router](03-service-und-router.md#fehlerbehandlung).

## Design-Kit (`kit/`)

```text
kit/css/    tokens · fonts · base · layout · components · print
kit/js/     kit.js (nur das Dialog-Muster, höchstens 1 KB minifiziert)
kit/icons/  icons.svg (Sprite; die Icon-IDs sind die Allow-List im Manifest-Schema)
kit/fonts/  IBM Plex Sans / Condensed / Mono (OFL, selbst gehostet)
kit/pairs.json, kit/tools/{build,contrast}.py
kit/dist/   GENERIERT (make kit): kit-<hash>.css, kit-<hash>.js, icons-<hash>.svg, fonts/, kit-manifest.json
```

- **Tokens** (`css/tokens.css`): Farben, Schriften, Abstände. Farbwerte stehen nur dort; ein Test erzwingt das. Zum Tauschen des
  Designs (z. B. mit dem offiziellen Designhandbuch) die Werte ändern, die Namen behalten, dann `make kit contrast`.
- **Kontrast-Gate** (`make contrast`, Teil von `make test`): `pairs.json` listet Farbpaare mit Art (`text` 4,5, `large-text` 3,0,
  `ui` 3,0, `decorative` nur Bericht). Jedes Farb-Token muss in mindestens einem Paar vorkommen; ein zu niedriger Kontrast bricht ab.
- **Build** (`make kit`): fügt die CSS-Dateien in fester Reihenfolge zusammen, minifiziert, hängt einen Hash an die Dateinamen und
  schreibt `kit-manifest.json`. Die Hash-Namen erlauben `immutable`-Caching; `Kit.id` (`kit-<hash>`) ist der Wert des Headers
  `X-Portal-Kit`. Das Portal startet nicht, wenn `kit/dist/` fehlt.
- **Auslieferung:** unter `/_portal/static/`, mit `Cache-Control: public, max-age=31536000, immutable`.

### Neues Icon

1. `<symbol id="i-<name>">` in `kit/icons/icons.svg` ergänzen.
2. Den Namen in `schemas/manifest.schema.json` im Enum `menu.icon` ergänzen.
3. `make kit`. Verwendet wird es im Manifest als `"icon": "<name>"`.

### Zugänglichkeit

Skip-Link als erstes Element, `<main tabindex="-1">`, eine Navigations-Landmark (der Menübaum wird zweimal gerendert, CSS blendet
eine Kopie aus), sichtbarer Fokus, Fehlerhinweise per `role="alert"`, Dialoge mit `<dialog>`. Die Details stehen im Skill `hka-design`.
