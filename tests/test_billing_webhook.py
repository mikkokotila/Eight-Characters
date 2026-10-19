import hashlib
import hmac
import json
import unittest
from unittest.mock import patch

from eight_characters.accounts.billing_webhook import InvalidDelivery, verify_delivery
from tests.test_billing_access import configuration


class SignedDelivery(unittest.TestCase):
    def setUp(self):
        self.config = configuration()
        self.now = 1792410000
        self.event = {'id': 'evt_fixture', 'object': 'event', 'api_version': self.config.payload_version, 'livemode': False, 'created': self.now, 'type': 'invoice.paid', 'data': {'object': {'id': 'in_fixture', 'customer': 'cus_fixture'}}}

    def signature(self, raw, *, timestamp=None, secret=None):
        timestamp = self.now if timestamp is None else timestamp
        mac = hmac.new(secret or self.config.webhook_secrets[0], str(timestamp).encode() + b'.' + raw, hashlib.sha256).hexdigest()
        return f't={timestamp},v1={mac}'

    def test_signature_is_checked_before_json_and_preserves_only_minimal_job_fields(self):
        raw = json.dumps(self.event).encode()
        with patch('eight_characters.accounts.billing_webhook.json.loads') as parse:
            with self.assertRaises(InvalidDelivery):
                verify_delivery(raw, 't=1792410000,v1=' + '0' * 64, self.config, wall_time=self.now)
            parse.assert_not_called()
        delivery = verify_delivery(raw, self.signature(raw), self.config, wall_time=self.now)
        self.assertEqual((delivery.event_id, delivery.related_id), ('evt_fixture', 'cus_fixture'))
        self.assertEqual(delivery.body_sha256, hashlib.sha256(raw).hexdigest())
        self.assertTrue(delivery.supported)
        self.assertFalse(hasattr(delivery, 'payload'))

    def test_wall_tolerance_both_directions_and_exactly_one_timestamp(self):
        raw = json.dumps(self.event).encode()
        for delta in (-301, 301):
            with self.assertRaises(InvalidDelivery):
                verify_delivery(raw, self.signature(raw, timestamp=self.now + delta), self.config, wall_time=self.now)
        for delta in (-300, 300):
            verify_delivery(raw, self.signature(raw, timestamp=self.now + delta), self.config, wall_time=self.now)
        with self.assertRaises(InvalidDelivery):
            verify_delivery(raw, self.signature(raw) + f',t={self.now}', self.config, wall_time=self.now)

    def test_rotation_and_payload_version_are_independent_of_native_get_version(self):
        config = configuration(EC_STRIPE_WEBHOOK_PREVIOUS_SECRET='whsec_previous', EC_STRIPE_PAYLOAD_VERSION='2026-08-01.dahlia')
        raw = json.dumps({**self.event, 'api_version': config.payload_version}).encode()
        verify_delivery(raw, self.signature(raw, secret=b'whsec_previous'), config, wall_time=self.now)
        for changed in ({'livemode': True}, {'api_version': self.config.catalogue.api_version}, {'account': 'acct_other'}, {'context': 'acct_other'}):
            bad = json.dumps({**self.event, 'api_version': config.payload_version, **changed}).encode()
            with self.assertRaises(InvalidDelivery):
                verify_delivery(bad, self.signature(bad), config, wall_time=self.now)

    def test_unsupported_signed_type_is_an_explicit_quarantine_candidate(self):
        raw = json.dumps({**self.event, 'type': 'customer.created'}).encode()
        self.assertFalse(verify_delivery(raw, self.signature(raw), self.config, wall_time=self.now).supported)
        with self.assertRaises(InvalidDelivery) as failure:
            verify_delivery(b'x' * (1024 * 1024 + 1), None, self.config, wall_time=self.now)
        self.assertEqual(failure.exception.status, 413)
