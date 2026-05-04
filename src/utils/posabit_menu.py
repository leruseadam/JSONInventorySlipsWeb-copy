"""
POSaBit menu feed: fetch store menu and match imported product names.

Docs: GET {api_base}/v1/menu_feeds/{feed_key} with Authorization: Bearer {token}.
"""
from __future__ import annotations

import difflib
import logging
import os
import re
import time
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote

import requests

logger = logging.getLogger(__name__)


def _request_timeout_sec() -> float:
    try:
        t = float(os.environ.get("POSABIT_REQUEST_TIMEOUT") or "18")
        return max(5.0, min(t, 300.0))
    except ValueError:
        return 18.0


def _menu_feed_stop_after_items() -> int:
    """Once a menu_feed response yields this many menu_items, skip trying remaining URLs."""
    try:
        v = int(os.environ.get("POSABIT_MENU_FEED_STOP_AFTER_ITEMS") or "400")
    except ValueError:
        return 400
    if v <= 0:
        return 10**9  # effectively never short-circuit
    return max(50, min(v, 100_000))


def _inventory_deadline_monotonic(data_view: bool) -> float:
    """Absolute monotonic deadline for venue inventory pagination."""
    g = _inventory_fetch_budget_deadline()
    if not data_view:
        return g
    try:
        dv = float(os.environ.get("POSABIT_DATA_VIEW_INVENTORY_BUDGET_SEC") or "28")
        dv = max(8.0, min(dv, 300.0))
    except ValueError:
        dv = 28.0
    return min(g, time.monotonic() + dv)


def _inventory_effective_max_pages(data_view: bool) -> int:
    try:
        max_pages = min(max(int(os.environ.get("POSABIT_INVENTORY_MAX_PAGES") or "250"), 1), 1000)
    except ValueError:
        max_pages = 250
    if not data_view:
        return max_pages
    try:
        cap = int(os.environ.get("POSABIT_DATA_VIEW_INVENTORY_MAX_PAGES") or "22")
        cap = min(max(cap, 1), 500)
    except ValueError:
        cap = 22
    return min(max_pages, cap)


def _inventory_fetch_budget_deadline() -> float:
    """Wall-clock stop time for the whole inventory fetch (several endpoints + pages)."""
    try:
        b = float(os.environ.get("POSABIT_INVENTORY_FETCH_BUDGET_SEC") or "45")
        b = max(15.0, min(b, 300.0))
    except ValueError:
        b = 45.0
    return time.monotonic() + b


# env key suffix -> (venue id, human label)
MENU_FEED_ENV_VARS: List[Tuple[str, str, str]] = [
    ("POSABIT_MENU_FEED_KEY_BOTHELL", "bothell", "Bothell"),
    ("POSABIT_MENU_FEED_KEY_SEATTLE", "seattle", "Seattle"),
    ("POSABIT_MENU_FEED_KEY_BURIEN", "burien", "Burien"),
    ("POSABIT_MENU_FEED_KEY_LYNNWOOD", "lynnwood", "Lynnwood"),
]

_MENU_CACHE: Dict[str, Tuple[float, List[Dict[str, Any]]]] = {}
_CACHE_TTL_SEC = 900.0

_PLACEHOLDER_FRAGMENTS = (
    "your_",
    "feed_key_here",
    "replace_me",
    "changeme",
    "xxx",
)

# Words too generic to help match long menu names (Bamboo-style strings)
_TOKEN_STOP = frozenset({
    "the", "and", "for", "med", "compliant",
    "preroll", "prerolls", "flower",
    "pack", "gram", "grams", "g", "oz", "each",
})


def _is_placeholder_key(value: str) -> bool:
    v = (value or "").strip().lower()
    if len(v) < 20:
        return True
    return any(p in v for p in _PLACEHOLDER_FRAGMENTS)


