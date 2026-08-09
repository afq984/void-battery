# -*- coding: utf-8 -*-
"""A deliberately slow, cached client for the public pathofexile.tw APIs.

The endpoints below are the ones the chrome extension and the ladder site use.
They are rate limited per IP and advertise their rules in X-Rate-Limit headers
(https://www.pathofexile.com/developer/docs/index#ratelimits).  As of
2026-08-09 pathofexile.tw serves:

    /api/leagues, /api/ladders          policy ladder-view
                                        Ip 5:5:10,10:10:30,15:10:300
    /character-window/get-items         policy backend-item-request-limit
                                        Ip 30:60:120,90:1800:600,180:7200:3600
    /character-window/get-passive-skills
                                        policy backend-character-request-limit
                                        Ip 15:60:120,90:1800:600,180:7200:3600

Reading `X-Rate-Limit-Ip: 30:60:120` as "30 hits per 60 seconds, else a 120
second ban".  This module's job is to make hitting any of that impossible in
normal use:

* every advertised rule is obeyed, and only `utilization` of it is ever spent;
* the hit log lives in a lockfile-guarded JSON file, so budgets survive a
  restart and are shared by concurrent runs instead of being double spent;
* the server's own X-Rate-Limit-*-State counters are folded back in, so
  requests this process never made still consume its budget;
* 4xx replies are metered separately, because the API rules count invalid
  requests toward their own restriction
  (https://www.pathofexile.com/developer/docs/index#errors) and probing which
  accounts are public necessarily produces 403s;
* every response is cached on disk, so re-runs are free.

None of that can make an absolute guarantee: a browser on the same IP shares
these budgets and is invisible here.  What it does guarantee is that this
client spends only a fraction of the advertised allowance and backs off
whenever the server says it is closer to the limit than we thought.

As a CLI it fetches one thing and prints it as JSON:

    python3 tools/poe_tw.py leagues
    python3 tools/poe_tw.py ladder --league 亡焰咒海 --limit 20
    python3 tools/poe_tw.py items --account 'afg984#0342' --character GPGPU
    python3 tools/poe_tw.py passives --account 'afg984#0342' --character GPGPU
"""

from __future__ import unicode_literals

import collections
import contextlib
import fcntl
import hashlib
import json
import os
import pathlib
import sys
import time
import urllib.parse

import requests


BASE_URL = 'https://pathofexile.tw'

USER_AGENT = (
    'void-battery-verify/1.0 '
    '(+https://void-battery.afq984.org; contact: afg984@gmail.com)'
)

LEAGUES = '/api/leagues'
LADDERS = '/api/ladders'
GET_ITEMS = '/character-window/get-items'
GET_PASSIVE_SKILLS = '/character-window/get-passive-skills'

LADDER_POLICY = 'ladder-view'
ITEMS_POLICY = 'backend-item-request-limit'
PASSIVES_POLICY = 'backend-character-request-limit'

LADDER_PAGE_MAX = 200

# The policy each endpoint answers with, so even the first request of a run is
# paced.  Every response re-reads the real policy and rules from the headers.
ENDPOINT_POLICY = {
    LEAGUES: LADDER_POLICY,
    LADDERS: LADDER_POLICY,
    GET_ITEMS: ITEMS_POLICY,
    GET_PASSIVE_SKILLS: PASSIVES_POLICY,
}

# Observed on 2026-08-09; used only until the first response of a run arrives.
DEFAULT_RULES = {
    LADDER_POLICY: '5:5:10,10:10:30,15:10:300',
    ITEMS_POLICY: '30:60:120,90:1800:600,180:7200:3600',
    PASSIVES_POLICY: '15:60:120,90:1800:600,180:7200:3600',
}

# For a policy we have never seen: one request a minute until it tells us more.
FALLBACK_RULES = '1:60:60'

