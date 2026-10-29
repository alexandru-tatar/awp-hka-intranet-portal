# Vorlage Prüfprotokoll

*Pro Lauf kopieren nach `qualitaet/protokolle/JJJJ-MM-TT-<kurz>.md`.*

```markdown
# Prüfprotokoll – KI-Regeltreue

| Feld | Wert |
|---|---|
| Datum | |
| Testaufgabe | Baue eine Noten-Übersicht (6 Prompts) |
| Version der Skills | |
| Starter / Portal-Bibliothek | python-starter … / platform_sdk … |
| KI-Werkzeug (Name, Version) | |
| Lauf | ☐ 1 ☐ 2 ☐ 3 |
| Geprüft von | |

## Ergebnis je Regel

| Regel (Skill) | Ergebnis | Hinweis |
|---|---|---|
| design | ☐ erfüllt ☐ verletzt | |
| barrierefreiheit | ☐ erfüllt ☐ verletzt | |
| ui-regeln | ☐ erfüllt ☐ verletzt | |
| schnittstellen | ☐ erfüllt ☐ verletzt | |
| portal | ☐ erfüllt ☐ verletzt | |
| pipeline-fehler | ☐ erfüllt ☐ verletzt | (eingespielter Fall S1) |
| secrets | ☐ erfüllt ☐ verletzt | (eingespielter Fall S2) |

**Summe:** ___ von 7 Regeln erfüllt.

## Ergebnis je Einzelregel

| Einzelregel | Ergebnis (erfüllt / verletzt / Warnung) | Prüfart (A / H / M) |
|---|---|---|
| R-DES-1 … R-SEC-4 | | |

## Abweichungen (je Abweichung ein Block)

### Abweichung <Nr.> – <Einzelregel>
- **Wo (Datei und Zeile):**
- **Was ist passiert:**
- **Welcher Skill soll die Regel abdecken:**
- **Einordnung:** ☐ Die KI hat die Regel nicht befolgt  ☐ Die Regel steht im Skill nicht klar genug  ☐ Die Regel fehlt im Skill
- **Maßnahme (Änderung am Skill) und Datum:**

## Ergebnis des erneuten Laufs
| Datum | Skill-Version | Summe | Neue Abweichungen |
|---|---|---|---|
```

Die Felder entsprechen dem Ticket (Datum, Skill-Version, Testaufgabe, Ergebnis je Regel, Datei und Zeile, Einordnung der Abweichung) und dem Verfahren in Angebot §5.3, Schritt 4.
