"""Typed exception hierarchy and error code mapping."""

from __future__ import annotations


class SynologyError(Exception):
    """Base exception for all Synology DSM errors."""

    def __init__(self, message: str, code: int | None = None, suggestion: str | None = None):
        self.code = code
        self.suggestion = suggestion
        super().__init__(message)


class AuthenticationError(SynologyError):
    """Authentication failed (bad credentials, 2FA required, etc.)."""


class SessionExpiredError(SynologyError):
    """Session expired or invalidated (codes 106, 107, 119)."""


class PermissionError(SynologyError):  # noqa: A001
    """Permission denied (code 105). NOT a session issue — never re-auth on this."""


class ApiNotFoundError(SynologyError):
    """Requested API does not exist on this NAS."""


class FileStationError(SynologyError):
    """Base exception for File Station API errors."""


class PathNotFoundError(FileStationError):
    """Path not found (code 408)."""


class FileExistsError(FileStationError):  # noqa: A001
    """File already exists at destination (code 414)."""


class DiskFullError(FileStationError):
    """No space left on device (code 416)."""


class IllegalNameError(FileStationError):
    """Invalid file or folder name (codes 418, 419)."""


# Common DSM error codes (100-series) shared across all APIs.
COMMON_ERROR_CODES: dict[int, tuple[str, str]] = {
    100: ("Unknown error", "Check NAS logs for details."),
    101: ("Invalid parameter", "Check the parameter values in your request."),
    102: ("API does not exist", "The requested API is not available on this NAS."),
    103: (
        "Method does not exist",
        "The requested method is not supported by this API version.",
    ),
    104: ("Not allowed version", "The API version is not supported by this NAS."),
    105: (
        "Permission denied",
        "The MCP service account may not have access. Check DSM user permissions.",
    ),
    106: ("Session timeout", "Session has expired. Re-authentication will be attempted."),
    107: (
        "Duplicate login",
        "Another session displaced this one. Consider using a dedicated DSM service account.",
    ),
    119: ("Invalid session", "Session ID is invalid. Re-authentication will be attempted."),
}

# File Station error codes (400-series).
FILESTATION_ERROR_CODES: dict[int, tuple[str, str]] = {
    400: ("Invalid parameter", "Check path format and parameter values."),
    401: ("Unknown error", "An unknown file operation error occurred. Retry or check NAS logs."),
    402: ("System too busy", "The NAS is too busy. Wait and retry."),
    408: ("No such file or directory", "Use list_files or search_files to find the correct path."),
    414: ("File already exists", "Use overwrite=true to replace existing files."),
    415: ("Disk quota exceeded", "Free space or contact NAS administrator."),
    416: ("No space left on device", "Free space on the NAS."),
    418: (
        "Illegal name or path",
        'Avoid characters: / \\ : * ? " < > |',
    ),
    419: (
        "Illegal file name",
        'Avoid characters: / \\ : * ? " < > |',
    ),
    421: ("Device or resource busy", "The file is in use by another process. Wait and retry."),
    599: ("No such task", "Background task not found (may have already completed)."),
}


def error_from_code(code: int, api_name: str = "") -> SynologyError:
    """Create a typed exception from a DSM error code.

    Checks File Station codes first if api_name contains 'FileStation',
    then falls back to common codes.
    """
    # Check File Station codes for FileStation APIs
    if "FileStation" in api_name and code in FILESTATION_ERROR_CODES:
        message, suggestion = FILESTATION_ERROR_CODES[code]
        if code == 408:
            return PathNotFoundError(message, code=code, suggestion=suggestion)
        if code == 414:
            return FileExistsError(message, code=code, suggestion=suggestion)
        if code == 416:
            return DiskFullError(message, code=code, suggestion=suggestion)
        if code in (418, 419):
            return IllegalNameError(message, code=code, suggestion=suggestion)
        return FileStationError(message, code=code, suggestion=suggestion)

    # Common codes
    if code in COMMON_ERROR_CODES:
        message, suggestion = COMMON_ERROR_CODES[code]
        if code == 105:
            return PermissionError(message, code=code, suggestion=suggestion)
        if code in (106, 107, 119):
            return SessionExpiredError(message, code=code, suggestion=suggestion)
        if code == 102:
            return ApiNotFoundError(message, code=code, suggestion=suggestion)
        if code in (403,):
            return AuthenticationError(message, code=code, suggestion=suggestion)
        return SynologyError(message, code=code, suggestion=suggestion)

    # Also check FileStation codes for non-FileStation APIs (fallback)
    if code in FILESTATION_ERROR_CODES:
        message, suggestion = FILESTATION_ERROR_CODES[code]
        return SynologyError(message, code=code, suggestion=suggestion)

    return SynologyError(f"Unknown error (code {code})", code=code)
