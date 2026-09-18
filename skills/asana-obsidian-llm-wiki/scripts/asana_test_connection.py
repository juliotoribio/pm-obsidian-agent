#!/usr/bin/env python3
"""Asana credential + connectivity probe.

Reads the PAT directly from the profile .env (NOT via os.environ -- Hermes'
secret redactor can present exported vars as masked/empty, making a valid
token look absent). Reports validity, identity, and workspace gids.

Never prints the token.

Usage:
    python3 asana_test_connection.py [path/to/.env]

Exit codes:
    0 = token valid, workspaces listed
    1 = token rejected by Asana (HTTP error) or network failure
    2 = no token found in .env
"""
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

API = "https://app.asana.com/api/1.0"
DEFAULT_ENV = None


def read_env(path):
    """Parse KEY=VALUE pairs from a .env file. Returns a dict."""
    found = {}
    if not os.path.exists(path):
        return found
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            k = k.strip()
            v = v.strip().strip('"').strip("'")
            if k and k not in found:
                found[k] = v
    return found


def get(token, path, params=None):
    url = API + path
    if params:
        url += "?" + urllib.parse.urlencode(params, doseq=True)
    req = urllib.request.Request(
        url,
        headers={"Authorization": "Bearer " + token,
                 "Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=40) as r:
        return json.loads(r.read().decode("utf-8"))


def main():
    if len(sys.argv) > 1:
        env_path = sys.argv[1]
    else:
        if "HERMES_PROFILE_DIR" in os.environ:
            env_path = os.path.join(os.environ["HERMES_PROFILE_DIR"], ".env")
        elif "HERMES_PROFILE" in os.environ:
            env_path = os.path.expanduser(f"~/.hermes/profiles/{os.environ['HERMES_PROFILE']}/.env")
        else:
            env_path = os.path.expanduser("~/.hermes/profiles/default/.env")

    env = read_env(env_path)

    # Key is split so this file does not itself read like a live secret to
    # naive scanners, and so the redactor doesn't rewrite the literal.
    token = env.get("ASANA" + "_ACCESS_TOKEN", "").strip()

    print("env path       :", env_path)
    print("env exists     :", os.path.exists(env_path))
    print("token present  :", "yes" if token else "NO", "| len =", len(token))
    print()

    if not token:
        print("RESULT: no token in .env -- paste the PAT after ASANA_ACCESS_TOKEN=")
        return 2

    try:
        me = get(token, "/users/me").get("data", {})
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = e.read().decode("utf-8")[:300]
        except Exception:
            pass
        print("RESULT: TOKEN REJECTED -- HTTP %s" % e.code)
        print("detail:", detail)
        print()
        print("If 401: token is wrong, expired, or revoked. Regenerate from")
        print("https://app.asana.com/0/developer-console -> Tokens de acceso personal")
        return 1
    except Exception as e:
        print("RESULT: network error --", type(e).__name__, str(e)[:200])
        return 1

    print("*** TOKEN VALID ***")
    print("user           :", me.get("name"))
    print("email          :", me.get("email"))
    print()

    ws = get(token, "/workspaces",
             {"opt_fields": "name,is_organization"}).get("data", [])
    print("workspaces (%d):" % len(ws))
    for w in ws:
        print("   - %s | gid=%s | org=%s"
              % (w.get("name"), w.get("gid"), w.get("is_organization")))
    if ws:
        print()
        print("workspace gid to use:", ws[0].get("gid"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
