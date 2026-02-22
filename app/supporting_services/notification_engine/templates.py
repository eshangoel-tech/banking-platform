"""Notification templates for the notification engine."""

NOTIFICATION_TEMPLATES = {
    "LOGIN_OTP": {
        "category": "OTP",
        "allowed_channels": ["SMS", "EMAIL", "WHATSAPP"],
        "required_fields": ["otp"],
        "message": "Your ADX Bank login OTP is {{otp}}. This OTP is valid for 5 minutes. Do not share it with anyone."
    },
    "LOAN_BOOKING_OTP": {
        "category": "OTP",
        "allowed_channels": ["SMS", "EMAIL", "WHATSAPP"],
        "required_fields": ["otp", "amount"],
        "message": "OTP {{otp}} is required to confirm your loan request of ₹{{amount}} from ADX Bank. Valid for 5 minutes."
    },
    "LOAN_REQUESTED_NOTIFICATION": {
        "category": "NOTIFICATION",
        "allowed_channels": ["SMS", "EMAIL", "WHATSAPP"],
        "required_fields": ["amount"],
        "message": "Loan of amount Rs.{{amount}} from ADX Bank is under process."
    },
    "LOAN_APPROVED_NOTIFICATION": {
        "category": "NOTIFICATION",
        "allowed_channels": ["SMS", "EMAIL", "WHATSAPP"],
        "required_fields": ["amount", "name"],
        "message": "Congratulations {{name}}! Your loan of ₹{{amount}} has been approved. Thank you for choosing ADX Bank."
    },
    "LOAN_REJECTED_NOTIFICATION": {
        "category": "NOTIFICATION",
        "allowed_channels": ["SMS", "EMAIL", "WHATSAPP"],
        "required_fields": ["var1"],
        "message": "Hello {{var1}}, we regret to inform you that your loan request has been rejected. Please contact ADX Bank for more details."
    }
}