# GGG documents an invalid-request threshold but not its numbers: "Invalid
# requests include any response codes in the HTTP 4xx range... Reasonable
# attempts must be made in order to avoid passing the threshold."  Asking
# whether a ladder account is public inevitably draws 403s, so meter them at
# roughly the rate a person clicking through profiles would produce.  These
# numbers are a self-imposed margin, not a server rule, so `utilization` is
# not applied on top of them.
# The leading rule is a minimum interval: without it the sliding window would
# let a whole burst through at once, which is not what "at a human pace" means.
INVALID_RULES = '1:5:0,10:120:0,30:1800:0'
INVALID_POLICY = '4xx'

# A run that is drawing 4xx faster than the budget allows should say so and
# stop, not stall for a quarter of an hour.
INVALID_MAX_WAIT = 120

# Statuses worth remembering: 403 (profile not public) and 404 (character
# renamed or deleted) are answers, not failures.
CACHEABLE_STATUSES = frozenset((200, 403, 404))

# How long a cached response stays usable.  Discovery data rolls over (a new
# league, a moving ladder); a character's gear changes but any real snapshot of
# it is still a valid thing to verify against.
DEFAULT_MAX_AGE = {
    LEAGUES: 6 * 3600,
    LADDERS: 3600,
    GET_ITEMS: 7 * 86400,
    GET_PASSIVE_SKILLS: 7 * 86400,
}
# A profile can be made public later, so do not remember a refusal for long.
NEGATIVE_MAX_AGE = 86400

MAX_RETRIES = 4
REQUEST_TIMEOUT = 30

# Reserved top-level key in the state file; every other key is a policy name.
ENDPOINTS_KEY = 'endpoints'

# Refuse to sleep longer than this in one go; something is wrong if we do.
MAX_SLEEP = 900


def default_state_path():
    """Where the rate limit budgets live.

    Deliberately not under the response cache: a budget belongs to this
    machine's IP, not to whichever cache directory a run was pointed at, and
    throwing away cached responses must not throw away the safety state with
    them.
    """
    base = os.environ.get('XDG_CACHE_HOME') or os.path.join(
        os.path.expanduser('~'), '.cache'
    )
    return pathlib.Path(base) / 'void-battery' / 'poe-tw-ratelimit.json'


class RateLimited(Exception):
    """Raised when honouring the limits would take longer than we will wait."""


Rule = collections.namedtuple('Rule', 'hits period restriction')


def parse_rules(header):
    """Parse `30:60:120,90:1800:600` into Rules.

    X-Rate-Limit-{rule} reads (max hits, period, ban length); its -State
    counterpart reuses the shape as (current hits, period, ban remaining).
    """
    rules = []
    for part in header.split(','):
        part = part.strip()
        if not part:
            continue
        fields = part.split(':')
        if len(fields) != 3:
            continue
        try:
            rules.append(Rule(*(int(field) for field in fields)))
        except ValueError:
            continue
    return rules


def format_rules(rules):
    return ','.join(
        '{}:{}:{}'.format(rule.hits, rule.period, rule.restriction) for rule in rules
    )


