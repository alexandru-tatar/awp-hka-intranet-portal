# 04 — Portal UI and Design Kit

Implementation-level specification. Overview: `../09-component-design.md` §4. The portal UI is served by the gateway (`02-gateway.md`); the kit is a set of static files. The institutional design manual is **not yet available** (`02-open-questions.md` §9, blocks package B), so the palette below is neutral and swappable behind the same token names.

## 1. Scope and principles

- Server-rendered HTML (Jinja2), **no JavaScript framework**; one ≤ 1 KB script for the dialog pattern (§7).
- The kit is **CSS plus documented HTML patterns**, not a component library (client, 08.10: *"ihr müsst keine Bibliothek anlegen"*). The patterns are the substance of the `design` and `ui-regeln` skills (`08-ai-layer.md`).
- WCAG 2.1 AA is the floor (Angebot §6, skill `barrierefreiheit`); text and UI contrast are **generated and checked**, not asserted (deck finding C1).
- German only in the pilot; every string lives in `messages.de.yml` so a later English UI is a data change (`02-open-questions.md` §9 default: i18n-ready).
- Fonts are self-hosted (deck finding C2): system UI stack by default; if the design manual prescribes a face, ship its `woff2` files from `/_portal/static/fonts/`.

## 2. URL map (portal origin)

| URL | Page | Access |
|---|---|---|
| `/` | Startseite: menu tree and short intro | session |
| `/_portal/status` | health table of all apps | role `platform-admin` |
| `/_portal/connections` | "Meine Verbindungen" (legacy credentials; only if the split-secret scheme is chosen, `05` §6) | session |
| `/_portal/error/{status}` | friendly error body used by Traefik's `errors` middleware | none |
| `/_portal/static/kit-<hash>.css`, `kit-<hash>.js`, `fonts/*`, `icons.svg` | assets, `Cache-Control: public, max-age=31536000, immutable` | none |
| `/login`, `/logout` (GET = confirmation page, POST = action), `/oidc/callback` | `02` | — |
| `/nav` (apps-facing :8001) | nav fragment for `layout()` | assertion |

## 3. Template tree

```
gateway/templates/
├── base.html            # <html lang="de">, head, skip link, header, <nav>, <main>, footer
├── partials/
│   ├── nav.html         # the menu tree (also rendered standalone for /nav)
│   ├── header.html
│   └── footer.html
├── pages/
│   ├── home.html
│   ├── status.html
│   ├── connections.html
│   └── error.html       # parameterised by status
└── macros/
    ├── fields.html      # label + input + hint + error
    ├── dialog.html      # two-button dialog
    └── table.html       # caption + th scope
```

## 4. Layout and wireframes

```text
Desktop (≥ 960 px)
┌───────────────────────────────────────────────────────────────┐
│ [Überspringen zum Inhalt]                       (skip link)   │
├───────────────────────────────────────────────────────────────┤
│ HKA Portal                              Erika Muster  [Abmelden]│  header (landmark: banner)
├────────────────┬──────────────────────────────────────────────┤
│ Navigation     │  <h1> Meine Noten </h1>                        │
│ ▸ Studium      │                                                │
│     Meine Noten│  … app content …                               │  <main>
│ ▸ Kommunikation│                                                │
│     Nachricht  │                                                │
│        senden  │                                                │
├────────────────┴──────────────────────────────────────────────┤
│ Hilfe · Datenschutz · Impressum                               │  footer (contentinfo)
└───────────────────────────────────────────────────────────────┘

Narrow (< 960 px): the navigation becomes a <details> element ("Menü") above <main>; no JavaScript.
```

Menu structure: `<nav aria-label="Hauptnavigation">` → one `<h2>` per category (visually a group label) → `<ul>` of links; the current page has `aria-current="page"`. Categories appear in fixed order *Studium, Verwaltung, Kommunikation, Sonstiges*; items alphabetical (`02-open-questions.md` §4 default). Empty categories are omitted. A user with no visible app sees the message in §6.

## 5. Design tokens (neutral palette) and contrast — computed

```css
:root {
  /* colour */
  --bg: #ffffff;           --bg-subtle: #f3f5f7;
  --ink: #1b1f24;          --ink-muted: #4a5360;
  --accent: #0b5cad;       --accent-ink: #ffffff;
  --danger: #b3261e;       --success: #17673a;
  --warn-ink: #7a4b00;     --warn-bg: #fff4d6;
  --border-ui: #6b7480;    /* borders of inputs/buttons (non-text contrast) */
  --border-soft: #d5dae0;  /* purely decorative dividers */
  --focus: #0b5cad;
  /* type */
  --font-body: system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
  --font-mono: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  --fs-0: 1rem; --fs-1: 1.125rem; --fs-2: 1.375rem; --fs-3: 1.75rem; --lh: 1.55;
  /* space (4 px base) */
  --s-1: .25rem; --s-2: .5rem; --s-3: .75rem; --s-4: 1rem; --s-6: 1.5rem; --s-8: 2rem;
  /* shape */
  --radius: 4px; --measure: 68ch;
}
```

