"""
GitHub REST API v3 specs.

Auth: OAuth2 via Nango (or Personal Access Token).
Base URL: https://api.github.com

Key actions for AI ops automation:
- Issues: create, get, update, list, comment, close
- Pull Requests: create, get, list, review, merge
- Repos: get, list, search
- Actions: list workflow runs, trigger workflow
"""

from __future__ import annotations

from anytool.specs.base import ActionSpec, ParamSpec


# ══════════════════════════════════════════════════════════════════════
#  ISSUES
# ══════════════════════════════════════════════════════════════════════

GITHUB_CREATE_ISSUE = ActionSpec(
    name="github_create_issue",
    app="github",
    description=(
        "Create a new issue in a GitHub repository. "
        "Supports title, body, labels, assignees, and milestone."
    ),
    method="POST",
    path="/repos/{owner}/{repo}/issues",
    content_type="application/json",
    params=[
        ParamSpec(name="owner", type="string", required=True, location="path",
                  description="Repository owner (user or org)"),
        ParamSpec(name="repo", type="string", required=True, location="path",
                  description="Repository name"),
        ParamSpec(name="title", type="string", required=True,
                  description="Issue title"),
        ParamSpec(name="body", type="string", required=False,
                  description="Issue body (Markdown supported)"),
        ParamSpec(name="labels", type="list", required=False,
                  description="Label names, e.g. ['bug', 'urgent']"),
        ParamSpec(name="assignees", type="list", required=False,
                  description="GitHub usernames to assign, e.g. ['octocat']"),
        ParamSpec(name="milestone", type="integer", required=False,
                  description="Milestone number to associate with"),
    ],
    response_ids={"number": "issue_number", "id": "issue_id"},
)

GITHUB_GET_ISSUE = ActionSpec(
    name="github_get_issue",
    app="github",
    description="Get a specific issue by number. Returns title, body, state, labels, assignees, and comments count.",
    method="GET",
    path="/repos/{owner}/{repo}/issues/{issue_number}",
    params=[
        ParamSpec(name="owner", type="string", required=True, location="path",
                  description="Repository owner"),
        ParamSpec(name="repo", type="string", required=True, location="path",
                  description="Repository name"),
        ParamSpec(name="issue_number", type="integer", required=True, location="path",
                  description="Issue number"),
    ],
    response_ids={"number": "issue_number", "id": "issue_id"},
)

GITHUB_UPDATE_ISSUE = ActionSpec(
    name="github_update_issue",
    app="github",
    description=(
        "Update an issue — change title, body, state, labels, or assignees. "
        "Set state to 'closed' to close the issue."
    ),
    method="PATCH",
    path="/repos/{owner}/{repo}/issues/{issue_number}",
    content_type="application/json",
    params=[
        ParamSpec(name="owner", type="string", required=True, location="path",
                  description="Repository owner"),
        ParamSpec(name="repo", type="string", required=True, location="path",
                  description="Repository name"),
        ParamSpec(name="issue_number", type="integer", required=True, location="path",
                  description="Issue number"),
        ParamSpec(name="title", type="string", required=False,
                  description="Updated title"),
        ParamSpec(name="body", type="string", required=False,
                  description="Updated body"),
        ParamSpec(name="state", type="string", required=False,
                  description="'open' or 'closed'"),
        ParamSpec(name="labels", type="list", required=False,
                  description="Replace all labels"),
        ParamSpec(name="assignees", type="list", required=False,
                  description="Replace all assignees"),
    ],
    response_ids={"number": "issue_number"},
)

GITHUB_LIST_ISSUES = ActionSpec(
    name="github_list_issues",
    app="github",
    description="List issues for a repository. Filter by state, labels, assignee, or sort order.",
    method="GET",
    path="/repos/{owner}/{repo}/issues",
    params=[
        ParamSpec(name="owner", type="string", required=True, location="path",
                  description="Repository owner"),
        ParamSpec(name="repo", type="string", required=True, location="path",
                  description="Repository name"),
        ParamSpec(name="state", type="string", required=False, location="query",
                  description="'open', 'closed', or 'all'. Default: 'open'"),
        ParamSpec(name="labels", type="string", required=False, location="query",
                  description="Comma-separated label names to filter by"),
        ParamSpec(name="assignee", type="string", required=False, location="query",
                  description="Filter by assignee username. '*' for any, 'none' for unassigned"),
        ParamSpec(name="sort", type="string", required=False, location="query",
                  description="'created', 'updated', 'comments'. Default: 'created'"),
        ParamSpec(name="direction", type="string", required=False, location="query",
                  description="'asc' or 'desc'. Default: 'desc'"),
        ParamSpec(name="per_page", type="integer", required=False, location="query",
                  description="Results per page (max 100, default 30)"),
        ParamSpec(name="page", type="integer", required=False, location="query",
                  description="Page number"),
    ],
)

