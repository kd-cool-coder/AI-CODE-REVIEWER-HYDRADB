import os
import time

from arcadepy import Arcade
from dotenv import load_dotenv


load_dotenv()

client = Arcade(api_key=os.environ["ARCADE_API_KEY"])
user_id = os.environ["ARCADE_USER_ID"]
tools = (
    "Github.GetPullRequest",
    "Github.CreateReviewComment",
    "Github.SubmitPullRequestReview",
)
AUTH_TIMEOUT_SECONDS = 300

for tool_name in tools:
    response = client.tools.authorize(tool_name=tool_name, user_id=user_id)
    if response.status == "completed":
        continue
    if response.status == "failed":
        raise RuntimeError(f"Authorization failed for {tool_name}.")
    if not response.id or not response.url:
        raise RuntimeError(
            f"Arcade did not return an authorization ID and URL for {tool_name}."
        )

    print(f"Authorize {tool_name}: {response.url}")
    deadline = time.monotonic() + AUTH_TIMEOUT_SECONDS
    while response.status not in {"completed", "failed"}:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError(
                f"Authorization for {tool_name} did not finish within "
                f"{AUTH_TIMEOUT_SECONDS} seconds."
            )
        response = client.auth.status(
            id=response.id,
            wait=min(45, max(1, int(remaining))),
        )

    if response.status == "failed":
        raise RuntimeError(f"Authorization failed for {tool_name}.")

print("GitHub authorization complete.")
