from rest_framework.exceptions import PermissionDenied


def require_journal_owner(request, journal):
    """Check ownership after the view has looked up a visible journal."""
    if journal.user_id != request.user.pk:
        raise PermissionDenied('Only the journal owner may make this change.')
