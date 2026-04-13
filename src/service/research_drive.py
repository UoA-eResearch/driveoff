"""Abstract interface for research drive access.

This module defines the protocol for interacting with research drives.
Implementations can use SMB, S3/VAST, or other backends.
Each implementation handles large data volumes efficiently with streaming.
"""

from pathlib import Path
from typing import Iterator, Protocol


class ResearchDrive(Protocol):
    """Protocol for accessing a research drive.

    Implementations should handle connection management, authentication,
    and efficient streaming for large data volumes.
    """

    def verify_access(self) -> None:
        """Verify that the drive is accessible and permissions are valid.

        Raises:
            FileNotFoundError: If drive is inaccessible
            PermissionError: If credentials lack sufficient permissions
            ConnectionError: If connection to drive fails
        """
        ...

    def get_root_path(self) -> Path:
        """Get the root path for this research drive.

        For mounted drives, returns the mount point.
        For remote-only access, still returns a path representation
        that can be used for relative path operations.

        Returns:
            Path: The root path for this drive

        Raises:
            RuntimeError: If drive is not properly initialized
        """
        ...

    def exists(self, path: Path) -> bool:
        """Check if a path exists on the drive.

        Args:
            path: Path to check (relative to drive root)

        Returns:
            bool: True if path exists, False otherwise
        """
        ...

    def is_directory(self, path: Path) -> bool:
        """Check if a path is a directory.

        Args:
            path: Path to check (relative to drive root)

        Returns:
            bool: True if path is a directory, False otherwise

        Raises:
            FileNotFoundError: If path does not exist
        """
        ...

    def list_directory(self, path: Path) -> Iterator[Path]:
        """List contents of a directory.

        Args:
            path: Directory path (relative to drive root)

        Yields:
            Path: Paths of items in the directory

        Raises:
            FileNotFoundError: If path does not exist
            NotADirectoryError: If path is not a directory
        """
        ...

    def open_file(self, path: Path, mode: str = "rb"):
        """Open a file for reading.

        For large files, this should support streaming to avoid
        loading entire file into memory.

        Args:
            path: File path (relative to drive root)
            mode: Open mode ('rb' for binary, 'r' for text)

        Returns:
            File-like object for reading

        Raises:
            FileNotFoundError: If file does not exist
            PermissionError: If insufficient read permissions
        """
        ...

    def get_file_size(self, path: Path) -> int:
        """Get the size of a file in bytes.

        Args:
            path: File path (relative to drive root)

        Returns:
            int: File size in bytes

        Raises:
            FileNotFoundError: If file does not exist
        """
        ...
