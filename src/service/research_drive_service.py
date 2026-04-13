"""Research drive service initialization and dependency injection for FastAPI."""

from __future__ import annotations

from fastapi import FastAPI, Request

from config import get_settings
from service.research_drive_smb import ResearchDriveSMB


def init_research_drive_service(app: FastAPI) -> None:
    """Initialize the research drive service and attach to FastAPI app state.

    Reads SMB configuration from application Settings (sourced from
    the mode-specific .env files).

    This initializes the service but does not create individual drive
    connections until they are needed.

    Raises:
        ValueError: If required SMB configuration is missing
    """
    settings = get_settings()

    # Validate required settings
    required_settings = {
        "smb_username": settings.smb_username,
        "smb_password": settings.smb_password,
        "smb_drive_base_path": settings.smb_drive_base_path,
    }

    missing = [name for name, value in required_settings.items() if not value]
    if missing:
        raise ValueError(
            f"SMB configuration incomplete. Missing: {', '.join(missing)}. "
            "Set SMB_USERNAME, SMB_PASSWORD, and SMB_DRIVE_BASE_PATH in environment."
        )

    # Store SMB configuration on app state for use in endpoints
    app.state.smb_config = {
        "username": settings.smb_username,
        "password": settings.smb_password,
        "base_path": settings.smb_drive_base_path,
    }

    print(
        f"Research drive service initialized with base path: {settings.smb_drive_base_path}"
    )


def get_research_drive_smb(drive_name: str, request: Request) -> ResearchDriveSMB:
    """Factory function to create a research drive instance for a specific drive.

    This is a factory rather than a simple dependency because each drive needs
    its own instance. Use this to create drive instances in your endpoints.

    Args:
        drive_name: Name of the research drive (e.g., 'RDATA-001')
        request: FastAPI request (provides access to app.state)

    Returns:
        ResearchDriveSMB: Configured drive instance

    Raises:
        RuntimeError: If research drive service not initialized
    """
    smb_config = getattr(request.app.state, "smb_config", None)
    if smb_config is None:
        raise RuntimeError(
            "Research drive service not initialized on application state"
        )

    return ResearchDriveSMB(
        drive_name=drive_name,
        base_path=smb_config["base_path"],
        username=smb_config["username"],
        password=smb_config["password"],
    )