GITHUB_CREATE_COMMENT = ActionSpec(
    name="github_create_comment",
    app="github",
    description="Add a comment to an issue or pull request.",
    method="POST",
    path="/repos/{owner}/{repo}/issues/{issue_number}/comments",
    content_type="application/json",
    params=[
        ParamSpec(name="owner", type="string", required=True, location="path",
                  description="Repository owner"),
        ParamSpec(name="repo", type="string", required=True, location="path",
                  description="Repository name"),
        ParamSpec(name="issue_number", type="integer", required=True, location="path",
                  description="Issue or PR number"),
        ParamSpec(name="body", type="string", required=True,
                  description="Comment body (Markdown supported)"),
    ],
    response_ids={"id": "comment_id"},
)

GITHUB_LIST_COMMENTS = ActionSpec(
    name="github_list_comments",
    app="github",
    description="List all comments on an issue or pull request.",
    method="GET",
    path="/repos/{owner}/{repo}/issues/{issue_number}/comments",
    params=[
        ParamSpec(name="owner", type="string", required=True, location="path",
                  description="Repository owner"),
        ParamSpec(name="repo", type="string", required=True, location="path",
                  description="Repository name"),
        ParamSpec(name="issue_number", type="integer", required=True, location="path",
                  description="Issue or PR number"),
        ParamSpec(name="per_page", type="integer", required=False, location="query",
                  description="Results per page (max 100)"),
        ParamSpec(name="page", type="integer", required=False, location="query",
                  description="Page number"),
    ],
)


# ══════════════════════════════════════════════════════════════════════
#  PULL REQUESTS
# ══════════════════════════════════════════════════════════════════════

GITHUB_CREATE_PR = ActionSpec(
    name="github_create_pr",
    app="github",
    description=(
        "Create a new pull request. Specify the head branch (your changes) "
        "and base branch (where to merge into, usually 'main')."
    ),
    method="POST",
    path="/repos/{owner}/{repo}/pulls",
    content_type="application/json",
    params=[
        ParamSpec(name="owner", type="string", required=True, location="path",
                  description="Repository owner"),
        ParamSpec(name="repo", type="string", required=True, location="path",
                  description="Repository name"),
        ParamSpec(name="title", type="string", required=True,
                  description="PR title"),
        ParamSpec(name="head", type="string", required=True,
                  description="Branch containing changes (e.g. 'feature-branch')"),
        ParamSpec(name="base", type="string", required=True,
                  description="Branch to merge into (e.g. 'main')"),
        ParamSpec(name="body", type="string", required=False,
                  description="PR description (Markdown supported)"),
        ParamSpec(name="draft", type="boolean", required=False,
                  description="Create as draft PR. Default: false"),
    ],
    response_ids={"number": "pr_number", "id": "pr_id"},
)

GITHUB_GET_PR = ActionSpec(
    name="github_get_pr",
    app="github",
    description="Get a pull request by number. Returns title, state, diff stats, review status, and merge info.",
    method="GET",
    path="/repos/{owner}/{repo}/pulls/{pull_number}",
    params=[
        ParamSpec(name="owner", type="string", required=True, location="path",
                  description="Repository owner"),
        ParamSpec(name="repo", type="string", required=True, location="path",
                  description="Repository name"),
        ParamSpec(name="pull_number", type="integer", required=True, location="path",
                  description="Pull request number"),
    ],
    response_ids={"number": "pr_number"},
)

GITHUB_LIST_PRS = ActionSpec(
    name="github_list_prs",
    app="github",
    description="List pull requests for a repository.",
    method="GET",
    path="/repos/{owner}/{repo}/pulls",
    params=[
        ParamSpec(name="owner", type="string", required=True, location="path",
                  description="Repository owner"),
        ParamSpec(name="repo", type="string", required=True, location="path",
                  description="Repository name"),
        ParamSpec(name="state", type="string", required=False, location="query",
                  description="'open', 'closed', or 'all'. Default: 'open'"),
        ParamSpec(name="sort", type="string", required=False, location="query",
                  description="'created', 'updated', 'popularity', 'long-running'. Default: 'created'"),
        ParamSpec(name="direction", type="string", required=False, location="query",
                  description="'asc' or 'desc'. Default: 'desc'"),
        ParamSpec(name="per_page", type="integer", required=False, location="query",
                  description="Results per page (max 100)"),
        ParamSpec(name="page", type="integer", required=False, location="query",
                  description="Page number"),
    ],
)

