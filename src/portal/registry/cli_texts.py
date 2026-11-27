"""Texte des Befehls ``python -m portal.registry`` (``portal-deploy``) und der Fehlerblöcke PF-nnn auf Deutsch und Englisch (HKA-101).

Die Sprache bestimmt ``cli_language``: ``PORTAL_LANG`` (``de`` oder ``en``), sonst die erste gesetzte Variable aus ``LC_ALL``,
``LC_MESSAGES`` und ``LANG`` (beginnt sie mit ``en``, gilt Englisch), sonst Deutsch. ``say`` liest die Sprache aus
``current_language`` (``core/i18n.py``); der Befehl setzt sie am Anfang. Platzhalter stehen in ``{geschweiften Klammern}``,
eine Klammer selbst als ``{{`` und ``}}``.
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Final, Mapping

from ..core.i18n import DEFAULT_LANGUAGE, LANGUAGES, current_language

LANGUAGE_VARIABLES: Final = ("PORTAL_LANG", "LC_ALL", "LC_MESSAGES", "LANG")


def cli_language(env: Mapping[str, str] | None = None) -> str:
    """Sprache der Ausgabe aus der Umgebung.

    :param env: Umgebungsvariablen, Standard ``os.environ``
    :return: ``de`` oder ``en``
    :rtype: str
    """
    env = os.environ if env is None else env
    explicit = (env.get("PORTAL_LANG") or "").strip().lower()
    if explicit in LANGUAGES:
        return explicit
    for name in LANGUAGE_VARIABLES[1:]:
        value = (env.get(name) or "").strip().lower()
        if value:
            return "en" if value.split("_")[0].split(".")[0] == "en" else DEFAULT_LANGUAGE
    return DEFAULT_LANGUAGE


def say(key: str, **kwargs: object) -> str:
    """Text zum Schlüssel in der Sprache der Ausgabe, Platzhalter ersetzt.

    :param key: Schlüssel aus ``TEXTS``
    :param kwargs: Werte der Platzhalter
    :return: Der Text; fehlt er auf Englisch, der deutsche
    :rtype: str
    :raises KeyError: Falls der Schlüssel in keiner Sprache steht
    """
    template = TEXTS[current_language.get()].get(key) or TEXTS[DEFAULT_LANGUAGE][key]
    return template.format(**kwargs)


def day(moment: datetime) -> str:
    """Datum für die Ausgabe: ``26.11.2026`` auf Deutsch, ``2026-11-26`` auf Englisch.

    :param moment: Zeitpunkt
    :return: Das Datum
    :rtype: str
    """
    return moment.strftime("%Y-%m-%d" if current_language.get() == "en" else "%d.%m.%Y")


def stamp(moment: datetime) -> str:
    """Datum und Uhrzeit für die Ausgabe.

    :param moment: Zeitpunkt
    :return: Datum, Uhrzeit und Zeitzone
    :rtype: str
    """
    return moment.strftime("%Y-%m-%d %H:%M:%S %Z" if current_language.get() == "en" else "%d.%m.%Y %H:%M:%S %Z")


TEXTS: Final[dict[str, dict[str, str]]] = {
    "de": {
        # Aufruf und Hilfe
        "cli.description": "Befehl zum Registrieren und Verwalten (auf der VM über portal-deploy).",
        "arg.config": "Konfiguration des Portals (YAML)",
        "arg.owner": "Repository, aus dem die App kommt (owner/name)",
        "arg.owner_form": "muss die Form owner/name haben",
        "arg.slug_form": "muss ein gültiger Name einer App sein (a-z, 0-9, -)",
        "arg.slug": "Name der App",
        "cmd.check": "Manifest von der Standardeingabe prüfen",
        "cmd.register": "Manifest prüfen und ablegen",
        "cmd.list": "Alle Apps mit Besitzer und Status zeigen",
        "cmd.remove": "App stilllegen",
        # Ausgabe von list
        "list.slug": "SLUG", "list.owner": "BESITZER", "list.version": "VERSION", "list.status": "STATUS",
        "list.last_probe": "LETZTE PRÜFUNG",
        "list.retired_since": "stillgelegt seit {date}",
        "list.unknown": "unbekannt",
        "list.not_taken": "noch nicht übernommen",
        "list.no_owner": "(ohne Besitzer)",
        "list.none": "Keine Apps registriert.",
        "list.no_status_file": "Hinweis: Keine Statusdatei gefunden. Läuft das Portal mit registry.status_file?",
        "list.stale": "Hinweis: Die Statusdatei ist älter als {seconds} s (Stand {stamp}). Läuft das Portal?",
        "list.status_from": "Status vom {stamp}.",
        # Meldungen des Befehls
        "err.config": "FEHLER Konfiguration: {detail}",
        "err.owners_missing": "FEHLER Konfiguration: registry.owners_file fehlt",
        "ok.removed": "OK slug={slug}: Stillgelegt. Das Portal nimmt die App innerhalb weniger Sekunden aus dem Menü. "
                      "Dasselbe Repository kann den Namen jederzeit wieder registrieren.",
        "ok.valid": "OK slug={slug} version={version}: Das Manifest ist gültig.",
        "ok.registered": "OK slug={slug} version={version}: {what}. Das Portal übernimmt die App innerhalb weniger "
                         "Sekunden und zeigt sie im Menü, sobald /healthz antwortet.",
        "ok.updated": "Aktualisiert",
        "ok.new": "Neu registriert",
        "err.not_registered": "FEHLER: Die App „{slug}\" ist nicht registriert. Es wurde nichts geändert.\n"
                              "Welche Apps registriert sind, zeigt: portal-deploy list",
        "err.registry": "FEHLER Registry: {detail}\nBitte das Plattform-Team informieren.",
        # Fehlerblock
        "block.error": "FEHLER",
        "block.what": "Was ist passiert:",
        "block.why": "Warum wichtig:",
        "block.todo": "Was tun:",
        "block.details": "Technische Details:",
        # PF-104
        "pf104.title": "manifest.json ungültig",
        "pf104.why": "Ohne gültiges Manifest nimmt das Portal die App nicht ins Menü auf. Der bisherige Menüstand bleibt.",
        "pf104.fix": "Korrigieren Sie die genannten Stellen in manifest.json.",
        "pf104.roles": "Erlaubte Rollen: {roles}.",
        "pf104.categories": "Erlaubte Kategorien: {categories}.",
        "pf104.skill": "Mehr dazu: Skill „portal\".",
        "pf104.too_big": "Die Datei ist größer als 64 KiB.",
        "pf104.bytes": "{count} Bytes",
        "pf104.not_json": "Die Datei ist kein gültiges JSON.",
        "pf104.rules": "Die Datei hält die Regeln der Plattform nicht ein. Betroffen: {fields}.",
        # PF-202
        "pf202.title": "Registrierung abgelehnt",
        "pf202.why": "Ein Name darf nur zu einer App gehören, sonst könnte eine App eine fremde ersetzen.",
        "pf202.other_slug": "Wählen Sie in manifest.json einen anderen slug als „{slug}\".",
        "pf202.ask": "Gehört der Name wirklich zu Ihrer App (zum Beispiel nach dem Umbenennen des Repositorys), fragen Sie "
                     "das Plattform-Team.",
        "pf202.foreign": "Der Name „{slug}\" gehört zu einem anderen Repository.",
        "pf202.foreign_detail": "slug={slug} angefragt von {owner}, gebunden an ein anderes Repository",
        "pf202.locked": "Der Name „{slug}\" gehörte zu einer stillgelegten App und ist noch gesperrt.",
        "pf202.locked_detail": "slug={slug} stillgelegt am {retired}, frei für andere Repositorys ab {free} ({days} Tage)",
        "pf202.second_file": "Der Name „{slug}\" steht schon in einer anderen Manifest-Datei.",
        "pf202.second_file_detail": "Datei {file}",
        "pf202.by_hand": "Der Name „{slug}\" ist von Hand eingerichtet und hat keinen Besitzer.",
        "pf202.by_hand_detail": "Datei {file} ohne Eintrag in der Besitzerdatei",
        # PF-202 beim Entfernen
        "pf202r.title": "Entfernen abgelehnt",
        "pf202r.what": "Die App „{slug}\" gehört zu einem anderen Repository.",
        "pf202r.why": "Nur der Besitzer darf eine App entfernen, sonst könnte jemand eine fremde App abschalten.",
        "pf202r.check_owner": "Prüfen Sie den Wert von --owner.",
        "pf202r.ask": "Gehört die App wirklich Ihnen, fragen Sie das Plattform-Team.",
        # PF-204
        "pf204.title": "Bereitstellung gesperrt",
        "pf204.what": "Eine andere Registrierung läuft gerade.",
        "pf204.why": "Zwei Registrierungen gleichzeitig könnten sich gegenseitig überschreiben.",
        "pf204.todo": "Warten Sie einige Sekunden, dann starten Sie die Registrierung erneut.",
        # Fehler im Betrieb der Registry
        "reg.write_failed": "Schreiben nicht möglich: {detail}",
        "reg.unreadable": "Datei {path} nicht lesbar",
        "reg.would_be_invalid": "Manifest {file} wäre danach ungültig: {detail}",
        "reg.lock_failed": "Sperrdatei nicht anlegbar: {detail}",
        "reg.owners_unreadable": "Besitzerdatei {path} nicht lesbar: {detail}",
        "reg.owners_shape": "Besitzerdatei {path} hat nicht die Form {{name: repository}}",
        "reg.retired_unreadable": "Datei {path} nicht lesbar: {detail}",
        "reg.retired_zone": "Datei {path}: Zeitpunkt ohne Zeitzone",
    },
    "en": {
        "cli.description": "Command to register and manage apps (on the VM through portal-deploy).",
        "arg.config": "Portal configuration (YAML)",
        "arg.owner": "Repository the app comes from (owner/name)",
        "arg.owner_form": "must have the form owner/name",
        "arg.slug_form": "must be a valid app name (a-z, 0-9, -)",
        "arg.slug": "Name of the app",
        "cmd.check": "Check the manifest from standard input",
        "cmd.register": "Check the manifest and store it",
        "cmd.list": "Show all apps with owner and status",
        "cmd.remove": "Retire an app",
        "list.slug": "SLUG", "list.owner": "OWNER", "list.version": "VERSION", "list.status": "STATUS",
        "list.last_probe": "LAST CHECK",
        "list.retired_since": "retired since {date}",
        "list.unknown": "unknown",
        "list.not_taken": "not taken over yet",
        "list.no_owner": "(no owner)",
        "list.none": "No apps registered.",
        "list.no_status_file": "Note: No status file found. Does the portal run with registry.status_file?",
        "list.stale": "Note: The status file is older than {seconds} s (as of {stamp}). Is the portal running?",
        "list.status_from": "Status as of {stamp}.",
        "err.config": "ERROR configuration: {detail}",
        "err.owners_missing": "ERROR configuration: registry.owners_file is missing",
        "ok.removed": "OK slug={slug}: Retired. The portal removes the app from the menu within a few seconds. "
                      "The same repository can register the name again at any time.",
        "ok.valid": "OK slug={slug} version={version}: The manifest is valid.",
        "ok.registered": "OK slug={slug} version={version}: {what}. The portal takes the app over within a few seconds "
                         "and shows it in the menu as soon as /healthz answers.",
        "ok.updated": "Updated",
        "ok.new": "Newly registered",
        "err.not_registered": "ERROR: The app \"{slug}\" is not registered. Nothing was changed.\n"
                              "To see which apps are registered, run: portal-deploy list",
        "err.registry": "ERROR registry: {detail}\nPlease inform the platform team.",
        "block.error": "ERROR",
        "block.what": "What happened:",
        "block.why": "Why it matters:",
        "block.todo": "What to do:",
        "block.details": "Technical details:",
        "pf104.title": "manifest.json invalid",
        "pf104.why": "Without a valid manifest the portal does not add the app to the menu. The current menu stays as it is.",
        "pf104.fix": "Correct the places named in manifest.json.",
        "pf104.roles": "Allowed roles: {roles}.",
        "pf104.categories": "Allowed categories: {categories}.",
        "pf104.skill": "More on this: skill \"portal\".",
        "pf104.too_big": "The file is larger than 64 KiB.",
        "pf104.bytes": "{count} bytes",
        "pf104.not_json": "The file is not valid JSON.",
        "pf104.rules": "The file does not follow the rules of the platform. Affected: {fields}.",
        "pf202.title": "Registration rejected",
        "pf202.why": "A name may belong to one app only, otherwise one app could replace another.",
        "pf202.other_slug": "Choose a different slug than \"{slug}\" in manifest.json.",
        "pf202.ask": "If the name really belongs to your app (for example after renaming the repository), ask the "
                     "platform team.",
        "pf202.foreign": "The name \"{slug}\" belongs to another repository.",
        "pf202.foreign_detail": "slug={slug} requested by {owner}, bound to another repository",
        "pf202.locked": "The name \"{slug}\" belonged to a retired app and is still blocked.",
        "pf202.locked_detail": "slug={slug} retired on {retired}, free for other repositories from {free} ({days} days)",
        "pf202.second_file": "The name \"{slug}\" is already used in another manifest file.",
        "pf202.second_file_detail": "File {file}",
        "pf202.by_hand": "The name \"{slug}\" was set up by hand and has no owner.",
        "pf202.by_hand_detail": "File {file} has no entry in the owners file",
        "pf202r.title": "Removal rejected",
        "pf202r.what": "The app \"{slug}\" belongs to another repository.",
        "pf202r.why": "Only the owner may remove an app, otherwise someone could switch off another person's app.",
        "pf202r.check_owner": "Check the value of --owner.",
        "pf202r.ask": "If the app really is yours, ask the platform team.",
        "pf204.title": "Deployment locked",
        "pf204.what": "Another registration is running right now.",
        "pf204.why": "Two registrations at the same time could overwrite each other.",
        "pf204.todo": "Wait a few seconds, then start the registration again.",
        "reg.write_failed": "Cannot write: {detail}",
        "reg.unreadable": "Cannot read file {path}",
        "reg.would_be_invalid": "Manifest {file} would be invalid afterwards: {detail}",
        "reg.lock_failed": "Cannot create lock file: {detail}",
        "reg.owners_unreadable": "Cannot read owners file {path}: {detail}",
        "reg.owners_shape": "Owners file {path} does not have the form {{name: repository}}",
        "reg.retired_unreadable": "Cannot read file {path}: {detail}",
        "reg.retired_zone": "File {path}: time without time zone",
    },
}
