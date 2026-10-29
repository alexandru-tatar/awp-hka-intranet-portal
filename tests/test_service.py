"""Service-Schicht: Menü, Zugriffsentscheidung, Sessions (ohne HTTP)."""

import pytest

from portal.app import create_app
from portal.service import (
    ForbiddenError,
    InvalidCsrfError,
    LoginRequiredError,
    NotFoundError,
    UnavailableError,
    UnknownUserError,
)


@pytest.fixture
def portal(env):
    return create_app(env / "gateway.dev.yml").state.portal


def test_create_session_unknown_user(portal):
    with pytest.raises(UnknownUserError):
        portal.session_write_service.create("gibt-es-nicht")


def test_session_roundtrip_and_delete_needs_csrf(portal):
    session = portal.session_write_service.create("alexandru")
    assert portal.session_service.find_by_id(session.sid).sub == session.sub

    with pytest.raises(InvalidCsrfError):
        portal.session_write_service.delete(session.sid, "falsch")
    portal.session_write_service.delete(session.sid, session.csrf)
    with pytest.raises(NotFoundError):
        portal.session_service.find_by_id(session.sid)


def test_find_authorized_unknown_app(portal):
    with pytest.raises(NotFoundError):
        portal.app_service.find_authorized("gibt-es-nicht", None)


def test_find_authorized_without_session(portal):
    with pytest.raises(LoginRequiredError):
        portal.app_service.find_authorized("noten", None)


def test_find_authorized_not_routed_is_not_found(portal):
    session = portal.session_write_service.create("admin")
    with pytest.raises(NotFoundError):
        portal.app_service.find_authorized("abschlussarbeiten", session)


def test_find_all_sorted_by_name(portal):
    names = [app.name.casefold() for app in portal.app_service.find_all()]
    assert names == sorted(names)


def test_nav_groups_empty_without_roles(portal):
    assert portal.app_service.find_nav_groups(frozenset()) == []


def test_find_authorized_role_before_status(portal):
    # Fremde ohne passende Rolle erfahren nichts über den Status (403 vor 503).
    gast = portal.session_write_service.create("gast")
    with pytest.raises(ForbiddenError):
        portal.app_service.find_authorized("raumbuchung", gast)


def test_find_authorized_unhealthy_and_healthy(portal):
    max_ = portal.session_write_service.create("max")
    with pytest.raises(UnavailableError):
        portal.app_service.find_authorized("raumbuchung", max_)
    alexandru = portal.session_write_service.create("alexandru")
    assert portal.app_service.find_authorized("noten", alexandru).slug == "noten"