GITHUB_MERGE_PR = ActionSpec(
    name="github_merge_pr",
    app="github",
    description=(
        "Merge a pull request. Choose merge method: 'merge' (merge commit), "
        "'squash' (squash and merge), or 'rebase' (rebase and merge)."
    ),
    method="PUT",
    path="/repos/{owner}/{repo}/pulls/{pull_number}/merge",
    content_type="application/json",
    params=[
        ParamSpec(name="owner", type="string", required=True, location="path",
                  description="Repository owner"),
        ParamSpec(name="repo", type="string", required=True, location="path",
                  description="Repository name"),
        ParamSpec(name="pull_number", type="integer", required=True, location="path",
                  description="Pull request number"),
        ParamSpec(name="commit_title", type="string", required=False,
                  description="Title for the merge commit"),
        ParamSpec(name="commit_message", type="string", required=False,
                  description="Body for the merge commit"),
        ParamSpec(name="merge_method", type="string", required=False,
                  description="'merge', 'squash', or 'rebase'. Default: 'merge'"),
    ],
)

GITHUB_CREATE_REVIEW = ActionSpec(
    name="github_create_review",
    app="github",
    description=(
        "Submit a review on a pull request. "
        "Event: 'APPROVE', 'REQUEST_CHANGES', or 'COMMENT'."
    ),
    method="POST",
    path="/repos/{owner}/{repo}/pulls/{pull_number}/reviews",
    content_type="application/json",
    params=[
        ParamSpec(name="owner", type="string", required=True, location="path",
                  description="Repository owner"),
        ParamSpec(name="repo", type="string", required=True, location="path",
                  description="Repository name"),
        ParamSpec(name="pull_number", type="integer", required=True, location="path",
                  description="Pull request number"),
        ParamSpec(name="body", type="string", required=False,
                  description="Review body text"),
        ParamSpec(name="event", type="string", required=True,
                  description="'APPROVE', 'REQUEST_CHANGES', or 'COMMENT'"),
    ],
    response_ids={"id": "review_id"},
)


# ══════════════════════════════════════════════════════════════════════
#  REPOSITORIES
# ══════════════════════════════════════════════════════════════════════

GITHUB_GET_REPO = ActionSpec(
    name="github_get_repo",
    app="github",
    description="Get repository details — description, stars, forks, language, default branch, and visibility.",
    method="GET",
    path="/repos/{owner}/{repo}",
    params=[
        ParamSpec(name="owner", type="string", required=True, location="path",
                  description="Repository owner"),
        ParamSpec(name="repo", type="string", required=True, location="path",
                  description="Repository name"),
    ],
)

GITHUB_LIST_REPOS = ActionSpec(
    name="github_list_repos",
    app="github",
    description="List repositories for a user or organization.",
    method="GET",
    path="/users/{username}/repos",
    params=[
        ParamSpec(name="username", type="string", required=True, location="path",
                  description="GitHub username or org name"),
        ParamSpec(name="type", type="string", required=False, location="query",
                  description="'all', 'owner', 'member'. Default: 'owner'"),
        ParamSpec(name="sort", type="string", required=False, location="query",
                  description="'created', 'updated', 'pushed', 'full_name'. Default: 'full_name'"),
        ParamSpec(name="per_page", type="integer", required=False, location="query",
                  description="Results per page (max 100)"),
        ParamSpec(name="page", type="integer", required=False, location="query",
                  description="Page number"),
    ],
)

GITHUB_SEARCH_REPOS = ActionSpec(
    name="github_search_repos",
    app="github",
    description=(
        "Search GitHub repositories. "
        "Query examples: 'machine learning language:python', 'org:facebook stars:>1000'."
    ),
    method="GET",
    path="/search/repositories",
    params=[
        ParamSpec(name="q", type="string", required=True, location="query",
                  description="Search query (e.g. 'fastapi language:python stars:>100')"),
        ParamSpec(name="sort", type="string", required=False, location="query",
                  description="'stars', 'forks', 'help-wanted-issues', 'updated'. Default: best match"),
        ParamSpec(name="order", type="string", required=False, location="query",
                  description="'asc' or 'desc'. Default: 'desc'"),
        ParamSpec(name="per_page", type="integer", required=False, location="query",
                  description="Results per page (max 100)"),
    ],
)


# ══════════════════════════════════════════════════════════════════════
#  ACTIONS (CI/CD)
# ══════════════════════════════════════════════════════════════════════

