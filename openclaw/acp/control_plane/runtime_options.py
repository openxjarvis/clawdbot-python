"""ACP runtime option validation and normalization — mirrors src/acp/control-plane/runtime-options.ts"""
from __future__ import annotations

import json
import os
import re
from typing import Any

from openclaw.acp.runtime.errors import AcpRuntimeError

_MAX_RUNTIME_MODE_LENGTH = 64
_MAX_MODEL_LENGTH = 200
_MAX_PERMISSION_PROFILE_LENGTH = 80
_MAX_CWD_LENGTH = 4096
_MIN_TIMEOUT_SECONDS = 1
_MAX_TIMEOUT_SECONDS = 24 * 60 * 60
_MAX_BACKEND_OPTION_KEY_LENGTH = 64
_MAX_BACKEND_OPTION_VALUE_LENGTH = 512
_MAX_BACKEND_EXTRAS = 32

_SAFE_OPTION_KEY_RE = re.compile(r"^[a-z0-9][a-z0-9._:\-]*$", re.IGNORECASE)


def _fail_invalid_option(message: str) -> None:
    raise AcpRuntimeError("ACP_INVALID_RUNTIME_OPTION", message)


def normalize_text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def _validate_no_control_chars(value: str, field: str) -> str:
    for ch in value:
        code = ord(ch)
        if code < 32 or code == 127:
            _fail_invalid_option(f"{field} must not include control characters.")
    return value


def _validate_bounded_text(value: Any, field: str, max_length: int) -> str:
    normalized = normalize_text(value)
    if not normalized:
        _fail_invalid_option(f"{field} must not be empty.")
    if len(normalized) > max_length:
        _fail_invalid_option(f"{field} must be at most {max_length} characters.")
    return _validate_no_control_chars(normalized, field)


def _validate_backend_option_key(raw_key: Any) -> str:
    key = _validate_bounded_text(raw_key, "ACP config key", _MAX_BACKEND_OPTION_KEY_LENGTH)
    if not _SAFE_OPTION_KEY_RE.match(key):
        _fail_invalid_option(
            "ACP config key must use letters, numbers, dots, colons, underscores, or dashes."
        )
    return key


def _validate_backend_option_value(raw_value: Any) -> str:
    return _validate_bounded_text(raw_value, "ACP config value", _MAX_BACKEND_OPTION_VALUE_LENGTH)


def validate_runtime_mode_input(raw_mode: Any) -> str:
    return _validate_bounded_text(raw_mode, "Runtime mode", _MAX_RUNTIME_MODE_LENGTH)


def validate_runtime_model_input(raw_model: Any) -> str:
    return _validate_bounded_text(raw_model, "Model id", _MAX_MODEL_LENGTH)


def validate_runtime_permission_profile_input(raw_profile: Any) -> str:
    return _validate_bounded_text(raw_profile, "Permission profile", _MAX_PERMISSION_PROFILE_LENGTH)


def validate_runtime_cwd_input(raw_cwd: Any) -> str:
    cwd = _validate_bounded_text(raw_cwd, "Working directory", _MAX_CWD_LENGTH)
    if not os.path.isabs(cwd):
        _fail_invalid_option(f'Working directory must be an absolute path. Received "{cwd}".')
    return cwd


def validate_runtime_timeout_seconds_input(raw_timeout: Any) -> int:
    if not isinstance(raw_timeout, (int, float)) or raw_timeout != raw_timeout:
        _fail_invalid_option("Timeout must be a positive integer in seconds.")
    timeout = round(float(raw_timeout))
    if timeout < _MIN_TIMEOUT_SECONDS or timeout > _MAX_TIMEOUT_SECONDS:
        _fail_invalid_option(
            f"Timeout must be between {_MIN_TIMEOUT_SECONDS} and {_MAX_TIMEOUT_SECONDS} seconds."
        )
    return timeout


def parse_runtime_timeout_seconds_input(raw_timeout: Any) -> int:
    normalized = normalize_text(raw_timeout)
    if not normalized or not re.match(r"^\d+$", normalized):
        _fail_invalid_option("Timeout must be a positive integer in seconds.")
    return validate_runtime_timeout_seconds_input(int(normalized))


def validate_runtime_config_option_input(raw_key: Any, raw_value: Any) -> dict[str, str]:
    return {
        "key": _validate_backend_option_key(raw_key),
        "value": _validate_backend_option_value(raw_value),
    }


