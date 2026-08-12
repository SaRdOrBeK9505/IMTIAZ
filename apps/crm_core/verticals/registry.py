"""Vertikal provider registratsiyasi."""

from __future__ import annotations

from apps.crm.models import BusinessType

from .base import RestaurantVerticalConfig, TravelVerticalConfig, VerticalConfig

_REGISTRY: dict[str, VerticalConfig] = {}


def register(config: VerticalConfig) -> None:
    _REGISTRY[config.business_type] = config


def get_vertical(business_type: str) -> VerticalConfig | None:
    return _REGISTRY.get(business_type)


def get_feature_flags(business_type: str) -> dict:
    config = get_vertical(business_type)
    return dict(config.feature_flags) if config else {}


def _bootstrap() -> None:
    register(RestaurantVerticalConfig(
        business_type='restaurant',
        url_prefix='/api/crm/restaurant/',
        frontend_url='https://imtiaz-crm-restaurant.vercel.app',
        feature_flags={
            'tables': True,
            'menu': True,
            'featured_items': True,
            'bookings': True,
        },
    ))
    register(TravelVerticalConfig(
        business_type='travel',
        url_prefix='/api/crm/travel/',
        frontend_url='https://imtiaz-crm-travel.vercel.app',
        feature_flags={
            'tour_packages': True,
            'bookings': True,
            'vouchers': True,
        },
    ))


_bootstrap()
