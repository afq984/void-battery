# -*- encoding: utf-8 -*-
"""Tests for the pathofexile.tw client's rate limiting and caching.

Nothing here touches the network: the point is that the budget arithmetic and
the persisted state are right, because a bug in them is only otherwise
discovered by being restricted.
"""

from __future__ import unicode_literals

import json
import os
import pathlib
import sys
import time

import pytest

sys.path.insert(
    0, str(pathlib.Path(__file__).resolve().parent.parent / 'tools')
)

import poe_tw  # noqa: E402


IP_HEADERS = {
    'X-Rate-Limit-Policy': 'ladder-view',
    'X-Rate-Limit-Rules': 'Ip',
    'X-Rate-Limit-Ip': '10:60:120',
    'X-Rate-Limit-Ip-State': '1:60:0',
}


def state(tmp_path, utilization=1.0):
    return poe_tw.RateLimitState(tmp_path / 'ratelimit.json', utilization)


def test_parse_rules():
    assert poe_tw.parse_rules('30:60:120,90:1800:600') == [
        poe_tw.Rule(30, 60, 120),
        poe_tw.Rule(90, 1800, 600),
    ]


def test_parse_rules_ignores_junk():
    assert poe_tw.parse_rules('') == []
    assert poe_tw.parse_rules('nonsense,1:2:3') == [poe_tw.Rule(1, 2, 3)]


def test_budget_runs_out(tmp_path):
    limits = state(tmp_path)
    with limits.locked():
        for _ in range(2):
            limits.wait_for_slot('p', '2:60:0', max_wait=0)
            limits.charge('p', '2:60:0')
        with pytest.raises(poe_tw.RateLimited):
            limits.wait_for_slot('p', '2:60:0', max_wait=0)


def test_utilization_shrinks_the_budget(tmp_path):
    limits = state(tmp_path, utilization=0.5)
    with limits.locked():
        limits.wait_for_slot('p', '4:60:0', max_wait=0)
        limits.charge('p', '4:60:0')
        limits.wait_for_slot('p', '4:60:0', max_wait=0)
        limits.charge('p', '4:60:0')
        # Half of 4 is 2, so the third does not fit even though the server
        # would have allowed it.
        with pytest.raises(poe_tw.RateLimited):
            limits.wait_for_slot('p', '4:60:0', max_wait=0)


def test_budget_survives_a_restart(tmp_path):
    with state(tmp_path).locked() as _:
        pass
    first = state(tmp_path)
    with first.locked():
        first.charge('p', '2:60:0')
        first.charge('p', '2:60:0')
    # A separate process, sharing only the state file, must see them.
    second = state(tmp_path)
    with second.locked():
        with pytest.raises(poe_tw.RateLimited):
            second.wait_for_slot('p', '2:60:0', max_wait=0)


def test_observe_adopts_advertised_rules(tmp_path):
    limits = state(tmp_path)
    with limits.locked():
        limits.observe('ladder-view', IP_HEADERS)
        assert limits._entry('ladder-view')['rules']['Ip'] == '10:60:120'


def test_observe_counts_requests_we_did_not_make(tmp_path):
    limits = state(tmp_path)
    headers = dict(IP_HEADERS, **{'X-Rate-Limit-Ip-State': '9:60:0'})
    with limits.locked():
        limits.observe('ladder-view', headers)
        # The server says 9 of 10 are gone; one more fits, a second does not.
        limits.wait_for_slot('ladder-view', '10:60:120', max_wait=0)
        limits.charge('ladder-view', '10:60:120')
        with pytest.raises(poe_tw.RateLimited):
            limits.wait_for_slot('ladder-view', '10:60:120', max_wait=0)


def test_restriction_is_recorded_and_persisted(tmp_path):
    limits = state(tmp_path)
    headers = dict(IP_HEADERS, **{'X-Rate-Limit-Ip-State': '1:60:300'})
    with limits.locked():
        limits.observe('ladder-view', headers)
    # A restriction outlives the process that learned about it, so a
    # concurrent run stays off the endpoint too.
    other = state(tmp_path)
    with other.locked():
        with pytest.raises(poe_tw.RateLimited):
            other.wait_for_slot('ladder-view', '10:60:120', max_wait=60)


def test_clock_going_backwards_keeps_hits(tmp_path):
    path = tmp_path / 'ratelimit.json'
    path.write_text(
        json.dumps(
            {'p': {'rules': {'Ip': '1:60:0'}, 'hits': [time.time() + 3600]}}
        )
    )
    limits = state(tmp_path)
    with limits.locked():
        # The hit is in the future; forgetting it would hand back capacity we
        # already spent.
        with pytest.raises(poe_tw.RateLimited):
            limits.wait_for_slot('p', '1:60:0', max_wait=0)


def client(tmp_path, **kwargs):
    kwargs.setdefault('state_path', tmp_path / 'ratelimit.json')
    return poe_tw.Client(tmp_path / 'cache', **kwargs)


@pytest.mark.parametrize(
    'kwargs',
    [
        {'limit': 0},
        {'limit': poe_tw.LADDER_PAGE_MAX + 1},
        {'offset': -1},
    ],
)
def test_ladder_rejects_requests_the_server_would_refuse(tmp_path, kwargs):
    # A rejected request would spend invalid-request allowance, so it must
    # never leave the process.
    with pytest.raises(ValueError):
        client(tmp_path).ladder('a league', **kwargs)


