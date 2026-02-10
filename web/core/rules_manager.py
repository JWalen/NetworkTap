"""Suricata rule management."""

import logging
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from core.config import get_config

logger = logging.getLogger("networktap.rules")

# Default rule paths
RULE_PATHS = [
    "/etc/suricata/rules",
    "/var/lib/suricata/rules",
    "/usr/share/suricata/rules",
]

DISABLED_RULES_FILE = "/etc/suricata/disable.conf"
ENABLE_RULES_FILE = "/etc/suricata/enable.conf"
THRESHOLD_FILE = "/etc/suricata/threshold.config"


@dataclass
class SuricataRule:
    sid: int
    msg: str
    action: str
    enabled: bool
    classtype: str
    severity: int
    raw: str
    file_path: str
    line_number: int


def find_rule_directories() -> list[Path]:
    """Find Suricata rule directories."""
    dirs = []
    for path in RULE_PATHS:
        p = Path(path)
        if p.exists() and p.is_dir():
            dirs.append(p)
    return dirs


def parse_rule(line: str, file_path: str = "", line_number: int = 0) -> Optional[SuricataRule]:
    """Parse a single Suricata rule line."""
    line = line.strip()
    
    # Check if disabled
    enabled = True
    if line.startswith("#"):
        enabled = False
        line = line[1:].strip()
    
    # Skip non-rules
    if not line or not re.match(r"^(alert|drop|reject|pass|log)", line):
        return None
    
    # Extract action
    action_match = re.match(r"^(\w+)", line)
    action = action_match.group(1) if action_match else "alert"
    
    # Extract SID
    sid_match = re.search(r"sid:\s*(\d+)", line)
    if not sid_match:
        return None
    sid = int(sid_match.group(1))
    
    # Extract message
    msg_match = re.search(r'msg:\s*"([^"]+)"', line)
    msg = msg_match.group(1) if msg_match else "Unknown"
    
    # Extract classtype
    class_match = re.search(r"classtype:\s*([^;]+)", line)
    classtype = class_match.group(1).strip() if class_match else ""
    
    # Extract severity/priority
    priority_match = re.search(r"priority:\s*(\d+)", line)
    severity = int(priority_match.group(1)) if priority_match else 3
    
    return SuricataRule(
        sid=sid,
        msg=msg,
        action=action,
        enabled=enabled,
        classtype=classtype,
        severity=severity,
        raw=line,
        file_path=file_path,
        line_number=line_number,
    )


def list_rules(
    search: Optional[str] = None,
    enabled_only: bool = False,
    classtype: Optional[str] = None,
    limit: int = 500,
) -> list[dict]:
    """List Suricata rules with optional filtering."""
    rules = []
    rule_dirs = find_rule_directories()
    
    if not rule_dirs:
        logger.warning("No Suricata rule directories found")
        return rules
    
    for rule_dir in rule_dirs:
        for rule_file in rule_dir.glob("*.rules"):
            try:
                with open(rule_file, "r", encoding="utf-8", errors="ignore") as f:
                    for line_num, line in enumerate(f, 1):
                        rule = parse_rule(line, str(rule_file), line_num)
                        if rule is None:
                            continue
                        
                        # Apply filters
                        if enabled_only and not rule.enabled:
                            continue
                        
                        if classtype and rule.classtype != classtype:
                            continue
                        
                        if search:
                            search_lower = search.lower()
                            if (search_lower not in rule.msg.lower() and
                                search_lower not in str(rule.sid) and
                                search_lower not in rule.classtype.lower()):
                                continue
                        
                        rules.append({
                            "sid": rule.sid,
                            "msg": rule.msg,
                            "action": rule.action,
                            "enabled": rule.enabled,
                            "classtype": rule.classtype,
                            "severity": rule.severity,
                            "file": rule_file.name,
                            "line": rule.line_number,
                        })
                        
                        if len(rules) >= limit:
                            return rules
            except Exception as e:
                logger.error("Error reading %s: %s", rule_file, e)
    
    return rules


def get_rule(sid: int) -> Optional[dict]:
    """Get a specific rule by SID."""
    rule_dirs = find_rule_directories()
    
    for rule_dir in rule_dirs:
        for rule_file in rule_dir.glob("*.rules"):
            try:
                with open(rule_file, "r", encoding="utf-8", errors="ignore") as f:
                    for line_num, line in enumerate(f, 1):
                        rule = parse_rule(line, str(rule_file), line_num)
                        if rule and rule.sid == sid:
                            return {
                                "sid": rule.sid,
                                "msg": rule.msg,
                                "action": rule.action,
                                "enabled": rule.enabled,
                                "classtype": rule.classtype,
                                "severity": rule.severity,
                                "raw": rule.raw,
                                "file": str(rule_file),
                                "line": rule.line_number,
                            }
            except Exception as e:
                logger.error("Error reading %s: %s", rule_file, e)
    
    return None


