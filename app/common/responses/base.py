"""Reusable API response helpers with standardized structure."""
from typing import Any, Dict, Optional

from fastapi import status
from fastapi.responses import JSONResponse


class APIResponse:
    """Standardized API response structure."""

    def __init__(
        self,
        success: bool,
        data: Any = None,
        message: Optional[str] = None,
        layout: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize API response.
        
        Args:
            success: Whether the operation was successful
            data: Response data payload
            message: Response message
            layout: Optional layout metadata for UI
        """
        self.success = success
        self.data = data
        self.message = message
        self.layout = layout or {}

    def to_dict(self) -> Dict[str, Any]:
        """Convert response to dictionary."""
        return {
            "success": self.success,
            "layout": self.layout,
            "data": self.data,
            "message": self.message,
        }

    def to_json_response(
        self, status_code: int = status.HTTP_200_OK
    ) -> JSONResponse:
        """
        Convert response to FastAPI JSONResponse.
        
        Args:
            status_code: HTTP status code
            
        Returns:
            JSONResponse: FastAPI JSON response
        """
        return JSONResponse(
            content=self.to_dict(),
            status_code=status_code,
        )


def success_response(
    data: Any = None,
    message: Optional[str] = None,
    layout: Optional[Dict[str, Any]] = None,
    status_code: int = status.HTTP_200_OK,
) -> JSONResponse:
    """
    Create a success response.
    
    Args:
        data: Response data payload
        message: Success message
        layout: Optional layout metadata for UI
        status_code: HTTP status code (default: 200)
        
    Returns:
        JSONResponse: FastAPI JSON response with success structure
    """
    response = APIResponse(
        success=True,
        data=data,
        message=message,
        layout=layout,
    )
    return response.to_json_response(status_code=status_code)


def error_response(
    message: str,
    data: Any = None,
    layout: Optional[Dict[str, Any]] = None,
    status_code: int = status.HTTP_400_BAD_REQUEST,
) -> JSONResponse:
    """
    Create an error response.
    
    Args:
        message: Error message
        data: Optional error data/details
        layout: Optional layout metadata for UI
        status_code: HTTP status code (default: 400)
        
    Returns:
        JSONResponse: FastAPI JSON response with error structure
    """
    response = APIResponse(
        success=False,
        data=data,
        message=message,
        layout=layout,
    )
    return response.to_json_response(status_code=status_code)
