from django import forms


class CustomSignupForm(forms.Form):
    """
    Mixed into allauth's SignupForm via ACCOUNT_SIGNUP_FORM_CLASS — allauth
    builds a combined form from its own base SignupForm plus this one, and
    calls signup(request, user) after the User is created.
    """

    display_name = forms.CharField(
        max_length=100,
        required=True,
        label='Nama tampilan',
        error_messages={'required': 'Nama tampilan wajib diisi.'},
    )

    def signup(self, request, user):
        user.profile.display_name = self.cleaned_data['display_name'].strip()
        user.profile.save()