def posabit_config_from_env() -> Dict[str, Any]:
    token = (os.environ.get("POSABIT_ORDER_PAD_TOKEN") or "").strip()
    base = (os.environ.get("POSABIT_API_BASE_URL") or "https://app.posabit.com/api").strip().rstrip("/")
    use = (os.environ.get("USE_POSABIT_PRODUCTS") or "").strip().lower() in ("1", "true", "yes", "on")

    venues: List[Dict[str, str]] = []
    for env_name, vid, label in MENU_FEED_ENV_VARS:
        key = (os.environ.get(env_name) or "").strip()
        if not key or _is_placeholder_key(key):
            continue
        venues.append({"id": vid, "label": label, "env_key": env_name, "feed_key": key})

    disabled_reasons: List[str] = []
    if not use:
        disabled_reasons.append(
            "Set USE_POSABIT_PRODUCTS=true in the .env file next to app.py, then restart the server."
        )
    if not token:
        disabled_reasons.append("Set POSABIT_ORDER_PAD_TOKEN (POSaBit API bearer token) in .env.")
    if not venues:
        disabled_reasons.append(
            "Set at least one POSABIT_MENU_FEED_KEY_* to your store’s menu feed UUID (not a placeholder)."
        )

    return {
        "enabled": use and bool(token) and bool(venues),
        "token": token,
        "api_base": base,
        "venues": venues,
        "disabled_reasons": disabled_reasons,
    }


def normalize_product_name(name: Optional[str]) -> str:
    if not name:
        return ""
    t = str(name).lower().strip()
    t = re.sub(r"\s+", " ", t)
    for prefix in ("medically compliant - ", "medically compliant "):
        if t.startswith(prefix):
            t = t[len(prefix) :].strip()
    return t


def _menu_item_count(data: Dict[str, Any]) -> int:
    mf = data.get("menu_feed") if isinstance(data, dict) else None
    if not isinstance(mf, dict):
        return 0
    n = 0
    for g in mf.get("menu_groups") or []:
        if isinstance(g, dict):
            n += len(g.get("menu_items") or [])
    return n


