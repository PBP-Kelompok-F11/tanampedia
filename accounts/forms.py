from django import forms
from django.contrib.auth.forms import UserCreationForm


class RegisterForm(UserCreationForm):
    display_name = forms.CharField(
        max_length=100,
        required=True,
        label='Nama tampilan',
        error_messages={'required': 'Nama tampilan wajib diisi.'},
    )

    def save(self, commit=True):
        user = super().save(commit=commit)
        if commit:
            user.profile.display_name = self.cleaned_data['display_name'].strip()
            user.profile.save()
        return user
