from django.test import SimpleTestCase

from .utils.onepipe_utils import extract_activation_url, extract_provider_transaction_ref


class OnePipeUtilsTests(SimpleTestCase):
    def test_extract_activation_url_from_data_activation(self):
        resp = {"data": {"activation_url": "https://pay/activate"}}
        self.assertEqual(extract_activation_url(resp), "https://pay/activate")

    def test_extract_activation_url_top_level(self):
        resp = {"activation_url": "https://top/activate"}
        self.assertEqual(extract_activation_url(resp), "https://top/activate")

    def test_extract_activation_url_data_url(self):
        resp = {"data": {"url": "https://data/url"}}
        self.assertEqual(extract_activation_url(resp), "https://data/url")

    def test_extract_activation_url_data_meta(self):
        resp = {"data": {"meta": {"activation_url": "https://meta/activate"}}}
        self.assertEqual(extract_activation_url(resp), "https://meta/activate")

    def test_extract_activation_url_missing(self):
        resp = {"data": {"foo": "bar"}}
        self.assertIsNone(extract_activation_url(resp))

    def test_extract_tx_ref_from_data(self):
        resp = {"data": {"transaction_ref": "tx-123"}}
        self.assertEqual(extract_provider_transaction_ref(resp), "tx-123")

    def test_extract_tx_ref_top_level(self):
        resp = {"transaction_ref": "top-tx"}
        self.assertEqual(extract_provider_transaction_ref(resp), "top-tx")

    def test_extract_tx_ref_alternate_keys(self):
        resp = {"data": {"tx_ref": "alt-456"}}
        self.assertEqual(extract_provider_transaction_ref(resp), "alt-456")

    def test_extract_tx_ref_missing(self):
        resp = {"data": {"nothing": "here"}}
        self.assertIsNone(extract_provider_transaction_ref(resp))
