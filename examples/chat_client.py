#!/usr/bin/env python3
"""Use openJEV's text-only chat subset without an SDK or extra dependencies."""

import argparse
import json
import os
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise URLError("Redirect refused; point the client at your local openJEV service")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8766")
    parser.add_argument("--prompt", default="Summarize this fictional support request: The parcel arrived damaged and the customer requests a replacement.")
    parser.add_argument("--max-tokens", type=int, default=128)
    args = parser.parse_args()
    parsed = urlparse(args.base_url)
    if (parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
            or parsed.username or parsed.password or parsed.query or parsed.fragment
            or parsed.path not in {"", "/"}):
        parser.error("--base-url must be a loopback HTTP origin; use an SSH tunnel for a remote server")
    if not 1 <= args.max_tokens <= 512:
        parser.error("--max-tokens must be 1–512")
    payload = {
        "model": "diffusiongemma-26b",
        "messages": [{"role": "user", "content": args.prompt}],
        "max_tokens": args.max_tokens,
        "stream": False,
    }
    headers = {"Content-Type": "application/json"}
    if os.getenv("OPENJEV_API_KEY"):
        headers["Authorization"] = "Bearer " + os.environ["OPENJEV_API_KEY"]
    request = Request(args.base_url.rstrip("/") + "/v1/chat/completions",
                      data=json.dumps(payload, ensure_ascii=False).encode(), headers=headers)
    try:
        with build_opener(ProxyHandler({}), NoRedirect()).open(request, timeout=220) as response:
            result = json.load(response)
    except HTTPError as exc:
        print(f"HTTP {exc.code}: {exc.read(65536).decode(errors='replace')}", file=sys.stderr)
        return 1
    except (URLError, TimeoutError, ValueError) as exc:
        print(f"Request failed: {exc}", file=sys.stderr)
        return 1
    print(result["choices"][0]["message"]["content"])
    if result["choices"][0]["finish_reason"] == "length":
        print("Output reached max_tokens; the answer may be incomplete.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
