from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.utils.html import strip_tags

from .models import Profile


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


class ProfileEditForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ['display_name', 'bio', 'profile_picture_url']
        widgets = {
            'bio': forms.Textarea(attrs={'rows': 3}),
        }

    def clean_display_name(self):
        return strip_tags(self.cleaned_data['display_name']).strip()

    def clean_bio(self):
        return strip_tags(self.cleaned_data['bio']).strip()
