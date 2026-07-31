from dataclasses import dataclass
from typing import Any

import requests
from requests.auth import HTTPBasicAuth

from app.core.config import Settings


class JiraConfigurationError(Exception):
    """Raised when Jira credentials are not configured."""

    def __init__(self, missing: list[str]):
        self.missing = missing
        super().__init__(", ".join(missing))


class JiraRequestError(Exception):
    """User-safe Jira API error."""

    def __init__(self, message: str, status_code: int | None = None):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


@dataclass(frozen=True)
class JiraCredentials:
    """Credentials required for Jira Cloud Basic Auth."""

    base_url: str
    email: str
    api_token: str
    timeout_seconds: float = 15.0

    @classmethod
    def from_settings(cls, settings: Settings) -> "JiraCredentials":
        return cls(
            base_url=settings.jira_url,
            email=settings.jira_email,
            api_token=settings.jira_api_token,
            timeout_seconds=settings.jira_timeout_seconds,
        )

    def missing_fields(self) -> list[str]:
        missing = []

        if not self.base_url.strip():
            missing.append("JIRA_URL")

        if not self.email.strip():
            missing.append("JIRA_EMAIL")

        if not self.api_token.strip():
            missing.append("JIRA_API_TOKEN")

        return missing


class JiraClient:
    """Small Jira Cloud REST API client used by JiraService."""

    def __init__(
        self,
        credentials: JiraCredentials,
        session: requests.Session | None = None,
    ):
        self.credentials = credentials
        self.session = session or requests.Session()

    def whoami(self) -> dict[str, Any]:
        return self._get("/rest/api/3/myself")

    def projects(self) -> list[dict[str, Any]]:
        data = self._get(
            "/rest/api/3/project/search",
            params={"maxResults": 50},
        )

        return list(data.get("values", []))

    def issue(self, key: str) -> dict[str, Any]:
        if not key.strip():
            raise JiraRequestError("Jira issue key is required.")

        return self._get(
            f"/rest/api/3/issue/{key.strip().upper()}",
            params={
                "fields": (
                    "summary,status,assignee,priority,reporter,"
                    "description,comment,issuelinks,updated"
                ),
            },
        )

    def assigned_issues(self, max_results: int = 25) -> list[dict[str, Any]]:
        data = self._get(
            "/rest/api/3/search/jql",
            params={
                "jql": "assignee = currentUser() ORDER BY updated DESC",
                "maxResults": max_results,
                "fields": "*all",
            },
        )

        return list(data.get("issues", []))

    def _get(
        self,
        path: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self._validate()

        try:
            response = self.session.get(
                self._url(path),
                auth=HTTPBasicAuth(
                    self.credentials.email.strip(),
                    self.credentials.api_token.strip(),
                ),
                headers={
                    "Accept": "application/json",
                },
                params=params,
                timeout=self.credentials.timeout_seconds,
            )
        except requests.Timeout as error:
            raise JiraRequestError(
                "Jira request timed out. Check network connectivity and try again."
            ) from error
        except requests.RequestException as error:
            raise JiraRequestError(
                "Network error while connecting to Jira. Check JIRA_URL and connectivity."
            ) from error

        if response.status_code == 401:
            raise JiraRequestError(
                "Jira authentication failed. Check JIRA_EMAIL and JIRA_API_TOKEN.",
                status_code=401,
            )

        if response.status_code == 403:
            raise JiraRequestError(
                "Jira access denied. The account does not have permission for this resource.",
                status_code=403,
            )

        if response.status_code == 404:
            raise JiraRequestError(
                "Jira resource was not found.",
                status_code=404,
            )

        if response.status_code >= 400:
            raise JiraRequestError(
                f"Jira API returned HTTP {response.status_code}.",
                status_code=response.status_code,
            )

        try:
            data = response.json()
        except ValueError as error:
            raise JiraRequestError("Jira returned a non-JSON response.") from error

        if not isinstance(data, dict):
            raise JiraRequestError("Jira returned an unexpected response shape.")

        return data

    def _validate(self) -> None:
        missing = self.credentials.missing_fields()

        if missing:
            raise JiraConfigurationError(missing)

    def _url(self, path: str) -> str:
        return f"{self.credentials.base_url.strip().rstrip('/')}{path}"


def adf_to_text(value: Any) -> str:
    """Extract readable text from Atlassian Document Format or plain values."""

    chunks: list[str] = []

    def visit(node: Any) -> None:
        if isinstance(node, str):
            chunks.append(node)
            return

        if isinstance(node, list):
            for item in node:
                visit(item)
            return

        if not isinstance(node, dict):
            return

        text = node.get("text")

        if isinstance(text, str):
            chunks.append(text)

        content = node.get("content")

        if isinstance(content, list):
            for item in content:
                visit(item)

    visit(value)

    return " ".join(" ".join(chunks).split())
