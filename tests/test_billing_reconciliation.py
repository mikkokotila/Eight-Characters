"""Injected discovery/provenance checks; no native payment proof is claimed."""

import unittest
from dataclasses import replace

import httpx

from eight_characters.accounts.billing_access import BillingHold
from eight_characters.accounts.billing_native import Stripe
from eight_characters.accounts.billing_operations import customer_mac, operation_key, prepare_request
from eight_characters.accounts.billing_reconciliation import discover_customers, observe_owner
from eight_characters.accounts.billing_records import Binding
from eight_characters.accounts.records import new_id
from tests.test_accounts_billing_recovery import NOW
from tests.test_billing_access import authority, configuration
from tests.test_billing_native import FundingGraph


class Discovery(unittest.TestCase):
    def setUp(self):
        self.scope, self.owner = authority()
        self.config = replace(configuration(), namespace=self.scope.id, clock_ids=(), purchase_clock=None)
        self.scope = self.scope.model_copy(update={'clock_ids': ()})
        self.operation = new_id()
        create = prepare_request(self.config, 'https://testserver', self.scope.model_copy(update={'binding_key_id': self.config.binding_key_id}), self.owner, purpose='customer_create', operation_id=self.operation, intent_id=None, subject_id=None)
        self.metadata = {key[9:-1]: value for key, value in create.parameters.items()}
        self.customers = [{'id': 'cus_one', 'object': 'customer', 'livemode': False, 'test_clock': None, 'metadata': self.metadata}]
        self.events = []
        self.calls = []
        def response(request):
            self.calls.append(request.url.path)
            path = request.url.path.removeprefix('/v1/')
            if path == 'account':
                body = {'id': self.config.catalogue.account_id, 'object': 'account'}
            else:
                rows = {'test_helpers/test_clocks': [], 'customers': self.customers, 'events': self.events}[path]
                body = {'object': 'list', 'has_more': False, 'data': rows}
            return httpx.Response(200, json=body, headers={'Stripe-Version': self.config.catalogue.api_version})
        self.client = httpx.Client(transport=httpx.MockTransport(response))
        self.addCleanup(self.client.close)
        self.native = Stripe(self.config, self.client)

    def test_unsealed_tag_requires_positive_native_creation_request_provenance(self):
        proof, = discover_customers(self.native, self.scope)
        self.assertFalse(proof.creation_proven)
        self.events.append({'object': 'event', 'type': 'customer.created', 'livemode': False, 'request': {'idempotency_key': operation_key(self.config, self.owner.id, 'customer_create', self.operation)}, 'data': {'object': self.customers[0]}})
        proof, = discover_customers(self.native, self.scope)
        self.assertTrue(proof.creation_proven)
        self.assertFalse(proof.sealed)
        self.events[0]['request']['idempotency_key'] = 'unrelated_request'
        proof, = discover_customers(self.native, self.scope)
        self.assertFalse(proof.creation_proven)

    def test_object_seal_is_positive_proof_but_two_customers_cannot_share_owner(self):
        self.metadata['ec_customer_mac'] = customer_mac(self.config, self.owner.id, 'cus_one', self.operation)
        proof, = discover_customers(self.native, self.scope)
        self.assertTrue(proof.creation_proven)
        self.assertTrue(proof.sealed)
        self.assertNotIn('/v1/events', self.calls)
        self.customers.append({**self.customers[0], 'id': 'cus_two', 'metadata': {**self.metadata, 'ec_customer_mac': customer_mac(self.config, self.owner.id, 'cus_two', self.operation)}})
        with self.assertRaises(BillingHold):
            discover_customers(self.native, self.scope)

    def test_missing_retained_clock_is_not_a_customer_absence_proof(self):
        with self.assertRaises(BillingHold) as failure:
            discover_customers(self.native, self.scope.model_copy(update={'clock_ids': ('clock_old',)}))
        self.assertEqual(failure.exception.reason, 'clock_unavailable')


class CurrentObservations(unittest.TestCase):
    def setUp(self):
        graph = FundingGraph('test_archived_historical_offer_and_full_native_chain')
        graph.setUp()
        self.addCleanup(graph.doCleanups)
        self.graph = graph
        self.owner = graph.owner.model_copy(update={'test_clock_id': None})
        self.native = Stripe(replace(graph.config, namespace=graph.scope.id), graph.client)
        creator = self.owner.binding.operation_id
        values = {'ec_scope': graph.scope.id, 'ec_owner': self.owner.id, 'ec_operation': creator}
        from eight_characters.accounts.billing_access import binding_mac
        values['ec_creation_mac'] = binding_mac(self.native.config, self.owner.id, 'new-customer', 'customer-create', creator)
        values['ec_customer_mac'] = customer_mac(self.native.config, self.owner.id, 'cus_one', creator)
        self.owner = self.owner.model_copy(update={'binding': Binding(operation_id=creator, object_id='cus_one', state='sealed', mac=values['ec_customer_mac'])})
        graph.objects['customers/cus_one'] = {'id': 'cus_one', 'object': 'customer', 'livemode': False, 'test_clock': None, 'metadata': values}
        intent = self.owner.intents[0]
        operation = new_id()
        metadata = {'ec_scope': graph.scope.id, 'ec_owner': self.owner.id, 'ec_intent': intent.id, 'ec_operation': operation, 'ec_offer': intent.offer_id, 'ec_creation_mac': binding_mac(self.native.config, self.owner.id, f'cus_one:{intent.id}:{intent.offer_id}', 'checkout-create', operation), 'ec_checkout_mac': binding_mac(self.native.config, self.owner.id, intent.checkout_id, 'checkout-sealed', operation)}
        graph.lists['checkout/sessions'] = [{'id': intent.checkout_id, 'object': 'checkout.session', 'livemode': False, 'customer': 'cus_one', 'mode': 'subscription', 'payment_method_types': ['card'], 'status': 'complete', 'created': intent.expires_at - 3600, 'expires_at': intent.expires_at, 'subscription': 'sub_one', 'metadata': metadata}]
        graph.lists['subscriptions'] = [graph.subscription]
        graph.lists['invoices'] = [graph.invoice]

    def observe(self):
        return observe_owner(self.native, self.graph.scope, self.owner, wall_time=1792404001, verified_at=NOW)

    def test_only_sealed_checkout_subscription_can_supply_current_coverage(self):
        observation = self.observe()
        self.assertEqual(observation.coverage[0].charge_id, 'ch_one')
        self.graph.lists['checkout/sessions'][0]['metadata']['ec_checkout_mac'] = 'b' * 64
        with self.assertRaises(BillingHold):
            self.observe()

    def test_missing_historical_invoice_or_unrelated_subscription_is_a_hold(self):
        self.graph.lists['invoices'] = []
        with self.assertRaises(BillingHold):
            self.observe()
        self.graph.lists['invoices'] = [self.graph.invoice]
        self.graph.lists['subscriptions'].append({**self.graph.subscription, 'id': 'sub_other'})
        with self.assertRaises(BillingHold):
            self.observe()
