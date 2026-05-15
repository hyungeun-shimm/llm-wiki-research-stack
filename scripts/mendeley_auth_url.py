#!/usr/bin/env python3
"""Create a Mendeley OAuth implicit-flow authorization URL.

Use this when you need a short-lived `MENDELEY_ACCESS_TOKEN` for local scripts.
The callback page lives at `_system/dashboard/mendeley_oauth.html` and should be served
from the repo with `python3 -m http.server 8765`.
"""

from __future__ import annotations

import argparse
import secrets
import urllib.parse


DEFAULT_REDIRECT = "http://localhost:8765/_system/dashboard/mendeley_oauth.html"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate the browser URL for a temporary Mendeley access token."
    )
    parser.add_argument("--client-id", required=True, help="Mendeley application ID from dev.mendeley.com/myapps.html")
    parser.add_argument("--redirect-uri", default=DEFAULT_REDIRECT, help=f"Registered redirect URI. Default: {DEFAULT_REDIRECT}")
    parser.add_argument("--state", default=None, help="Optional OAuth state. Defaults to a generated random value.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    state = args.state or secrets.token_urlsafe(24)
    params = {
        "client_id": args.client_id,
        "redirect_uri": args.redirect_uri,
        "response_type": "token",
        "scope": "all",
        "state": state,
    }
    url = "https://api.mendeley.com/oauth/authorize?" + urllib.parse.urlencode(params)
    print("Open this URL in your browser:")
    print(url)
    print()
    print("Expected state:")
    print(state)
    print()
    print("Redirect URI that must be registered in Mendeley:")
    print(args.redirect_uri)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
