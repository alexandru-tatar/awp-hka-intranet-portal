---
name: hka-design
description: Design-Regeln und HTML-Muster des HKA Portals (Look nach www.h-ka.de). Verwenden, sobald UI für das Portal oder eine Portal-App entsteht oder geändert wird – Seiten, Jinja-Templates, Formulare, Tabellen, Dialoge, Buttons, Farben, Schriften, Icons, CSS im Ordner kit/ – und beim Prüfen von UI auf Kit-Konformität und Barrierefreiheit.
---

# HKA Portal – Design-Kit

Das Kit ist **CSS plus dokumentierte HTML-Muster**, keine Komponentenbibliothek.
Quelle der Wahrheit: `kit/css/*.css`, `kit/pairs.json`, `gateway/templates/macros/`.
Spezifikation: `04-portal-ui-and-design-kit.md`. Wenn dieses Dokument und der Code
sich widersprechen, gilt der Code – dann dieses Dokument korrigieren.

## 1. Grundsätze (nicht verhandelbar)

1. **Server-gerendertes HTML**, kein JS-Framework. Einziges Skript: `kit.js` (≤ 1 KB, nur Dialoge).
2. **WCAG 2.1 AA ist Untergrenze.** Kontrast wird berechnet, nicht behauptet (`make contrast`).
3. **Keine Farbe außerhalb der Tokens.** Hex-Werte nur in `kit/css/tokens.css` (`:root`).
   Apps schreiben kein eigenes Farb-CSS.
4. **Jeder Text auf Deutsch, in „Sie“, einfache Sprache.** Portal-Texte stehen in
   `gateway/portal/locales/messages.de.yml`, nie im Template hart kodiert.
5. **Apps bauen keinen eigenen Rahmen.** Header, Menü und Footer liefert `layout()` /
   `/nav`; die App liefert nur den Inhalt von `<main>`.
6. **Schriften selbst gehostet** (`kit/fonts/`), keine externen Requests (kein Google Fonts, kein CDN).

## 2. Look (nach www.h-ka.de)

| Merkmal | Regel |
|---|---|
| Grundfläche | Weiß; Flächen/Kacheln in Hellgrau `--bg-subtle` |
| Akzent | HKA-Rot `--accent` für Links, Buttons, Marker, Icons |
| Formen | **Eckig**: `--radius: 0`. Keine runden Ecken, keine Schatten (außer Dialog-Backdrop) |
| Überschriften | Fett, kondensiert (`--font-heading`), eng gesetzt |
| Aktionen | Fette Mono-Schrift (`--font-mono`); Links mit nachgestelltem „>“ (`.cta`) |
| Hover | Rot wird dunkler (`--accent-strong`); Kacheln werden rot mit weißer Schrift |
| Fokus | 3 px Ring in HKA-Blau `--focus` – bewusst nicht Rot, damit er neben roten Buttons sichtbar bleibt |

## 3. Tokens

Immer `var(--token)` verwenden, nie den Wert.

| Token | Wert | Zweck |
|---|---|---|
| `--bg` | `#ffffff` | Seitenhintergrund |
| `--bg-subtle` | `#f4f4f4` | Kacheln, Footer, Hinweise, aktiver Menüpunkt |
| `--ink` | `#1a1a1a` | Fließtext, Überschriften |
| `--ink-muted` | `#6e6e6e` | Hinweise, Metadaten, Gruppenlabels |
| `--accent` | `#d72305` | HKA-Rot: Links, Buttons, Icons |
| `--accent-ink` | `#ffffff` | Text auf Rot |
| `--accent-strong` | `#990b24` | Hover/aktiv |
| `--danger` | `#990b24` | Fehlermeldungen |
| `--success` | `#288732` | Status „in Betrieb“ (nur auf `--bg`) |
| `--warn-ink` / `--warn-bg` | `#7a4b00` / `#fff4d6` | Warnhinweise |
| `--border-ui` | `#6e6e6e` | Rahmen von Eingabefeldern |
| `--border-soft` | `#d8d8d8` | rein dekorative Linien |
| `--focus` | `#1e4696` | Fokusring |

Typografie: `--font-body` IBM Plex Sans · `--font-heading` IBM Plex Sans Condensed 700 ·
`--font-mono` IBM Plex Mono 700. Größen `--fs-0` 1rem · `--fs-1` 1.25rem · `--fs-2` 1.75rem ·
`--fs-3` 2.5rem; Zeilenhöhe `--lh` 1.75.
Abstände (4-px-Raster): `--s-1` .25 · `--s-2` .5 · `--s-3` .75 · `--s-4` 1 · `--s-6` 1.5 ·
`--s-8` 2 · `--s-12` 3 rem. Lesebreite `--measure` 68ch.

**Neuer Farb-Token?** Nur mit mindestens einem Eintrag in `kit/pairs.json`
(`text` ≥ 4.5, `large-text`/`ui` ≥ 3.0, `decorative` ohne Schwelle). Danach `make contrast`;
der Build bricht unter der Schwelle ab.

