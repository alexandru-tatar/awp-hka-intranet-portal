"""Router-Schicht: REST-/HTML-Schnittstelle, ruft nur Services und Views auf."""

from portal.router.auth_router import router as auth_router
from portal.router.dev_login_router import router as dev_login_router
from portal.router.dev_router import router as dev_router
from portal.router.health_router import router as health_router
from portal.router.nav_router import router as nav_router
from portal.router.oidc_router import router as oidc_router
from portal.router.page_router import router as page_router

__all__ = [
    "auth_router", "dev_login_router", "dev_router", "health_router",
    "nav_router", "oidc_router", "page_router",
]
