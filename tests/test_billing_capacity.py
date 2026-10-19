"""Actual chart writes against injected financial authority and separate clocks."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from threading import Event

from eight_characters.accounts.billing_access import BillingHold
from eight_characters.accounts.billing_records import RefundFact
from eight_characters.accounts.restore import restore_backup
from eight_characters.accounts.store import AccountStore, BillingReadOnly, ChartLimit
from tests.test_accounts_settings import BIRTH
from tests.test_billing_authority import AuthorityCase


def birth(index):
    return replace(
        BIRTH,
        name=f'Chart {index}',
        date=f'1990-{index // 28 + 1:02d}-{index % 28 + 1:02d}',
    )


class FundedCapacity(AuthorityCase):
    def configured(self, clock_reader=None):
        return AccountStore.open(
            self.store.path,
            clock=self.clock,
            billing_config=self.config,
            billing_clock=clock_reader,
        )

    def grant(self, plan='plus', *, native_clock=False):
        lease, owner = self.bound()
        scope = self.authority.scope(self.authority.snapshot()[0])
        offer = next(
            offer
            for offer in scope.offers
            if offer.plan == plan and offer.period == 'monthly'
        )
        now = int(self.clock().timestamp())
        coverage = self.receipt().model_copy(
            update={
                'offer_id': offer.id,
                'price_id': offer.price_id,
                'period_start': now,
                'period_end': now + 3600,
                'paid_at': now,
                'captured_amount': offer.amount,
                'allocated_amount': offer.amount,
                'base_amount': offer.amount,
                'refunds': (),
                'disputes': (),
            }
        )
        self.authority.apply(
            lease,
            owner.model_copy(
                update={
                    'coverage': (coverage,),
                    'test_clock_id': 'clock_one' if native_clock else None,
                }
            ),
        )
        return coverage

    def save(self, store, count):
        settings = None
        for index in range(count):
            settings, _ = store.save_chart(
                self.user.id,
                birth(index),
                None if settings is None else settings.updated_at,
            )
        return settings

    def test_enabled_free_has_one_addition_and_legacy_couples_are_unchanged(self):
        store = self.configured()
        access, limits = store.capacity(self.user.id)
        self.assertEqual((access.tier, limits.charts_per_account), ('free', 1))
        self.assertIsNone(limits.couples_per_chart)
        saved = self.save(store, 1)
        with self.assertRaises(ChartLimit):
            store.save_chart(self.user.id, birth(1), saved.updated_at)

    def test_basic_has_five_and_plus_has_twenty_five_without_legacy_plan_changes(self):
        self.grant('basic')
        store = self.configured()
        self.assertEqual(store.capacity(self.user.id)[1].charts_per_account, 5)
        saved = self.save(store, 5)
        with self.assertRaises(ChartLimit):
            store.save_chart(self.user.id, birth(5), saved.updated_at)
        self.assertEqual(store.user_by_id(self.user.id).plan, 'free')

    def test_plus_twenty_five_is_enforced_by_the_actual_addition(self):
        self.grant('plus')
        store = self.configured()
        saved = self.save(store, 25)
        with self.assertRaises(ChartLimit):
            store.save_chart(self.user.id, birth(25), saved.updated_at)

    def test_pro_exceeds_fifty_and_refund_retains_reads_edits_and_encrypted_recovery(
        self,
    ):
        coverage = self.grant('pro')
        store = self.configured()
        self.assertIsNone(store.capacity(self.user.id)[1].charts_per_account)
        saved = self.save(store, 51)
        lease, owner = self.authority.claim(self.user.id)
        refunded = coverage.model_copy(
            update={
                'refunds': (
                    RefundFact(
                        id='re_full',
                        amount=coverage.captured_amount,
                        status='succeeded',
                    ),
                )
            }
        )
        self.authority.apply(lease, owner.model_copy(update={'coverage': (refunded,)}))
        self.assertEqual(store.capacity(self.user.id)[1].charts_per_account, 1)
        with self.assertRaises(ChartLimit):
            store.save_chart(self.user.id, birth(51), saved.updated_at)
        self.assertEqual(len(store.settings(self.user.id).charts), 51)
        renamed = store.rename_chart(
            self.user.id, saved.charts[0].id, 'Retained', saved.updated_at
        )
        self.assertEqual(len(renamed.charts), 51)
        self.backup()
        target = self.directory / 'above-cap.sqlite3'
        restore_backup(self.checkout, self.identity, target)
        recovered = AccountStore.open(target)
        self.assertEqual(len(recovered.settings(self.user.id).charts), 51)
        with self.assertRaises(BillingReadOnly):
            recovered.capacity(self.user.id)

    def test_native_clock_is_reobserved_for_each_decision_without_wall_time_substitution(
        self,
    ):
        coverage = self.grant(native_clock=True)
        native_now = coverage.period_start
        calls = []

        def current_clock(clock_id):
            calls.append(clock_id)
            return native_now

        store = self.configured(current_clock)
        saved = self.save(store, 1)
        native_now = coverage.period_end
        self.assertEqual(store.capacity(self.user.id)[1].charts_per_account, 1)
        with self.assertRaises(ChartLimit):
            store.save_chart(self.user.id, birth(1), saved.updated_at)
        self.assertEqual(calls, ['clock_one'] * 3)

    def test_clock_http_holds_no_sql_lock_and_a_concurrent_refund_fences_the_addition(
        self,
    ):
        coverage = self.grant(native_clock=True)
        started, finish = Event(), Event()

        def current_clock(_clock_id):
            started.set()
            if not finish.wait(10):
                raise AssertionError('The test did not release native clock HTTP.')
            return coverage.period_start

        store = self.configured(current_clock)
        with ThreadPoolExecutor(max_workers=1) as pool:
            work = pool.submit(store.save_chart, self.user.id, birth(0), None)
            try:
                self.assertTrue(started.wait(5))
                unrelated = self.configured()
                unrelated.save_chart(self.other.id, birth(0), None)
                lease, owner = self.authority.claim(self.user.id)
                refunded = coverage.model_copy(
                    update={
                        'refunds': (
                            RefundFact(id='re_full', amount=1499, status='succeeded'),
                        )
                    }
                )
                self.authority.apply(
                    lease, owner.model_copy(update={'coverage': (refunded,)})
                )
            finally:
                finish.set()
            with self.assertRaises(BillingHold) as failure:
                work.result()
        self.assertEqual(failure.exception.reason, 'uncertain_operation')
        self.assertIsNone(store.settings(self.user.id))

    def test_bound_mode_and_key_flips_and_direct_delete_are_refused(self):
        store = self.configured()
        with self.assertRaises(BillingHold):
            AccountStore.open(
                self.store.path, billing_config=replace(self.config, namespace='b' * 32)
            )
        with self.assertRaises(BillingHold):
            AccountStore.open(
                self.store.path,
                billing_config=replace(self.config, binding_key=b'C' * 43),
            )
        with self.assertRaises(BillingHold):
            store.delete_user(self.user.id)
        self.assertIsNotNone(store.user_by_id(self.user.id))
