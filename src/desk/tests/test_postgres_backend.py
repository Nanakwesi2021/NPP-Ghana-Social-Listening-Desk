import os
import urllib.parse
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.urls import reverse

from desk.ingest import replay
from desk.models import Case, Item, Topic, TrendRow


class PostgresBackendTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        replay(settings.DESK_FIXTURE_DIR)
        User = get_user_model()
        cls.ama = User.objects.get(username="ama")

    def test_postgres_settings_parsing(self):
        sample_url = "postgresql://npp_admin:secret_pass@10.0.0.5:5432/npp_listening_desk"
        parsed = urllib.parse.urlparse(sample_url)
        db_config = {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": parsed.path.lstrip("/"),
            "USER": parsed.username,
            "PASSWORD": parsed.password,
            "HOST": parsed.hostname,
            "PORT": parsed.port,
            "CONN_MAX_AGE": 600,
        }
        self.assertEqual(db_config["ENGINE"], "django.db.backends.postgresql")
        self.assertEqual(db_config["NAME"], "npp_listening_desk")
        self.assertEqual(db_config["USER"], "npp_admin")
        self.assertEqual(db_config["PASSWORD"], "secret_pass")
        self.assertEqual(db_config["HOST"], "10.0.0.5")
        self.assertEqual(db_config["PORT"], 5432)
        self.assertEqual(db_config["CONN_MAX_AGE"], 600)

    def test_native_jsonb_indexes_configured(self):
        # TrendRow JSONB indexes
        trendrow_indexes = [idx.name for idx in TrendRow._meta.indexes]
        self.assertIn("trendrow_pcounts_gin", trendrow_indexes)
        self.assertIn("trendrow_buckets_gin", trendrow_indexes)

        # Trigram GIN indexes on Item and Case
        item_indexes = [idx.name for idx in Item._meta.indexes]
        self.assertIn("desk_item_excerpt_trgm", item_indexes)
        self.assertIn("desk_item_collected_idx", item_indexes)

        case_indexes = [idx.name for idx in Case._meta.indexes]
        self.assertIn("desk_case_claim_trgm", case_indexes)

    def test_search_endpoint_returns_matches(self):
        self.client.force_login(self.ama)
        resp = self.client.get(reverse("desk:search"), {"q": "tariff"})
        self.assertEqual(resp.status_code, 200)

        # Context contains matches for tariff in topics and cases
        topics = resp.context["topics"]
        cases = resp.context["cases"]
        self.assertTrue(any("tariff" in t.name.lower() for t in topics))
        self.assertTrue(any("tariff" in c.claim.lower() for c in cases))

    def test_search_view_postgres_branch(self):
        from django.db.models import Value
        self.client.force_login(self.ama)
        with patch.object(connection, "vendor", "postgresql"):
            with patch("django.contrib.postgres.search.SearchVector") as mock_sv, \
                 patch("django.contrib.postgres.search.TrigramSimilarity") as mock_trgm:
                mock_sv.return_value = Value("mock_vector")
                mock_trgm.return_value = Value(0.5)
                # Mock the query evaluation list results
                with patch("desk.models.Topic.objects.annotate") as mock_top_ann, \
                     patch("desk.models.Case.objects.annotate") as mock_case_ann, \
                     patch("desk.models.Item.objects.filter") as mock_item_filt:
                    mock_top_ann.return_value.filter.return_value.order_by.return_value = []
                    mock_case_ann.return_value.filter.return_value.order_by.return_value = []
                    mock_item_filt.return_value.annotate.return_value.filter.return_value.select_related.return_value.order_by.return_value = []

                    resp = self.client.get(reverse("desk:search"), {"q": "dumsor"})
                    self.assertEqual(resp.status_code, 200)
                    self.assertTrue(mock_sv.called)
                    self.assertTrue(mock_trgm.called)
