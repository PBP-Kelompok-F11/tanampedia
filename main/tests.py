from unittest.mock import patch, MagicMock

import requests
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from . import trefle


def _mock_response(status_code=200, json_data=None, raise_json_error=False):
    response = MagicMock()
    response.status_code = status_code
    response.ok = 200 <= status_code < 300
    if raise_json_error:
        response.json.side_effect = ValueError("bad json")
    else:
        response.json.return_value = json_data or {}
    return response


SEARCH_PAYLOAD = {
    "data": [
        {
            "id": 1,
            "common_name": "Tomat",
            "scientific_name": "Solanum lycopersicum",
            "family": "Solanaceae",
            "family_common_name": "Nightshades",
            "slug": "solanum-lycopersicum",
            "links": {"self": "/api/v1/species/solanum-lycopersicum"},
        }
    ],
    "meta": {"total": 1, "page": 1, "per_page": 20},
    "links": {},
}

DETAIL_PAYLOAD = {
    "data": {
        "id": 1,
        "common_name": "Tomat",
        "scientific_name": "Solanum lycopersicum",
        "family": "Solanaceae",
        "family_common_name": "Nightshades",
        "genus": "Solanum",
        "year": 1753,
        "slug": "solanum-lycopersicum",
        "links": {"self": "/api/v1/species/solanum-lycopersicum"},
        "main_species": {
            "growth": {
                "light": 7,
                "minimum_temperature": {"deg_c": 10},
                "maximum_temperature": {"deg_c": 35},
            }
        },
    }
}


@override_settings(TREFLE_API_TOKEN="test-token")
class TrefleServiceTests(TestCase):
    """Unit tests for the service layer, mocking requests.get directly so
    no real network call is ever made."""

    def setUp(self):
        from django.core.cache import cache
        cache.clear()

    @patch("main.trefle.requests.get")
    def test_search_plants_success(self, mock_get):
        mock_get.return_value = _mock_response(200, SEARCH_PAYLOAD)
        data, meta = trefle.search_plants("tomat")
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["common_name"], "Tomat")
        self.assertEqual(meta["total"], 1)

    @patch("main.trefle.requests.get")
    def test_search_plants_caches_result(self, mock_get):
        mock_get.return_value = _mock_response(200, SEARCH_PAYLOAD)
        trefle.search_plants("tomat")
        trefle.search_plants("tomat")
        self.assertEqual(mock_get.call_count, 1)

    @patch("main.trefle.requests.get")
    def test_get_plant_detail_success(self, mock_get):
        mock_get.return_value = _mock_response(200, DETAIL_PAYLOAD)
        plant = trefle.get_plant_detail("solanum-lycopersicum")
        self.assertEqual(plant["common_name"], "Tomat")
        care = trefle.extract_care_info(plant)
        labels = [c["label"] for c in care]
        self.assertIn("Kebutuhan cahaya (skala 0-10)", labels)
        # fields Trefle didn't return must not be fabricated
        self.assertNotIn("Toleransi salinitas tanah (skala 0-10)", labels)

    @patch("main.trefle.requests.get")
    def test_get_plant_detail_not_found(self, mock_get):
        mock_get.return_value = _mock_response(404)
        plant = trefle.get_plant_detail("does-not-exist")
        self.assertIsNone(plant)

    @patch("main.trefle.requests.get")
    def test_timeout_raises_unavailable(self, mock_get):
        mock_get.side_effect = requests.exceptions.Timeout()
        with self.assertRaises(trefle.TrefleUnavailable):
            trefle.search_plants("tomat")

    @patch("main.trefle.requests.get")
    def test_connection_error_raises_unavailable(self, mock_get):
        mock_get.side_effect = requests.exceptions.ConnectionError()
        with self.assertRaises(trefle.TrefleUnavailable):
            trefle.search_plants("tomat")

    @patch("main.trefle.requests.get")
    def test_rate_limit_raises_rate_limited(self, mock_get):
        mock_get.return_value = _mock_response(429)
        with self.assertRaises(trefle.TrefleRateLimited):
            trefle.search_plants("tomat")

    @patch("main.trefle.requests.get")
    def test_invalid_json_raises_unavailable(self, mock_get):
        mock_get.return_value = _mock_response(200, raise_json_error=True)
        with self.assertRaises(trefle.TrefleUnavailable):
            trefle.search_plants("tomat")

    @patch("main.trefle.requests.get")
    def test_empty_query_lists_instead_of_searching(self, mock_get):
        mock_get.return_value = _mock_response(200, {"data": [], "meta": {}})
        trefle.search_plants("   ")
        called_url = mock_get.call_args[0][0]
        self.assertIn("/species", called_url)
        self.assertNotIn("/search", called_url)


@override_settings(TREFLE_API_TOKEN="")
class TrefleNotConfiguredTests(TestCase):
    def test_missing_token_raises_not_configured(self):
        from django.core.cache import cache
        cache.clear()
        with self.assertRaises(trefle.TrefleNotConfigured):
            trefle.search_plants("tomat")


