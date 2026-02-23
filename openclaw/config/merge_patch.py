"""
JSON Merge Patch (RFC 7396) implementation — matches openclaw/src/config/merge-patch.ts
"""
from __future__ import annotations

import copy
from typing import Any, Optional


def apply_merge_patch(
    base: Any,
    patch: Any,
    merge_object_arrays_by_id: bool = False,
) -> Any:
    """
    Apply a JSON Merge Patch (RFC 7396) to base.

    Rules:
    - If patch is None: return None (signals deletion when used in parent context).
    - If patch is a dict: recursively merge into base dict; None values delete keys.
    - If patch is array and merge_object_arrays_by_id=True: merge by "id" field.
    - Otherwise: patch replaces base.

    Matches TS applyMergePatch().
    """
    if patch is None:
        return None

    if not isinstance(patch, dict):
        # Arrays and scalars replace entirely (unless array merge is enabled)
        if merge_object_arrays_by_id and isinstance(patch, list):
            return _merge_arrays_by_id(base, patch)
        return copy.deepcopy(patch)

    if not isinstance(base, dict):
        base = {}

    result = dict(base)
    for key, value in patch.items():
        if value is None:
            # null in patch means delete the key
            result.pop(key, None)
        else:
            existing = result.get(key)
            result[key] = apply_merge_patch(existing, value, merge_object_arrays_by_id=merge_object_arrays_by_id)

    return result


def _merge_arrays_by_id(base: Any, patch: list) -> list:
    """
    Merge two arrays of objects by their "id" field.

    Objects in patch with a matching "id" in base are merged;
    others are appended.
    """
    if not isinstance(base, list):
        return copy.deepcopy(patch)

    base_by_id: dict = {}
    base_order = []
    for item in base:
        item_id = item.get("id") if isinstance(item, dict) else None
        if item_id is not None:
            base_by_id[item_id] = item
            base_order.append(item_id)
        else:
            base_order.append(item)

    result_by_id = dict(base_by_id)
    new_items = []
    for patch_item in patch:
        if isinstance(patch_item, dict):
            item_id = patch_item.get("id")
            if item_id is not None and item_id in result_by_id:
                result_by_id[item_id] = apply_merge_patch(result_by_id[item_id], patch_item, merge_object_arrays_by_id=True)
            else:
                new_items.append(copy.deepcopy(patch_item))
        else:
            new_items.append(copy.deepcopy(patch_item))

    result = []
    for entry in base_order:
        if isinstance(entry, str) and entry in result_by_id:
            result.append(result_by_id[entry])
        else:
            result.append(entry)
    result.extend(new_items)
    return result


__all__ = [
    "apply_merge_patch",
]
