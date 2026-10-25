"""Loopback-only browser contract fixture; every Stripe request is injected."""

import json
import socket
from unittest.mock import patch

import uvicorn

from eight_characters.accounts.billing_records import AccountBillingRecord
from eight_characters.main import app
from tests.test_billing_service import ServiceApi


def main() -> None:
    with socket.socket() as connection:
        connection.bind(('127.0.0.1', 0))
        port = connection.getsockname()[1]
    origin = f'http://127.0.0.1:{port}'
    case = ServiceApi(
        'test_billing_replies_name_the_authenticated_account_without_caching'
    )
    with patch('tests.accounts_support.TEST_ORIGIN', origin):
        case.setUp()

    @app.get('/__test/billing/state')
    def state() -> dict[str, int]:
        return {
            'sessions': len(case.provider.sessions),
            'subscriptions': len(case.provider.subscriptions),
            'stopped': sum(
                subscription['cancel_at_period_end'] is True
                for subscription in case.provider.subscriptions.values()
            ),
        }

    @app.post('/__test/billing/complete')
    def complete() -> dict[str, bool]:
        case.provider.complete()
        owner = next(
            record
            for record in case.accounts.store.billing_records()
            if isinstance(record, AccountBillingRecord)
        )
        case.service.reconcile(owner.id)
        return {'applied': True}

    @app.post('/__test/billing/overdue')
    def overdue() -> dict[str, bool]:
        case.clock.advance(3601)
        case.provider.subscriptions['sub_one']['status'] = 'past_due'
        return {'overdue': True}

    class ReadyServer(uvicorn.Server):
        async def startup(self, sockets=None):
            await super().startup(sockets)
            print(
                json.dumps({'origin': origin, 'mail': str(case.directory / 'mail')}),
                flush=True,
            )

    try:
        ReadyServer(
            uvicorn.Config(
                app, host='127.0.0.1', port=port, lifespan='off', log_level='warning'
            )
        ).run()
    finally:
        case.doCleanups()


if __name__ == '__main__':
    main()