def fetch_menu_feed_json(api_base: str, bearer_token: str, feed_key: str) -> Dict[str, Any]:
    """
    POSaBit exposes menu feeds at several paths depending on account/setup:
    - /v1/menu_feeds/{key} and /v2/menu_feeds/{key} with Bearer token
    - /{POSABIT_VENUE_TOKEN}/v2/menu_feeds/{key} only when that env is set (not the Bearer token).
    """
    base = (api_base or "").strip().rstrip("/")
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {bearer_token}",
    }

    # Never put the Bearer/API token in the URL path (404). Only POSABIT_VENUE_TOKEN if set.
    venue_path = (os.environ.get("POSABIT_VENUE_TOKEN") or "").strip()
    venue_seg = quote(venue_path, safe="-_.~") if venue_path else ""

    urls: List[str] = []
    # Prefer v2 first (often larger payload); then v1.
    urls.extend(
        [
            f"{base}/v2/menu_feeds/{feed_key}",
            f"{base}/v1/menu_feeds/{feed_key}",
        ]
    )
    if venue_path:
        urls.extend(
            [
                f"{base}/{venue_seg}/v2/menu_feeds/{feed_key}",
                f"{base}/{venue_seg}/v1/menu_feeds/{feed_key}",
            ]
        )

    failures: List[str] = []
    last_exc: Optional[BaseException] = None
    best: Optional[Dict[str, Any]] = None
    best_n = 0

    for url in urls:
        try:
            r = requests.get(url, headers=headers, timeout=_request_timeout_sec())
            if r.status_code >= 400:
                snippet = (r.text or "")[:220].replace("\n", " ").strip()
                if len(snippet) > 180:
                    snippet = snippet[:180] + "…"
                err_line = f"{r.status_code} {r.reason} — {snippet}" if snippet else f"{r.status_code} {r.reason}"
                failures.append(err_line)
                logger.warning("POSaBit menu_feed HTTP error for %s: %s", url, err_line)
                continue
            data = r.json()
            if not isinstance(data, dict):
                failures.append(
                    f"response JSON was not an object (got {type(data).__name__})"
                )
                continue
            n = _menu_item_count(data)
            # Keep first successful body, or replace if another endpoint returns more items.
            # (If every response has 0 items, n > best_n was never true before — left best=None and hid the real situation.)
            if best is None or n > best_n:
                best = data
                best_n = n
                if best_n >= _menu_feed_stop_after_items():
                    logger.info(
                        "POSaBit menu: using %d items from this endpoint (POSABIT_MENU_FEED_STOP_AFTER_ITEMS reached; skipping later URLs).",
                        best_n,
                    )
                    return best
        except requests.RequestException as e:
            last_exc = e
            failures.append(str(e))
            logger.warning("POSaBit menu_feed request failed (%s): %s", url, e)
        except ValueError as e:
            last_exc = e
            failures.append(f"invalid JSON: {e}")
            logger.warning("POSaBit menu_feed bad JSON (%s): %s", url, e)

    if best is not None and best_n > 0:
        logger.info("POSaBit menu: loaded %d products (best of %d endpoint attempts)", best_n, len(urls))
        return best

    if best is not None:
        ng = len(((best.get("menu_feed") or {}) if isinstance(best.get("menu_feed"), dict) else {}).get("menu_groups") or [])
        logger.info(
            "POSaBit menu_feed: 0 menu_items from %d URL attempts (%d menu_groups). "
            "Common for filtered/ecomm feeds; if POSABIT_FALLBACK_TO_VENUE_INVENTORY=1, SKUs load next from /venue/inventories.",
            len(urls),
            ng,
        )
        return best

    if not failures:
        failures.append(
            "no error details (no 2xx JSON object with menu_feed was retained — check network / API shape)"
        )
    uniq = " | ".join(dict.fromkeys(failures))  # preserve order, dedupe
    if len(uniq) > 800:
        uniq = uniq[:800] + "…"
    msg = f"POSaBit menu_feed: all {len(urls)} attempts failed. {uniq}"
    logger.error(msg)
    if last_exc:
        raise RuntimeError(msg) from last_exc
    raise RuntimeError(msg)


def _format_menu_qty(raw: Any) -> str:
    if raw is None:
        return ""
    if isinstance(raw, bool):
        return ""
    if isinstance(raw, float) and raw.is_integer():
        return str(int(raw))
    if isinstance(raw, int):
        return str(raw)
    s = str(raw).strip()
    return s


def _extract_menu_quantity(d: Dict[str, Any]) -> str:
    """Best-effort qty from menu_item or inventory API objects (field names vary)."""
    for k in (
        "quantity",
        "qty",
        "inventory_quantity",
        "inventoryQuantity",
        "on_hand",
        "onHand",
        "stock",
        "available_quantity",
        "availableQuantity",
        "inventory_qty",
        "qty_available",
        "remaining_quantity",
        "par_level",
        "units_available",
    ):
        if k not in d:
            continue
        v = d.get(k)
        if v is None or (isinstance(v, str) and not v.strip()):
            continue
        return _format_menu_qty(v)
    nested = d.get("inventory")
    if isinstance(nested, dict):
        return _extract_menu_quantity(nested)
    return ""


