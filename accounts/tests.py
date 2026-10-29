from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse

from .admin import ProfileAdmin
from .context_processors import google_oauth_enabled
from .forms import ProfileEditForm, RegisterForm
from .models import Profile
from .validators import (
    FriendlyMinimumLengthValidator,
    FriendlyUserAttributeSimilarityValidator,
    PasswordComplexityValidator,
)

User = get_user_model()


class ProfileModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='profile-user', password='TestPass123')

    def test_str(self):
        self.assertEqual(str(self.user.profile), 'profile-user profile')

    def test_display_name_or_username_falls_back_to_username(self):
        self.assertEqual(self.user.profile.display_name_or_username, 'profile-user')

    def test_display_name_or_username_prefers_display_name(self):
        self.user.profile.display_name = 'Zidane'
        self.user.profile.save()
        self.assertEqual(self.user.profile.display_name_or_username, 'Zidane')

    def test_level_thresholds(self):
        cases = [
            (0, 'Petani Magang'),
            (50, 'Petani Magang'),
            (51, 'Tukang Siram'),
            (150, 'Tukang Siram'),
            (151, 'Sobat Cangkul'),
            (300, 'Sobat Cangkul'),
            (301, 'Peracik Pupuk'),
            (600, 'Peracik Pupuk'),
            (601, 'Pawang Hama'),
            (1000, 'Pawang Hama'),
            (1001, 'Ahli Cangkok'),
            (1700, 'Ahli Cangkok'),
            (1701, 'Mandor Kebun'),
            (2800, 'Mandor Kebun'),
            (2801, 'Juragan Bibit'),
            (4500, 'Juragan Bibit'),
            (4501, 'Bos Panen'),
            (7500, 'Bos Panen'),
            (7501, 'Sultan Lahan'),
            (100000, 'Sultan Lahan'),
        ]
        for points, expected_title in cases:
            with self.subTest(points=points):
                self.user.profile.pedia_points = points
                self.assertEqual(self.user.profile.level['title'], expected_title)

    def test_add_points_increases_and_persists(self):
        self.user.profile.add_points(10)
        self.assertEqual(self.user.profile.pedia_points, 10)
        self.assertEqual(Profile.objects.get(user=self.user).pedia_points, 10)

    def test_add_points_accumulates(self):
        self.user.profile.add_points(10)
        self.user.profile.add_points(5)
        self.assertEqual(self.user.profile.pedia_points, 15)

    def test_add_points_does_not_go_below_zero(self):
        self.user.profile.add_points(-100)
        self.assertEqual(self.user.profile.pedia_points, 0)

    def test_add_points_clamps_negative_delta_from_positive_balance(self):
        self.user.profile.add_points(5)
        self.user.profile.add_points(-20)
        self.assertEqual(self.user.profile.pedia_points, 0)


class ProfileAdminTests(TestCase):
    def test_level_title_returns_level_title(self):
        user = User.objects.create_user(username='admin-target', password='TestPass123')
        user.profile.pedia_points = 1000
        admin_instance = ProfileAdmin(Profile, None)
        self.assertEqual(admin_instance.level_title(user.profile), 'Pawang Hama')


class ProfileSignalTests(TestCase):
    def test_profile_created_on_user_creation(self):
        user = User.objects.create_user(username='signal-user', password='TestPass123')
        self.assertTrue(Profile.objects.filter(user=user).exists())
        self.assertEqual(user.profile.pedia_points, 0)

    def test_resaving_existing_user_does_not_duplicate_profile(self):
        user = User.objects.create_user(username='signal-user-2', password='TestPass123')
        user.first_name = 'Updated'
        user.save()
        self.assertEqual(Profile.objects.filter(user=user).count(), 1)


