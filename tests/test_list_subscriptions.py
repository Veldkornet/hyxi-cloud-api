"""Tests for listing the push subscriptions HYXI holds."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from hyxi_cloud_api import HyxiApiClient, Subscription, SubscriptionType

# HYXI's documented answer for GET /api/subscribe/v1/list.
_DOCUMENTED_RESPONSE = {
    "code": "0",
    "msg": "Success",
    "data": [
        {
            "subscribeCode": "a1b2c3d4e5f6789012345678abcdef01",
            "subscribeType": 2,
            "callbackUrl": "https://xxx.example.com/callback",
            "createTime": "2026-09-28 10:30:00",
            "devices": ["25270000000001", "25270000000002"],
        },
        {
            "subscribeCode": "b2c3d4e5f678901234567890abcdef12",
            "subscribeType": 3,
            "callbackUrl": "https://xxx.example.com/alarmCallback",
            "createTime": "2026-09-27 18:20:11",
            "devices": [],
        },
    ],
    "success": True,
}


def _client(response) -> HyxiApiClient:
    api = HyxiApiClient("ak", "sk", "https://api.com", MagicMock())
    api.ensure_token = AsyncMock()
    api._request = AsyncMock(return_value=(200, response))
    return api


@pytest.mark.asyncio
async def test_subscriptions_are_listed():
    """HYXI's subscription list becomes Subscription records."""
    api = _client(_DOCUMENTED_RESPONSE)

    subscriptions = await api.list_subscriptions()

    assert subscriptions == [
        Subscription(
            subscribe_code="a1b2c3d4e5f6789012345678abcdef01",
            subscribe_type=SubscriptionType.REAL_TIME_DATA,
            callback_url="https://xxx.example.com/callback",
            create_time="2026-09-28 10:30:00",
            devices=("25270000000001", "25270000000002"),
        ),
        Subscription(
            subscribe_code="b2c3d4e5f678901234567890abcdef12",
            subscribe_type=SubscriptionType.ALARM,
            callback_url="https://xxx.example.com/alarmCallback",
            create_time="2026-09-27 18:20:11",
            devices=(),
        ),
    ]
    args, kwargs = api._request.call_args
    assert args[:2] == ("GET", "/api/subscribe/v1/list")
    assert kwargs["params"] is None


@pytest.mark.asyncio
async def test_subscriptions_can_be_listed_for_one_device():
    """A device serial number is passed as HYXI's deviceSn filter."""
    api = _client({"success": True, "data": []})

    assert await api.list_subscriptions(" 25270000000001 ") == []
    assert api._request.call_args.kwargs["params"] == {"deviceSn": "25270000000001"}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "device_sn", ["  ", 25270000000001], ids=["blank", "not-a-string"]
)
async def test_an_invalid_device_filter_is_rejected(device_sn):
    """A blank or non-string device serial number is a caller error, not
    "all devices"."""
    api = _client({"success": True, "data": []})

    with pytest.raises(ValueError, match="device_sn"):
        await api.list_subscriptions(device_sn)
    api._request.assert_not_awaited()


@pytest.mark.asyncio
async def test_unexpected_entries_are_read_tolerantly():
    """Entries without a code are left out; other unexpected fields fall
    back to empty values rather than failing the whole list."""
    api = _client(
        {
            "success": True,
            "data": [
                {"subscribeType": 2},
                "not-an-entry",
                {"subscribeCode": " c1 ", "subscribeType": 7, "devices": "SN1"},
                {"subscribeCode": "c2", "subscribeType": "3", "callbackUrl": None},
                {
                    "subscribeCode": "c3",
                    "subscribeType": 3,
                    "devices": [None, " SN1 ", 5, ""],
                },
                {"subscribeCode": "c4", "subscribeType": True},
                {"subscribeCode": "c5", "subscribeType": 2.9},
            ],
        }
    )

    subscriptions = await api.list_subscriptions()

    assert subscriptions == [
        Subscription("c1", 7, "", "", ()),
        Subscription("c2", None, "", "", ()),
        Subscription("c3", SubscriptionType.ALARM, "", "", ("SN1",)),
        Subscription("c4", None, "", "", ()),
        Subscription("c5", None, "", "", ()),
    ]
    assert subscriptions[2].subscribe_type is SubscriptionType.ALARM


@pytest.mark.asyncio
async def test_no_subscription_data_is_an_empty_list():
    """A successful answer without data means there are no subscriptions."""
    api = _client({"success": True, "data": None})

    assert await api.list_subscriptions() == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "response",
    [
        {"success": True, "data": {"subscribeCode": "c1"}},
        {
            "code": "A000003",
            "msg": "User information does not exist",
            "data": None,
            "success": False,
        },
    ],
    ids=["data-not-a-list", "rejected"],
)
async def test_a_failed_listing_raises_subscription_error(response):
    """A rejected request or an answer that is not a list raises
    SubscriptionError."""
    api = _client(response)

    with pytest.raises(api.SubscriptionError):
        await api.list_subscriptions()
