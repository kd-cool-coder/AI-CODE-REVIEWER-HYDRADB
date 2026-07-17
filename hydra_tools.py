import asyncio
import hashlib
import json
import os
import time
from typing import Any

from claude_agent_sdk import create_sdk_mcp_server, tool
from hydra_db import HydraDB
from hydra_db.helpers import build_string


DATABASE = "acme_code_review"
TEAM_COLLECTION = "backend_team"

client = HydraDB(token=os.environ["HYDRA_DB_API_KEY"])


def repo_collection(owner: str, repo: str) -> str:
    """Return a deterministic, collection-safe scope for one GitHub repository."""
    repo_key = f"{owner}/{repo}".lower().encode("utf-8")
    return f"repo_{hashlib.sha256(repo_key).hexdigest()[:16]}"


async def wait_for_indexing(
    source_ids: list[str],
    collection: str,
    timeout: int = 300,
) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        response = client.context.status(
            database=DATABASE,
            collection=collection,
            ids=source_ids,
        )
        statuses = response.data.statuses or []
        states = {item.id: item.indexing_status for item in statuses}

        if any(state in {"failed", "errored"} for state in states.values()):
            errors = {
                item.id: item.error_message or item.message
                for item in statuses
                if item.indexing_status in {"failed", "errored"}
            }
            raise RuntimeError(f"Memory indexing failed: {errors}")

        if len(states) == len(source_ids) and all(
            state == "completed" for state in states.values()
        ):
            return

        await asyncio.sleep(2)

    raise TimeoutError(f"Memory indexing did not finish within {timeout} seconds.")


@tool(
    "search_team_context",
    "Search team coding standards plus review history for one repository and "
    "author. Use type='knowledge' for standards only, 'memory' for past reviews "
    "only, or 'all' for both.",
    {"owner": str, "repo": str, "author": str, "query": str, "type": str},
)
async def search_team_context(args: dict[str, Any]) -> dict[str, Any]:
    repository = f"{args['owner']}/{args['repo']}"
    repository_scope = repo_collection(args["owner"], args["repo"])
    collection_response = client.databases.collections(database=DATABASE)
    available_collections = set(
        (collection_response.data.collections if collection_response.data else []) or []
    )
    query_collections = [TEAM_COLLECTION]
    if repository_scope in available_collections:
        query_collections.append(repository_scope)

    query_text = (
        f"Repository: {repository}\n"
        f"Author: {args['author']}\n"
        f"{args['query']}"
    )
    result = client.query(
        query=query_text,
        database=DATABASE,
        collections=query_collections,
        type=args["type"],
        query_by="hybrid",
        mode="thinking",
        max_results=8,
        graph_context=True,
    )

    context = build_string(result)
    return {"content": [{"type": "text", "text": context}]}


@tool(
    "store_review_memory",
    "Store a completed review in the repository's scoped memory. Include only "
    "verified review facts: the actual author, files and functions reviewed, "
    "issues found, and standards cited.",
    {
        "owner": str,
        "repo": str,
        "pr_number": int,
        "author": str,
        "summary": str,
    },
)
async def store_review_memory(args: dict[str, Any]) -> dict[str, Any]:
    repository = f"{args['owner']}/{args['repo']}"
    collection = repo_collection(args["owner"], args["repo"])
    review_id = f"pr_{args['pr_number']}_review"
    title = f"{repository} PR #{args['pr_number']} review"

    result = client.context.ingest(
        database=DATABASE,
        collection=collection,
        type="memory",
        memories=json.dumps(
            [
                {
                    "id": review_id,
                    "title": title,
                    "text": (
                        f"Repository: {repository}\n"
                        f"Pull request: #{args['pr_number']}\n"
                        f"Author: {args['author']}\n\n"
                        f"{args['summary']}"
                    ),
                    "is_markdown": True,
                    "infer": False,
                    "additional_metadata": {
                        "repository": repository,
                        "pr_number": args["pr_number"],
                        "author": args["author"],
                    },
                }
            ]
        ),
        upsert="true",
    )

    source_ids = [item.id for item in result.data.results]
    if not source_ids:
        raise RuntimeError("HydraDB did not return a source ID for the review memory.")
    await wait_for_indexing(source_ids, collection)
    return {
        "content": [
            {
                "type": "text",
                "text": f"Stored and indexed review memory: {title}",
            }
        ]
    }


hydra_server = create_sdk_mcp_server(
    name="hydra-context",
    version="1.0.0",
    tools=[search_team_context, store_review_memory],
)