class RegisterFormTests(TestCase):
    def valid_data(self, **overrides):
        data = {
            'display_name': 'New User',
            'username': 'new_user_01',
            'password1': 'Str0ngPassword',
            'password2': 'Str0ngPassword',
        }
        data.update(overrides)
        return data

    def test_valid_data_creates_user_and_profile_display_name(self):
        form = RegisterForm(self.valid_data())
        self.assertTrue(form.is_valid(), form.errors)
        user = form.save()
        self.assertTrue(User.objects.filter(username='new_user_01').exists())
        self.assertEqual(user.profile.display_name, 'New User')

    def test_display_name_is_stripped(self):
        form = RegisterForm(self.valid_data(display_name='  Spacey Name  '))
        self.assertTrue(form.is_valid(), form.errors)
        user = form.save()
        self.assertEqual(user.profile.display_name, 'Spacey Name')

    def test_missing_display_name_is_invalid(self):
        form = RegisterForm(self.valid_data(display_name=''))
        self.assertFalse(form.is_valid())
        self.assertIn('display_name', form.errors)

    def test_password_mismatch_is_invalid(self):
        form = RegisterForm(self.valid_data(password2='SomethingElse123'))
        self.assertFalse(form.is_valid())
        self.assertIn('password2', form.errors)

    def test_weak_password_is_invalid(self):
        form = RegisterForm(self.valid_data(username='weakpwuser', password1='short', password2='short'))
        self.assertFalse(form.is_valid())
        self.assertIn('password2', form.errors)

    def test_save_without_commit_does_not_touch_profile(self):
        form = RegisterForm(self.valid_data(username='uncommitted_user'))
        self.assertTrue(form.is_valid(), form.errors)
        user = form.save(commit=False)
        self.assertIsNone(user.pk)
        self.assertFalse(User.objects.filter(username='uncommitted_user').exists())


class ProfileEditFormTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='edit-form-user', password='TestPass123')

    def test_valid_data_updates_profile(self):
        form = ProfileEditForm({
            'display_name': 'New Name',
            'bio': 'Hobi berkebun',
            'profile_picture_url': 'https://example.com/avatar.png',
        }, instance=self.user.profile)
        self.assertTrue(form.is_valid(), form.errors)
        profile = form.save()
        self.assertEqual(profile.display_name, 'New Name')
        self.assertEqual(profile.bio, 'Hobi berkebun')
        self.assertEqual(profile.profile_picture_url, 'https://example.com/avatar.png')

    def test_blank_optional_fields_are_valid(self):
        form = ProfileEditForm({
            'display_name': '',
            'bio': '',
            'profile_picture_url': '',
        }, instance=self.user.profile)
        self.assertTrue(form.is_valid(), form.errors)

    def test_invalid_profile_picture_url_is_rejected(self):
        form = ProfileEditForm({
            'display_name': 'New Name',
            'bio': '',
            'profile_picture_url': 'not-a-url',
        }, instance=self.user.profile)
        self.assertFalse(form.is_valid())
        self.assertIn('profile_picture_url', form.errors)

    def test_display_name_strips_tags(self):
        # strip_tags removes tag markers only, not their text content - it's
        # not a script sanitizer. The actual XSS protection is that the
        # result later gets rendered via Django's auto-escaping template
        # output (or set via .textContent on the client), never raw HTML.
        form = ProfileEditForm({
            'display_name': 'Hello <b>World</b>',
            'bio': '',
            'profile_picture_url': '',
        }, instance=self.user.profile)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['display_name'], 'Hello World')
        self.assertNotIn('<b>', form.cleaned_data['display_name'])

    def test_bio_strips_tags(self):
        form = ProfileEditForm({
            'display_name': 'Name',
            'bio': 'Suka <b>berkebun</b> organik',
            'profile_picture_url': '',
        }, instance=self.user.profile)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['bio'], 'Suka berkebun organik')


class ValidatorsTests(TestCase):
    def test_friendly_minimum_length_validator_rejects_short_password(self):
        validator = FriendlyMinimumLengthValidator(min_length=8)
        with self.assertRaises(ValidationError) as cm:
            validator.validate('short1')
        self.assertIn('Kata sandi terlalu pendek, minimal 8 karakter.', cm.exception.messages)

    def test_friendly_minimum_length_validator_accepts_long_password(self):
        validator = FriendlyMinimumLengthValidator(min_length=8)
        validator.validate('longenough1')

    def test_friendly_user_attribute_similarity_validator_rejects_similar_password(self):
        validator = FriendlyUserAttributeSimilarityValidator()
        user = User(username='johndoe123')
        with self.assertRaises(ValidationError) as cm:
            validator.validate('johndoe123', user=user)
        self.assertIn('terlalu mirip dengan', cm.exception.messages[0])

    def test_friendly_user_attribute_similarity_validator_accepts_different_password(self):
        validator = FriendlyUserAttributeSimilarityValidator()
        user = User(username='johndoe123')
        validator.validate('Zx9#QuietRiver', user=user)

    def test_password_complexity_validator_rejects_letters_only(self):
        validator = PasswordComplexityValidator()
        with self.assertRaises(ValidationError) as cm:
            validator.validate('onlylettersnoDigits')
        self.assertIn('Kata sandi harus mengandung kombinasi huruf dan angka.', cm.exception.messages)

    def test_password_complexity_validator_rejects_digits_only(self):
        validator = PasswordComplexityValidator()
        with self.assertRaises(ValidationError):
            validator.validate('12345678')

    def test_password_complexity_validator_accepts_mixed_password(self):
        validator = PasswordComplexityValidator()
        validator.validate('letters123')

    def test_password_complexity_validator_help_text(self):
        validator = PasswordComplexityValidator()
        self.assertEqual(
            validator.get_help_text(),
            'Kata sandi harus mengandung kombinasi huruf dan angka.',
        )