@override_settings(TREFLE_API_TOKEN="test-token")
class KatalogViewTests(TestCase):
    def setUp(self):
        from django.core.cache import cache
        cache.clear()

    @patch("main.trefle.requests.get")
    def test_list_view_renders_results(self, mock_get):
        mock_get.return_value = _mock_response(200, SEARCH_PAYLOAD)
        response = self.client.get(reverse("main:katalog_list"), {"q": "tomat"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Tomat")

    @patch("main.trefle.requests.get")
    def test_list_view_empty_state(self, mock_get):
        mock_get.return_value = _mock_response(200, {"data": [], "meta": {}})
        response = self.client.get(reverse("main:katalog_list"), {"q": "zzzznotaplant"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Tidak ada tanaman")

    @patch("main.trefle.requests.get")
    def test_list_view_error_state_does_not_500(self, mock_get):
        mock_get.side_effect = requests.exceptions.Timeout()
        response = self.client.get(reverse("main:katalog_list"), {"q": "tomat"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "tidak bisa diakses")

    @patch("main.trefle.requests.get")
    def test_detail_view_renders(self, mock_get):
        mock_get.return_value = _mock_response(200, DETAIL_PAYLOAD)
        response = self.client.get(
            reverse("main:katalog_detail", kwargs={"slug": "solanum-lycopersicum"})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Tomat")
        self.assertContains(response, "Kebutuhan cahaya")

    @patch("main.trefle.requests.get")
    def test_detail_view_404_for_unknown_plant(self, mock_get):
        mock_get.return_value = _mock_response(404)
        response = self.client.get(
            reverse("main:katalog_detail", kwargs={"slug": "does-not-exist"})
        )
        self.assertEqual(response.status_code, 404)

    @patch("main.trefle.requests.get")
    def test_detail_view_error_state_does_not_500(self, mock_get):
        mock_get.side_effect = requests.exceptions.ConnectionError()
        response = self.client.get(
            reverse("main:katalog_detail", kwargs={"slug": "solanum-lycopersicum"})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "tidak bisa dimuat")

    @override_settings(TREFLE_API_TOKEN="")
    def test_list_view_without_token_shows_friendly_message_no_crash(self):
        from django.core.cache import cache
        cache.clear()
        response = self.client.get(reverse("main:katalog_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "belum terhubung")

    @patch("main.trefle.requests.get")
    def test_token_is_never_rendered_in_html(self, mock_get):
        mock_get.return_value = _mock_response(200, DETAIL_PAYLOAD)
        response = self.client.get(
            reverse("main:katalog_detail", kwargs={"slug": "solanum-lycopersicum"})
        )
        self.assertNotContains(response, "test-token")

    @patch("main.trefle.requests.get")
    def test_token_not_in_outgoing_request_logged_url_leak_via_params_only(self, mock_get):
        # Token is sent as a query param to Trefle (required by their API),
        # never hardcoded/logged elsewhere. This asserts it's passed through
        # params, not embedded directly in a string we might log verbatim.
        mock_get.return_value = _mock_response(200, SEARCH_PAYLOAD)
        trefle.search_plants("tomat")
        _, kwargs = mock_get.call_args
        self.assertEqual(kwargs["params"]["token"], "test-token")

    def test_navbar_katalog_link_is_wired(self):
        response = self.client.get(reverse("main:home"))
        self.assertContains(response, reverse("main:katalog_list"))


class LeaderboardViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.users = []
        for i, points in enumerate([900, 800, 700, 600, 500, 400, 300, 200, 100, 50, 10]):
            user = User.objects.create_user(username=f"lb-user-{i}")
            user.profile.pedia_points = points
            user.profile.save()
            cls.users.append(user)

    def test_anonymous_can_view_leaderboard(self):
        response = self.client.get(reverse("main:leaderboard"))
        self.assertEqual(response.status_code, 200)

    def test_shows_at_most_top_ten(self):
        response = self.client.get(reverse("main:leaderboard"))
        self.assertEqual(len(response.context["top_profiles"]), 10)

    def test_ranked_highest_points_first(self):
        response = self.client.get(reverse("main:leaderboard"))
        points = [profile.pedia_points for profile in response.context["top_profiles"]]
        self.assertEqual(points, sorted(points, reverse=True))

    def test_eleventh_place_is_excluded(self):
        response = self.client.get(reverse("main:leaderboard"))
        self.assertNotContains(response, "lb-user-10")

    def test_top_scorer_is_shown(self):
        response = self.client.get(reverse("main:leaderboard"))
        self.assertContains(response, "lb-user-0")

    def test_navbar_links_to_leaderboard_not_design_system(self):
        response = self.client.get(reverse("main:home"))
        self.assertContains(response, reverse("main:leaderboard"))
        self.assertNotContains(response, "Design System")


class LeaderboardEmptyStateTests(TestCase):
    def test_shows_empty_message_when_no_profiles_exist(self):
        response = self.client.get(reverse("main:leaderboard"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["top_profiles"]), 0)
        self.assertContains(response, "Belum ada data PediaPoints")
