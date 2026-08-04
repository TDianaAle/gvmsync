# SPDX-FileCopyrightText: 2025-2026 Diana Tichy
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""XML response parsing and GMP call retry utilities."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import Any, TypeVar

from lxml import etree
from lxml.etree import _Element as Element

from ._errors import GvmSyncConnectionError, XmlParseError

logger = logging.getLogger(__name__)

T = TypeVar("T")

MAX_RETRIES = 3
RETRY_DELAY = 2


def parse_response(
    data: Any,
) -> Element | None:
    """Parse a GMP response into an lxml Element.

    Handles string, bytes, and objects with a ``to_string()``
    method (as returned by python-gvm with the default
    string transform).

    Args:
        data: The raw GMP response.

    Returns:
        Parsed lxml Element, or ``None`` if *data* is ``None``.

    Raises:
        XmlParseError: If the response cannot be parsed.
    """
    if data is None:
        return None
    if hasattr(data, "to_string"):
        data = data.to_string()
    if isinstance(data, str):
        data = data.encode()
    try:
        return etree.fromstring(data)
    except etree.XMLSyntaxError as exc:
        raise XmlParseError(str(exc)) from exc


def select_entities(
    root: Element,
    entity_name: str,
) -> list[Element]:
    """Return the top-level entities of a GMP response.

    GMP embeds elements that share the name of an enclosing
    element, so a descendant search (``.//``) returns far more
    than the actual result set:

    * every entity carries a ``<permissions>`` block listing
      the effective permissions on it, each an inner
      ``<permission>``;
    * with ``details=True`` a ``<report>`` wraps an inner
      ``<report>`` holding the results, and an OSP
      ``<scanner>`` embeds a ``<scanner>`` describing the
      scan engine.

    Those inner elements are metadata, not results: they
    duplicate ids or carry none at all.  Only direct children
    of the response root are real entities.

    Args:
        root: The parsed ``<get_*_response>`` element.
        entity_name: The element name to select, e.g.
            ``scanner``, ``task``, ``report``, ``permission``.

    Returns:
        The entity elements, skipping any without an id.
    """
    return [elem for elem in root.xpath(f"./{entity_name}") if elem.get("id")]


def call_with_retry(
    func: Callable[..., T],
    *args: Any,
    max_retries: int = MAX_RETRIES,
    retry_delay: int = RETRY_DELAY,
    **kwargs: Any,
) -> T:
    """Call a GMP function with retry on connection loss.

    Args:
        func: The GMP method to call.
        *args: Positional arguments forwarded to *func*.
        max_retries: Maximum number of attempts.
        retry_delay: Seconds to wait between retries.
        **kwargs: Keyword arguments forwarded to *func*.

    Returns:
        The result of *func*.

    Raises:
        GvmSyncConnectionError: If the connection is lost
            after all retry attempts.
    """
    for attempt in range(1, max_retries + 1):
        try:
            return func(*args, **kwargs)
        except BrokenPipeError:
            if attempt < max_retries:
                logger.warning(
                    "Connection broken (attempt %d/%d), retrying in %ds...",
                    attempt,
                    max_retries,
                    retry_delay,
                )
                time.sleep(retry_delay)
            else:
                raise GvmSyncConnectionError(
                    f"Connection lost after {max_retries} attempts"
                ) from None

    msg = "Unreachable: retry loop exited without return"
    raise GvmSyncConnectionError(msg)
