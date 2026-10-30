"""Prüfung der Assertion (06 §5). Auszug aus dem gemeinsamen Katalog F1–F22 (06 §9)."""

import asyncio
import time

import jwt
import pytest
from conftest import ISSUER, KEYS, PRIVATE_KEY, make_token
from platform_sdk.errors import VerifyError
from platform_sdk.verify import verify


def check(token: str) -> dict:
    return asyncio.run(verify(token, keys=KEYS, issuer=ISSUER, audience="noten"))


def expect_error(token: str, code: str) -> None:
    with pytest.raises(VerifyError) as exc:
        check(token)
    assert exc.value.code == code


def test_f1_gueltig():
    assert check(make_token())["sub"] == "student-test"


def test_f2_mit_email():
    assert check(make_token(email="erika@test.hka.example"))["email"] == "erika@test.hka.example"


def test_f3_aud_als_text():
    assert check(make_token(aud="noten"))


def test_f4_innerhalb_der_toleranz():
    assert check(make_token(exp=int(time.time()) - 3))


def test_f5_abgelaufen():
    expect_error(make_token(exp=int(time.time()) - 40), "Expired")


def test_f6_noch_nicht_gueltig():
    expect_error(make_token(iat=int(time.time()) + 30), "NotYetValid")


def test_f7_falsche_zielgruppe():
    expect_error(make_token(aud=["other", "portal"]), "WrongAudience")


def test_f8_falscher_aussteller():
    expect_error(make_token(iss="https://boese.example/"), "WrongIssuer")


def test_f9_alg_none():
    expect_error(jwt.encode({"sub": "x"}, None, algorithm="none", headers={"kid": "test-key"}), "BadAlgorithm")


def test_f12_veraenderte_daten():
    header, _, signature = make_token().split(".")
    other_payload = make_token(roles=["platform-admin"]).split(".")[1]
    expect_error(f"{header}.{other_payload}.{signature}", "BadSignature")


def test_f14_unbekannter_schluessel():
    token = jwt.encode({"sub": "x"}, PRIVATE_KEY, algorithm="RS256", headers={"kid": "fremd"})
    expect_error(token, "UnknownKey")


def test_f15_ohne_kid():
    expect_error(jwt.encode({"sub": "x"}, PRIVATE_KEY, algorithm="RS256"), "MissingKid")


def test_f17_version_2():
    expect_error(make_token(v=2), "UnsupportedVersion")


def test_f18_rollen_kein_array():
    expect_error(make_token(roles="student"), "BadRoles")


def test_f19_leeres_sub():
    expect_error(make_token(sub=""), "MissingSubject")


def test_f20_unbekannter_claim():
    assert check(make_token(foo="bar"))


@pytest.mark.parametrize("token", ["", "a.b", "x.y.z", "a" * 9000])
def test_f21_f22_kaputt(token):
    expect_error(token, "Malformed")
