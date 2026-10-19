"""Immutable request and recovery-proof boundaries without provider side effects."""

import unittest
from dataclasses import replace

from eight_characters.accounts.billing_access import BillingHold
from eight_characters.accounts.billing_operations import (
    customer_mac,
    deletion_mac,
    operation_key,
    prepare_request,
    read_customer_binding,
    read_deletion,
    request_for,
    sealed_checkout,
)
from eight_characters.accounts.billing_records import Binding, Deletion, Operation
from eight_characters.accounts.records import new_id
from tests.test_accounts_billing_recovery import NOW
from tests.test_billing_access import authority, configuration


class NativeOperations(unittest.TestCase):
    def setUp(self):
        scope, owner = authority()
        self.config = replace(configuration(), namespace=scope.id)
        self.scope = scope.model_copy(
            update={'binding_key_id': self.config.binding_key_id}
        )
        self.creator = new_id()
        binding = Binding(
            operation_id=self.creator,
            object_id='cus_one',
            state='sealed',
            mac=customer_mac(self.config, owner.id, 'cus_one', self.creator),
        )
        self.intent = owner.intents[0].model_copy(
            update={'state': 'reserved', 'checkout_id': None, 'subscription_id': None}
        )
        self.owner = owner.model_copy(
            update={
                'binding': binding,
                'intents': (self.intent,),
                'operations': (),
                'coverage': (),
            }
        )
        self.origin = 'http://127.0.0.1:8873'

    def operation(self, purpose, kind, *, subject=None):
        identifier = new_id()
        request = prepare_request(
            self.config,
            self.origin,
            self.scope,
            self.owner,
            purpose=purpose,
            operation_id=identifier,
            intent_id=self.intent.id,
            subject_id=subject,
        )
        operation = Operation(
            id=identifier,
            intent_id=self.intent.id,
            kind=kind,
            subject_id=subject,
            request_sha256=request.digest,
            idempotency_key=operation_key(
                self.config, self.owner.id, purpose, identifier
            ),
            created_at=NOW,
            sent_at=None,
            state='prepared',
            result_id=None,
            reason=None,
        )
        return operation, request

    @staticmethod
    def metadata(request):
        return {
            key[len('metadata[') : -1]: value
            for key, value in request.parameters.items()
            if key.startswith('metadata[')
        }

    def test_original_checkout_parameters_and_key_cannot_change_on_retry(self):
        operation, request = self.operation('checkout_create', 'checkout_create')
        again = request_for(self.config, self.origin, self.scope, self.owner, operation)
        self.assertEqual(again.digest, request.digest)
        self.assertNotIn('payment_method_types[0]', again.parameters)
        self.assertEqual(
            again.parameters['payment_method_configuration'],
            self.config.payment_method_configuration,
        )
        with self.assertRaises(BillingHold):
            request_for(
                replace(self.config, payment_method_configuration='pmc_changed'),
                self.origin,
                self.scope,
                self.owner,
                operation,
            )
        self.assertEqual(
            again.parameters['line_items[0][price]'], self.scope.offers[0].price_id
        )
        self.assertEqual(again.parameters['expires_at'], str(self.intent.expires_at))
        self.assertEqual(
            again.parameters['success_url'], self.origin + '/account/billing/return'
        )
        with self.assertRaises(TypeError):
            again.parameters['line_items[0][quantity]'] = '2'
        with self.assertRaises(BillingHold):
            request_for(
                self.config, 'http://127.0.0.1:8874', self.scope, self.owner, operation
            )

    def test_creation_tag_is_not_an_object_bound_customer_seal(self):
        operation, request = self.operation('customer_create', 'customer_create')
        customer = {
            'id': 'cus_one',
            'object': 'customer',
            'livemode': False,
            'metadata': self.metadata(request),
        }
        self.assertEqual(
            read_customer_binding(self.config, customer),
            (self.owner.id, operation.id, False),
        )
        customer['metadata']['ec_customer_mac'] = customer_mac(
            self.config, self.owner.id, 'cus_one', operation.id
        )
        self.assertTrue(read_customer_binding(self.config, customer)[2])
        self.assertFalse(
            read_customer_binding(self.config, {**customer, 'id': 'cus_other'})[2]
        )
        for invalid in ('å' * 64, 'a' * 63, 'a' * 65, None):
            with self.subTest(invalid=invalid):
                self.assertFalse(
                    read_customer_binding(
                        self.config,
                        {
                            **customer,
                            'metadata': {
                                **customer['metadata'],
                                'ec_customer_mac': invalid,
                            },
                        },
                    )[2]
                )
                with self.assertRaises(BillingHold):
                    read_customer_binding(
                        self.config,
                        {
                            **customer,
                            'metadata': {
                                **customer['metadata'],
                                'ec_creation_mac': invalid,
                            },
                        },
                    )
        with self.assertRaises(BillingHold):
            read_customer_binding(
                replace(self.config, binding_key=b'other' * 10), customer
            )

    def test_checkout_seal_also_authenticates_the_frozen_intent_and_offer(self):
        create, _request = self.operation('checkout_create', 'checkout_create')
        create = create.model_copy(update={'state': 'done', 'result_id': 'cs_test_one'})
        self.owner = self.owner.model_copy(
            update={
                'operations': (create,),
                'intents': (
                    self.intent.model_copy(
                        update={'checkout_id': 'cs_test_one', 'state': 'open'}
                    ),
                ),
            }
        )
        _, seal = self.operation(
            'checkout_seal', 'checkout_create', subject='cs_test_one'
        )
        session = {
            'id': 'cs_test_one',
            'object': 'checkout.session',
            'livemode': False,
            'customer': 'cus_one',
            'metadata': self.metadata(seal),
        }
        self.assertEqual(
            sealed_checkout(self.config, self.owner, session),
            (self.intent.id, self.intent.offer_id),
        )
        for changes in (
            {'ec_offer': 'b' * 64},
            {'ec_intent': new_id()},
            {'ec_checkout_mac': 'å' * 64},
            {'ec_creation_mac': 'å' * 64},
        ):
            with self.assertRaises(BillingHold):
                sealed_checkout(
                    self.config,
                    self.owner,
                    {**session, 'metadata': {**session['metadata'], **changes}},
                )
        with self.assertRaises(BillingHold):
            sealed_checkout(self.config, self.owner, {**session, 'id': 'cs_test_other'})

    def test_period_cancellation_stays_immutable_when_deletion_requires_a_new_command(
        self,
    ):
        period, original = self.operation('cancel_period', 'cancel', subject='sub_one')
        _, deletion = self.operation('cancel_delete', 'cancel', subject='sub_one')
        self.assertEqual(
            (original.method, dict(original.parameters)),
            ('POST', {'cancel_at_period_end': 'true'}),
        )
        self.assertEqual(
            (deletion.method, dict(deletion.parameters)),
            ('DELETE', {'invoice_now': 'false', 'prorate': 'false'}),
        )
        self.assertEqual(
            request_for(
                self.config,
                self.origin,
                self.scope,
                self.owner.model_copy(update={'lifecycle': 'held'}),
                period,
            ).digest,
            original.digest,
        )
        self.assertNotEqual(original.digest, deletion.digest)

    def test_native_deletion_decision_is_bound_to_customer_owner_nonce_and_time(self):
        nonce = new_id()
        marker = deletion_mac(self.config, self.owner.id, 'cus_one', nonce, NOW)
        decision = Deletion(
            requested_at=NOW,
            completed_at=None,
            nonce=nonce,
            native_object_id='cus_one',
            native_marker=marker,
            retain_until=None,
        )
        self.owner = self.owner.model_copy(
            update={'lifecycle': 'deleting', 'deletion': decision}
        )
        _, request = self.operation('delete_mark', 'delete_mark', subject='cus_one')
        customer = {
            'id': 'cus_one',
            'object': 'customer',
            'livemode': False,
            'metadata': self.metadata(request),
        }
        self.assertEqual(
            read_deletion(self.config, customer), (self.owner.id, decision)
        )
        with self.assertRaises(BillingHold):
            read_deletion(self.config, {**customer, 'id': 'cus_other'})
        with self.assertRaises(BillingHold):
            read_deletion(
                self.config,
                {
                    **customer,
                    'metadata': {**customer['metadata'], 'ec_delete_mac': 'å' * 64},
                },
            )
        with self.assertRaises(BillingHold) as failure:
            read_deletion(
                self.config,
                {
                    **customer,
                    'metadata': {
                        **customer['metadata'],
                        'ec_delete_requested': 'whsec_DO_NOT_LOG',
                    },
                },
            )
        self.assertNotIn('DO_NOT_LOG', str(failure.exception))
