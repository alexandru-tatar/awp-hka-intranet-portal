"""Sessions und Login-Transaktionen in Redis (02 §4).

Schlüssel: ``sess:{sid}`` (Hash), ``usr:{sha256(sub)}:sessions`` (Set der Session-IDs eines Benutzers,
für die Sperrung) und ``oidc:{lid}`` (Login-Transaktion, wird genau einmal verbraucht).
"""

from __future__ import annotations

import hashlib
import json
import secrets
import time
from typing import Any

from loguru import logger
from redis import Redis
from redis.exceptions import RedisError

from .sessions import Session


def _user_key(sub: str) -> str:
    """Redis-Schlüssel des Sets der Sessions eines Benutzers.

    :param sub: Subject des IdP
    :return: ``usr:{sha256(sub)}:sessions``
    :rtype: str
    """
    return f"usr:{hashlib.sha256(sub.encode()).hexdigest()}:sessions"


class RedisSessionStore:
    """Session-Store in Redis.

    Die Inaktivitätsgrenze wird über ``EXPIRE`` erzwungen, die absolute Lebensdauer beim Lesen.
    ``last_seen`` wird höchstens alle ``touch_min_interval_seconds`` geschrieben.
    """
    def __init__(self, client: Redis, *, idle_seconds: int, absolute_seconds: int,
                 touch_min_interval_seconds: int) -> None:
        """Konstruktor mit Redis-Client und Zeitgrenzen.

        :param client: Redis-Client mit ``decode_responses=True``
        :param idle_seconds: Inaktivitätsgrenze
        :param absolute_seconds: Maximale Lebensdauer
        :param touch_min_interval_seconds: Mindestabstand zwischen zwei Aktualisierungen von ``last_seen``
        """
        self._redis = client
        self._idle = idle_seconds
        self._absolute = absolute_seconds
        self._touch_min = touch_min_interval_seconds

    def create(self, sub: str, name: str, roles: frozenset[str], id_token: str | None = None) -> Session:
        """Eine Session anlegen und im Set des Benutzers vermerken.

        :param sub: Subject des IdP
        :param name: Anzeigename
        :param roles: Rollen
        :param id_token: ID-Token des IdP für die Abmeldung beim IdP
        :return: Die neue Session
        :rtype: Session
        """
        session = Session(
            sid=secrets.token_urlsafe(32),
            sub=sub,
            name=name,
            roles=roles,
            csrf=secrets.token_urlsafe(16),
            id_token=id_token,
        )
        now = int(time.time())
        key = f"sess:{session.sid}"
        user_key = _user_key(sub)
        with self._redis.pipeline() as pipe:
            pipe.hset(key, mapping={
                "sub": sub, "name": name, "roles": json.dumps(sorted(roles)),
                "csrf": session.csrf, "created": now, "last_seen": now,
                **({"id_token": id_token} if id_token else {}),
            })
            pipe.expire(key, self._idle)
            pipe.sadd(user_key, session.sid)
            pipe.expire(user_key, self._absolute)
            pipe.execute()
        return session

    def get(self, sid: str | None) -> Session | None:
        """Eine Session lesen.

        Abgelaufene Sessions (absolute Lebensdauer) werden gelöscht. Sonst wird bei Bedarf ``last_seen``
        und die Inaktivitätsgrenze aktualisiert.

        :param sid: Session-ID, ``None`` oder leer ergibt ``None``
        :return: Die Session oder ``None``
        :rtype: Session | None
        :raises redis.exceptions.RedisError: Falls Redis nicht antwortet
        """
        if not sid:
            return None
        key = f"sess:{sid}"
        data: dict[str, Any] = self._redis.hgetall(key)
        if not data:
            return None
        now = int(time.time())
        if now - int(data["created"]) > self._absolute:
            self.delete(sid)
            return None
        if now - int(data["last_seen"]) >= self._touch_min:
            with self._redis.pipeline() as pipe:
                pipe.hset(key, "last_seen", now)
                pipe.expire(key, self._idle)
                pipe.execute()
        return Session(
            sid=sid,
            sub=data["sub"],
            name=data["name"],
            roles=frozenset(json.loads(data["roles"])),
            csrf=data["csrf"],
            id_token=data.get("id_token"),
        )

    def delete(self, sid: str) -> None:
        """Eine Session und ihren Eintrag im Set des Benutzers löschen.

        :param sid: Session-ID
        """
        key = f"sess:{sid}"
        sub = self._redis.hget(key, "sub")
        with self._redis.pipeline() as pipe:
            if sub:
                pipe.srem(_user_key(sub), sid)
            pipe.delete(key)
            pipe.execute()

    def ping(self) -> bool:
        """Ob Redis antwortet.

        :return: ``True``, falls erreichbar; bei Fehler ``False`` (wird protokolliert)
        :rtype: bool
        """
        try:
            return bool(self._redis.ping())
        except RedisError:
            logger.error("redis_unavailable op=ping")
            return False


class RedisLoginStore:
    """Login-Transaktionen ``oidc:{lid}``: beim Login geschrieben, im Callback genau einmal verbraucht."""

    def __init__(self, client: Redis, *, ttl_seconds: int) -> None:
        """Konstruktor mit Redis-Client und Lebensdauer.

        :param client: Redis-Client mit ``decode_responses=True``
        :param ttl_seconds: Lebensdauer einer Transaktion
        """
        self._redis = client
        self._ttl = ttl_seconds

    def put(self, lid: str, record: dict[str, str]) -> None:
        """Eine Transaktion speichern.

        :param lid: Transaktions-ID (steht im Login-Cookie)
        :param record: State, Nonce, PKCE-Verifier und Zielpfad
        """
        self._redis.set(f"oidc:{lid}", json.dumps(record), ex=self._ttl)

    def pop(self, lid: str) -> dict[str, str] | None:
        """Eine Transaktion lesen und im selben Schritt löschen (``GETDEL``).

        :param lid: Transaktions-ID
        :return: Die Transaktion oder ``None``, falls unbekannt, abgelaufen oder schon verbraucht
        :rtype: dict[str, str] | None
        """
        raw = self._redis.getdel(f"oidc:{lid}")
        return json.loads(raw) if raw else None
