import json
import os
import ssl
import sys
import urllib.error
import urllib.request
from pathlib import Path

from dotenv import load_dotenv


def post_json(url: str, payload: dict, headers: dict[str, str]) -> tuple[int, dict, bytes]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    context = ssl.create_default_context()
    with urllib.request.urlopen(request, timeout=30, context=context) as response:
        body = response.read()
        return response.status, dict(response.headers.items()), body


def main() -> int:
    env_path = Path(__file__).with_name(".env")
    load_dotenv(env_path)

    required = ("ARCADE_API_KEY", "ARCADE_USER_ID", "ARCADE_GATEWAY_SLUG")
    missing = [name for name in required if not os.environ.get(name)]
    if missing:
        print(f"Missing required environment variables: {', '.join(missing)}")
        return 1

    gateway_url = f"https://api.arcade.dev/mcp/{os.environ['ARCADE_GATEWAY_SLUG']}"
    common_headers = {
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json",
        "Authorization": f"Bearer {os.environ['ARCADE_API_KEY']}",
        "Arcade-User-ID": os.environ["ARCADE_USER_ID"],
        "MCP-Protocol-Version": "2025-06-18",
        # Some edge protections are stricter with default library user agents.
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0 Safari/537.36",
    }

    initialize_payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-06-18",
            "capabilities": {},
            "clientInfo": {
                "name": "arcade-connection-check",
                "version": "1.0.0",
            },
        },
    }

    try:
        print(f"Connecting to {gateway_url}")
        status, response_headers, body = post_json(
            gateway_url,
            initialize_payload,
            common_headers,
        )
        print(f"Initialize HTTP status: {status}")
        print(f"Response body: {body.decode('utf-8', errors='replace')}")

        session_id = response_headers.get("Mcp-Session-Id")
        if not session_id:
            print("No Mcp-Session-Id was returned. The gateway did not start an MCP session.")
            return 1

        print(f"MCP session established: {session_id}")

        tools_payload = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {},
        }
        tools_headers = {
            **common_headers,
            "Mcp-Session-Id": session_id,
        }
        status, _, body = post_json(gateway_url, tools_payload, tools_headers)
        print(f"tools/list HTTP status: {status}")

        parsed = json.loads(body.decode("utf-8"))
        tools = parsed.get("result", {}).get("tools", [])
        print(f"Gateway returned {len(tools)} tool(s).")
        for tool in tools:
            print(f"- {tool.get('name')}")

        if not tools:
            print("Connected, but the gateway returned no tools.")
            return 1

        print("Arcade MCP gateway connection looks healthy.")
        return 0

    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        print(f"HTTP error: {exc.code} {exc.reason}")
        print(error_body)
        if "browser_signature_banned" in error_body:
            print(
                "The request was blocked by Cloudflare before it reached Arcade. "
                "This usually means the HTTP client fingerprint was denied."
            )
        return 1
    except urllib.error.URLError as exc:
        print(f"Network error: {exc.reason}")
        return 1
    except json.JSONDecodeError as exc:
        print(f"Could not parse JSON response: {exc}")
        return 1
    except Exception as exc:
        print(f"Unexpected error: {type(exc).__name__}: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
