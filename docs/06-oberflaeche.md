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

## Texte (`src/portal/locales/messages.de.yml`, `messages.en.yml`)

Alle sichtbaren Texte stehen in diesen Dateien, nicht in Templates oder Code. Deutsch ist die Standardsprache (Anrede „Sie", kurze
Sätze, einfache Sprache), Englisch die zweite Sprache (Anrede „you", ebenfalls kurze Sätze). Beide Dateien haben dieselben Schlüssel
und dieselben Platzhalter; `tests/test_i18n.py` schlägt fehl, wenn ein Schlüssel oder Platzhalter in einer Sprache fehlt.
Aufruf im Template `{{ t('home.title') }}`, im Code `portal.t("home.title")`. Platzhalter in `{geschweiften Klammern}`;
`{kontakt}` kommt aus der Konfiguration (`kontakt` für Deutsch, `kontakt_en` für Englisch; ist `kontakt_en` leer, gilt `kontakt` in beiden Sprachen). Ein unbekannter Schlüssel löst einen Fehler (`KeyError`) aus, ein fehlender Platzhalter
bleibt als `{name}` stehen. Neue Seite: Schlüssel in **beiden** Dateien anlegen, dann im Template verwenden.

**Welche Sprache gilt (HKA-101):** `portal.core.i18n.pick_language` entscheidet je Anfrage, die Middleware setzt das Ergebnis
(`request.state.language`, `current_language`). `t(...)` und `<html lang="{{ t.lang }}">` folgen ihr.
1. Das Cookie `hka_lang` (`de` oder `en`) gewinnt.
2. Sonst die erste unterstützte Sprache aus `Accept-Language` nach Gewicht (`en-GB` zählt als `en`).
3. Sonst Deutsch.

Jede Seite trägt `Content-Language` und `Vary: Accept-Language, Cookie`. `/nav` liefert das Menü in der Sprache der Anfrage
(eigener ETag). Der Umschalter im Kopf (`DE`/`EN`, nur die andere Sprache) ruft `GET /sprache/<code>?next=<Pfad>`; das setzt das
Cookie (ein Jahr, `HttpOnly`, `SameSite=Lax`) und leitet mit 303 zurück. Ein unbekannter Code ergibt 404, ein fremdes `next` die
Startseite (`auth/redirects.py`, `sanitize_local_path`). Im Dev-Modus macht das Portal das selbst. Hinter dem Security-Gateway
entfernt dieses Cookies auf dem Weg zum Portal; dort speichert das Gateway die Wahl und gibt sie als `Accept-Language` weiter.
Der Umschalter erscheint dann mit `language_switch: true` in der Konfiguration.

Die Regel R-UI-7 (`docs/qualitaet/regeln.md` im docs-Repository) verlangt für Apps beide Sprachen; sie lesen die Sprache mit
`portal.language(request)` aus dem SDK (`sdk/README.md`, Abschnitt „Sprache“).

Neue Sprache: Datei `messages.<code>.yml`, Eintrag in `LANGUAGES` (`core/i18n.py`), Name der Sprache als `lang.name.<code>` in allen
Dateien. Fehlt ein Text in der gewählten Sprache, zeigt das Portal den deutschen (der Test verhindert das).

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

## Dokumentation (`/_portal/docs`)

Die AWP-Dokumentation ist eine eigenständige Seite mit eigenem Stil (nicht das Kit), die das Portal aus Bausteinen zusammensetzt
(`web/docs_page.py`):

| Datei in `src/portal/docs/` | Inhalt |
|---|---|
| `shell.html` | Hülle: Stil, Kopf, Navigation, Suche, Skript; Platzhalter `<!--DOCS:PAGES-->` und `<!--DOCS:BOOT-->` |
| `seed.html` | Ausgangsstand der Seiten, je Seite ein `<article class="page" data-page=… data-title=… data-group=…>` |
| `editor.js`, `editor.css` | Zeile „Zuletzt aktualisiert“, Versionsverlauf, Editor |
| `store.py` | `DocStore`: Seiten, Versionen, Änderungsprotokoll, hochgeladene Dateien |
| `sanitize.py` | `sanitize_html`: lässt nur erlaubte Tags und Attribute durch |

**Rollen.** Lesen dürfen `docs.read_roles` (`all` = alle Angemeldeten, so in allen Konfigurationen; sonst eine
Liste von Rollen). Anlegen, bearbeiten, wiederherstellen und löschen dürfen `docs.edit_roles` (Standard `maintainer`) und
Personen, die `platform-admin` auf der Verwaltungsseite im Abschnitt „Dokumentation – Maintainer“ freigibt. Eine Freigabe gilt
sofort, ohne neue Anmeldung, und liegt in `editors.json` im Docs-Speicher. Zur Auswahl stehen alle, die das Portal schon
genutzt haben (`people.json`: Subject, Name, Rollen, letzter Besuch; aktualisiert beim Aufruf von Startseite und Docs,
höchstens einmal pro Stunde); sonst wird das Subject eingegeben. Testperson: `entwickler` (Eva Entwicklerin, Rolle
`maintainer`). Im Gateway-Modus kommt die Rolle aus dem Claim `eduPersonEntitlement` = `urn:hka:portal:maintainer`
(`dev/roles.yml`).

**Speicher.** `docs.dir` (lokal `dev/docs/`, in `.gitignore`; Compose und VM `/var/lib/portal/registry/docs` im beschreibbaren
Registry-Volume). Ein leerer Ordner bekommt beim Start `seed.html` als Version 1 (Autor „Projektteam AWP“). Aufbau:

```text
pages/<slug>.json          aktueller Stand
versions/<slug>/<n>.json   jede veröffentlichte Version, wird nie überschrieben
changes.jsonl              eine Zeile je Änderung: Zeit, Seite, Version, Person, Art, Notiz
order.json                 Reihenfolge in der Navigation
editors.json               Maintainer, die die Verwaltungsseite freigegeben hat
people.json                Personen, die das Portal genutzt haben (Auswahl auf der Verwaltungsseite)
seed.json                  Prüfsumme des zuletzt übernommenen Ausgangsstands je Seite
assets/<hash>.<endung>     Bilder (PNG, JPEG, GIF, WebP) und PDFs, Name aus dem SHA-256 des Inhalts
```

**Neue Fassung von `seed.html`.** Ändert jemand `seed.html` im Repository (z. B. eine Anleitung per Pull Request),
übernimmt der nächste Start die neue Fassung als neue Version (Autor „Projektteam AWP“, Notiz „Ausgangsstand
aktualisiert“), aber nur für Seiten, die seit dem letzten Ausgangsstand niemand im Browser bearbeitet hat. Bearbeitete
Seiten bleiben unverändert; das Log nennt sie (`docs seed skipped slug=…`), die Änderung muss dann im Editor nachgezogen
werden. Neue Seiten aus `seed.html` kommen dazu, gelöschte Seiten bleiben gelöscht.

Ohne `docs.dir` ist die Dokumentation nur lesbar (Ausgangsstand, kein Editor). Zurücksetzen lokal: `dev/docs/` löschen.

**Funktionen.**

- Unter dem Titel jeder Seite steht wie in Confluence, wer sie zuletzt geändert hat und wann (relativ und als Datum), dazu
  Version, Ersteller und Lesezeit, sowie die Knöpfe „Verlauf“ und „Bearbeiten“.
- Die Systemseite „Letzte Änderungen“ (`#aenderungen`, Bereich Hilfe) gibt es immer. Sie zeigt alle Änderungen, die neueste zuerst
  und nach Tagen gruppiert, mit Notiz und Filter. Sie ist auch über das Uhr-Symbol im Kopf und die Fußzeile der Docs erreichbar.
  Die Fußzeile nennt die letzte Änderung.
- Im Versionsverlauf lässt sich jede ältere Version ansehen und als neue Version wiederherstellen.
- Editor (WYSIWYG, `contenteditable`), Start mit „Bearbeiten“ oder der Taste `E`. Fokus-Modus: Navigation und
  Inhaltsverzeichnis verschwinden, oben steht eine Leiste mit Titel, Status („Keine Änderungen“, „Nicht veröffentlicht“,
  „Entwurf gespeichert“), Wortzahl, „⋯“ (Seiteneinstellungen, HTML bearbeiten, Tastenkürzel, Seite löschen), „Abbrechen“
  und „Veröffentlichen“. Darunter die Formatleiste mit Absatzformat, Fett, Kursiv, Code, Link, Listen und „Einfügen“.
- Schreiben wie in Confluence oder Notion: `/` öffnet das Befehlsmenü (Überschriften, Listen, Bild, Tabelle,
  Hinweisboxen, Befehl, Codeblock, Zitat, Link, PDF, Trennlinie), filterbar und per Tastatur bedienbar. Über markiertem
  Text erscheint eine kleine Formatleiste. Markdown-Kürzel: `## ` Überschrift 2, `### ` Überschrift 3, `- ` Aufzählung,
  `1. ` nummerierte Liste, `> ` Zitat, `` ``` `` Codeblock, `---` + Enter Trennlinie. Leere Zeilen zeigen einen Hinweis.
- Links zeigen beim Anklicken eine Karte mit Adresse, „Bearbeiten“ und „Entfernen“; Tabellen eine Leiste für Zeilen
  und Spalten; Bilder eine Leiste für Größe, Zentrieren, Beschreibung (Alternativtext, Bildunterschrift) und Entfernen.
  Bilder kommen per Menü, Einfügen aus der Zwischenablage oder Ziehen und Ablegen dazu, mit Fortschritt. PDFs werden als
  Download-Link eingefügt. Eine kopierte Adresse über markiertem Text wird zum Link.
- „Veröffentlichen“ (oder Strg/⌘+S) öffnet einen Dialog für die Änderungsnotiz. Ein Entwurf liegt laufend im
  `localStorage` des Browsers und wird beim nächsten Öffnen angeboten. Hat inzwischen jemand anderes veröffentlicht,
  antwortet die Schnittstelle mit 409, und der Editor fragt nach.
- Neue Seiten legt „Neue Seite“ im Kopf an (Titel, Bereich, Stufe). Löschen nimmt eine Seite aus der Navigation, ihre Versionen
  bleiben erhalten. Die Startseite lässt sich nicht löschen.

**Sicherheit.** Gespeichertes HTML läuft durch `sanitize_html` (keine Skripte, keine `on…`-Attribute, keine `javascript:`-Links,
Bilder nur aus `/_portal/docs/assets/`). Die Seite hat eine eigene Content-Security-Policy mit Nonce: nur das Skript der Hülle und
des Editors laufen. Hochgeladene Dateien werden am Dateianfang geprüft (kein SVG) und mit `Content-Security-Policy: sandbox`
ausgeliefert, PDFs als Download. Ändernde Anfragen brauchen das CSRF-Token der Session im Header `X-CSRF-Token`.
