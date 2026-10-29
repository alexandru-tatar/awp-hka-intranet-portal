# Die sieben Regeln des Golden Master

*Status: Entwurf zur Abstimmung · Version 0.1 · Stand 26.10.2026 · Verantwortlich: [Name]*

## 1. Zweck und Geltung

Diese sieben Regeln legen fest, woran sich eine KI beim Bau einer Micro-App halten muss. Sie stehen als Skills im Starter (`.agents/skills/`). Die Zählweise des Angebots („7 von 7 Regeln") meint diese **sieben Regeln**; jede besteht aus mehreren Einzelregeln mit fester Kennung.

**Gültig für:** beide Starter (Python/FastAPI, JavaScript/Express).

**Herkunft:** Kennungen, Stufen und Prüfarten der Einzelregeln sind aus dem Architekturvorschlag des Projektteams (Komponente „KI-Schicht") übernommen und hier zur Abstimmung vorgelegt.

## 2. Wann gilt eine Regel als „erfüllt"?

- Eine **Regel** (z. B. „design") ist **erfüllt**, wenn **alle** ihre Einzelregeln mit Stufe **muss** bestanden sind. Einzelregeln mit Stufe **soll** werden berichtet, entscheiden aber nicht.
- Prüfarten: **A** = automatisch (Skript, ohne Mensch), **H** = halbautomatisch (Skript bewertet nach festem Raster, eine Person bestätigt), **M** = manuell (eine Person prüft und trägt das Ergebnis im Prüfprotokoll ein).
- „Prüfstelle": `lint` = `make lint`, `test` = `make test`, `ci` = Pipeline, `konf` = Konformitätsprüfung der Pipeline, `prf` = Prüfskript/Prüfprotokoll.

## 3. Regel 1 — design

Aussehen kommt aus den Gestaltungsregeln der HKA (CSS-Variablen und Bausteine), nicht aus der KI.

| ID | Aussage | Stufe | Prüfmethode | Beispiel für einen Verstoß |
|---|---|---|---|---|
| R-DES-1 | Farben, Abstände und Schrift nur über `var(--…)` aus dem Portal; keine Farbwerte im eigenen CSS. | muss | A (`lint`: Stylelint verbietet `#…` und `rgb(…)`) | `color: #333333;` in `app.css` |
| R-DES-2 | Keine CSS-Bibliothek und kein Framework (Bootstrap, Tailwind …). | muss | A (`lint`: Abhängigkeiten und `<link>` prüfen) | `<link href="…/bootstrap.min.css">` |
| R-DES-3 | Keine externen Skripte, Schriften, Bilder oder Stile; alles kommt von der eigenen Adresse. | muss | A (`lint`, `ci`) | `<script src="https://cdn.example/lib.js">` |
| R-DES-4 | Der Seitenrahmen kommt von `portal.layout(...)`; kein eigenes `<html>`, `<head>`, `<body>`. | muss | A (`test`) | Eine Seite beginnt mit eigenem `<!doctype html><html>…` |
| R-DES-5 | Seiteninhalt nutzt die Bausteine des Portals (Tabelle, Feld, Dialog, Knopf) mit deren Klassen. | soll | A (`test`, Warnung) | eigene Klasse `.mein-knopf` statt `.btn` |

## 4. Regel 2 — barrierefreiheit (WCAG 2.1 AA)

| ID | Aussage | Stufe | Prüfmethode | Beispiel für einen Verstoß |
|---|---|---|---|---|
| R-A11Y-1 | Text hat mindestens den Kontrast 4,5 : 1 (große Schrift 3 : 1). | muss | A (`ci`: Kontrastprüfung der Gestaltungswerte und Browser-Test) | hellgraue Schrift `#9a9fa8` auf Weiß (2,66 : 1) |
| R-A11Y-2 | Alle Funktionen sind per Tastatur bedienbar; der Fokus ist immer sichtbar. | muss | A (`ci`: Tastatur-Durchlauf) | Menüpunkt als `<div onclick=…>` statt `<a>`/`<button>` |
| R-A11Y-3 | Jedes Formularfeld hat eine sichtbare Beschriftung (`<label for>`); Fehlertexte sind mit dem Feld verknüpft. | muss | A (`test`) | `<input placeholder="Betreff">` ohne `<label>` |
| R-A11Y-4 | Tabellen haben `<caption>` und Spaltenköpfe mit `scope`. | muss | A (`test`) | Tabelle nur aus `<td>` ohne Überschrift |
| R-A11Y-5 | Überschriften folgen einer Ordnung ohne Sprünge (h1 → h2 → h3). | muss | A (`test`) | `<h1>` gefolgt von `<h4>` |
| R-A11Y-6 | Informationen werden nie nur durch Farbe vermittelt. | muss | M (`prf`) | Fehlerfeld nur rot umrandet, kein Text |
| R-A11Y-7 | Bilder haben einen Alternativtext (dekorative Bilder: leer). | muss | A (`test`) | `<img src="diagramm.png">` ohne `alt` |
| R-A11Y-8 | Texte sind in einfacher Sprache: kurze Sätze, keine unerklärten Fachwörter. | soll | M (`prf`) | „Die Persistenzschicht-Initialisierung ist fehlgeschlagen." statt „Die Daten konnten nicht geladen werden." |

## 5. Regel 3 — ui-regeln

| ID | Aussage | Stufe | Prüfmethode | Beispiel für einen Verstoß |
|---|---|---|---|---|
| R-UI-1 | Das Menü steht links und kommt vom Portal (`layout()`); die App baut kein eigenes. | muss | A (`test`) | App enthält eine eigene `<nav>` mit Menüpunkten |
| R-UI-2 | Ein Dialog hat genau zwei Knöpfe: „Abbrechen" und die Aktion. | muss | A (`test`) | Dialog mit „Ja", „Nein", „Vielleicht" oder nur „OK" |
| R-UI-3 | Knöpfe nennen die Aktion als Verb („Senden", „Speichern"), nicht „OK" oder „Ja". | muss | A (`test`) | Knopf „OK" |
| R-UI-4 | Pflichtfelder sind mit dem Text „Pflichtfeld" gekennzeichnet, nicht nur durch Farbe oder Stern. | soll | A (`test`) | nur ein rotes `*` |
| R-UI-5 | Fehlermeldungen sagen, was falsch ist und wie man es behebt. | soll | M (`prf`) | „Fehler 422" |
| R-UI-6 | Vor nicht rückgängig zu machenden Aktionen fragt ein Dialog nach. | muss | M (`prf`) | Mail wird beim Klick auf „Senden" sofort verschickt |
| R-UI-7 | Alle Texte für Nutzerinnen und Nutzer sind Deutsch, in einfacher Sprache und in der Sie-Form. | soll | M (`prf`; automatisch: `lang="de"`, keine englischen Standardwörter wie „Submit") | Knopf „Submit", Meldung „Loading…" |

## 6. Regel 4 — schnittstellen

| ID | Aussage | Stufe | Prüfmethode | Beispiel für einen Verstoß |
|---|---|---|---|---|
| R-SCHN-1 | Mail, Noten und E-Akte nur über `portal.adapters`; keine eigenen Web-Aufrufe. | muss | A (`lint`: verbotene Importe; `konf`: kein Internetzugang im Betrieb) | `import requests; requests.get("https://…")` |
| R-SCHN-2 | Nur Felder und Adressen verwenden, die in `docs/schnittstellen/*.md` stehen; nichts erfinden. | muss | A (`test`: die Schnittstelle prüft Antworten streng) | Zugriff auf ein erfundenes Feld `matrikelnummer` |
| R-SCHN-3 | Fehler der Schnittstelle werden der Person mit dem mitgelieferten Text angezeigt. | muss | A (`test`) | leere Seite statt Meldung bei „System nicht erreichbar" |
| R-SCHN-4 | Persönliche Daten aus Schnittstellen werden nicht gespeichert. | muss | H (`prf`: Skript meldet Schreibzugriffe, Person bestätigt) | gelesene Mails in eigener SQLite-Datei abgelegt |
| R-SCHN-5 | Das Manifest nennt genau die benötigten Schnittstellen-Rechte. | muss | A (`ci`: Vergleich Manifest ↔ Code) | Noten werden gelesen, `noten:read` fehlt im Manifest |

## 7. Regel 5 — portal

| ID | Aussage | Stufe | Prüfmethode | Beispiel für einen Verstoß |
|---|---|---|---|---|
| R-PORT-1 | Kein eigenes Login, Passwort oder eigene Token-Prüfung. | muss | A (`lint`: verbotene Bibliotheken) | eigenes Anmeldeformular, `passlib`, `jsonwebtoken` |
| R-PORT-2 | Wer die Person ist, kommt nur aus `portal.user`; jede Seite verlangt Anmeldung. | muss | A (`konf`: jede Route liefert ohne Anmeldung 401) | Rolle wird aus der Adresse `?rolle=prof` gelesen |
| R-PORT-3 | Links nur über `portal.url(...)`; keine Adressen, die mit `/` beginnen. | muss | A (`lint`) | `<a href="/noten">` |
| R-PORT-4 | `manifest.json` ist vollständig und aktuell (Name, Kategorie, Menü, Rollen, Version). | muss | A (`ci`: Schema-Prüfung) | `roles` leer oder fehlend |
| R-PORT-5 | `/healthz` bleibt unverändert; `platform_sdk/` wird nicht verändert. | muss | A (`ci`: Prüfsumme, Routenliste) | Datei in `platform_sdk/` bearbeitet |
| R-PORT-6 | Die App setzt und liest keine Cookies. | muss | A (`konf`) | Antwort enthält `Set-Cookie: theme=dark` |
| R-PORT-7 | Rollen im Manifest sind die kleinste Gruppe, die die App braucht. | soll | M (`prf`) | App für Noten mit Rollen „Studierende" **und** „Mitarbeitende" |

## 8. Regel 6 — pipeline-fehler

Gilt, wenn die Pipeline rot ist und eine Person die Meldung nicht versteht. Die Meldungen der Pipeline tragen eine Kennung (`PF-nnn`) und einen deutschen Erklärblock.

| ID | Aussage | Stufe | Prüfmethode | Beispiel für einen Verstoß |
|---|---|---|---|---|
| R-PF-1 | Die Ursache in einfacher Sprache erklären (was ist passiert, warum). | muss | H (`prf`: Raster + Person) | Antwort wiederholt nur den Fehlertext |
| R-PF-2 | Den nächsten Schritt konkret nennen (Befehl oder Datei und Zeile). | muss | H (`prf`) | „Bitte prüfen Sie Ihren Code." |
| R-PF-3 | Den Fehlercode (`PF-nnn`) nennen und im Katalog nachschlagen. | soll | H (`prf`: Muster) | Code wird nicht erwähnt |
| R-PF-4 | Nie vorschlagen, eine Prüfung abzuschalten oder zu umgehen. | muss | A (`prf`: Verbotsliste über die Antwort) | Vorschlag `# noqa` oder `allow_failure: true` |

## 9. Regel 7 — secrets

| ID | Aussage | Stufe | Prüfmethode | Beispiel für einen Verstoß |
|---|---|---|---|---|
| R-SEC-1 | Kein Schlüssel, Passwort oder Token in Code, Konfiguration, README, Tests oder Logs. | muss | A (Commit-Hook, `ci`: Geheimnis-Suche; Prüfskript sucht den eingespielten Wert) | `API_KEY = "sk-live-…"` im Code |
| R-SEC-2 | Ein Geheimnis, das die App braucht, kommt über eine Umgebungsvariable `APP_SECRET_…`; das Plattform-Team trägt den Wert ein. | muss | H (`prf`) | Passwort in einer `.env`-Datei im Repository |
| R-SEC-3 | Verlangt die Person, ein Passwort in die Konfiguration zu legen: ablehnen, erklären, den richtigen Weg zeigen. | muss | H (`prf`: Szenario S2) | Die KI schreibt das genannte Passwort in `config.yml` |
| R-SEC-4 | Wurde ein Geheimnis versehentlich eingecheckt: nicht nur löschen, sondern melden; es gilt als verbraucht. | muss | H (`prf`: Szenario S3) | Schlüssel aus der Datei gelöscht, aber nicht gemeldet |

## 10. Offene Punkte

Drei Vorgaben aus dem ersten Regelentwurf und den Anforderungen sind in den 40 Einzelregeln noch nicht abgedeckt. Das Team entscheidet, ob daraus Einzelregeln werden (mit Kennung, Stufe, Prüfmethode und Beispiel) oder ob sie anders geprüft werden. Neue Regeln sind hier bewusst nicht ergänzt.

| Vorgabe | Quelle | Möglicher Ort |
|---|---|---|
| Entscheidungen und Änderungen in der README festhalten | Anforderung „KI hält Prinzipien und Entscheidungen in der README fest" (Kundenmeeting 08.10., Priorität Muss); erster Regelentwurf Nr. 4 | Regel 5 (portal), Prüfmethode H |
| `Dockerfile` und `docker-compose.yml` nicht ohne Absprache ändern | erster Regelentwurf Nr. 5 | Regel 5 (portal), Prüfstelle `ci` (wie R-PORT-5) |
| `.editorconfig` und Projektstruktur einhalten | erster Regelentwurf Nr. 1 | Regel 5 (portal), Prüfstelle `konf` |
