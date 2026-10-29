from django.db import models
from django.conf import settings

class Question(models.Model):
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='forum_questions'
    )
    title = models.CharField(max_length=255)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title

class Answer(models.Model):
    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        related_name='answers'
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='forum_answers'
    )
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    upvotes = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name='upvoted_forum_answers',
        blank=True
    )

    @property
    def total_upvotes(self):
        return self.upvotes.count()

    def __str__(self):
        return f"Answer by {self.author} on '{self.question.title}'"