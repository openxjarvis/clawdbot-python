"""
Skill/plugin static code scanner — mirrors TS src/security/skill-scanner.ts.

Scans installed skill and plugin files for dangerous code patterns in 7 categories:
1. dangerous-exec     — direct subprocess/exec calls
2. dynamic-code       — eval, exec, compile of untrusted code
3. crypto-mining      — mining pool connections, CPU-intensive XMR/ETH patterns
4. exfiltration       — suspicious data upload / external POST with sensitive data
5. obfuscation        — base64/hex decode→exec, atob, fromCharCode chains
6. env-harvesting     — bulk os.environ reads or env snapshot sending
7. suspicious-network — raw socket connections, TOR, proxy bypass

Results are cached by (file_size, mtime) to avoid repeated scans.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import re

logger = logging.getLogger(__name__)

SkillScanRuleId = Literal[
    "dangerous-exec",
    "dynamic-code",
    "crypto-mining",
    "exfiltration",
    "obfuscation",
    "env-harvesting",
    "suspicious-network",
]


@dataclass
class SkillScanMatch:
    rule_id: SkillScanRuleId
    description: str
    line: int
    snippet: str


@dataclass
class SkillScanResult:
    file_path: str
    matches: list[SkillScanMatch] = field(default_factory=list)
    error: str | None = None

    @property
    def clean(self) -> bool:
        return not self.matches and not self.error


@dataclass
class _ScanRule:
    id: SkillScanRuleId
    description: str
    patterns: list[re.Pattern[str]]


# ---------------------------------------------------------------------------
# Rule definitions — mirrors TS skill-scanner.ts 7 rules
# ---------------------------------------------------------------------------

_RULES: list[_ScanRule] = [
    _ScanRule(
        id="dangerous-exec",
        description="Direct subprocess or os.system execution",
        patterns=[
            re.compile(r"\bsubprocess\.(?:run|call|Popen|check_output|check_call)\s*\(", re.IGNORECASE),
            re.compile(r"\bos\.(?:system|popen|execv?[pe]?)\s*\(", re.IGNORECASE),
            re.compile(r"\bchild_process\b", re.IGNORECASE),
            re.compile(r"\bexecSync\s*\(", re.IGNORECASE),
            re.compile(r"\bspawnSync\s*\(", re.IGNORECASE),
            re.compile(r"\b__import__\s*\(\s*['\"]subprocess", re.IGNORECASE),
        ],
    ),
    _ScanRule(
        id="dynamic-code",
        description="Dynamic code execution (eval/exec/compile of runtime strings)",
        patterns=[
            re.compile(r"\beval\s*\(", re.IGNORECASE),
            re.compile(r"\bexec\s*\((?!\s*['\"])", re.IGNORECASE),  # exec( not followed by string literal
            re.compile(r"\bcompile\s*\(\s*(?:input|request|data|body|text|msg)\b", re.IGNORECASE),
            re.compile(r"\b__import__\s*\(", re.IGNORECASE),
            re.compile(r"\bimportlib\.import_module\s*\(", re.IGNORECASE),
            # JS-style
            re.compile(r"\bnew\s+Function\s*\(", re.IGNORECASE),
            re.compile(r"\bFunction\s*\(\s*['\"][^'\"]*['\"],\s*['\"]", re.IGNORECASE),
        ],
    ),
    _ScanRule(
        id="crypto-mining",
        description="Cryptocurrency mining indicators",
        patterns=[
            re.compile(r"\bmonero\b|\bxmr\b|\bstratum\+tcp://", re.IGNORECASE),
            re.compile(r"\bxmrig\b|\bwildrig\b|\bcpuminer\b|\bnsfminer\b", re.IGNORECASE),
            re.compile(r"\bpool\.minergate\.com\b|\bpool\.supportxmr\.com\b", re.IGNORECASE),
            re.compile(r"coinhive\.min\.js|miner\.start\s*\(", re.IGNORECASE),
            re.compile(r"\bGetTickCount64\b.*\bthrottle\b|\bSetThreadPriority\b.*\bIDLE_PRIORITY_CLASS\b"),
        ],
    ),
    _ScanRule(
        id="exfiltration",
        description="Suspicious data exfiltration patterns",
        patterns=[
            re.compile(
                r"requests\.post\s*\([^)]*\b(?:environ|password|token|secret|api_key)\b",
                re.IGNORECASE,
            ),
            re.compile(
                r"urllib\.request\.urlopen\s*\([^)]*\b(?:data=|POST)\b",
                re.IGNORECASE,
            ),
            re.compile(
                r"\bsmtplib\b.*\bsendmail\b",
                re.IGNORECASE,
            ),
            # Large data upload to external IP/domain
            re.compile(
                r"(?:http|https)://(?:\d{1,3}\.){3}\d{1,3}(?::\d+)?/(?:upload|exfil|data|collect)",
                re.IGNORECASE,
            ),
        ],
    ),
    _ScanRule(
        id="obfuscation",
        description="Code obfuscation patterns (base64 decode→exec, fromCharCode)",
        patterns=[
            re.compile(
                r"base64\.b64decode\s*\([^)]+\)\s*[,;)\n].*(?:exec|eval|compile)",
                re.IGNORECASE | re.DOTALL,
            ),
            re.compile(
                r"(?:bytes\.fromhex|binascii\.unhexlify)\s*\([^)]+\).*(?:exec|eval)",
                re.IGNORECASE,
            ),
            re.compile(r"\\u[0-9a-fA-F]{4}.*\\u[0-9a-fA-F]{4}.*\\u[0-9a-fA-F]{4}"),  # long unicode escape chain
            re.compile(r"String\.fromCharCode\s*\((?:\d+\s*,\s*){5,}", re.IGNORECASE),
            re.compile(r"atob\s*\([^)]+\)", re.IGNORECASE),
            # Python codecs decode trick
            re.compile(r"\.decode\s*\(\s*['\"](?:rot.?13|base64|zip|bz2)['\"]", re.IGNORECASE),
        ],
    ),
    _ScanRule(
        id="env-harvesting",
        description="Bulk environment variable harvesting",
        patterns=[
            re.compile(r"\bos\.environ\s*(?:\.copy\s*\(\)|\.items\s*\()|dict\s*\(\s*os\.environ\s*\)", re.IGNORECASE),
            re.compile(r"\bprocess\.env\b", re.IGNORECASE),
            re.compile(r"\bgetenv\s*\(\s*['\"](?:HOME|PATH|USER|LOGNAME|TOKEN|SECRET|API_KEY|PASSWORD)['\"]", re.IGNORECASE),
            # Snapshot + send pattern
            re.compile(r"os\.environ.*requests\.(post|get)\b", re.IGNORECASE | re.DOTALL),
        ],
    ),
    _ScanRule(
        id="suspicious-network",
        description="Suspicious raw network connections (Tor, SOCKS, raw TCP)",
        patterns=[
            re.compile(r"\bsocket\.socket\s*\(.*SOCK_STREAM\b.*\bconnect\b", re.IGNORECASE),
            re.compile(r"9050|9150", ),  # Tor SOCKS ports
            re.compile(r"socks5h?://|socks4a?://", re.IGNORECASE),
            re.compile(r"\.onion\b", re.IGNORECASE),
            re.compile(r"\brequests\.get\s*\([^)]*proxies\s*=", re.IGNORECASE),
        ],
    ),
]


# ---------------------------------------------------------------------------
# File scan cache: (file_size, mtime_ns) -> SkillScanResult
# ---------------------------------------------------------------------------

_SCAN_CACHE: dict[tuple[int, int], SkillScanResult] = {}

_SCANNABLE_EXTENSIONS: frozenset[str] = frozenset([
    ".py", ".js", ".ts", ".mjs", ".cjs", ".sh", ".bash",
])

_MAX_FILE_SIZE = 2 * 1024 * 1024  # 2 MB — skip very large files


def scan_skill_file(file_path: Path) -> SkillScanResult:
    """
    Scan a single skill/plugin file for dangerous patterns.

    Results are cached by (size, mtime_ns).

    Args:
        file_path: Path to the file to scan.

    Returns:
        SkillScanResult with matches and/or error.
    """
    try:
        st = file_path.stat()
        cache_key = (st.st_size, st.st_mtime_ns)
        if cache_key in _SCAN_CACHE:
            return _SCAN_CACHE[cache_key]

        if st.st_size > _MAX_FILE_SIZE:
            result = SkillScanResult(file_path=str(file_path))
            _SCAN_CACHE[cache_key] = result
            return result

        content = file_path.read_text(encoding="utf-8", errors="replace")
        lines = content.splitlines()
        matches: list[SkillScanMatch] = []

        for rule in _RULES:
            for pattern in rule.patterns:
                for lineno, line in enumerate(lines, start=1):
                    if pattern.search(line):
                        snippet = line.strip()[:120]
                        matches.append(SkillScanMatch(
                            rule_id=rule.id,
                            description=rule.description,
                            line=lineno,
                            snippet=snippet,
                        ))
                        break  # one match per rule per file is enough

        result = SkillScanResult(file_path=str(file_path), matches=matches)
        _SCAN_CACHE[cache_key] = result
        return result

    except PermissionError as exc:
        return SkillScanResult(file_path=str(file_path), error=f"Permission denied: {exc}")
    except Exception as exc:
        return SkillScanResult(file_path=str(file_path), error=str(exc))


def scan_skill_directory(skill_dir: Path) -> list[SkillScanResult]:
    """
    Recursively scan all scannable files in a skill/plugin directory.

    Args:
        skill_dir: Root directory to scan.

    Returns:
        List of SkillScanResult (one per scanned file).
    """
    results: list[SkillScanResult] = []
    if not skill_dir.exists():
        return results
    for root, _dirs, files in os.walk(skill_dir):
        for fname in files:
            fpath = Path(root) / fname
            if fpath.suffix.lower() in _SCANNABLE_EXTENSIONS:
                result = scan_skill_file(fpath)
                if not result.clean:
                    results.append(result)
    return results


__all__ = [
    "SkillScanMatch",
    "SkillScanResult",
    "scan_skill_file",
    "scan_skill_directory",
]
