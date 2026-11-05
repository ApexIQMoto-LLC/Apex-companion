"""Assemble bounded, authorized operational context for explicitly invoked AI.

Only table-level totals/whitelisted statuses go to OpenAI. This module never
passes credentials, user identity, full telemetry, or raw database rows.
"""
from __future__ import annotations

from .dashboard_state import bounded_ai_context, due
from .steamworks import SteamworksReader


def gather_dashboard_context(*, monitor, cloud_cached, steam_cached, marketing,
                             news, signed_in, cloud_last=None, steam_last=None,
                             cloud_ttl_minutes=5, steam_ttl_minutes=30,
                             steam_reader_factory=SteamworksReader):
    """Refresh stale sources before answering, then return sanitized prompt.

    Network operations are performed by the caller's background worker, never
    on the tkinter event/UI thread. Previously obtained data can be retained
    if an update fails; the prompt explicitly identifies unavailable sources.
    """
    cloud, steam = cloud_cached, steam_cached
    refreshed = set()
    errors = []
    if signed_in and monitor is not None:
        if cloud is None or due(cloud_last, cloud_ttl_minutes):
            try:
                cloud = monitor.snapshot()
                refreshed.add('cloud')
            except (OSError, RuntimeError, ValueError, TimeoutError) as exc:
                errors.append('A.R.I.S Cloud refresh failed (' + type(exc).__name__ + ')')
        if steam is None or due(steam_last, steam_ttl_minutes):
            try:
                steam = steam_reader_factory(monitor).fetch(days=30)
                refreshed.add('steam')
            except (OSError, RuntimeError, ValueError, TimeoutError) as exc:
                errors.append('Steam report refresh failed (' + type(exc).__name__ + ')')

    context = bounded_ai_context(cloud, steam, marketing, news, bool(signed_in))
    if errors:
        context += '\nREFRESH WARNINGS: ' + '; '.join(errors)
        context += '\nCached values, if shown, can be stale. Never claim access to missing values.'
    return context[:5400], cloud, steam, frozenset(refreshed), tuple(errors)
