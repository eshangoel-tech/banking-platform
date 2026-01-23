"""Application message constants for errors and success messages."""

# Authentication & Authorization
INVALID_CREDENTIALS = "Invalid email or password"
UNAUTHORIZED = "Unauthorized access"
TOKEN_EXPIRED = "Token has expired"
TOKEN_INVALID = "Invalid token"
INSUFFICIENT_PERMISSIONS = "You do not have permission to perform this action"
ACCOUNT_LOCKED = "Account has been locked due to multiple failed login attempts"

# Validation errors
INVALID_INPUT = "Invalid input provided"
MISSING_REQUIRED_FIELD = "Required field is missing"
INVALID_EMAIL_FORMAT = "Invalid email format"
INVALID_PHONE_FORMAT = "Invalid phone number format"
INVALID_AMOUNT = "Invalid amount"
INVALID_DATE_FORMAT = "Invalid date format"
FIELD_TOO_LONG = "Field value exceeds maximum length"
FIELD_TOO_SHORT = "Field value is too short"

# OTP & Verification
OTP_EXPIRED = "OTP has expired"
OTP_INVALID = "Invalid OTP"
OTP_LIMIT_EXCEEDED = "Maximum OTP attempts exceeded for today"
OTP_SENT = "OTP has been sent successfully"

# Resource errors
RESOURCE_NOT_FOUND = "Resource not found"
RESOURCE_ALREADY_EXISTS = "Resource already exists"
RESOURCE_DELETED = "Resource has been deleted"

# Account & User
USER_NOT_FOUND = "User not found"
USER_ALREADY_EXISTS = "User already exists"
ACCOUNT_NOT_FOUND = "Account not found"
ACCOUNT_INACTIVE = "Account is inactive"

# Transaction & Payment
INSUFFICIENT_BALANCE = "Insufficient balance"
TRANSACTION_FAILED = "Transaction failed"
PAYMENT_FAILED = "Payment processing failed"
INVALID_TRANSACTION = "Invalid transaction"
TRANSACTION_NOT_FOUND = "Transaction not found"

# Loan
LOAN_NOT_FOUND = "Loan not found"
LOAN_ALREADY_APPROVED = "Loan has already been approved"
LOAN_ALREADY_REJECTED = "Loan has already been rejected"
INVALID_LOAN_AMOUNT = "Invalid loan amount"
LOAN_ELIGIBILITY_FAILED = "Loan eligibility check failed"

# Rate limiting
RATE_LIMIT_EXCEEDED = "Rate limit exceeded. Please try again later"
TOO_MANY_REQUESTS = "Too many requests. Please try again later"

# Server errors
INTERNAL_SERVER_ERROR = "An internal server error occurred"
SERVICE_UNAVAILABLE = "Service is temporarily unavailable"
DATABASE_ERROR = "Database operation failed"

# Success messages
OPERATION_SUCCESSFUL = "Operation completed successfully"
CREATED_SUCCESSFULLY = "Resource created successfully"
UPDATED_SUCCESSFULLY = "Resource updated successfully"
DELETED_SUCCESSFULLY = "Resource deleted successfully"
LOGIN_SUCCESSFUL = "Login successful"
LOGOUT_SUCCESSFUL = "Logout successful"
PASSWORD_CHANGED = "Password changed successfully"
PROFILE_UPDATED = "Profile updated successfully"
PAYMENT_SUCCESSFUL = "Payment processed successfully"
TRANSACTION_SUCCESSFUL = "Transaction completed successfully"
LOAN_APPLICATION_SUBMITTED = "Loan application submitted successfully"
VERIFICATION_SUCCESSFUL = "Verification completed successfully"
