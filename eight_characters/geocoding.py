"""Validate the Open-Meteo connection without exposing its customer key."""

import os
from collections.abc import Mapping
from dataclasses import dataclass, field

PUBLIC_URL = 'https://geocoding-api.open-meteo.com/v1/search'
CUSTOMER_URL = 'https://customer-geocoding-api.open-meteo.com/v1/search'


@dataclass(frozen=True)
class GeocodingConfig:
    url: str
    api_key: str = field(repr=False)


def load_geocoding_config(
    environ: Mapping[str, str] | None = None,
) -> GeocodingConfig:
    values = os.environ if environ is None else environ
    url = values.get('EC_GEOCODING_URL', PUBLIC_URL)
    key = values.get('EC_GEOCODING_API_KEY', '')
    if url not in {PUBLIC_URL, CUSTOMER_URL}:
        raise ValueError('EC_GEOCODING_URL must name a supported Open-Meteo endpoint.')
    if any(character.isspace() for character in key):
        raise ValueError('EC_GEOCODING_API_KEY must contain no whitespace.')
    if url == CUSTOMER_URL and not key:
        raise ValueError('The customer geocoding endpoint requires EC_GEOCODING_API_KEY.')
    if url == PUBLIC_URL and key:
        raise ValueError('EC_GEOCODING_API_KEY requires the customer geocoding endpoint.')
    return GeocodingConfig(url=url, api_key=key)
