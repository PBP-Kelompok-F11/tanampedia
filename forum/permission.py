from rest_framework import permissions

class IsAuthorOrReadOnly(permissions.BasePermission):
    message = "Anda tidak memiliki izin untuk mengubah atau menghapus konten ini."

    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        return obj.author == request.user


class IsNotAuthorForUpvote(permissions.BasePermission):
    message = "Anda tidak dapat memberikan upvote pada jawaban Anda sendiri."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        return obj.author != request.user