## 4. Seitenrahmen (liefert das Portal)

```
Header   rote Wortmarke „Hochschule Karlsruhe / Portal“ · Name · ABMELDEN
Menü     ≥ 960 px Seitenleiste, darunter <details>„Menü“ – ohne JavaScript
<main>   Inhalt der App (id="main", tabindex="-1", Ziel des Skip-Links)
Footer   Hellgrau · Hilfe > · Datenschutz > · Impressum >
```

Seitentitel: `{Seitenname} – HKA Portal`. Pro Seite genau **eine** `<h1>`; Überschriften
ohne Ebenen-Sprung.

## 5. Muster (exaktes Markup)

### Buttons und Aktionslinks

```html
<button type="submit" class="btn btn--primary">Speichern</button>   <!-- Hauptaktion: rot gefüllt -->
<a class="btn btn--secondary" href="/">Abbrechen</a>                 <!-- Nebenaktion: roter Rahmen -->
<a class="cta" href="/apps/noten/">mehr erfahren</a>                 <!-- Textlink mit „>“ -->
<div class="actions">…mehrere Buttons…</div>                        <!-- Button-Reihe -->
```
- Höchstens **ein** `btn--primary` pro Formular/Bereich.
- Beschriftung = Verb der Aktion („Senden“, „Speichern“), nicht „OK“/„Ja“.
- Das „>“ von `.cta` ist CSS-Deko (für Screenreader stumm) – nie selbst ins HTML schreiben.

### Formularfeld mit Fehler

```html
<div class="field">
  <label for="subject">Betreff <span class="field__required">(Pflichtfeld)</span></label>
  <p id="subject-hint" class="field__hint">Höchstens 120 Zeichen.</p>
  <input id="subject" name="subject" type="text" maxlength="120"
         aria-describedby="subject-hint subject-error" aria-invalid="true" required>
  <p id="subject-error" class="field__error">Bitte geben Sie einen Betreff ein.</p>
</div>
```
- Jedes Feld hat ein sichtbares `<label for>`; Platzhaltertext ersetzt nie das Label.
- Pflichtfelder mit Text „(Pflichtfeld)“ markieren, nicht nur mit Farbe oder `*`.
- `aria-describedby` nennt nur IDs, die existieren; `aria-invalid` nur im Fehlerfall.
- Bei Fehlern oben im Formular eine Zusammenfassung mit Links auf die Felder:

```html
<div class="error-summary" role="alert" tabindex="-1">
  <h2>Bitte prüfen Sie Ihre Eingaben</h2>
  <ul><li><a href="#subject">Bitte geben Sie einen Betreff ein.</a></li></ul>
</div>
```
Im Gateway: Makros `field(...)` und `error_summary(...)` aus `macros/fields.html`.

### Dialog – genau zwei Buttons (Regel R-UI-2)

```html
<button type="button" class="btn btn--primary" data-dialog-open="confirm-send">Senden …</button>

<dialog id="confirm-send" aria-labelledby="confirm-send-title" data-submit-form="send-form">
  <form method="dialog">
    <h2 id="confirm-send-title">Nachricht senden?</h2>
    <p>Die Nachricht geht an das Studienbüro. Das lässt sich danach nicht zurücknehmen.</p>
    <div class="dialog__actions">
      <button value="cancel" class="btn btn--secondary">Abbrechen</button>
      <button value="confirm" class="btn btn--primary" autofocus>Senden</button>
    </div>
  </form>
</dialog>
```
- Nur für Bestätigungen vor nicht umkehrbaren Aktionen. Titel als Frage, Text nennt die Folge.
- Exakt **zwei** `<button>` in `.dialog__actions`: Abbrechen links, Aktion rechts.
- `data-submit-form` = ID des Formulars, das bei „confirm“ abgeschickt wird.
- Öffnen per `data-dialog-open`; Fokusfalle, `Esc`, Fokusrückgabe macht `<dialog>` nativ.
- Auslöser-Button endet mit „…“ (es folgt noch eine Rückfrage).
Im Gateway: Makro `dialog(id, title, body, confirm_label, submit_form)`.

### Datentabelle

```html
<div class="table-wrap" role="region" aria-labelledby="grades-caption" tabindex="0">
  <table class="table">
    <caption id="grades-caption">Meine Noten</caption>
    <thead><tr><th scope="col">Modul</th><th scope="col" class="num">Note</th></tr></thead>
    <tbody><tr><th scope="row">Mathematik 1</th><td class="num">2,3</td></tr></tbody>
  </table>
</div>
```
- Immer `<caption>`, `th scope="col"`, erste Zelle je Zeile `th scope="row"`.
- Zahlen rechtsbündig mit `class="num"` (Ziffern sind tabellarisch gesetzt); deutsches Komma.
- Breite Tabellen scrollen im `.table-wrap` (fokussierbar, benannt) – nie die ganze Seite.
Im Gateway: Makro `table(caption, columns, rows, num_cols, id)`.

