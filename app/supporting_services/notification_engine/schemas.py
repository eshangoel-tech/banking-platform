"""Pydantic schemas for Notification Engine APIs."""

from typing import Dict, Any, Literal

from pydantic import BaseModel, Field


class SendOTPRequest(BaseModel):
    """Schema for sending OTP requests."""

    channel: Literal["SMS", "EMAIL", "WHATSAPP"] = Field(
        ...,
        description="Channel through which OTP will be sent"
    )
    category: Literal["OTP"] = Field(
        ...,
        description="Must always be OTP for this API"
    )
    template_id: str = Field(
        ...,
        description="OTP template ID (e.g. LOGIN_OTP, LOAN_BOOKING_OTP)"
    )
    auth_value: str = Field(
        ...,
        description="Phone number or email depending on channel"
    )
    template_data: Dict[str, Any] = Field(
        ...,
        description="Key-value map for template variables (otp is injected by backend)"
    )
    flow: Literal["test_notify", "prod_notify"] = Field(
        ...,
        description="Flow identifier (mini-project vs bank)"
    )


class VerifyOTPRequest(BaseModel):
    """Schema for verifying OTP requests."""

    otp_id: str = Field(
        ...,
        description="OTP identifier received from send OTP API"
    )
    otp_value: str = Field(
        ...,
        description="OTP entered by the user"
    )
    flow: Literal["test_notify", "prod_notify"] = Field(
        ...,
        description="Flow identifier"
    )


class SendNotificationRequest(BaseModel):
    """Schema for sending notification requests."""

    channel: Literal["SMS", "EMAIL", "WHATSAPP"] = Field(
        ...,
        description="Channel through which notification will be sent"
    )
    category: Literal["NOTIFICATION"] = Field(
        ...,
        description="Must always be NOTIFICATION for this API"
    )
    template_id: str = Field(
        ...,
        description="Notification template ID"
    )
    template_data: Dict[str, Any] = Field(
        ...,
        description="Key-value map for template variables"
    )
    flow: Literal["test_notify", "prod_notify"] = Field(
        ...,
        description="Flow identifier (mini-project vs bank)"
    )