def validate_runtime_option_patch(patch: dict | None) -> dict:
    if not patch:
        return {}
    allowed_keys = {
        "runtimeMode", "runtime_mode",
        "model",
        "cwd",
        "permissionProfile", "permission_profile",
        "timeoutSeconds", "timeout_seconds",
        "backendExtras", "backend_extras",
    }
    for key in patch:
        if key not in allowed_keys:
            _fail_invalid_option(f'Unknown runtime option "{key}".')

    next_opts: dict[str, Any] = {}

    def _get(d: dict, *keys: str) -> Any:
        for k in keys:
            if k in d:
                return d[k], True
        return None, False

    runtime_mode_val, runtime_mode_present = _get(patch, "runtimeMode", "runtime_mode")
    if runtime_mode_present:
        if runtime_mode_val is None:
            next_opts["runtimeMode"] = None
        else:
            next_opts["runtimeMode"] = validate_runtime_mode_input(runtime_mode_val)

    model_val, model_present = _get(patch, "model")
    if model_present:
        if model_val is None:
            next_opts["model"] = None
        else:
            next_opts["model"] = validate_runtime_model_input(model_val)

    cwd_val, cwd_present = _get(patch, "cwd")
    if cwd_present:
        if cwd_val is None:
            next_opts["cwd"] = None
        else:
            next_opts["cwd"] = validate_runtime_cwd_input(cwd_val)

    perm_val, perm_present = _get(patch, "permissionProfile", "permission_profile")
    if perm_present:
        if perm_val is None:
            next_opts["permissionProfile"] = None
        else:
            next_opts["permissionProfile"] = validate_runtime_permission_profile_input(perm_val)

    timeout_val, timeout_present = _get(patch, "timeoutSeconds", "timeout_seconds")
    if timeout_present:
        if timeout_val is None:
            next_opts["timeoutSeconds"] = None
        else:
            next_opts["timeoutSeconds"] = validate_runtime_timeout_seconds_input(timeout_val)

    extras_val, extras_present = _get(patch, "backendExtras", "backend_extras")
    if extras_present:
        if extras_val is None:
            next_opts["backendExtras"] = None
        elif not isinstance(extras_val, dict) or isinstance(extras_val, list):
            _fail_invalid_option("Backend extras must be a key/value object.")
        else:
            entries = list(extras_val.items())
            if len(entries) > _MAX_BACKEND_EXTRAS:
                _fail_invalid_option(
                    f"Backend extras must include at most {_MAX_BACKEND_EXTRAS} entries."
                )
            extras: dict[str, str] = {}
            for k, v in entries:
                validated = validate_runtime_config_option_input(k, v)
                extras[validated["key"]] = validated["value"]
            next_opts["backendExtras"] = extras or None

    return next_opts


def normalize_runtime_options(options: dict | None) -> dict:
    opts = options or {}
    result: dict[str, Any] = {}
    for key_camel, key_snake in [
        ("runtimeMode", "runtime_mode"),
        ("model", "model"),
        ("cwd", "cwd"),
        ("permissionProfile", "permission_profile"),
    ]:
        val = opts.get(key_camel) or opts.get(key_snake)
        normalized = normalize_text(val)
        if normalized:
            result[key_camel] = normalized

    timeout = opts.get("timeoutSeconds") or opts.get("timeout_seconds")
    if isinstance(timeout, (int, float)) and timeout == timeout and timeout > 0:
        result["timeoutSeconds"] = round(float(timeout))

    raw_extras = opts.get("backendExtras") or opts.get("backend_extras")
    if isinstance(raw_extras, dict):
        extras = {
            k2: v2
            for k, v in raw_extras.items()
            if (k2 := normalize_text(k)) and (v2 := normalize_text(v))
        }
        if extras:
            result["backendExtras"] = extras

    return result


def merge_runtime_options(current: dict | None, patch: dict | None) -> dict:
    c = normalize_runtime_options(current)
    p = normalize_runtime_options(validate_runtime_option_patch(patch))
    merged_extras = {**(c.get("backendExtras") or {}), **(p.get("backendExtras") or {})}
    merged = {**c, **p}
    if merged_extras:
        merged["backendExtras"] = merged_extras
    return normalize_runtime_options(merged)


def resolve_runtime_options_from_meta(meta: dict) -> dict:
    normalized = normalize_runtime_options(meta.get("runtimeOptions"))
    if normalized.get("cwd") or not meta.get("cwd"):
        return normalized
    return normalize_runtime_options({**normalized, "cwd": meta["cwd"]})


def runtime_options_equal(a: dict | None, b: dict | None) -> bool:
    return json.dumps(normalize_runtime_options(a), sort_keys=True) == \
           json.dumps(normalize_runtime_options(b), sort_keys=True)


def build_runtime_control_signature(options: dict) -> str:
    normalized = normalize_runtime_options(options)
    extras = sorted(
        (normalized.get("backendExtras") or {}).items(),
        key=lambda t: t[0],
    )
    return json.dumps({
        "runtimeMode": normalized.get("runtimeMode"),
        "model": normalized.get("model"),
        "permissionProfile": normalized.get("permissionProfile"),
        "timeoutSeconds": normalized.get("timeoutSeconds"),
        "backendExtras": extras,
    })


def build_runtime_config_option_pairs(options: dict) -> list[tuple[str, str]]:
    normalized = normalize_runtime_options(options)
    pairs: dict[str, str] = {}
    if normalized.get("model"):
        pairs["model"] = normalized["model"]
    if normalized.get("permissionProfile"):
        pairs["approval_policy"] = normalized["permissionProfile"]
    if "timeoutSeconds" in normalized:
        pairs["timeout"] = str(normalized["timeoutSeconds"])
    for k, v in (normalized.get("backendExtras") or {}).items():
        if k not in pairs:
            pairs[k] = v
    return list(pairs.items())


def infer_runtime_option_patch_from_config_option(key: str, value: str) -> dict:
    validated = validate_runtime_config_option_input(key, value)
    normalized_key = validated["key"].lower()
    if normalized_key == "model":
        return {"model": validate_runtime_model_input(validated["value"])}
    if normalized_key in ("approval_policy", "permission_profile", "permissions"):
        return {"permissionProfile": validate_runtime_permission_profile_input(validated["value"])}
    if normalized_key in ("timeout", "timeout_seconds"):
        return {"timeoutSeconds": parse_runtime_timeout_seconds_input(validated["value"])}
    if normalized_key == "cwd":
        return {"cwd": validate_runtime_cwd_input(validated["value"])}
    return {"backendExtras": {validated["key"]: validated["value"]}}
