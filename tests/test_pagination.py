"""Tests for following HYXI's paged list responses."""

import logging
from unittest.mock import AsyncMock, MagicMock

import pytest

from hyxi_cloud_api.api import _MAX_LIST_PAGES, HyxiApiClient


def _page(list_key, items, current, total):
    return (
        200,
        {
            "success": True,
            "data": {
                list_key: items,
                "currentPage": current,
                "totalPage": total,
                "totalRows": 99,
            },
        },
    )


def _client(responses):
    api = HyxiApiClient("ak", "sk", "https://api.com", MagicMock())
    api._request = AsyncMock(side_effect=responses)
    return api


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "fetch, list_key, item",
    [
        (lambda api: api._fetch_plants(), "list", "plantId"),
        (lambda api: api._fetch_device_list_for_plant("P1"), "deviceList", "deviceSn"),
        (lambda api: api._fetch_sub_device_list("PARENT"), "childDevice", "deviceSn"),
        (lambda api: api._fetch_alarms_for_plant("P1"), "pageData", "deviceSn"),
    ],
    ids=["plants", "devices", "sub-devices", "alarms"],
)
async def test_lists_are_collected_across_pages(fetch, list_key, item):
    """Every list endpoint follows totalPage and returns all pages' items."""
    api = _client(
        [
            _page(list_key, [{item: "A"}], 1, 2),
            _page(list_key, [{item: "B"}], 2, 2),
        ]
    )

    result = await fetch(api)

    assert [entry[item] for entry in result] == ["A", "B"]
    pages = [
        call.kwargs["json"]["currentPage"] for call in api._request.await_args_list
    ]
    assert pages == [1, 2]


@pytest.mark.asyncio
async def test_a_rejected_later_page_is_a_rejection():
    """A page rejected after the first one makes the whole list rejected, so
    discovery treats it as incomplete rather than as the full list."""
    api = _client(
        [
            _page("deviceList", [{"deviceSn": "A"}], 1, 2),
            (200, {"success": False, "code": "C000002"}),
        ]
    )

    assert await api._fetch_device_list_for_plant("P1") is None


@pytest.mark.asyncio
async def test_unparseable_total_page_is_one_page():
    """A totalPage that is not a number is read as a single page."""
    api = _client([_page("list", [{"plantId": "A"}], 1, "many")])

    assert await api._fetch_plants() == [{"plantId": "A"}]
    assert api._request.await_count == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "responses",
    [
        [(200, {"success": True, "data": {"deviceList": "AB"}})],
        [
            _page("deviceList", [{"deviceSn": "A"}], 1, 2),
            (200, {"success": True, "data": None}),
        ],
        [
            _page("deviceList", [{"deviceSn": "A"}], 1, 2),
            (200, {"success": True, "data": [{"deviceSn": "B"}]}),
        ],
        [
            _page("deviceList", [{"deviceSn": "A"}], 1, 2),
            (200, {"success": True, "data": {"deviceList": {"B": {}}}}),
        ],
    ],
    ids=["first-list-not-a-list", "no-data", "plain-list", "list-not-a-list"],
)
async def test_a_malformed_page_is_a_rejection(responses):
    """A page without a readable list fails the whole list instead of
    returning the earlier pages' items as if they were complete."""
    api = _client(responses)

    assert await api._fetch_device_list_for_plant("P1") is None


@pytest.mark.asyncio
async def test_paging_past_the_page_limit_is_a_rejection(caplog):
    """A response claiming endless pages is followed only up to the limit,
    then treated as rejected so a truncated list is never taken as complete."""
    caplog.set_level(logging.ERROR, logger="hyxi_cloud_api.api")
    api = _client(
        [
            _page("list", [{"plantId": n}], n, 10_000)
            for n in range(1, _MAX_LIST_PAGES + 1)
        ]
    )

    assert await api._fetch_plants() is None
    assert api._request.await_count == _MAX_LIST_PAGES
    assert f"more than {_MAX_LIST_PAGES} pages" in caplog.text
