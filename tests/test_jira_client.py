import unittest
from unittest.mock import Mock

import requests

from app.services.jira_client import (
    JiraClient,
    JiraCredentials,
    JiraRequestError,
    adf_to_text,
)


class FakeResponse:
    def __init__(self, status_code: int, payload: dict):
        self.status_code = status_code
        self.payload = payload

    def json(self):
        return self.payload


class JiraClientTest(unittest.TestCase):
    def setUp(self):
        self.session = Mock()
        self.client = JiraClient(
            JiraCredentials(
                base_url="https://example.atlassian.net",
                email="qa@example.com",
                api_token="secret-token",
                timeout_seconds=3.0,
            ),
            session=self.session,
        )

    def test_whoami_success(self):
        self.session.get.return_value = FakeResponse(
            200,
            {
                "displayName": "QA Engineer",
                "accountId": "account-1",
                "emailAddress": "qa@example.com",
            },
        )

        user = self.client.whoami()

        self.assertEqual(user["displayName"], "QA Engineer")
        self.session.get.assert_called_once()
        _, kwargs = self.session.get.call_args
        self.assertEqual(kwargs["headers"]["Accept"], "application/json")
        self.assertEqual(kwargs["timeout"], 3.0)

    def test_projects_success(self):
        self.session.get.return_value = FakeResponse(
            200,
            {
                "values": [
                    {"key": "QA", "name": "QA Project"},
                    {"key": "SCRUM", "name": "Scrum Project"},
                ]
            },
        )

        projects = self.client.projects()

        self.assertEqual(
            [(project["key"], project["name"]) for project in projects],
            [("QA", "QA Project"), ("SCRUM", "Scrum Project")],
        )

    def test_issue_success_extracts_description_text(self):
        self.session.get.return_value = FakeResponse(
            200,
            {
                "key": "SCRUM-42",
                "fields": {
                    "summary": "Login fails",
                    "description": {
                        "type": "doc",
                        "content": [
                            {
                                "type": "paragraph",
                                "content": [
                                    {"type": "text", "text": "Steps to reproduce"}
                                ],
                            }
                        ],
                    },
                },
            },
        )

        issue = self.client.issue("scrum-42")

        self.assertEqual(issue["key"], "SCRUM-42")
        self.assertEqual(
            adf_to_text(issue["fields"]["description"]),
            "Steps to reproduce",
        )

    def test_assigned_issues_uses_jql_search(self):
        self.session.get.return_value = FakeResponse(
            200,
            {
                "issues": [
                    {"key": "SCRUM-1", "fields": {"summary": "Daily task"}},
                ]
            },
        )

        issues = self.client.assigned_issues(max_results=10)

        self.assertEqual(issues[0]["key"], "SCRUM-1")
        url, kwargs = self.session.get.call_args.args[0], self.session.get.call_args.kwargs
        self.assertTrue(url.endswith("/rest/api/3/search/jql"))
        self.assertIn("assignee = currentUser()", kwargs["params"]["jql"])
        self.assertEqual(kwargs["params"]["maxResults"], 10)

    def test_unauthorized_returns_user_safe_error(self):
        self.session.get.return_value = FakeResponse(401, {})

        with self.assertRaises(JiraRequestError) as context:
            self.client.whoami()

        self.assertEqual(context.exception.status_code, 401)
        self.assertIn("authentication failed", context.exception.message.lower())
        self.assertNotIn("secret-token", context.exception.message)

    def test_not_found_returns_user_safe_error(self):
        self.session.get.return_value = FakeResponse(404, {})

        with self.assertRaises(JiraRequestError) as context:
            self.client.issue("SCRUM-404")

        self.assertEqual(context.exception.status_code, 404)
        self.assertIn("not found", context.exception.message.lower())

    def test_forbidden_returns_user_safe_error(self):
        self.session.get.return_value = FakeResponse(403, {})

        with self.assertRaises(JiraRequestError) as context:
            self.client.projects()

        self.assertEqual(context.exception.status_code, 403)
        self.assertIn("access denied", context.exception.message.lower())

    def test_timeout_returns_user_safe_error(self):
        self.session.get.side_effect = requests.Timeout()

        with self.assertRaises(JiraRequestError) as context:
            self.client.projects()

        self.assertIsNone(context.exception.status_code)
        self.assertIn("timed out", context.exception.message.lower())

    def test_network_error_returns_user_safe_error(self):
        self.session.get.side_effect = requests.RequestException()

        with self.assertRaises(JiraRequestError) as context:
            self.client.projects()

        self.assertIsNone(context.exception.status_code)
        self.assertIn("network error", context.exception.message.lower())


if __name__ == "__main__":
    unittest.main()
