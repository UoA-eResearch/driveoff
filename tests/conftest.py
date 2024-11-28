from datetime import datetime
from typing import Any

import pytest

from models.common import DataClassification


@pytest.fixture
def submission() -> dict[str, Any]:
    """Fixture with a working submission.

    Returns:
        dict[str, Any]: submission data.
    """
    return {
        "retention_period_years": 6,
        "data_classification": DataClassification.PUBLIC,
        "is_completed": True,
        "updated_time": datetime.now(),
        "is_project_updated": True,
        "drive_id": 1,
    }
