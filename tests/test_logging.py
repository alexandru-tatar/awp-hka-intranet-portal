"""Logging: Konsolen- und Dateiformat, Level je Logger, Request-ID in jeder Zeile, Umleitung der Standardbibliothek."""

import logging
import re

import pytest
from loguru import logger

from portal.app import create_app
from portal.core.config import LoggingConfig
from portal.core.log import abbreviate, configure_logging


@pytest.fixture
def logfile(tmp_path):
    """Logging mit Logdatei einrichten und danach alle Ausgaben wieder entfernen."""
    path = tmp_path / "app.log"
    yield path
    logger.remove()
    logging.getLogger().handlers.clear()


def read(path) -> str:
    logger.complete()
    return path.read_text(encoding="utf-8")


def test_abbreviate_keeps_short_names_and_shrinks_long_ones():
    assert abbreviate("portal.service.app_service") == "portal.service.app_service"
    short = abbreviate("portal.auth.redis_sessions.very_long_module_name_here_x")
    assert len(short) <= 40 and short.endswith("very_long_module_name_here_x")
    assert short.startswith("p.a.")


def test_file_line_has_time_level_pid_thread_logger_and_message(logfile):
    configure_logging(LoggingConfig(console_level="ERROR", file=logfile, file_level="DEBUG"))
    logger.info("hallo {}", "welt")
    line = read(logfile).strip()
    assert re.match(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}[+-]\d{2}:\d{2} INFO +\d+ --- \[ *[^\]]+\] \S+ +: hallo welt \[req=-\]$",
        line,
    ), line


def test_levels_per_logger_override_the_default(logfile):
    configure_logging(
        LoggingConfig(console_level="ERROR", file=logfile, file_level="WARNING", levels={"portal.sub": "DEBUG"})
    )
    logger.bind().debug("global-debug")
    with logger.contextualize():
        sub = logger.patch(lambda r: r.update(name="portal.sub.mod"))
        other = logger.patch(lambda r: r.update(name="other.mod"))
        sub.debug("sub-debug")
        other.debug("other-debug")
        other.warning("other-warning")
    text = read(logfile)
    assert "sub-debug" in text and "other-warning" in text
    assert "global-debug" not in text and "other-debug" not in text


def test_standard_library_logging_goes_through_loguru(logfile):
    configure_logging(LoggingConfig(console_level="ERROR", file=logfile, file_level="INFO"))
    logging.getLogger("uvicorn.error").warning("von uvicorn")
    logging.getLogger("httpx").info("von httpx")
    text = read(logfile)
    assert "WARNING" in text and "von uvicorn" in text and "von httpx" in text


def test_request_id_appears_in_log_lines_of_the_request(env, logfile):
    from fastapi.testclient import TestClient

    configure_logging(LoggingConfig(console_level="ERROR", file=logfile, file_level="DEBUG"))
    client = TestClient(create_app(env / "gateway.dev.yml"), follow_redirects=False)
    client.post("/login", data={"user": "alexandru", "next": "/"}, headers={"X-Request-Id": "req-4711"})
    text = read(logfile)
    assert "[req=req-4711]" in text and "user=alexandru" in text


def test_exception_is_written_with_traceback(logfile):
    configure_logging(LoggingConfig(console_level="ERROR", file=logfile, file_level="DEBUG"))
    try:
        raise ValueError("kaputt")
    except ValueError:
        logger.exception("fehler")
    text = read(logfile)
    assert "fehler" in text and "ValueError: kaputt" in text and "Traceback" in text


def test_config_rejects_unknown_logging_key_and_level(tmp_path, env):
    from portal.core.config import ConfigError, load_config

    cfg_text = (env / "gateway.dev.yml").read_text(encoding="utf-8")
    for extra, message in [("logging: { gibtsnicht: 1 }\n", "unknown logging key"),
                           ("logging: { console_level: LAUT }\n", "unknown log level"),
                           ("logging: { levels: { portal: LAUT } }\n", "unknown log level")]:
        path = env / "bad.yml"
        path.write_text(cfg_text + extra, encoding="utf-8")
        with pytest.raises(ConfigError, match=message):
            load_config(path)


def test_config_defaults_by_environment_and_relative_file(env):
    from portal.core.config import load_config

    cfg_text = (env / "gateway.dev.yml").read_text(encoding="utf-8")
    path = env / "x.yml"
    path.write_text(cfg_text + "logging: { file: logs/app.log, retention: 5, levels: { httpx: warning } }\n", encoding="utf-8")
    cfg = load_config(path).logging
    assert cfg.console_level == "DEBUG" and cfg.file == (env / "logs" / "app.log").resolve()
    assert cfg.retention == 5 and cfg.levels == {"httpx": "WARNING"}


@pytest.mark.parametrize("color,expected", [("always", True), ("never", False)])
def test_console_color_setting(color, expected, capsys):
    configure_logging(LoggingConfig(console_level="INFO", color=color))
    try:
        logger.info("farbtest")
        err = capsys.readouterr().err
    finally:
        logger.remove()
        logging.getLogger().handlers.clear()
    assert "farbtest" in err and ("\x1b[" in err) is expected


def test_config_rejects_unknown_color(env):
    from portal.core.config import ConfigError, load_config

    path = env / "bad.yml"
    path.write_text((env / "gateway.dev.yml").read_text(encoding="utf-8") + "logging: { color: bunt }\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="color"):
        load_config(path)


def test_access_line_carries_request_id_status_and_duration(env, logfile):
    from fastapi.testclient import TestClient

    configure_logging(LoggingConfig(console_level="ERROR", file=logfile, file_level="DEBUG"))
    client = TestClient(create_app(env / "gateway.dev.yml"), follow_redirects=False)
    client.get("/gibt/es/nicht", headers={"X-Request-Id": "req-404"})
    access = [line for line in read(logfile).splitlines() if '"GET /gibt/es/nicht HTTP/1.1" 404' in line]
    assert len(access) == 1
    assert "[req=req-404]" in access[0] and re.search(r"\(\d+\.\d ms\)", access[0])


def test_access_line_for_unhandled_exception_is_500(env, logfile, monkeypatch):
    from fastapi.testclient import TestClient

    configure_logging(LoggingConfig(console_level="ERROR", file=logfile, file_level="DEBUG"))
    app = create_app(env / "gateway.dev.yml")
    monkeypatch.setattr(app.state.portal.app_service, "find_nav_groups", lambda roles: 1 / 0)
    client = TestClient(app, raise_server_exceptions=False, follow_redirects=False)
    client.post("/login", data={"user": "alexandru", "next": "/"})
    client.get("/", headers={"X-Request-Id": "req-500"})
    text = read(logfile)
    assert re.search(r'"GET / HTTP/1.1" 500 .*\[req=req-500\]', text)


def test_stdlib_logger_levels_use_the_stdlib_logger_name(logfile):
    configure_logging(
        LoggingConfig(console_level="ERROR", file=logfile, file_level="INFO", levels={"httpx": "WARNING", "uvicorn.access": "WARNING"})
    )
    logging.getLogger("httpx").info("httpx-info")
    logging.getLogger("httpx").warning("httpx-warnung")
    logging.getLogger("uvicorn.access").info("access-info")
    logging.getLogger("uvicorn.error").info("error-info")
    text = read(logfile)
    assert "httpx-warnung" in text and "error-info" in text
    assert "httpx-info" not in text and "access-info" not in text
    assert re.search(r"httpx +: httpx-warnung", text)
