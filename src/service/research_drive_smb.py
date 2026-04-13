"""SMB Protocol implementation for research drive access.

Uses smbprotocol library to connect to network drives via SMB.
Handles authentication with service account credentials.
Supports large file streaming for TB-scale data.
"""

from pathlib import Path
from typing import Iterator, Literal

import smbclient


class ResearchDriveSMB:
    """Access research drive via SMB protocol with service account credentials.

    Handles authentication, connection verification, and file operations.
    Supports streaming access for large files to avoid memory overload.
    """

    def __init__(
        self,
        drive_name: str,
        base_path: str,
        username: str,
        password: str,
    ) -> None:
        """Initialize SMB research drive connection.

        Args:
            drive_name: Name of the research drive (e.g., 'RDATA-001')
            base_path: Base SMB path (e.g., '//files.auckland.ac.nz/research')
            username: Service account username
            password: Service account password

        Example:
            drive = ResearchDriveSMB(
                drive_name='RDATA-001',
                base_path='//files.auckland.ac.nz/research',
                username='service_account',
                password='secret'
            )
            drive.verify_access()
            root = drive.get_root_path()
        """
        self.drive_name = drive_name
        self.base_path = base_path
        self.username = username
        self.password = password
        self._root_path = Path(base_path) / drive_name
        self._server = self._extract_server(base_path)
        self._register_session()

    @staticmethod
    def _extract_server(base_path: str) -> str:
        """Extract SMB server name from UNC-style path.

        Example: "//files.auckland.ac.nz/research" -> "files.auckland.ac.nz"
        """
        normalized = base_path.replace("\\", "/").lstrip("/")
        server = normalized.split("/", 1)[0]
        if not server:
            raise ValueError(f"Invalid SMB base path '{base_path}'. Expected UNC path.")
        return server

    def _register_session(self) -> None:
        """Register SMB credentials once for this server.

        Uses both ClientConfig (global default) and register_session
        (server-specific override) so subsequent operations do not need
        per-call username/password.
        """
        smbclient.ClientConfig(username=self.username, password=self.password)
        smbclient.register_session(
            self._server,
            username=self.username,
            password=self.password,
        )

    def verify_access(self) -> None:
        """Verify that the drive is accessible and permissions are valid.

        Attempts to list the root directory using service account credentials.

        Raises:
            FileNotFoundError: If drive is inaccessible
            PermissionError: If credentials lack sufficient permissions
            ConnectionError: If connection to drive fails
        """
        smb_path = str(self._root_path)
        try:
            # Try to list the root directory to verify access
            smbclient.listdir(smb_path)
        except FileNotFoundError as e:
            raise FileNotFoundError(
                f"Research Drive '{self.drive_name}' not found at {smb_path}"
            ) from e
        except PermissionError as e:
            raise PermissionError(
                f"Access denied to research drive '{self.drive_name}'. "
                "Check service account credentials and permissions."
            ) from e
        except Exception as e:
            raise ConnectionError(
                f"Failed to connect to research drive '{self.drive_name}': {str(e)}"
            ) from e

    def get_root_path(self) -> Path:
        """Get the root path for this research drive.

        Returns:
            Path: The root path for this drive
        """
        return self._root_path

    def exists(self, path: Path) -> bool:
        """Check if a path exists on the drive.

        Args:
            path: Path to check (relative to drive root)

        Returns:
            bool: True if path exists, False otherwise
        """
        try:
            full_path = str(self._root_path / path)
            smbclient.stat(full_path)
            return True
        except FileNotFoundError:
            return False
        except Exception:
            # For other errors (permission, connection), consider it not existing
            return False

    def is_directory(self, path: Path) -> bool:
        """Check if a path is a directory.

        Args:
            path: Path to check (relative to drive root)

        Returns:
            bool: True if path is a directory, False otherwise

        Raises:
            FileNotFoundError: If path does not exist
        """
        try:
            full_path = str(self._root_path / path)
            stat_info = smbclient.stat(full_path)
            # Check if it's a directory (mode includes directory flag)
            return bool(stat_info.st_file_attributes & 0x10)  # FILE_ATTRIBUTE_DIRECTORY
        except FileNotFoundError as e:
            raise FileNotFoundError(f"Path does not exist: {path}") from e
        except Exception as e:
            raise FileNotFoundError(f"Error checking path: {path}") from e

    def list_directory(self, path: Path) -> Iterator[Path]:
        """List contents of a directory.

        Args:
            path: Directory path (relative to drive root)

        Yields:
            Path: Relative paths of items in the directory

        Raises:
            FileNotFoundError: If path does not exist
            NotADirectoryError: If path is not a directory
        """
        full_path = str(self._root_path / path)
        try:
            entries = smbclient.listdir(full_path)
            for entry in entries:
                yield Path(entry)
        except FileNotFoundError as e:
            raise FileNotFoundError(f"Directory does not exist: {path}") from e
        except Exception as e:
            raise Exception(f"Error listing directory {path}: {str(e)}") from e

    def open_file(self, path: Path, mode: Literal["rb", "r"] = "rb"):
        """Open a file for reading.

        Supports streaming to handle large files without loading
        entire contents into memory.

        Args:
            path: File path (relative to drive root)
            mode: Open mode ('rb' for binary, 'r' for text)

        Returns:
            File-like object for reading

        Raises:
            FileNotFoundError: If file does not exist
            PermissionError: If insufficient read permissions
        """
        full_path = str(self._root_path / path)
        try:
            # Open file using smbclient
            file_obj = smbclient.open_file(full_path, mode=mode)
            return file_obj
        except FileNotFoundError as e:
            raise FileNotFoundError(f"File does not exist: {path}") from e
        except PermissionError as e:
            raise PermissionError(f"Permission denied reading file: {path}") from e
        except Exception as e:
            raise Exception(f"Error opening file {path}: {str(e)}") from e

    def get_file_size(self, path: Path) -> int:
        """Get the size of a file in bytes.

        Args:
            path: File path (relative to drive root)

        Returns:
            int: File size in bytes

        Raises:
            FileNotFoundError: If file does not exist
        """
        try:
            full_path = str(self._root_path / path)
            stat_info = smbclient.stat(full_path)
            return stat_info.st_size
        except FileNotFoundError as e:
            raise FileNotFoundError(f"File does not exist: {path}") from e
        except Exception as e:
            raise Exception(f"Error getting file size for {path}: {str(e)}") from e
