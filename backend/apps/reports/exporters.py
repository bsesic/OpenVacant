"""Personal data export contribution for reports."""


def collect_reports(user):
    """Reports the user submitted while signed in.

    Anonymous reports carry no link to an account, so they cannot appear here —
    which is the point of submitting anonymously.
    """
    reports = user.reports.all().order_by("created_at")
    return {
        "reports": [
            {
                "reference": report.reference,
                "category": report.category,
                "status": report.status,
                "address": report.address_line,
                "description": report.description,
                "submitted_at": report.created_at.isoformat(),
            }
            for report in reports
        ]
    }
