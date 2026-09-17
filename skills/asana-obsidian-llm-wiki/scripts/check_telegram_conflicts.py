#!/usr/bin/env python3
"""Detect duplicate TELEGRAM_BOT_TOKEN across Hermes profiles.

Why this exists
---------------
Two Hermes profiles sharing one Telegram bot token produce an infinite
gateway restart loop:

    ERROR gateway.run: Gateway hit a non-retryable startup conflict:
    telegram: Telegram bot token already in use (PID 1438).

The gateway starts, collides, exits, and launchd/systemd revives it forever.
Cron never fires, and nothing surfaces to the user. This is the single most
common cause of a "loaded but dead" gateway.

Usage
-----
    python3 check_telegram_conflicts.py
    python3 check_telegram_conflicts.py --hermes-home ~/.hermes

Run this during onboarding for any NEW profile, BEFORE starting its gateway.

Privacy
-------
Prints only a short SHA-256 fingerprint per token — never the token itself.
Safe to paste the output into a chat or an issue.
"""

import argparse
import hashlib
import os

KEY = "TELEGRAM_BOT_TOKEN"


def read_key(path):
    """Return the value of KEY from a .env file, or None."""
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            s = line.strip()
            if not s or s.startswith("#") or "=" not in s:
                continue
            k, _, v = s.partition("=")
            if k.strip() == KEY:
                return v.strip().strip('"').strip("'")
    return None


def discover(hermes_home):
    """Map label -> .env path for the root profile and every named profile."""
    found = {}
    root_env = os.path.join(hermes_home, ".env")
    if os.path.exists(root_env):
        found["default (root)"] = root_env

    profiles_dir = os.path.join(hermes_home, "profiles")
    if os.path.isdir(profiles_dir):
        for name in sorted(os.listdir(profiles_dir)):
            env = os.path.join(profiles_dir, name, ".env")
            if os.path.exists(env):
                found[name] = env
    return found


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--hermes-home",
                    default=os.path.expanduser("~/.hermes"),
                    help="Hermes home directory (default: ~/.hermes)")
    args = ap.parse_args()

    targets = discover(args.hermes_home)
    if not targets:
        print("No .env files found under %s" % args.hermes_home)
        return 1

    print("%-24s %-7s %s" % ("PROFILE", "LEN", "FINGERPRINT"))
    print("-" * 50)

    seen = {}
    for label, path in targets.items():
        tok = read_key(path)
        if not tok:
            print("%-24s %-7s %s" % (label, "-", "no token"))
            continue
        h = hashlib.sha256(tok.encode()).hexdigest()[:10]
        seen.setdefault(h, []).append(label)
        print("%-24s %-7d %s" % (label, len(tok), h))

    print()
    print("=== CONFLICTS (same token = gateway restart loop) ===")
    conflicts = {h: ps for h, ps in seen.items() if len(ps) > 1}
    if not conflicts:
        print("  none — every profile has a unique token")
        return 0

    for h, ps in conflicts.items():
        print("  %s shared by: %s" % (h, ", ".join(ps)))
    print()
    print("Fix: create a NEW bot per profile via @BotFather, put each token")
    print("in that profile's .env, then re-run this check before starting")
    print("the gateway.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
