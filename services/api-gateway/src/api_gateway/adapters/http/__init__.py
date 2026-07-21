"""HTTP adapters."""

from api_gateway.adapters.http.routes import register_proxy_routes, router

__all__ = ["register_proxy_routes", "router"]
