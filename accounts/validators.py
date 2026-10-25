from django.contrib.auth.password_validation import (
    MinimumLengthValidator,
    UserAttributeSimilarityValidator,
)
from django.core.exceptions import ValidationError


class FriendlyMinimumLengthValidator(MinimumLengthValidator):
    def get_error_message(self):
        return f'Kata sandi terlalu pendek, minimal {self.min_length} karakter.'


class FriendlyUserAttributeSimilarityValidator(UserAttributeSimilarityValidator):
    def get_error_message(self):
        return 'Kata sandi terlalu mirip dengan %(verbose_name)s kamu. Coba kombinasi yang lebih beda.'


class PasswordComplexityValidator:
    def validate(self, password, user=None):
        has_letter = any(char.isalpha() for char in password)
        has_digit = any(char.isdigit() for char in password)
        if not (has_letter and has_digit):
            raise ValidationError(
                'Kata sandi harus mengandung kombinasi huruf dan angka.',
                code='password_no_complexity',
            )

    def get_help_text(self):
        return 'Kata sandi harus mengandung kombinasi huruf dan angka.'