Contrast matrix (WCAG 2.x relative luminance; **produced by `tools/contrast.py`, regenerated in CI — the table below is its output for the palette above**):

| Foreground | Background | Ratio | Requirement | Result |
|---|---|---|---|---|
| `--ink` | `--bg` | 16.56 | text 4.5 | pass |
| `--ink` | `--bg-subtle` | 15.15 | text 4.5 | pass |
| `--ink-muted` | `--bg` | 7.79 | text 4.5 | pass |
| `--ink-muted` | `--bg-subtle` | 7.12 | text 4.5 | pass |
| `--accent` (links) | `--bg` | 6.67 | text 4.5 | pass |
| `--accent` (links) | `--bg-subtle` | 6.10 | text 4.5 | pass |
| `--accent-ink` | `--accent` (buttons) | 6.67 | text 4.5 | pass |
| `--danger` | `--bg` | 6.54 | text 4.5 | pass |
| `--danger` | `--bg-subtle` | 5.98 | text 4.5 | pass |
| `--success` | `--bg` | 6.91 | text 4.5 | pass |
| `--warn-ink` | `--warn-bg` | 6.76 | text 4.5 | pass |
| `--border-ui` | `--bg` | 4.74 | UI component 3.0 | pass |
| `--border-ui` | `--bg-subtle` | 4.33 | UI component 3.0 | pass |

For comparison, the colour `#9a9fa8` used for the footer in the 22.10 slide deck measures 2.66 on white and would fail this gate (`../06-praesentation-deck-review.md` C1).

**CI rule (`tools/contrast.py`):** parse every `--token: #hex` pair declared in the kit's `pairs.json` (foreground, background, kind `text|ui|large-text`), compute the ratio, **fail the build** below 4.5 (`text`), 3.0 (`large-text`, `ui`). A new token cannot be added without declaring at least one pair. Stylelint additionally forbids hex literals outside `:root`, so apps cannot introduce unchecked colours.

Focus: `:focus-visible { outline: 3px solid var(--focus); outline-offset: 2px; }` on every interactive element; never `outline: none`. Respect `prefers-reduced-motion` (the kit has no animation except a 100 ms colour transition removed under that setting) and `prefers-color-scheme` is **not** implemented in the pilot (single verified palette; a dark palette would need its own contrast pairs).

## 6. German copy

Register: *Sie*, short sentences, no jargon (*einfache Sprache*, a requirement the client repeated on 08.10).