### Hinweise und Status

```html
<div class="notice"><p>Neutraler Hinweis, rote Randlinie.</p></div>
<div class="notice notice--warn"><p>Warnung.</p></div>
<div class="notice" role="status"><p>Gespeichert.</p></div>   <!-- Erfolgsmeldung nach Aktion -->
<span class="badge badge--healthy">in Betrieb</span>          <!-- auch: unhealthy, failed, registering, retired -->
```
Status nie nur über Farbe: Badge hat immer Text.

### Kacheln (Startseite)

```html
<a class="app-card" href="/apps/noten/">
  <svg class="icon" aria-hidden="true" focusable="false"><use href="{icons_url}#i-grades"></use></svg>
  <span class="app-card__name">Meine Noten</span>
  <span class="app-card__meta">Noten und Leistungen</span>
  <span class="app-card__cta cta" aria-hidden="true">öffnen</span>
</a>
```

### Icons

Nur aus dem Sprite `kit/icons/icons.svg`, Erlaubnisliste = `menu.icon` im Manifest-Schema:
`grades` `mail` `calendar` `document` `people` `book` `room` `settings` `info`.
Immer `aria-hidden="true" focusable="false"`; das Icon steht neben Text, nie allein.
Neues Icon: `<symbol id="i-<name>" viewBox="0 0 24 24">` (Strich, keine Füllung) **und**
Eintrag im Schema-Enum – ein Test prüft, dass beide übereinstimmen.

### Hilfsklassen

`.prose` (Lesebreite) · `.lead` (Einleitungssatz) · `.muted` · `.small` ·
`.visually-hidden` (nur für Screenreader) · `.actions` (Button-Reihe).

## 6. Texte

- Anrede „Sie“, kurze Sätze, keine Fachbegriffe, keine Schuldzuweisung („Das liegt nicht an Ihnen.“).
- Fehlermeldung = was ist passiert + was die Person jetzt tun kann.
- Kontakt immer über `{kontakt}` aus der Konfiguration, nie eine Adresse hart kodieren.
- Fehlerseiten zeigen immer Titel, Text, Link „zur Startseite“ und die Fehlernummer (`request_id`).
- Datum `26.10.2026`, Zeit `09:14`, Dezimalkomma `2,3`.

## 7. Barrierefreiheit – Pflicht

- `<html lang="de">`; Skip-Link „Zum Inhalt springen“ ist erstes fokussierbares Element.
- Nie `outline: none`; Fokus muss überall sichtbar sein.
- Alles per Tastatur bedienbar; keine `div`/`span` als Buttons.
- `aria-current="page"` für den aktiven Menüpunkt.
- Animationen höchstens 100 ms Farbwechsel; unter `prefers-reduced-motion` aus.
- Kein Dark Mode (nur eine geprüfte Palette).
- Druckansicht blendet Header, Menü, Footer, Buttons aus (`print.css`).

## 8. Verboten

- Hex-/RGB-Farben, eigene Schriften oder `border-radius` in App-CSS.
- Externe Schriften, Skripte oder Styles (CDN, Google Fonts).
- Eigene Header/Menüs/Footer in Apps.
- Dialoge mit einem oder mehr als zwei Buttons; Dialoge für reine Information.
- Rot für etwas anderes als Aktion/Marke (Fehler nutzen `--danger`).
- Text in Bildern; Icons ohne Text.
- Die Wortmarke durch ein nachgebautes Logo ersetzen – das offizielle Logo kommt mit dem Designhandbuch.

## 9. Prüfen vor dem Abschluss

```sh
make contrast   # alle Paare in pairs.json über der Schwelle
make test       # u. a. Nav-Reihenfolge, Fehlerseiten, Feld-IDs, Dialog = 2 Buttons, kein Hex außerhalb tokens.css
make dev        # Seite bei 1280 px und 375 px ansehen, nur mit Tastatur durchklicken
```

Checkliste:
- [ ] Nur Tokens, keine neuen Farben ohne `pairs.json`
- [ ] Eine `<h1>`, logische Überschriften, Seitentitel `… – HKA Portal`
- [ ] Jedes Feld mit Label; Fehler mit Text, Zusammenfassung, `aria-describedby`
- [ ] Tabellen mit `caption` und `scope`; Zahlen `.num`
- [ ] Dialoge: genau zwei Buttons, Frage als Titel
- [ ] Alle Texte in „Sie“ und in `messages.de.yml` (Portal) bzw. der App-Sprache-Datei
- [ ] Tastatur: Tab-Reihenfolge Skip-Link → Wortmarke → Abmelden → Menü → Inhalt → Footer; Fokus sichtbar

## Offene Punkte

Designhandbuch der HKA fehlt noch. Dann: Token-Werte tauschen, offizielles Logo in den
Header, ggf. GT Pressura (lizenziert) statt Plex Condensed/Mono – Token-**Namen** bleiben,
`make contrast` erneut ausführen und dieses Dokument anpassen.