class RateLimitState:
    """Hit logs for every policy, shared across processes through a lockfile.

    An in-memory limiter is only correct while exactly one run exists.  Two
    concurrent runs, or one restarted after a crash, would each start from an
    empty budget and together blow through the real one.  So the state lives in
    a file, and the lock is held across the whole check-send-record cycle:
    requests from different processes interleave instead of racing.
    """

    def __init__(self, path, utilization, log=None):
        self.path = pathlib.Path(path)
        self.utilization = utilization
        self.log = log or (lambda message: None)
        self._lock_file = None
        self._depth = 0
        self._state = None

    # -- lockfile plumbing -------------------------------------------------

    def _open_lock(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        lock_path = self.path.with_suffix('.lock')
        self._lock_file = lock_path.open('a+')
        fcntl.flock(self._lock_file.fileno(), fcntl.LOCK_EX)

    def _close_lock(self):
        fcntl.flock(self._lock_file.fileno(), fcntl.LOCK_UN)
        self._lock_file.close()
        self._lock_file = None

    def _load(self):
        try:
            with self.path.open(encoding='utf-8') as file:
                state = json.load(file)
        except (OSError, ValueError):
            state = {}
        now = time.time()
        for policy in list(state):
            if policy == ENDPOINTS_KEY:
                continue
            entry = state[policy]
            # The clock moved backwards, so hits appear to be in the future.
            # Pull them to now rather than dropping them: keeping a hit too
            # long costs a wait, forgetting one costs a violation.
            entry['hits'] = [min(hit, now) for hit in entry.get('hits', ())]
        self._state = state

    def _save(self):
        tmp = self.path.with_suffix('.{}.tmp'.format(os.getpid()))
        with tmp.open('w', encoding='utf-8') as file:
            json.dump(self._state, file)
            file.flush()
            os.fsync(file.fileno())
        os.replace(str(tmp), str(self.path))

    def flush(self):
        """Persist the state now, without giving up the lock."""
        self._save()

    # Reserved top-level key: everything else in the state file is a policy.
    def endpoint_policy(self, path, assumed):
        """The policy an endpoint last answered with, remembered across runs.

        Without this every fresh process paces its first request of an
        endpoint by a policy the server stopped using.
        """
        return self._state.get(ENDPOINTS_KEY, {}).get(path, assumed)

    def remember_endpoint_policy(self, path, policy):
        self._state.setdefault(ENDPOINTS_KEY, {})[path] = policy

    @contextlib.contextmanager
    def locked(self):
        if self._depth:
            self._depth += 1
            try:
                yield
            finally:
                self._depth -= 1
            return
        self._open_lock()
        self._depth = 1
        self._load()
        try:
            yield
        finally:
            self._save()
            self._depth = 0
            self._close_lock()

    # -- budget bookkeeping ------------------------------------------------

    def _policy(self, policy, default_rules):
        entry = self._state.setdefault(policy, {})
        entry.setdefault('rules', {'Ip': default_rules})
        entry.setdefault('hits', [])
        return entry

    def _trim(self, entry, now):
        periods = [
            rule.period
            for rules in entry['rules'].values()
            for rule in parse_rules(rules)
        ]
        if not periods:
            return
        horizon = now - max(periods)
        entry['hits'] = [hit for hit in entry['hits'] if hit > horizon]

    def _delay(self, entry, now, utilization):
        """Seconds until one more request fits under every rule."""
        delay = 0.0
        for rules in entry['rules'].values():
            for rule in parse_rules(rules):
                # Never round the budget down to zero, or a small rule would
                # block forever.
                budget = max(1, int(rule.hits * utilization))
                recent = sorted(hit for hit in entry['hits'] if hit > now - rule.period)
                if len(recent) >= budget:
                    # Room opens when the budget-th newest hit leaves the window.
                    expiry = recent[len(recent) - budget] + rule.period
                    delay = max(delay, expiry - now)
        return delay

    def charge(self, policy, default_rules):
        """Record one hit against a policy.  Call inside locked()."""
        self._policy(policy, default_rules)['hits'].append(time.time())

    def block_until(self, policy, deadline):
        """Record a server-imposed restriction.  Call inside locked().

        Persisted so that a concurrent run -- which shares the IP but not this
        process's memory -- also stays off the endpoint until it expires.
        """
        entry = self._entry(policy)
        entry['blocked_until'] = max(entry.get('blocked_until', 0), deadline)
        self.log(
            'rate limit {}: blocked for {:.0f}s'.format(
                policy, entry['blocked_until'] - time.time()
            )
        )

    def wait_for_slot(self, policy, default_rules, max_wait=MAX_SLEEP,
                      utilization=None):
        """Block until one more request would fit.  Call inside locked()."""
        if utilization is None:
            utilization = self.utilization
        waited = 0.0
        while True:
            now = time.time()
            entry = self._policy(policy, default_rules)
            self._trim(entry, now)
            delay = max(
                self._delay(entry, now, utilization),
                entry.get('blocked_until', 0) - now,
            )
            if delay <= 0:
                return
            if waited + delay > max_wait:
                raise RateLimited(
                    '{} needs {:.0f}s more than the {:.0f}s budget'.format(
                        policy, delay, max_wait
                    )
                )
            self.log('rate limit {}: waiting {:.1f}s'.format(policy, delay))
            # Drop the lock while sleeping so other runs are not starved; the
            # budget is re-checked from scratch afterwards.
            self._save()
            self._close_lock()
            try:
                time.sleep(delay + 0.1)
            finally:
                self._open_lock()
                self._load()
            waited += delay

    def observe(self, policy, headers):
        """Adopt the advertised rules and reconcile our count with the server's."""
        rule_names = [
            name.strip()
            for name in headers.get('X-Rate-Limit-Rules', '').split(',')
            if name.strip()
        ]
        for rule_name in rule_names:
            limit = headers.get('X-Rate-Limit-{}'.format(rule_name))
            if limit and parse_rules(limit):
                self._entry(policy)['rules'][rule_name] = limit
            state = headers.get('X-Rate-Limit-{}-State'.format(rule_name))
            if state:
                self._reconcile(policy, parse_rules(state))

    def _entry(self, policy):
        return self._policy(policy, DEFAULT_RULES.get(policy, FALLBACK_RULES))

    def _reconcile(self, policy, states):
        """Fold the server's view of this IP's usage into the local hit log.

        The server counts every request from this IP, including a browser's.
        Hits we cannot account for are stamped `now`, which expires them later
        than reality: deliberately pessimistic.

        A restriction is recorded rather than slept off here: `wait_for_slot`
        owns all the waiting, and a ban longer than the caller's patience
        should surface as RateLimited instead of being quietly retried early.
        """
        for state in states:
            now = time.time()
            entry = self._entry(policy)
            self._trim(entry, now)
            if state.restriction:
                self.block_until(policy, now + state.restriction)
                continue
            local = sum(1 for hit in entry['hits'] if hit > now - state.period)
            entry['hits'].extend([now] * max(0, state.hits - local))


class Response(collections.namedtuple('Response', 'status body cached')):
    @property
    def ok(self):
        return self.status == 200


class Client:
    """Cached, rate-limit-obeying access to the public pathofexile.tw APIs."""

    def __init__(
        self,
        cache_dir,
        utilization=0.5,
        offline=False,
        refresh=False,
        verbose=False,
        max_wait=MAX_SLEEP,
        state_path=None,
    ):
        if not 0 < utilization <= 1:
            raise ValueError('utilization must be in (0, 1]')
        self.cache_dir = pathlib.Path(cache_dir)
        self.offline = offline
        self.refresh = refresh
        self.verbose = verbose
        self.max_wait = max_wait
        self.requests_made = 0
        self.cache_hits = 0
        self.limits = RateLimitState(
            state_path or default_state_path(), utilization, self.log
        )
        self.session = requests.Session()
        self.session.headers['User-Agent'] = USER_AGENT

    def log(self, message):
        if self.verbose:
            print('# {}'.format(message), file=sys.stderr, flush=True)

    # -- endpoints ---------------------------------------------------------

    def leagues(self, realm='pc'):
        return self.get(LEAGUES, {'realm': realm, 'type': 'main'})

    def ladder(self, league, limit=200, offset=0, realm='pc'):
        # Validated here rather than only in the CLI: a request the server
        # will reject costs invalid-request allowance, so never send one.
        if not league:
            raise ValueError('league is required')
        limit, offset = int(limit), int(offset)
        if not 1 <= limit <= LADDER_PAGE_MAX:
            raise ValueError('limit must be 1..{}'.format(LADDER_PAGE_MAX))
        if offset < 0:
            raise ValueError('offset must not be negative')
        return self.get(
            LADDERS,
            {
                'id': league,
                'realm': realm,
                'limit': str(limit),
                'offset': str(offset),
            },
        )

    def character_items(self, account, character):
        return self.get(GET_ITEMS, self._character(account, character))

    def character_passives(self, account, character):
        return self.get(GET_PASSIVE_SKILLS, self._character(account, character))

    @staticmethod
    def _character(account, character):
        if not account or not character:
            raise ValueError('account and character are both required')
        return {'accountName': account, 'character': character}

    # -- transport ---------------------------------------------------------

    def _cache_path(self, path, params):
        query = urllib.parse.urlencode(sorted(params.items()))
        digest = hashlib.sha256(
            '{}?{}'.format(path, query).encode('utf-8')
        ).hexdigest()[:32]
        return self.cache_dir / path.strip('/').replace('/', '-') / (digest + '.json')

    def _read_cache(self, cache_path, path, allow_stale=False):
        try:
            with cache_path.open(encoding='utf-8') as file:
                cached = json.load(file)
        except (OSError, ValueError):
            return None
        status = cached.get('status')
        max_age = (
            DEFAULT_MAX_AGE.get(path, 3600) if status == 200 else NEGATIVE_MAX_AGE
        )
        age = time.time() - cached.get('fetched_at', 0)
        if age > max_age:
            if not allow_stale:
                self.log('cache expired: {}'.format(cache_path))
                return None
            self.log('serving stale cache ({:.0f}s old): {}'.format(age, cache_path))
        return Response(status, cached.get('body'), True)

    def _write_cache(self, cache_path, response):
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = cache_path.with_suffix('.tmp')
        with tmp.open('w', encoding='utf-8') as file:
            json.dump(
                {
                    'status': response.status,
                    'body': response.body,
                    'fetched_at': time.time(),
                },
                file,
                ensure_ascii=False,
            )
        os.replace(str(tmp), str(cache_path))

    def get(self, path, params):
        cache_path = self._cache_path(path, params)
        if not self.refresh:
            cached = self._read_cache(cache_path, path)
            if cached is not None:
                self.cache_hits += 1
                return cached
        if self.offline:
            # Offline means "make no requests", so an expired entry beats no
            # answer at all -- re-checking a code change against yesterday's
            # ladder is exactly what this mode is for.
            stale = (
                None if self.refresh
                else self._read_cache(cache_path, path, allow_stale=True)
            )
            if stale is not None:
                self.cache_hits += 1
                return stale
            raise RateLimited(
                'offline: nothing cached for {} {}'.format(path, params)
            )

        response = self._request(path, params)
        if response.status in CACHEABLE_STATUSES:
            self._write_cache(cache_path, response)
        return response

    def _request(self, path, params):
        with self.limits.locked():
            policy = self.limits.endpoint_policy(path, ENDPOINT_POLICY[path])
        last_error = None
        for attempt in range(MAX_RETRIES):
            try:
                status, body, headers = self._send(path, params, policy)
            except requests.RequestException as exception:
                # Connection resets and timeouts are not answers; retry them,
                # but the request was still sent, so it stays charged.
                last_error = exception
                delay = 2 ** attempt
                self.log('{} on {}: retrying in {}s'.format(
                    type(exception).__name__, path, delay))
                time.sleep(delay)
                continue

            served_by = headers.get('X-Rate-Limit-Policy')
            if served_by and served_by != policy:
                # The endpoint answers under a policy we did not assume: charge
                # the hit there too, and pace by it from here on.
                self.log('policy for {} is {!r}, not {!r}'.format(
                    path, served_by, policy))
                with self.limits.locked():
                    self.limits.charge(
                        served_by, DEFAULT_RULES.get(served_by, FALLBACK_RULES)
                    )
                    self.limits.observe(served_by, headers)
                    # Remembered on disk so the next process paces its first
                    # request by the policy that is actually in force.
                    self.limits.remember_endpoint_policy(path, served_by)
                policy = served_by

            if status == 429:
                try:
                    delay = int(headers.get('Retry-After', 60))
                except ValueError:
                    delay = 60
                # Record the ban and let wait_for_slot serve it, so a
                # concurrent run honours it too and nothing retries early.
                with self.limits.locked():
                    self.limits.block_until(policy, time.time() + delay + 1)
                last_error = RateLimited(
                    '429 from {}, blocked for {}s'.format(path, delay)
                )
                continue
            if status >= 500:
                last_error = RateLimited('HTTP {} from {}'.format(status, path))
                delay = 2 ** attempt
                self.log('{} from {}: retrying in {}s'.format(status, path, delay))
                time.sleep(delay)
                continue

            if status in CACHEABLE_STATUSES and status != 200:
                return Response(status, None, False)
            if status == 200:
                if body is None:
                    # 200 with an unparseable body is a transient edge, not an
                    # answer worth caching.
                    last_error = ValueError('non-JSON 200 from {}'.format(path))
                    time.sleep(2 ** attempt)
                    continue
                return Response(status, body, False)
            return Response(status, None, False)
        raise RateLimited('{} failed after {} attempts: {}'.format(
            path, MAX_RETRIES, last_error))

    def _send(self, path, params, policy):
        """Charge the budget, send one request, and record what came back.

        The lock is held across the whole cycle so a concurrent run cannot
        spend the same slot; `wait_for_slot` drops it while it sleeps.
        """
        rules = DEFAULT_RULES.get(policy, FALLBACK_RULES)
        with self.limits.locked():
            self.limits.wait_for_slot(policy, rules, self.max_wait)
            # A 4xx also spends invalid-request allowance, so make sure there
            # is room for one before sending; only a 4xx actually charges it.
            self.limits.wait_for_slot(
                INVALID_POLICY, INVALID_RULES, INVALID_MAX_WAIT, utilization=1.0
            )
            self.limits.charge(policy, rules)
            # Flush before the request goes out: if this process dies between
            # sending and unwinding, the slot must still be spent as far as
            # the next one is concerned.
            self.limits.flush()

            self.requests_made += 1
            self.log('GET {} {}'.format(path, params))
            http = self.session.get(
                BASE_URL + path, params=params, timeout=REQUEST_TIMEOUT
            )

            if 400 <= http.status_code < 500:
                self.limits.charge(INVALID_POLICY, INVALID_RULES)
            self.limits.observe(policy, http.headers)

            body = None
            if http.status_code == 200:
                try:
                    body = http.json()
                except ValueError:
                    body = None
            return http.status_code, body, http.headers


def main():
    import argparse

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        'what', choices=['leagues', 'ladder', 'items', 'passives']
    )
    parser.add_argument('--league')
    parser.add_argument('--limit', type=int, default=20)
    parser.add_argument('--offset', type=int, default=0)
    parser.add_argument('--account')
    parser.add_argument('--character')
    parser.add_argument('--utilization', type=float, default=0.5)
    parser.add_argument(
        '--cache-dir',
        default=os.path.join(
            os.path.dirname(os.path.abspath(__file__)), '..', '.ladder-cache'
        ),
    )
    parser.add_argument('--refresh', action='store_true')
    parser.add_argument('-v', '--verbose', action='store_true')
    args = parser.parse_args()

    client = Client(
        args.cache_dir,
        utilization=args.utilization,
        refresh=args.refresh,
        verbose=args.verbose,
    )
    if args.what == 'leagues':
        response = client.leagues()
    elif args.what == 'ladder':
        if not args.league:
            parser.error('--league is required for ladder')
        response = client.ladder(args.league, args.limit, args.offset)
    else:
        if not (args.account and args.character):
            parser.error('--account and --character are required')
        if args.what == 'items':
            response = client.character_items(args.account, args.character)
        else:
            response = client.character_passives(args.account, args.character)

    if not response.ok:
        print('HTTP {}'.format(response.status), file=sys.stderr)
        return 1
    json.dump(response.body, sys.stdout, ensure_ascii=False, indent=2)
    print()
    return 0


if __name__ == '__main__':
    sys.exit(main())
