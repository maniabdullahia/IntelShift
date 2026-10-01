"""
net_guard.py — outbound-fetch safety for the crawler.

Two jobs, both process-wide:

1. SSRF guard. Every URL we fetch ultimately comes from a user (store URL,
   competitor URL, picked pages). Without a check, "http://127.0.0.1:27017",
   "http://169.254.169.254/latest/meta-data/" or "http://localhost:8000/docs"
   would be fetched and — through /debug-fetch or an analysis result — read
   back. `is_public_url()` resolves the host and rejects loopback, private,
   link-local, reserved and multicast addresses, non-http(s) schemes and
   embedded credentials. We check the URL BEFORE fetching and the FINAL URL
   after redirects (so a public URL that 302s to an internal one is discarded).

   Set ALLOW_PRIVATE_URLS=1 to disable (local testing against a dev store only).

2. Browser concurrency cap. Each Playwright fetch launches a full Chromium
   (~150–300 MB). FastAPI runs sync endpoints in a 40-thread pool, so a burst of
   analyses could start dozens of browsers at once and OOM the box.
   `browser_slot()` is a bounded semaphore around every launch.
   MAX_BROWSERS (default 3) sets the cap; BROWSER_SLOT_WAIT_S (default 300) is
   how long a caller waits for a slot before giving up (fail-open: the caller
   treats it like a failed render, exactly as it handles a browser crash).
"""
from __future__ import annotations

import ipaddress
import os
import socket
import threading
import time
from contextlib import contextmanager
from typing import Dict, Optional, Tuple
from urllib.parse import urlparse


class UnsafeUrlError(ValueError):
    """Raised when a URL points at a non-public address or a disallowed scheme."""


class BrowserBusyError(RuntimeError):
    """Raised when no browser slot frees up within BROWSER_SLOT_WAIT_S."""


def _truthy(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes"}


_DNS_TTL_S = 600
_dns_cache: Dict[str, Tuple[float, bool]] = {}
_dns_lock = threading.Lock()

_BLOCKED_HOSTNAMES = {"localhost", "localhost.localdomain", "ip6-localhost", "ip6-loopback"}


def _ip_is_public(ip_str: str) -> bool:
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        return False
    # IPv4-mapped IPv6 (::ffff:127.0.0.1) must be judged by the embedded v4.
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
        ip = ip.ipv4_mapped
    return not (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    )


def _host_is_public(host: str) -> bool:
    host = (host or "").strip().lower().rstrip(".")
    if not host or host in _BLOCKED_HOSTNAMES or host.endswith(".localhost") or host.endswith(".internal"):
        return False
    # Literal IP — no DNS needed.
    try:
        ipaddress.ip_address(host.strip("[]"))
        return _ip_is_public(host.strip("[]"))
    except ValueError:
        pass

    now = time.time()
    with _dns_lock:
        hit = _dns_cache.get(host)
        if hit and now - hit[0] < _DNS_TTL_S:
            return hit[1]
    try:
        infos = socket.getaddrinfo(host, None)
        addrs = {info[4][0] for info in infos}
        ok = bool(addrs) and all(_ip_is_public(a) for a in addrs)
    except socket.gaierror:
        # Unresolvable here — let the fetch itself fail normally. An
        # unresolvable name can't reach an internal service either.
        ok = True
    except Exception:
        ok = False
    with _dns_lock:
        _dns_cache[host] = (now, ok)
    return ok


def is_public_url(url: str) -> bool:
    """True when `url` is http(s), carries no credentials, and every address its
    host resolves to is public. Always True when ALLOW_PRIVATE_URLS=1."""
    if _truthy("ALLOW_PRIVATE_URLS"):
        return True
    try:
        p = urlparse(url if "://" in (url or "") else f"https://{url}")
    except Exception:
        return False
    if p.scheme not in ("http", "https"):
        return False
    if p.username or p.password:
        return False
    return _host_is_public(p.hostname or "")


def assert_public_url(url: str) -> str:
    if not is_public_url(url):
        raise UnsafeUrlError(f"Refusing to fetch non-public URL: {url}")
    return url


def blocked_result(url: str, fetch_method: str) -> Tuple[None, str, dict]:
    """The (html, final_url, headers) triple every fetcher returns, for a URL the
    guard refused — shaped like any other failed fetch so callers degrade."""
    return None, url, {
        "status_code": None,
        "blocked": True,
        "fetch_method": fetch_method,
        "fetch_error": "unsafe_url",
    }


# ── Browser concurrency cap ─────────────────────────────────────────────────
def _max_browsers() -> int:
    try:
        return max(1, int(os.getenv("MAX_BROWSERS", "3")))
    except ValueError:
        return 3


_browser_sem = threading.BoundedSemaphore(_max_browsers())
_active = 0
_active_lock = threading.Lock()


@contextmanager
def browser_slot(wait_s: Optional[float] = None):
    """Hold one of MAX_BROWSERS slots for the duration of a Chromium session."""
    global _active
    if wait_s is None:
        try:
            wait_s = float(os.getenv("BROWSER_SLOT_WAIT_S", "300"))
        except ValueError:
            wait_s = 300.0
    if not _browser_sem.acquire(timeout=wait_s):
        raise BrowserBusyError(f"No browser slot free after {wait_s:.0f}s")
    with _active_lock:
        _active += 1
    try:
        yield
    finally:
        with _active_lock:
            _active -= 1
        _browser_sem.release()


def browser_stats() -> dict:
    with _active_lock:
        return {"maxBrowsers": _max_browsers(), "activeBrowsers": _active}
