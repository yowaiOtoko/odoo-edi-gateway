import logging
import os
from typing import Any

_logger = logging.getLogger(__name__)


def _get_dsn(env=None) -> str:
    dsn = os.getenv('ODOO_ADDON_SENTRY_DSN', '').strip()
    if dsn:
        return dsn
    if env:
        params = env['ir.config_parameter'].sudo()
        return (
            (params.get_param('odoo_addon_sentry_dsn') or '').strip()
            or (params.get_param('sentry_dsn') or '').strip()
        )
    return ''


def _ensure_sentry(env=None):
    try:
        import sentry_sdk  # type: ignore
    except Exception:
        return None

    dsn = _get_dsn(env)
    if not dsn:
        return None

    if sentry_sdk.Hub.current.client is None:
        sentry_sdk.init(
            dsn=dsn,
            environment=(os.getenv('ODOO_ADDON_RUNNING_ENV') or os.getenv('ODOO_ENV') or 'odoo'),
            traces_sample_rate=0.0,
        )
    return sentry_sdk


def _stringify(value: Any) -> str:
    if value is None:
        return ''
    text = str(value)
    return text[:2000]


def capture_exception(exc: Exception, env=None, context: dict | None = None):
    sentry_sdk = _ensure_sentry(env)
    if not sentry_sdk:
        return

    try:
        with sentry_sdk.push_scope() as scope:
            if context:
                for key, value in context.items():
                    scope.set_extra(key, _stringify(value))
            sentry_sdk.capture_exception(exc)
    except Exception as sentry_exc:
        _logger.debug('Failed to report exception to Sentry: %s', sentry_exc)
