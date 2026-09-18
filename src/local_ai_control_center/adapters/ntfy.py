"""Notifiers: saying that a run finished, to a machine the user named.

`Notifier` is an abstract port, like the provider and the converter. `NtfyNotifier` posts
to an ntfy server the user hosts themselves, reached over their own private network
(ADR-027).

Two rules shape everything here. A notification never carries document content: it says
which skill ran, how it ended and how long it took, and nothing about what was read or
written. And delivery is best effort: a notifier that cannot reach its server does not fail
a run that already succeeded.

The transport is injectable so the test suite can exercise this without opening a socket -
the egress guard in `conftest` still forbids reaching the network, and it stays that way.
"""

from __future__ import annotations

import os
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping

from local_ai_control_center.core.config import Config
from local_ai_control_center.ports.notifier import (
    Delivery,
    Notification,
    Notifier,
    NotifierMisconfigured,
)

Post = Callable[[str, bytes, Mapping[str, str], float], int]
"""Send a body to a URL with headers and return the status code."""

_TIMEOUT_SECONDS = 10.0
_MAX_BODY_BYTES = 3900
"""ntfy refuses bodies much larger than this, and a notification has no business being one."""

_ALLOWED_SCHEMES = frozenset({"http", "https"})
_CONTROL_CHARACTERS = frozenset(chr(code) for code in range(32)) | {chr(127)}


def header_safe(value: str) -> str:
    """Fold ``value`` into something that can be an HTTP header, losing accents not meaning.

    Three separate hazards, and it is worth naming them because only the first is obvious.
    An HTTP header is encoded latin-1, so a character outside it raises `UnicodeEncodeError`
    - a `ValueError`, not an `OSError`, which would sail straight past a handler catching
    network failures and take down a run that had already produced its answer. A carriage
    return would be header injection, and the standard library refuses it by raising, which
    lands in the same place. And ntfy reads titles as ASCII.

    So accents are folded rather than dropped: an "o" with an acute over it decomposes into
    an "o" and the accent, the accent is discarded, and the word stays readable. Only what
    has no ASCII form at all - an emoji, another alphabet - becomes "?". A notification with
    an approximated title is delivered; an exception is a crashed run.
    """
    decomposed = unicodedata.normalize("NFKD", value)
    kept = [
        " " if character in _CONTROL_CHARACTERS else character
        for character in decomposed
        if not unicodedata.combining(character)
    ]
    return "".join(kept).encode("ascii", "replace").decode("ascii").strip()


def _clipped(text: str, limit: int) -> bytes:
    """Encode ``text``, cut to ``limit`` bytes without splitting a character in half.

    Cutting the encoded bytes directly is the obvious way and it is wrong: a body in Spanish
    ends on half of an accented character and what arrives is invalid UTF-8.
    """
    encoded = text.encode("utf-8")
    if len(encoded) <= limit:
        return encoded
    return encoded[:limit].decode("utf-8", "ignore").encode("utf-8")


class NtfyNotifier(Notifier):
    """Publish to an ntfy topic on a server the user hosts.

    Authenticates with a bearer token when one is configured. Everything sensitive is read
    from the environment: the configuration names the variable, it does not hold the value.

    Basic credentials are **not** supported. A helper for them lived here, was tested, and
    was called by nothing - there was no configuration field for a username either, so no
    user could have reached it, while this docstring said otherwise. Removed rather than
    wired: an untested authentication path added to satisfy a sentence is worse than the
    sentence being true (ADR-058).
    """

    def __init__(
        self,
        server_url: str,
        topic: str,
        token: str = "",
        priority: int = 3,
        tags: tuple[str, ...] = (),
        post: Post | None = None,
    ) -> None:
        """Create the notifier for one server and topic.

        Raises ``NotifierMisconfigured`` when the server is not an ``http`` or ``https``
        URL, or when the topic is empty.

        The configuration refuses an address that is not a URL before this runs (ADR-060),
        so on that path this is a second line rather than the only one. It stays because
        this class is public and constructible: nothing should be able to hand it a scheme
        and have LACC post a body to it.
        """
        parsed = urllib.parse.urlparse(server_url)
        if parsed.scheme.lower() not in _ALLOWED_SCHEMES or not parsed.netloc:
            raise NotifierMisconfigured(
                f"the ntfy server must be an http or https URL, not {server_url!r}"
            )
        if not topic.strip():
            raise NotifierMisconfigured("the ntfy topic is empty")

        self._url = f"{server_url.rstrip('/')}/{urllib.parse.quote(topic, safe='')}"
        self._token = token
        self._priority = priority
        self._tags = tags
        self._post = post if post is not None else _post_with_urllib

    @property
    def name(self) -> str:
        """Identify this transport."""
        return "ntfy"

    def send(self, notification: Notification) -> Delivery:
        """Post the notification, translating any failure into a reported result."""
        headers = {
            "Title": header_safe(notification.title),
            "Priority": str(self._priority),
        }
        tags = tuple(dict.fromkeys((*self._tags, *notification.tags)))
        if tags:
            headers["Tags"] = header_safe(",".join(tags))
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"

        body = _clipped(notification.body, _MAX_BODY_BYTES)
        try:
            status = self._post(self._url, body, headers, _TIMEOUT_SECONDS)
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as error:
            return Delivery(transport=self.name, delivered=False, detail=f"{error}")

        if 200 <= status < 300:
            return Delivery(transport=self.name, delivered=True, detail=f"HTTP {status}")
        return Delivery(transport=self.name, delivered=False, detail=f"HTTP {status}")


def _post_with_urllib(url: str, body: bytes, headers: Mapping[str, str], timeout: float) -> int:
    """The real transport. Replaced in tests so nothing reaches the network there."""
    request = urllib.request.Request(url, data=body, headers=dict(headers), method="POST")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        code = response.getcode()
    return int(code)


def notifier_from_config(config: Config, post: Post | None = None) -> Notifier | None:
    """Build the configured notifier, or ``None`` when there is nothing to build.

    Returns ``None`` unless notifications are enabled, network access is permitted, the
    configuration names a server, and the environment holds a topic. Each of those is a
    separate way of saying "not configured", and none of them is an error: a run that
    cannot notify is still a run that worked.

    The address comes from the configuration and the topic from the environment, which is
    the split ADR-030 draws: destinations are written down, secrets are named (ADR-060).
    """
    settings = config.notifier.ntfy
    if not settings.enabled or not config.network_access:
        return None

    server = settings.server_url.strip()
    topic = os.environ.get(settings.topic_env, "").strip()
    if not server or not topic:
        return None

    return NtfyNotifier(
        server_url=server,
        topic=topic,
        token=os.environ.get(settings.token_env, "").strip(),
        priority=settings.priority,
        tags=settings.tags,
        post=post,
    )
