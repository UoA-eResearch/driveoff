"""Lightweight local ProjectDB REST API client.

Replaces the ceradmin-cli ProjectDBApi dependency with a minimal client
that only includes the API calls needed by driveoff.
"""

from __future__ import annotations

from typing import Any

import requests


class ProjectDBClient:
    """Minimal HTTP client for the eResearch Project Database API."""

    def __init__(self, base_url: str, api_key: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "apikey": api_key,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get(self, endpoint: str, params: dict[str, Any] | None = None) -> Any:
        """Perform a GET request and return parsed JSON."""
        print(f"GET {endpoint} with params {params}")  # Debug logging
        response = requests.get(
            self.base_url + endpoint,
            headers=self.headers,
            params=params,
            timeout=30,
        )
        response.raise_for_status()
        return response.json()

    def _build_expand_params(self, expand: list[str] | None) -> dict[str, Any] | None:
        if not expand:
            return None
        return {"expand": ",".join(expand)}

    # ------------------------------------------------------------------
    # Public API — only the methods driveoff actually uses
    # ------------------------------------------------------------------

    def get_research_drive_by_name(self, drive_name: str) -> Any:
        """GET /researchdrive/{drive_name}"""
        return self._get(f"/researchdrive/{drive_name}")

    def get_research_drive_projects(
        self, drive_id: int, expand: list[str] | None = None
    ) -> Any:
        """GET /researchdrive/{drive_id}/project"""
        return self._get(
            f"/researchdrive/{drive_id}/project",
            self._build_expand_params(expand),
        )

    def get_project(self, pid: int, expand: list[str] | None = None) -> Any:
        """GET /project/{pid}"""
        return self._get(
            f"/project/{pid}",
            self._build_expand_params(expand),
        )

    def get_project_members(
        self, project_id: int, expand: list[str] | None = None
    ) -> Any:
        """GET /project/{project_id}/member"""
        return self._get(
            f"/project/{project_id}/member",
            self._build_expand_params(expand),
        )