class GoogleOAuthContextProcessorTests(TestCase):
    @override_settings(GOOGLE_CLIENT_ID='client-id', GOOGLE_CLIENT_SECRET='client-secret')
    def test_enabled_when_both_credentials_set(self):
        self.assertEqual(google_oauth_enabled(None), {'google_oauth_enabled': True})

    @override_settings(GOOGLE_CLIENT_ID='', GOOGLE_CLIENT_SECRET='')
    def test_disabled_when_both_missing(self):
        self.assertEqual(google_oauth_enabled(None), {'google_oauth_enabled': False})

    @override_settings(GOOGLE_CLIENT_ID='client-id', GOOGLE_CLIENT_SECRET='')
    def test_disabled_when_only_client_id_set(self):
        self.assertEqual(google_oauth_enabled(None), {'google_oauth_enabled': False})


class RegisterViewTests(TestCase):
    def test_get_renders_form(self):
        response = self.client.get(reverse('accounts:register'))
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.context['form'], RegisterForm)

    def test_post_valid_creates_user_and_redirects_to_login(self):
        response = self.client.post(reverse('accounts:register'), {
            'display_name': 'View User',
            'username': 'view_user',
            'password1': 'Str0ngPassword',
            'password2': 'Str0ngPassword',
        })
        self.assertRedirects(response, reverse('accounts:login'))
        self.assertTrue(User.objects.filter(username='view_user').exists())

    def test_post_invalid_rerenders_with_errors(self):
        response = self.client.post(reverse('accounts:register'), {
            'display_name': 'View User',
            'username': 'view_user_bad',
            'password1': 'Str0ngPassword',
            'password2': 'DoesNotMatch',
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username='view_user_bad').exists())
        self.assertTrue(response.context['form'].errors)


class LoginViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='login-user', password='Str0ngPassword')

    def test_get_renders_form(self):
        response = self.client.get(reverse('accounts:login'))
        self.assertEqual(response.status_code, 200)

    def test_post_valid_logs_in_and_redirects_to_profile_by_default(self):
        response = self.client.post(reverse('accounts:login'), {
            'username': 'login-user',
            'password': 'Str0ngPassword',
        })
        self.assertRedirects(response, reverse('accounts:profile'))
        self.assertIn('_auth_user_id', self.client.session)

    def test_post_invalid_credentials_shows_error(self):
        response = self.client.post(reverse('accounts:login'), {
            'username': 'login-user',
            'password': 'WrongPassword',
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['form'].errors)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_get_with_safe_next_is_echoed_in_hidden_field(self):
        response = self.client.get(reverse('accounts:login'), {'next': '/kuis/'})
        self.assertContains(response, 'value="/kuis/"')

    def test_post_with_safe_next_redirects_there(self):
        response = self.client.post(reverse('accounts:login'), {
            'username': 'login-user',
            'password': 'Str0ngPassword',
            'next': '/kuis/',
        })
        self.assertRedirects(response, '/kuis/')

    def test_post_with_unsafe_next_falls_back_to_profile(self):
        response = self.client.post(reverse('accounts:login'), {
            'username': 'login-user',
            'password': 'Str0ngPassword',
            'next': 'https://evil.example.com/',
        })
        self.assertRedirects(response, reverse('accounts:profile'))

    def test_get_with_unsafe_next_is_not_echoed_in_form(self):
        # The Google button's own {% provider_login_url %} tag independently
        # echoes request.GET['next'] into its own href - that's allauth's
        # behavior, validated by allauth itself once the OAuth flow
        # completes. What we control is the manual login form's hidden
        # "next" field, which must not carry an unvalidated value through.
        response = self.client.get(reverse('accounts:login'), {'next': 'https://evil.example.com/'})
        self.assertNotContains(response, 'name="next"')


class LogoutViewTests(TestCase):
    def test_logout_logs_out_and_redirects_home(self):
        user = User.objects.create_user(username='logout-user', password='Str0ngPassword')
        self.client.force_login(user)
        response = self.client.get(reverse('accounts:logout'))
        self.assertRedirects(response, reverse('main:home'))
        self.assertNotIn('_auth_user_id', self.client.session)


class ProfileViewTests(TestCase):
    def test_anonymous_is_redirected_to_login(self):
        response = self.client.get(reverse('accounts:profile'))
        self.assertRedirects(
            response,
            f"{reverse('accounts:login')}?next={reverse('accounts:profile')}",
        )

    def test_authenticated_user_sees_own_profile(self):
        user = User.objects.create_user(username='profile-view-user', password='Str0ngPassword')
        user.profile.display_name = 'Profile View User'
        user.profile.save()
        self.client.force_login(user)
        response = self.client.get(reverse('accounts:profile'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['profile'], user.profile)
        self.assertContains(response, 'Profile View User')
        self.assertIsInstance(response.context['edit_form'], ProfileEditForm)

    def test_sole_user_is_rank_one(self):
        user = User.objects.create_user(username='rank-sole-user', password='Str0ngPassword')
        self.client.force_login(user)
        response = self.client.get(reverse('accounts:profile'))
        self.assertEqual(response.context['leaderboard_rank'], 1)
        self.assertContains(response, '#1 di Leaderboard')

    def test_rank_reflects_position_among_other_profiles(self):
        leader = User.objects.create_user(username='rank-leader', password='Str0ngPassword')
        leader.profile.pedia_points = 500
        leader.profile.save()

        me = User.objects.create_user(username='rank-me', password='Str0ngPassword')
        me.profile.pedia_points = 100
        me.profile.save()

        self.client.force_login(me)
        response = self.client.get(reverse('accounts:profile'))
        self.assertEqual(response.context['leaderboard_rank'], 2)
        self.assertContains(response, '#2 di Leaderboard')

    def test_tied_points_share_the_same_rank(self):
        me = User.objects.create_user(username='rank-tied-me', password='Str0ngPassword')
        me.profile.pedia_points = 300
        me.profile.save()

        rival = User.objects.create_user(username='rank-tied-rival', password='Str0ngPassword')
        rival.profile.pedia_points = 300
        rival.profile.save()

        lower = User.objects.create_user(username='rank-tied-lower', password='Str0ngPassword')
        lower.profile.pedia_points = 50
        lower.profile.save()

        self.client.force_login(me)
        response = self.client.get(reverse('accounts:profile'))
        # Both tied users are #1; the next distinct score is #3, not #2.
        self.assertEqual(response.context['leaderboard_rank'], 1)

        self.client.force_login(lower)
        response = self.client.get(reverse('accounts:profile'))
        self.assertEqual(response.context['leaderboard_rank'], 3)


class EditProfileViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='edit-view-user', password='Str0ngPassword')
        self.client.force_login(self.user)

    def test_anonymous_cannot_edit(self):
        self.client.logout()
        response = self.client.post(reverse('accounts:edit_profile'), {
            'display_name': 'New Name',
            'bio': '',
            'profile_picture_url': '',
        })
        self.assertRedirects(
            response,
            f"{reverse('accounts:login')}?next={reverse('accounts:edit_profile')}",
        )

    def test_get_is_not_allowed(self):
        response = self.client.get(reverse('accounts:edit_profile'))
        self.assertEqual(response.status_code, 405)

    def test_valid_post_updates_profile_and_returns_json(self):
        response = self.client.post(reverse('accounts:edit_profile'), {
            'display_name': 'Updated Name',
            'bio': 'Suka berkebun organik',
            'profile_picture_url': 'https://example.com/avatar.png',
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['display_name'], 'Updated Name')
        self.assertEqual(data['display_name_or_username'], 'Updated Name')
        self.assertEqual(data['bio'], 'Suka berkebun organik')
        self.assertEqual(data['profile_picture_url'], 'https://example.com/avatar.png')

        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.display_name, 'Updated Name')

    def test_invalid_post_returns_field_errors(self):
        response = self.client.post(reverse('accounts:edit_profile'), {
            'display_name': 'Updated Name',
            'bio': '',
            'profile_picture_url': 'not-a-url',
        })
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertIn('profile_picture_url', data['errors'])

    def test_script_tags_are_stripped_before_saving(self):
        response = self.client.post(reverse('accounts:edit_profile'), {
            'display_name': 'Name <script>alert(1)</script>',
            'bio': '',
            'profile_picture_url': '',
        })
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('<script>', response.json()['display_name'])
        self.user.profile.refresh_from_db()
        self.assertNotIn('<script>', self.user.profile.display_name)
