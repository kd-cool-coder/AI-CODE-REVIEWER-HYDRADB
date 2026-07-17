import json
import os
import time

from dotenv import load_dotenv
from hydra_db import HydraDB
from hydra_db.errors import ConflictError


load_dotenv()

DATABASE = "acme_code_review"
COLLECTION = "backend_team"

client = HydraDB(token=os.environ["HYDRA_DB_API_KEY"])


def wait_for_database(timeout: int = 300) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        status = client.databases.status(database=DATABASE)
        if status.data.infra.ready_for_ingestion:
            print("Database ready.")
            return
        print("Waiting for database provisioning...")
        time.sleep(2)
    raise TimeoutError(f"Database {DATABASE!r} was not ready within {timeout} seconds.")


def wait_for_indexing(source_ids: list[str], timeout: int = 300) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        response = client.context.status(
            database=DATABASE,
            collection=COLLECTION,
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
            raise RuntimeError(f"Indexing failed: {errors}")

        if len(states) == len(source_ids) and all(
            state == "completed" for state in states.values()
        ):
            print("Standards indexed and graph-ready.")
            return

        print(f"Indexing status: {states}")
        time.sleep(3)

    raise TimeoutError(f"Indexing did not finish within {timeout} seconds.")


try:
    client.databases.create(database=DATABASE)
    print(f"Created database {DATABASE!r}.")
except ConflictError:
    print(f"Database {DATABASE!r} already exists; reusing it.")

wait_for_database()

with open("standards.md", "rb") as f:
    result = client.context.ingest(
        database=DATABASE,
        collection=COLLECTION,
        type="knowledge",
        documents=("standards.md", f, "text/markdown"),
        document_metadata=json.dumps(
            [
                {
                    "id": "backend-team-standards-v1",
                    "title": "Backend team coding standards",
                }
            ]
        ),
        upsert="true",
    )

source_ids = [item.id for item in result.data.results]
if not source_ids:
    raise RuntimeError("HydraDB did not return a source ID for the standards.")
print(f"Queued standards ingestion. Source IDs: {source_ids}")
wait_for_indexing(source_ids)

smoke_test = client.query(
    database=DATABASE,
    collection=COLLECTION,
    query="What is the team's standard for nested conditionals and early returns?",
    type="knowledge",
    query_by="hybrid",
    mode="fast",
    graph_context=False,
    max_results=3,
)
if not (smoke_test.data.chunks or []):
    raise RuntimeError("Smoke test returned no standards. Check the ingestion status.")
print("Smoke test passed: the standards are queryable.")