| Key | Text |
|---|---|
| `app.title` | HKA Portal |
| `skip.link` | Zum Inhalt springen |
| `nav.label` | Hauptnavigation |
| `nav.menu_button` | Menü |
| `nav.empty` | Für Sie ist im Moment keine Anwendung freigeschaltet. Wenn Sie eine erwarten, melden Sie sich bei {kontakt}. |
| `header.logout` | Abmelden |
| `logout.title` / `logout.body` | Abmelden? · Möchten Sie sich vom Portal abmelden? |
| `footer.help` / `.privacy` / `.imprint` | Hilfe · Datenschutz · Impressum |
| `login.failed.title` | Anmeldung nicht möglich |
| `login.failed.body` | Die Anmeldung hat nicht geklappt. Bitte versuchen Sie es noch einmal. Wenn es wieder nicht klappt, melden Sie sich bei {kontakt}. |
| `login.expired.title` | Anmeldung abgelaufen |
| `login.expired.body` | Die Anmeldung hat zu lange gedauert. Bitte beginnen Sie noch einmal. |
| `error.403.title` | Dafür fehlt Ihnen die Berechtigung |
| `error.403.body` | Diese Anwendung ist für Ihre Rolle nicht freigegeben. Wenn Sie glauben, dass das ein Fehler ist, melden Sie sich bei {kontakt}. |
| `error.404.title` | Seite nicht gefunden |
| `error.404.body` | Diese Adresse gibt es nicht (mehr). Nutzen Sie das Menü, um zu Ihrer Anwendung zu kommen. |
| `error.503.title` | Anwendung vorübergehend nicht verfügbar |
| `error.503.body` | Diese Anwendung antwortet im Moment nicht. Bitte versuchen Sie es in ein paar Minuten noch einmal. Wenn es länger dauert, melden Sie sich bei {kontakt}. |
| `error.5xx.title` | Es ist ein Fehler aufgetreten |
| `error.5xx.body` | Das liegt nicht an Ihnen. Bitte versuchen Sie es später noch einmal. Nennen Sie bei einer Meldung diese Nummer: {request_id}. |
| `maintenance.title` | Wartungsarbeiten |
| `maintenance.body` | Das Portal ist gerade nicht erreichbar. Bitte versuchen Sie es später noch einmal. |
| `status.title` | Betriebsstatus |
| `status.columns` | Anwendung · Version · Status · Letzte Prüfung · Letzte Bereitstellung |
| `status.healthy` / `.unhealthy` / `.failed` | in Betrieb · gestört · fehlgeschlagen |
| `connections.title` | Meine Verbindungen |
| `connections.intro` | Für einige Systeme braucht das Portal einmal Ihr Passwort, damit Anwendungen dort für Sie lesen können. Das Passwort wird verschlüsselt und nur für diese Sitzung gespeichert. |
| `dialog.cancel` / `dialog.confirm` | Abbrechen · {Aktionsname} (z. B. „Senden") |

`{kontakt}` is a configuration value (a mailbox or phone number from HKA-IT) — **open item**, no text ships without it. Page titles follow `{Seitenname} – HKA Portal`. Error pages always show the `request_id` in small text to help support.

## 7. Patterns (exact markup)

### 7.1 Navigation fragment (`partials/nav.html`, also the `/nav` response)

```html
<nav aria-label="Hauptnavigation" class="nav">
  <h2 class="nav__group">Studium</h2>
  <ul class="nav__list">
    <li><a href="/apps/noten/" aria-current="page">Meine Noten</a></li>
  </ul>
  <h2 class="nav__group">Kommunikation</h2>
  <ul class="nav__list">
    <li><a href="/apps/nachricht/">Nachricht senden</a></li>
  </ul>
</nav>
```
`/nav?current=/apps/noten/` marks the current item. Response headers: `Content-Type: text/html; charset=utf-8`, `ETag`, `Cache-Control: private, max-age=60`; `layout()` revalidates with `If-None-Match` (304 when unchanged).

### 7.2 Dialog with exactly two buttons (rule `R-UI-2`)

```html
<button type="button" data-dialog-open="confirm-send">Senden …</button>

<dialog id="confirm-send" aria-labelledby="confirm-send-title">
  <form method="dialog">
    <h2 id="confirm-send-title">Nachricht senden?</h2>
    <p>Die Nachricht geht an {empfaenger}. Das lässt sich danach nicht zurücknehmen.</p>
    <div class="dialog__actions">
      <button value="cancel" class="btn btn--secondary">Abbrechen</button>
      <button value="confirm" class="btn btn--primary" autofocus>Senden</button>
    </div>
  </form>
</dialog>
```
`kit.js` (≤ 1 KB, no dependencies): on `[data-dialog-open]` click call `document.getElementById(id).showModal()`; on `close`, if `returnValue === "confirm"` submit the form named in `data-submit-form`. Focus trapping, `Esc`, and focus return are native `<dialog>` behaviour. A dialog has **exactly two** `<button>` elements inside `.dialog__actions`; the lint rule counts them.

### 7.3 Form field with error

```html
<div class="field">
  <label for="subject">Betreff</label>
  <p id="subject-hint" class="field__hint">Höchstens 120 Zeichen.</p>
  <input id="subject" name="subject" type="text" maxlength="120"
         aria-describedby="subject-hint subject-error" aria-invalid="true" required>
  <p id="subject-error" class="field__error">Bitte geben Sie einen Betreff ein.</p>
</div>
```
Error summary at the top of the form (`role="alert"`, links to each invalid field). Required fields are marked with text ("Pflichtfeld"), not colour alone.

### 7.4 Data table

```html
<table class="table">
  <caption>Meine Noten</caption>
  <thead><tr><th scope="col">Modul</th><th scope="col">Semester</th><th scope="col">Note</th></tr></thead>
  <tbody><tr><th scope="row">Mathematik 1</th><td>WS 2025/26</td><td>2,3</td></tr></tbody>
</table>
```
Numbers use `font-variant-numeric: tabular-nums`; wide tables sit in a container with `overflow-x: auto` and `tabindex="0"` plus an accessible name.

## 8. Layout contract with the SDK

`layout(title, body_html, current)` (`06-portal-sdk.md`) returns:
```html
<!doctype html>
<html lang="de">
<head>
  <meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title} – HKA Portal</title>
  <link rel="stylesheet" href="/_portal/static/kit-{hash}.css">
  <script src="/_portal/static/kit-{hash}.js" defer></script>
</head>
<body>
  <a class="skip" href="#main">Zum Inhalt springen</a>
  <header class="site-header">…{user.name}… <a href="/logout">Abmelden</a></header>
  {nav_fragment}
  <main id="main" tabindex="-1">{body_html}</main>
  <footer>…</footer>
</body></html>
```
The nav response (`GET /nav` on the apps-facing listener) carries the header `X-Portal-Kit: kit-<hash>`; `layout()` builds the stylesheet and script URLs from it, so a kit release reaches every app within one nav-cache lifetime (60 s) without redeploying anything.

"Abmelden" is a plain link to the portal-origin page `GET /logout`, which shows a confirmation ("Möchten Sie sich abmelden?" with the buttons *Abbrechen* / *Abmelden*) containing a `POST /logout` form with the session's CSRF token. Apps therefore never handle a logout token, and a hostile page can at worst send the user to a confirmation screen.

## 9. Accessibility gate

| Tier | Where | What | Fails the build when |
|---|---|---|---|
| Structural | `make test` in every app (R15) | axe-core run on the rendered HTML in jsdom: labels, landmarks, headings order, `lang`, table headers, ARIA validity | any violation (jsdom cannot compute contrast) |
| Full | CI, stage, portal pages and reference apps | Playwright (Chromium) + axe-core, tags `wcag2a, wcag2aa, wcag21a, wcag21aa`, at 1280 px and 375 px width; keyboard-only walkthrough (Tab order reaches nav, main, logout; dialog traps and returns focus) | any `serious` or `critical` violation; any contrast violation |
| Token | CI, kit repo | `tools/contrast.py` over `pairs.json` | any pair below its threshold |

Axe cannot judge *plain language* or reading level; the `barrierefreiheit` skill covers that as a manual line in the Prüfprotokoll.

## 10. Visual regression

Playwright `toHaveScreenshot()` for: home (empty and populated), status, each error page, the two reference apps; viewports 375/768/1280; baseline images committed with the kit; threshold 0.2 % pixels. Every kit release regenerates baselines in the same merge request, reviewed by the second person. Purpose: a central restyle reaches all apps without redeploying them (`../09-component-design.md` §4.2) — this is the guard against surprising regressions.

## 11. Kit packaging

```
kit/
├── css/{tokens.css,base.css,layout.css,components.css,print.css}
├── js/kit.js
├── icons/icons.svg            # <symbol> sprite for the icon allow-list
├── fonts/                     # only if the design manual prescribes a face
├── pairs.json                 # contrast pairs
├── tools/contrast.py
└── VERSION                    # semver
```
Build step concatenates and minifies, writes `kit-<sha256[:12]>.css/js`, and a `kit-manifest.json` mapping `kit.css → kit-<hash>.css` that the gateway reads. Semver rule: tokens renamed/removed or pattern markup changed incompatibly = major (requires a pass over the reference apps).

## 12. Tests

| # | Case |
|---|---|
| UI1 | Home with roles `student`: only student apps; empty category omitted; alphabetical order |
| UI2 | User with no mapped role sees `nav.empty` text |
| UI3 | `unhealthy` app absent from the menu |
| UI4 | Every error page contains title, body, `request_id`, link back to `/` |
| UI5 | Skip link is first in tab order; `main` receives focus on activation |
| UI6 | Dialog: opens, traps focus, `Esc` cancels, confirm submits, focus returns to the trigger |
| UI7 | Field macro: `aria-describedby` references existing ids; error summary links focus the field |
| UI8 | axe structural + full tiers green on all pages |
| UI9 | Contrast script: all `pairs.json` rows pass; adding `#9a9fa8` on white fails the build |
| UI10 | Stylelint rejects a hex colour in app CSS |
| UI11 | `/nav` returns 304 on matching `If-None-Match`; changes after a registry change within 60 s |
| UI12 | Narrow viewport: menu in `<details>`, operable by keyboard |
| UI13 | Print stylesheet hides nav/header/footer |
| UI14 | "Abmelden" from an app page opens `/logout`; `POST /logout` without or with a foreign CSRF token is rejected; with the right token it ends the session |

## 13. Open points

- Contact string `{kontakt}` and legal links (Datenschutz, Impressum) — HKA to supply.
- Design manual (colours, typeface, logo) — swap token values; rerun the contrast gate.
- Whether `prefers-color-scheme: dark` is wanted — would require a second verified palette.