GITHUB_LIST_WORKFLOW_RUNS = ActionSpec(
    name="github_list_workflow_runs",
    app="github",
    description="List recent workflow runs for a repository. Shows CI/CD pipeline status.",
    method="GET",
    path="/repos/{owner}/{repo}/actions/runs",
    params=[
        ParamSpec(name="owner", type="string", required=True, location="path",
                  description="Repository owner"),
        ParamSpec(name="repo", type="string", required=True, location="path",
                  description="Repository name"),
        ParamSpec(name="status", type="string", required=False, location="query",
                  description="Filter: 'completed', 'in_progress', 'queued', 'failure', 'success'"),
        ParamSpec(name="branch", type="string", required=False, location="query",
                  description="Filter by branch name"),
        ParamSpec(name="per_page", type="integer", required=False, location="query",
                  description="Results per page (max 100)"),
    ],
)

GITHUB_TRIGGER_WORKFLOW = ActionSpec(
    name="github_trigger_workflow",
    app="github",
    description=(
        "Trigger a workflow dispatch event. "
        "The workflow must have 'workflow_dispatch' trigger configured."
    ),
    method="POST",
    path="/repos/{owner}/{repo}/actions/workflows/{workflow_id}/dispatches",
    content_type="application/json",
    params=[
        ParamSpec(name="owner", type="string", required=True, location="path",
                  description="Repository owner"),
        ParamSpec(name="repo", type="string", required=True, location="path",
                  description="Repository name"),
        ParamSpec(name="workflow_id", type="string", required=True, location="path",
                  description="Workflow ID or filename (e.g. 'deploy.yml')"),
        ParamSpec(name="ref", type="string", required=True,
                  description="Branch or tag to run workflow on (e.g. 'main')"),
        ParamSpec(name="inputs", type="object", required=False,
                  description="Workflow input parameters as key-value pairs"),
    ],
)


# ── Export ────────────────────────────────────────────────────────────

GITHUB_CREATE_WEBHOOK = ActionSpec(
    name="github_create_webhook",
    app="github",
    description=(
        "Create a webhook on a GitHub repository. Sends events to the specified URL. "
        "Used internally by anytool to set up real-time triggers."
    ),
    method="POST",
    path="/repos/{owner}/{repo}/hooks",
    content_type="application/json",
    params=[
        ParamSpec(name="owner", type="string", required=True, location="path",
                  description="Repository owner"),
        ParamSpec(name="repo", type="string", required=True, location="path",
                  description="Repository name"),
        ParamSpec(name="url", type="string", required=True,
                  description="Webhook URL to receive events"),
        ParamSpec(name="events", type="list", required=False,
                  description="Events to subscribe to. Default: ['push']"),
        ParamSpec(name="secret", type="string", required=False,
                  description="Secret for HMAC signature verification"),
    ],
    body_template={
        "name": "web",
        "active": True,
        "config": {
            "url": "{url}",
            "content_type": "json",
            "secret": "{secret}",
        },
    },
)

GITHUB_DELETE_WEBHOOK = ActionSpec(
    name="github_delete_webhook",
    app="github",
    description="Delete a webhook from a GitHub repository.",
    method="DELETE",
    path="/repos/{owner}/{repo}/hooks/{hook_id}",
    params=[
        ParamSpec(name="owner", type="string", required=True, location="path",
                  description="Repository owner"),
        ParamSpec(name="repo", type="string", required=True, location="path",
                  description="Repository name"),
        ParamSpec(name="hook_id", type="string", required=True, location="path",
                  description="Webhook ID to delete"),
    ],
)


GITHUB_SPECS = [
    # Issues
    GITHUB_CREATE_ISSUE,
    GITHUB_GET_ISSUE,
    GITHUB_UPDATE_ISSUE,
    GITHUB_LIST_ISSUES,
    GITHUB_CREATE_COMMENT,
    GITHUB_LIST_COMMENTS,
    # Pull Requests
    GITHUB_CREATE_PR,
    GITHUB_GET_PR,
    GITHUB_LIST_PRS,
    GITHUB_MERGE_PR,
    GITHUB_CREATE_REVIEW,
    # Repos
    GITHUB_GET_REPO,
    GITHUB_LIST_REPOS,
    GITHUB_SEARCH_REPOS,
    # Actions
    GITHUB_LIST_WORKFLOW_RUNS,
    GITHUB_TRIGGER_WORKFLOW,
    # Webhooks
    GITHUB_CREATE_WEBHOOK,
    GITHUB_DELETE_WEBHOOK,
]
