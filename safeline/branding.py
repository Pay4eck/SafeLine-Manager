"""Compatibility branding layer around the pinned Hiddify Panel runtime.

This module deliberately does not rename hiddifypanel, its routes, services,
database objects, environment variables, or install paths.  It owns only the
SafeLine presentation boundary while the inherited internals remain stable.
"""

from __future__ import annotations

from pathlib import Path
import re
from typing import Any

from jinja2 import ChoiceLoader, FileSystemLoader

from .brand import BRAND


PACKAGE_ROOT = Path(__file__).resolve().parent
STATIC_ROOT = PACKAGE_ROOT / "static"
TEMPLATE_ROOT = PACKAGE_ROOT / "templates"


def create_app(*args: Any, **kwargs: Any):
    """Create the inherited Panel app and attach the SafeLine presentation."""
    import hiddifypanel

    return install_branding(hiddifypanel.create_app(*args, **kwargs))


def install_branding(app):
    """Attach the SafeLine UI overlay to an initialized Flask application."""
    if app.extensions.get("safeline_branding"):
        return app

    from flask import Blueprint, current_app, g, request, send_from_directory, url_for
    from markupsafe import escape

    brand_blueprint = Blueprint("safeline_brand", __name__)

    @brand_blueprint.get("/<proxy_path>/safeline-static/<path:filename>")
    def asset(proxy_path: str, filename: str):
        del proxy_path
        response = send_from_directory(STATIC_ROOT, filename)
        if "/assets/" in request.path:
            response.cache_control.public = True
            response.cache_control.max_age = 31536000
            response.cache_control.immutable = True
        return response

    app.register_blueprint(brand_blueprint)
    app.jinja_loader = ChoiceLoader(
        [FileSystemLoader(str(TEMPLATE_ROOT)), app.jinja_loader]
    )
    app.jinja_env.globals["brand"] = BRAND.as_dict()

    # APIFlask uses these values when generating the administrator API schema.
    if hasattr(app, "title"):
        app.title = f"{BRAND.manager_name} API"
    if hasattr(app, "description"):
        app.description = BRAND.description
    if isinstance(getattr(app, "info", None), dict):
        # Preserve the inherited license object verbatim; it is attribution,
        # not product chrome.
        app.info.update(
            {
                "description": (
                    f"{BRAND.manager_name} API, based on {BRAND.upstream_name}."
                ),
                "termsOfService": BRAND.repository_url,
                "contact": {
                    "name": f"{BRAND.manager_name} support",
                    "url": f"{BRAND.repository_url}/issues",
                },
            }
        )
    _install_notification_branding()

    @app.after_request
    def apply_safeline_presentation(response):
        path = request.path.rstrip("/")

        if response.headers.get("WWW-Authenticate") == 'Basic realm="Hiddify"':
            response.headers["WWW-Authenticate"] = f'Basic realm="{BRAND.manager_name}"'

        if path.endswith("/api/v2/user/me") and response.is_json:
            payload = response.get_json(silent=True)
            if isinstance(payload, dict):
                try:
                    _brand_profile_payload(payload, g.proxy_path, url_for)
                except Exception:
                    current_app.logger.exception(
                        "SafeLine could not read the real Panel branding context"
                    )
                else:
                    response.set_data(current_app.json.dumps(payload))

        if path.endswith("/manifest.webmanifest") and response.is_json:
            payload = response.get_json(silent=True)
            if isinstance(payload, dict):
                payload.update(
                    {
                        "name": BRAND.full_name,
                        "short_name": BRAND.product_name,
                        "description": BRAND.description,
                        "icons": [
                            {
                                "src": url_for(
                                    "safeline_brand.asset",
                                    proxy_path=g.proxy_path,
                                    filename="brand/safeline-mark.svg",
                                ),
                                "sizes": "any",
                                "type": "image/svg+xml",
                                "purpose": "maskable any",
                            }
                        ],
                    }
                )
                response.set_data(current_app.json.dumps(payload))

        if response.is_json:
            payload = response.get_json(silent=True)
            if isinstance(payload, dict) and isinstance(payload.get("message"), str):
                payload["message"] = payload["message"].replace(
                    "This version of Hiddify Panel is outdated",
                    f"This version of {BRAND.manager_name} is outdated",
                )
                response.set_data(current_app.json.dumps(payload))

        if response.mimetype == "text/html" and not response.direct_passthrough:
            html = response.get_data(as_text=True)
            if "</head>" in html and "id=\"safeline-branding\"" not in html:
                asset_url = url_for(
                    "safeline_brand.asset",
                    proxy_path=g.proxy_path,
                    filename="brand/branding.js",
                )
                icon_url = url_for(
                    "safeline_brand.asset",
                    proxy_path=g.proxy_path,
                    filename="brand/safeline-mark.svg",
                )
                integration = (
                    f'<meta name="description" content="{escape(BRAND.description)}">'
                    f'<link rel="icon" type="image/svg+xml" href="{escape(icon_url)}">'
                    f'<script id="safeline-branding" defer src="{escape(asset_url)}" '
                    f'data-product="{escape(BRAND.product_name)}" '
                    f'data-full-name="{escape(BRAND.full_name)}" '
                    f'data-manager="{escape(BRAND.manager_name)}" '
                    f'data-version="{escape(BRAND.version)}" '
                    f'data-repository="{escape(BRAND.repository_url)}" '
                    f'data-upstream="{escape(BRAND.upstream_repository_url)}" '
                    f'data-icon="{escape(icon_url)}"></script>'
                )
                response.set_data(html.replace("</head>", integration + "</head>", 1))

        return response

    # Flask executes application-wide after_request callbacks in reverse order.
    # Put SafeLine first so it runs last, after the inherited callback has set
    # headers such as the Basic-auth realm.
    callbacks = app.after_request_funcs.get(None, [])
    if callbacks and callbacks[-1] is apply_safeline_presentation:
        callbacks.insert(0, callbacks.pop())

    app.extensions["safeline_branding"] = {"brand": BRAND.as_dict()}
    return app


def _brand_profile_payload(payload: dict[str, Any], proxy_path: str, url_for) -> None:
    """Replace only upstream defaults; preserve administrator custom branding."""
    from hiddifypanel.models.config import hconfig
    from hiddifypanel.models.config_enum import ConfigEnum

    custom_title = bool(hconfig(ConfigEnum.branding_title))
    custom_message = bool(hconfig(ConfigEnum.branding_freetext))
    custom_site = bool(hconfig(ConfigEnum.branding_site))

    if not custom_title:
        payload["brand_title"] = BRAND.full_name
        payload["brand_icon_url"] = url_for(
            "safeline_brand.asset",
            proxy_path=proxy_path,
            filename="brand/safeline-mark.svg",
            _external=True,
        )
    if not custom_message:
        payload["admin_message_html"] = (
            f"{BRAND.full_name} is ready. Contact your administrator for support."
        )
    if not custom_site:
        payload["admin_message_url"] = BRAND.repository_url


def _install_notification_branding() -> None:
    """Brand inherited Telegram message copy without changing bot behavior."""
    from hiddifypanel.panel.commercial.telegrambot import information

    if getattr(information._, "__safeline_branding__", False):
        return
    upstream_gettext = information._

    def safeline_gettext(*args: Any, **kwargs: Any):
        translated = upstream_gettext(*args, **kwargs)
        if isinstance(translated, str):
            return re.sub(r"\bhiddify\b", BRAND.full_name, translated, flags=re.IGNORECASE)
        return translated

    safeline_gettext.__safeline_branding__ = True
    information._ = safeline_gettext