def set_rule_enabled(sid: int, enabled: bool) -> tuple[bool, str]:
    """Enable or disable a rule using Suricata's disable.conf."""
    # Find the rule first
    rule = get_rule(sid)
    if rule is None:
        return False, f"Rule SID {sid} not found"
    
    disable_path = Path(DISABLED_RULES_FILE)
    enable_path = Path(ENABLE_RULES_FILE)
    
    try:
        # Read current disable list
        disabled_sids = set()
        if disable_path.exists():
            with open(disable_path, "r") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        try:
                            disabled_sids.add(int(line))
                        except ValueError:
                            pass
        
        # Update
        if enabled:
            disabled_sids.discard(sid)
        else:
            disabled_sids.add(sid)
        
        # Write back
        disable_path.parent.mkdir(parents=True, exist_ok=True)
        with open(disable_path, "w") as f:
            f.write("# Disabled rules (managed by NetworkTap)\n")
            for s in sorted(disabled_sids):
                f.write(f"{s}\n")
        
        logger.info("Rule SID %d %s", sid, "enabled" if enabled else "disabled")
        return True, f"Rule {'enabled' if enabled else 'disabled'}"
    
    except Exception as e:
        logger.error("Error updating rule state: %s", e)
        return False, str(e)


def set_rule_threshold(
    sid: int,
    threshold_type: str = "limit",
    track: str = "by_src",
    count: int = 1,
    seconds: int = 60,
) -> tuple[bool, str]:
    """Set a threshold for a rule."""
    if threshold_type not in ("limit", "threshold", "both"):
        return False, "Invalid threshold type"
    
    if track not in ("by_src", "by_dst"):
        return False, "Invalid track value"
    
    rule = get_rule(sid)
    if rule is None:
        return False, f"Rule SID {sid} not found"
    
    threshold_path = Path(THRESHOLD_FILE)
    
    try:
        # Read existing thresholds
        lines = []
        if threshold_path.exists():
            with open(threshold_path, "r") as f:
                lines = f.readlines()
        
        # Remove existing threshold for this SID
        lines = [l for l in lines if f"gen_id 1, sig_id {sid}" not in l]
        
        # Add new threshold
        threshold_line = (
            f"threshold gen_id 1, sig_id {sid}, type {threshold_type}, "
            f"track {track}, count {count}, seconds {seconds}\n"
        )
        lines.append(threshold_line)
        
        # Write back
        threshold_path.parent.mkdir(parents=True, exist_ok=True)
        with open(threshold_path, "w") as f:
            f.writelines(lines)
        
        logger.info("Set threshold for SID %d: %s", sid, threshold_line.strip())
        return True, "Threshold set"
    
    except Exception as e:
        logger.error("Error setting threshold: %s", e)
        return False, str(e)


def remove_rule_threshold(sid: int) -> tuple[bool, str]:
    """Remove threshold for a rule."""
    threshold_path = Path(THRESHOLD_FILE)
    
    if not threshold_path.exists():
        return True, "No thresholds configured"
    
    try:
        with open(threshold_path, "r") as f:
            lines = f.readlines()
        
        new_lines = [l for l in lines if f"sig_id {sid}" not in l]
        
        with open(threshold_path, "w") as f:
            f.writelines(new_lines)
        
        return True, "Threshold removed"
    
    except Exception as e:
        return False, str(e)


def get_classtypes() -> list[str]:
    """Get list of unique classtypes from rules."""
    classtypes = set()
    rule_dirs = find_rule_directories()
    
    for rule_dir in rule_dirs:
        for rule_file in rule_dir.glob("*.rules"):
            try:
                with open(rule_file, "r", encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        match = re.search(r"classtype:\s*([^;]+)", line)
                        if match:
                            classtypes.add(match.group(1).strip())
            except Exception:
                pass
    
    return sorted(classtypes)


def reload_suricata() -> tuple[bool, str]:
    """Reload Suricata to apply rule changes."""
    try:
        result = subprocess.run(
            ["systemctl", "reload", "networktap-suricata"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        
        if result.returncode == 0:
            return True, "Suricata reloaded"
        else:
            # Try suricatasc for live reload
            result = subprocess.run(
                ["suricatasc", "-c", "reload-rules"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            
            if result.returncode == 0:
                return True, "Rules reloaded via suricatasc"
            
            return False, result.stderr or "Reload failed"
    
    except subprocess.TimeoutExpired:
        return False, "Reload timed out"
    except Exception as e:
        return False, str(e)


def get_rule_stats() -> dict:
    """Get rule statistics."""
    total = 0
    enabled = 0
    by_action = {}
    by_classtype = {}
    
    rule_dirs = find_rule_directories()
    
    for rule_dir in rule_dirs:
        for rule_file in rule_dir.glob("*.rules"):
            try:
                with open(rule_file, "r", encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        rule = parse_rule(line)
                        if rule:
                            total += 1
                            if rule.enabled:
                                enabled += 1
                            
                            by_action[rule.action] = by_action.get(rule.action, 0) + 1
                            
                            if rule.classtype:
                                by_classtype[rule.classtype] = by_classtype.get(rule.classtype, 0) + 1
            except Exception:
                pass
    
    return {
        "total": total,
        "enabled": enabled,
        "disabled": total - enabled,
        "by_action": by_action,
        "by_classtype": by_classtype,
    }