def parse_menu_products(menu_json: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Flatten menu_feed.menu_groups[].menu_items into rows for display and matching."""
    out: List[Dict[str, Any]] = []
    mf = menu_json.get("menu_feed")
    if mf is None and isinstance(menu_json.get("menu_groups"), list):
        mf = menu_json
    mf = mf or {}
    for group in mf.get("menu_groups") or []:
        category = str(group.get("name") or "").strip()
        for item in group.get("menu_items") or []:
            name = str(item.get("name") or "").strip()
            brand = str(item.get("brand") or "").strip()
            strain = str(item.get("strain") or "").strip()
            ptype = str(item.get("product_type") or "").strip()
            desc = str(item.get("description") or "").strip()
            display = name or item.get("id") or ""
            variants: List[str] = []
            for p in item.get("prices") or []:
                pn = str(p.get("name") or "").strip()
                if pn and pn not in variants:
                    variants.append(pn)
            mq = _extract_menu_quantity(item)
            out.append(
                {
                    "name": name,
                    "display": display,
                    "brand": brand,
                    "strain": strain,
                    "product_type": ptype,
                    "category": category,
                    "description": desc,
                    "variant_names": variants,
                    "menu_quantity": mq,
                }
            )
    return out


def _truthy_env(key: str, default: str = "0") -> bool:
    return (os.environ.get(key) or default).strip().lower() in ("1", "true", "yes", "on")


def parse_inventory_records(inv: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Normalize /v1|v2/venue/inventories items into the same row shape as menu_feed products."""
    out: List[Dict[str, Any]] = []
    for it in inv:
        if not isinstance(it, dict):
            continue
        name = str(it.get("name") or "").strip()
        brand = str(it.get("brand") or "").strip()
        strain = str(it.get("strain") or "").strip()
        ptype = str(
            it.get("category")
            or it.get("producttype")
            or it.get("product_type")
            or ""
        ).strip()
        desc = str(it.get("description") or "").strip()
        sku = str(it.get("sku") or it.get("productId") or it.get("product_id") or "").strip()
        display = name or sku or str(it.get("id") or "")
        variants: List[str] = []
        if name:
            variants.append(name)
        if sku:
            variants.append(sku)
        mq = _extract_menu_quantity(it)
        out.append(
            {
                "name": name,
                "display": display,
                "brand": brand,
                "strain": strain,
                "product_type": ptype,
                "category": ptype,
                "description": desc,
                "variant_names": variants,
                "menu_quantity": mq,
            }
        )
    return out


def fetch_venue_inventory_menu_rows(
    api_base: str,
    bearer_token: str,
    *,
    data_view: bool = False,
) -> List[Dict[str, Any]]:
    """
    Paginated GET /v2/venue/inventories (or v1) — real SKUs on hand when menu_feed is empty.
    See POSaBit docs: inventory[].name, brand, strain, sku, category.
    """
    base = (api_base or "").strip().rstrip("/")
    # Global paths first — the API bearer token must NOT be used as a path segment.
    endpoints: List[str] = [
        f"{base}/v2/venue/inventories",
        f"{base}/v1/venue/inventories",
    ]
    venue_path = (os.environ.get("POSABIT_VENUE_TOKEN") or "").strip()
    if venue_path:
        vs = quote(venue_path, safe="-_.~")
        endpoints.extend(
            [
                f"{base}/{vs}/v2/venue/inventories",
                f"{base}/{vs}/v1/venue/inventories",
            ]
        )
    headers = {
        "Accept": "application/json; charset=utf-8",
        "Authorization": f"Bearer {bearer_token}",
    }
    inv_deadline = _inventory_deadline_monotonic(data_view)
    max_pages = _inventory_effective_max_pages(data_view)
    logger.info(
        "POSaBit venue inventory: trying %d URL(s), first %s (budget %.0fs, max_pages=%d, data_view=%s)",
        len(endpoints),
        endpoints[0].replace(base, "") or endpoints[0],
        inv_deadline - time.monotonic(),
        max_pages,
        data_view,
    )
    try:
        per_page = min(max(int(os.environ.get("POSABIT_INVENTORY_PER_PAGE") or "200"), 1), 500)
    except ValueError:
        per_page = 200

    for ep in endpoints:
        combined: List[Dict[str, Any]] = []
        rel = ep.replace(base, "") or ep
        try:
            page = 1
            while page <= max_pages:
                if time.monotonic() >= inv_deadline:
                    logger.warning(
                        "POSaBit venue inventory: time budget exceeded at %s page %d (raise POSABIT_INVENTORY_FETCH_BUDGET_SEC or POSABIT_DATA_VIEW_FETCH_TIMEOUT_SEC).",
                        rel,
                        page,
                    )
                    break
                t_req = time.monotonic()
                try:
                    r = requests.get(
                        ep,
                        headers=headers,
                        params={"page": page, "per_page": per_page},
                        timeout=_request_timeout_sec(),
                    )
                except requests.RequestException as e:
                    logger.warning(
                        "POSaBit venue inventory: request failed %s page %d: %s",
                        rel,
                        page,
                        e,
                    )
                    break
                elapsed = time.monotonic() - t_req
                if page == 1 or logger.isEnabledFor(logging.DEBUG):
                    logger.info(
                        "POSaBit venue inventory: %s page %d -> HTTP %s in %.2fs",
                        rel,
                        page,
                        r.status_code,
                        elapsed,
                    )
                if r.status_code >= 400:
                    if page == 1:
                        hint = (r.text or "")[:120].replace("\n", " ").strip()
                        logger.info(
                            "POSaBit venue inventory: %s returned HTTP %s%s",
                            rel,
                            r.status_code,
                            f" — {hint}" if hint else "",
                        )
                    break
                try:
                    data = r.json()
                except ValueError as e:
                    logger.warning("POSaBit venue inventory: invalid JSON %s page %d: %s", rel, page, e)
                    break
                if not isinstance(data, dict):
                    break
                inv = data.get("inventory") or data.get("products") or []
                if not isinstance(inv, list):
                    break
                for row in inv:
                    if isinstance(row, dict):
                        combined.append(row)
                tp = int(data.get("total_pages") or 1)
                cp = int(data.get("current_page") or page)
                if cp >= tp or len(inv) < per_page:
                    break
                page += 1
            if combined:
                parsed = parse_inventory_records(combined)
                logger.info(
                    "POSaBit: loaded %d inventory SKUs from %s (menu feed was empty or unused)",
                    len(parsed),
                    rel,
                )
                return parsed
        except requests.RequestException as e:
            logger.warning("venue inventory %s: %s", rel, e)
        except ValueError as e:
            logger.debug("venue inventory JSON %s: %s", rel, e)
    return []


def build_match_index(
    rows: List[Dict[str, Any]],
) -> Tuple[Dict[str, str], Dict[str, str], List[str]]:
    """normalized -> POS display label and menu quantity (first row wins per normalized key)."""
    norm_to_display: Dict[str, str] = {}
    norm_to_qty: Dict[str, str] = {}
    for row in rows:
        mq = str(row.get("menu_quantity") or "").strip()
        candidates = [row["display"], row["name"]]
        candidates.extend(row.get("variant_names") or [])
        for c in candidates:
            n = normalize_product_name(c)
            if not n:
                continue
            if n not in norm_to_display:
                norm_to_display[n] = row["display"] or c
                norm_to_qty[n] = mq
    return norm_to_display, norm_to_qty, list(norm_to_display.keys())


def _word_tokens(norm_text: str) -> set:
    return {
        w
        for w in re.findall(r"[a-z0-9]+", norm_text)
        if len(w) >= 3 and w not in _TOKEN_STOP
    }


def _best_token_match(
    import_norm: str,
    norm_to_display: Dict[str, str],
    norm_keys: List[str],
    min_jaccard: float = 0.28,
) -> Tuple[Optional[str], Optional[str], float]:
    """Return (normalized_key, display, score) for best token-overlap match."""
    t_import = _word_tokens(import_norm)
    if len(t_import) < 2:
        return None, None, 0.0
    best_k: Optional[str] = None
    best_score = 0.0
    ln = len(import_norm)
    len_slack = max(24, min(120, ln // 2 + 16))
    for nk in norm_keys:
        if abs(len(nk) - ln) > len_slack:
            continue
        t_pos = _word_tokens(nk)
        if not t_pos:
            continue
        inter = len(t_import & t_pos)
        union = len(t_import | t_pos)
        j = inter / union if union else 0.0
        if j > best_score:
            best_score = j
            best_k = nk
    if best_k is not None and best_score >= min_jaccard:
        return best_k, norm_to_display.get(best_k), best_score
    return None, None, best_score


def find_pos_menu_match(
    import_name: str,
    norm_to_display: Dict[str, str],
    norm_to_qty: Dict[str, str],
    norm_keys: List[str],
    fuzzy_cutoff: float = 0.72,
) -> Tuple[bool, Optional[str], str, str]:
    """
    Returns (matched, pos_display_name_or_none, kind, menu_quantity_str).
    kind: exact | contains | fuzzy | tokens | none
    """
    n = normalize_product_name(import_name)
    if not n:
        return False, None, "none", ""
    if n in norm_to_display:
        return True, norm_to_display[n], "exact", norm_to_qty.get(n, "")
    best_display: Optional[str] = None
    best_key: Optional[str] = None
    ln = len(n)
    # Large catalogs: skip substring checks between wildly different lengths (major speedup).
    len_slack = max(24, min(120, ln // 2 + 16))
    for nk in norm_keys:
        lk = len(nk)
        if abs(lk - ln) > len_slack:
            continue
        if n in nk or nk in n:
            if lk < 4 and ln > 12:
                continue
            if best_key is None or abs(ln - lk) < abs(ln - len(best_key)):
                best_key = nk
                best_display = norm_to_display[nk]
    if best_display and best_key is not None:
        return True, best_display, "contains", norm_to_qty.get(best_key, "")
    # get_close_matches on the full catalog is O(N) per call and freezes Data View for large menus.
    fuzzy_candidates = [
        nk for nk in norm_keys if abs(len(nk) - ln) <= len_slack
    ]
    if len(fuzzy_candidates) > 600:
        fuzzy_candidates = fuzzy_candidates[:600]
    close = (
        difflib.get_close_matches(n, fuzzy_candidates, n=1, cutoff=fuzzy_cutoff)
        if fuzzy_candidates
        else []
    )
    if close:
        ck = close[0]
        return True, norm_to_display[ck], "fuzzy", norm_to_qty.get(ck, "")
    _nk, disp, _score = _best_token_match(n, norm_to_display, norm_keys)
    if disp and _nk is not None:
        return True, disp, "tokens", norm_to_qty.get(_nk, "")
    return False, None, "none", ""


def get_menu_rows_cached(
    api_base: str,
    token: str,
    feed_key: str,
    cache_key: str,
    ttl_sec: float = _CACHE_TTL_SEC,
    *,
    for_data_view: bool = False,
) -> List[Dict[str, Any]]:
    now = time.time()
    eff_key = f"{cache_key}:dv" if for_data_view else cache_key
    ent = _MENU_CACHE.get(eff_key)
    if ent and (now - ent[0]) < ttl_sec and ent[1]:
        return ent[1]
    data = fetch_menu_feed_json(api_base, token, feed_key)
    rows = parse_menu_products(data)
    inv_attempted = False
    if not rows and _truthy_env("POSABIT_FALLBACK_TO_VENUE_INVENTORY", "1"):
        inv_attempted = True
        logger.info("POSaBit: fetching venue inventory (menu_feed had no items to match)")
        rows = fetch_venue_inventory_menu_rows(api_base, token, data_view=for_data_view)
    if not rows:
        if inv_attempted:
            logger.warning(
                "POSaBit: venue inventory returned 0 SKUs (check token can access /v2/venue/inventories; "
                "set POSABIT_VENUE_TOKEN only if POSaBit gave a separate path token — never use the Bearer token in the URL)."
            )
        elif not _truthy_env("POSABIT_FALLBACK_TO_VENUE_INVENTORY", "1"):
            logger.info(
                "POSaBit: 0 matchable products; set POSABIT_FALLBACK_TO_VENUE_INVENTORY=1 to try /venue/inventories when the menu feed is empty."
            )
    if rows:
        _MENU_CACHE[eff_key] = (now, rows)
    return rows
