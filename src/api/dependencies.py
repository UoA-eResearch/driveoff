"""FastAPI dependency providers and database engine setup."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Annotated

from fastapi import Depends
from sqlmodel import Session, SQLModel, create_engine

from service.projectdb import get_projectdb_client
from service.projectdb_client import ProjectDBClient

# Ensure the driveoff data directory exists
(Path.home() / ".driveoff").mkdir(exist_ok=True)

DB_FILE_NAME = Path.home() / ".driveoff" / "database.db"
DB_URL = f"sqlite:///{DB_FILE_NAME}"

connect_args = {"check_same_thread": False}
engine = create_engine(DB_URL, connect_args=connect_args, echo=False)


def create_db_and_tables() -> None:
    """Create database tables for archive submissions and retrievals."""
    SQLModel.metadata.create_all(engine)


def get_session() -> Iterable[Session]:
    """Yield a database session."""
    with Session(engine) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]
ProjectDbDep = Annotated[ProjectDBClient, Depends(get_projectdb_client)]
