"""Shape coercion for small-model JSON.

The grammar guarantees valid JSON, not the *asked-for* JSON. A small model
given a schema will return the list unwrapped, the key singular, or the items
as bare strings -- all valid, all previously breaking callers.

These helpers recover the content instead of discarding it. A claim written as
a bare string is still a claim.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


def as_items(data: Any, key: str) -> list:
    """The list named `key`, from however the model wrapped it. Never None."""
    if isinstance(data, list):
        return data

    if not isinstance(data, dict):
        logger.warning("model returned %s, expected an object or list", type(data).__name__)
        return []

    for candidate in (key, key.rstrip("s"), f"{key}_list"):
        value = data.get(candidate)
        if isinstance(value, list):
            return value
        if isinstance(value, dict):
            return [value]  # singular object where a list was asked for

    # Last resort: exactly one list-valued field, whatever it is called.
    lists = [v for v in data.values() if isinstance(v, list)]
    if len(lists) == 1:
        logger.info("model used an unexpected key for %r; recovered by shape", key)
        return lists[0]

    logger.warning("no list found for %r in model output (keys: %s)", key, list(data))
    return []


def as_dict(item: Any, text_key: str) -> dict:
    """One list entry as a dict. A bare string becomes `{text_key: item}`."""
    if isinstance(item, dict):
        return item
    if isinstance(item, str):
        return {text_key: item}
    logger.warning("dropping %s entry in model list", type(item).__name__)
    return {}


def one_of(value: Any, allowed: tuple[str, ...], default: str) -> str:
    """Constrain a model enum to `allowed`.

    An invented category is not harmless: it reaches the canvas as a node label
    and the interface as a filter matching nothing.
    """
    if isinstance(value, str):
        v = value.strip().lower().replace(" ", "_").replace("-", "_")
        if v in allowed:
            return v
    if value not in (None, ""):
        logger.info("model returned %r, not one of %s; using %r", value, allowed, default)
    return default


def as_str_list(value: Any) -> list[str]:
    """A list of strings. A lone string becomes one element -- models drop the
    brackets when there is only one item."""
    if isinstance(value, str):
        return [value] if value else []
    if not isinstance(value, list):
        return []
    return [str(v) for v in value if v not in (None, "")]
