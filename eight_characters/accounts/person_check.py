"""Telling people from scripts before an email is sent: Cloudflare Turnstile.

The page's widget gives the browser a token; the server asks Cloudflare whether it
is good. A token is good once, so each request for a code needs a fresh one.
"""

from typing import Final, Protocol, cast

import httpx

SITEVERIFY_URL: Final = 'https://challenges.cloudflare.com/turnstile/v0/siteverify'
TOKEN_MAX_LENGTH: Final = 2048
TIMEOUT_SECONDS: Final = 10.0


class PersonCheckUnavailable(Exception):
    """Cloudflare could not be asked, so whether this is a person is unknown."""


class PersonCheck(Protocol):
    def verify(self, token: str, client: str | None) -> bool: ...


class Turnstile:
    def __init__(self, secret: str, http: httpx.Client) -> None:
        self._secret = secret
        self._http = http

    def verify(self, token: str, client: str | None) -> bool:
        if not token or len(token) > TOKEN_MAX_LENGTH:
            return False
        form = {'secret': self._secret, 'response': token}
        if client is not None:
            form['remoteip'] = client
        try:
            response = self._http.post(
                SITEVERIFY_URL, data=form, timeout=TIMEOUT_SECONDS
            )
        except httpx.HTTPError as exc:
            raise PersonCheckUnavailable(
                f'Turnstile could not be reached ({type(exc).__name__}).'
            ) from exc
        if response.status_code != 200:
            raise PersonCheckUnavailable(f'Turnstile answered {response.status_code}.')
        try:
            answer: object = response.json()
        except ValueError as exc:
            raise PersonCheckUnavailable(
                'Turnstile answered something not JSON.'
            ) from exc
        if not isinstance(answer, dict):
            raise PersonCheckUnavailable('Turnstile answered without a verdict.')
        fields = cast(dict[str, object], answer)
        if 'success' not in fields:
            raise PersonCheckUnavailable('Turnstile answered without a verdict.')
        return fields['success'] is True