def test_character_requires_both_names(tmp_path):
    with pytest.raises(ValueError):
        client(tmp_path).character_items('', 'GPGPU')


def test_bad_utilization_is_rejected(tmp_path):
    with pytest.raises(ValueError):
        client(tmp_path, utilization=1.5)


def write_cache(api, path, params, body, age=0):
    cache_path = api._cache_path(path, params)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(
        json.dumps(
            {'status': 200, 'body': body, 'fetched_at': time.time() - age},
            ensure_ascii=False,
        )
    )


def test_fresh_cache_is_served_offline(tmp_path):
    api = client(tmp_path, offline=True)
    params = {'realm': 'pc', 'type': 'main'}
    write_cache(api, poe_tw.LEAGUES, params, [{'id': 'a league'}])
    response = api.leagues()
    assert response.ok and response.cached
    assert response.body == [{'id': 'a league'}]
    assert api.requests_made == 0


def test_stale_cache_is_not_served_when_online(tmp_path):
    api = client(tmp_path)
    params = {'realm': 'pc', 'type': 'main'}
    write_cache(
        api, poe_tw.LEAGUES, params, [{'id': 'last league'}],
        age=poe_tw.DEFAULT_MAX_AGE[poe_tw.LEAGUES] + 60,
    )
    # Otherwise a run would keep sampling a league that has since rolled over.
    assert api._read_cache(api._cache_path(poe_tw.LEAGUES, params),
                           poe_tw.LEAGUES) is None


def test_stale_cache_is_served_offline(tmp_path):
    # Offline means "make no requests", so yesterday's answer beats none.
    api = client(tmp_path, offline=True)
    params = {'realm': 'pc', 'type': 'main'}
    write_cache(
        api, poe_tw.LEAGUES, params, [{'id': 'last league'}],
        age=poe_tw.DEFAULT_MAX_AGE[poe_tw.LEAGUES] + 60,
    )
    assert api.leagues().body == [{'id': 'last league'}]
    assert api.requests_made == 0


def test_refresh_ignores_the_cache(tmp_path):
    api = client(tmp_path, offline=True, refresh=True)
    params = {'realm': 'pc', 'type': 'main'}
    write_cache(api, poe_tw.LEAGUES, params, [{'id': 'a league'}])
    with pytest.raises(poe_tw.RateLimited):
        api.leagues()


def test_state_path_defaults_outside_the_cache(tmp_path, monkeypatch):
    # Clearing cached responses must not clear the rate limit budgets.
    monkeypatch.setenv('XDG_CACHE_HOME', str(tmp_path / 'xdg'))
    api = poe_tw.Client(tmp_path / 'cache')
    assert not str(api.limits.path).startswith(str(api.cache_dir))
    assert str(api.limits.path).startswith(str(tmp_path / 'xdg'))


def test_invalid_request_rules_enforce_a_minimum_interval():
    # A burst of 403s is exactly what the invalid-request threshold punishes.
    first = poe_tw.parse_rules(poe_tw.INVALID_RULES)[0]
    assert first.hits == 1
    assert first.period > 0


def test_cache_path_is_stable_and_specific(tmp_path):
    api = client(tmp_path)
    one = api._cache_path(poe_tw.GET_ITEMS, {'accountName': 'a#1', 'character': 'x'})
    same = api._cache_path(poe_tw.GET_ITEMS, {'character': 'x', 'accountName': 'a#1'})
    other = api._cache_path(poe_tw.GET_ITEMS, {'accountName': 'a#1', 'character': 'y'})
    assert one == same
    assert one != other
    assert os.path.basename(str(one.parent)) == 'character-window-get-items'


def test_endpoint_policy_is_remembered_across_processes(tmp_path):
    limits = state(tmp_path)
    with limits.locked():
        assert limits.endpoint_policy(poe_tw.GET_ITEMS, 'assumed') == 'assumed'
        limits.remember_endpoint_policy(poe_tw.GET_ITEMS, 'the-real-one')
    # Otherwise every fresh process paces its first request by a policy the
    # server has stopped using.
    with state(tmp_path).locked() as _:
        pass
    other = state(tmp_path)
    with other.locked():
        assert other.endpoint_policy(poe_tw.GET_ITEMS, 'assumed') == 'the-real-one'


def test_endpoint_mapping_is_not_mistaken_for_a_policy(tmp_path):
    limits = state(tmp_path)
    with limits.locked():
        limits.remember_endpoint_policy(poe_tw.GET_ITEMS, 'p')
        limits.charge('p', '2:60:0')
    reloaded = state(tmp_path)
    with reloaded.locked():
        assert reloaded._state[poe_tw.ENDPOINTS_KEY] == {poe_tw.GET_ITEMS: 'p'}


def test_flush_persists_without_releasing_the_lock(tmp_path):
    limits = state(tmp_path)
    with limits.locked():
        limits.charge('p', '2:60:0')
        limits.flush()
        # A crash here must not hand the spent slot back to the next process.
        onlooker = state(tmp_path)
        onlooker._state = None
        onlooker._load()
        assert len(onlooker._state['p']['hits']) == 1
