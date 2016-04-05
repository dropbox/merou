REQUEST_STATUS_CHOICES = {
    # Request has been made and awaiting action.
    "pending": set(["actioned", "cancelled"]),
    "actioned": set([]),
    "cancelled": set([]),
}
