# -*- coding: utf-8 -*-
"""Verify the PoB exporter against real characters from the pathofexile.tw ladder.

Takes a page of the current TW challenge league ladder, fetches each
character's items and passive tree through `poe_tw` (which owns all the rate
limiting and caching), and runs them through the real POBGenerator.  A
character passes when the export decodes to a PoB build that accounts for
every item, gem and passive the API reported, with nothing left untranslated.

Only accounts that opted into a public profile answer these endpoints.  The
rest return 403; they are reported as skipped, not as failures, and the run
stops probing once it has drawn --max-private of them.

    python3 tools/ladder_verify.py                 # verify 10 characters
    python3 tools/ladder_verify.py --count 20 -v
    python3 tools/ladder_verify.py --offline       # re-check from the cache
"""

from __future__ import unicode_literals

import argparse
import base64
import collections
import os
import pathlib
import re
import sys
import warnings
import zlib

import lxml.etree

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import poe_tw  # noqa: E402
import nebuloch.names  # noqa: E402
from nebuloch import TranslateError  # noqa: E402
from pobgen import (  # noqa: E402
    ALTERNATE_MAP,
    CLASS_AND_ASCENDANCY_CLASS_IDS,
    INVENTORY_BLACKLIST,
    POBGenerator,
    RARITY_MAP,
    SLOT_MAP,
    alt_matcher,
)


UNIQUE_ID = re.compile(r'^Unique ID: (\S+)$', re.MULTILINE)

TREE_URL_VERSION = 6


def current_league(client):
    """The current softcore trade challenge league on the TW realm."""
    response = client.leagues()
    if not response.ok:
        raise SystemExit('cannot list leagues: HTTP {}'.format(response.status))
    for league in response.body:
        if league.get('category', {}).get('id') != 'Standard' and not league['rules']:
            return league['id']
    raise SystemExit(
        'no challenge league among {}'.format(
            [league['id'] for league in response.body]
        )
    )


def ladder_entries(client, league, offsets, limit):
    """Merge several pages spread down the ladder.

    Sampling only the top ranks is doubly bad: those players run whatever is
    meta this week, and they are the ones most likely to have hidden their
    profile.  Reading a page from a few depths costs a handful of requests
    under the cheap ladder-view policy and yields far more variety.
    """
    entries = []
    for offset in offsets:
        response = client.ladder(league, limit=limit, offset=offset)
        if not response.ok:
            raise SystemExit(
                'cannot read the {} ladder at offset {}: HTTP {}'.format(
                    league, offset, response.status
                )
            )
        entries.extend(response.body['entries'])
    return entries


def by_class_round_robin(entries):
    """Order ladder entries so consecutive picks differ in class and account.

    Rank order alone would spend the whole request budget on whatever
    ascendancy is dominating the league; interleaving covers far more of the
    mod and base-item space for the same number of requests.  One character
    per account also keeps a single private account from costing several
    403s -- those count against an invalid-request threshold.
    """
    groups = collections.OrderedDict()
    seen_accounts = set()
    for entry in entries:
        account = entry.get('account', {}).get('name')
        if not account or account in seen_accounts:
            continue  # anonymous, or already represented
        seen_accounts.add(account)
        groups.setdefault(entry['character']['class'], []).append(entry)
    ordered = []
    while groups:
        for class_name in list(groups):
            ordered.append(groups[class_name].pop(0))
            if not groups[class_name]:
                del groups[class_name]
    return ordered


class Result:
    def __init__(self, entry, status, detail='', problems=(), stats=None,
                 cached=False):
        self.entry = entry
        self.status = status
        self.detail = detail
        self.problems = list(problems)
        self.stats = stats or {}
        # Whether this answer cost a request.  A 403 served from the cache did
        # not spend any invalid-request allowance, so it must not count
        # against the run's probing budget.
        self.cached = cached

    @property
    def account(self):
        return self.entry['account']['name']

    @property
    def character(self):
        return self.entry['character']['name']


def check_character(client, entry):
    account = entry['account']['name']
    character = entry['character']['name']

    items = client.character_items(account, character)
    if items.status == 403:
        return Result(entry, 'private', 'profile or characters not public',
                      cached=items.cached)
    if items.status == 404:
        return Result(entry, 'missing', 'character not found', cached=items.cached)
    if not items.ok:
        return Result(entry, 'unavailable', 'get-items HTTP {}'.format(items.status))

    tree = client.character_passives(account, character)
    if tree.status == 403:
        return Result(entry, 'private', 'passives not public', cached=tree.cached)
    if tree.status == 404:
        return Result(entry, 'missing', 'passives not found', cached=tree.cached)
    if not tree.ok:
        return Result(
            entry, 'unavailable', 'get-passive-skills HTTP {}'.format(tree.status)
        )

    return export_and_check(entry, items.body, tree.body)


def export_and_check(entry, items, tree):
    """Run the real exporter over one character and audit what comes out."""
    problems = []
    generator = POBGenerator()
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        try:
            code = generator.export(items, tree)
        except Exception as exception:  # noqa: BLE001 -- reported, not raised
            return Result(
                entry, 'failed', '{}: {}'.format(type(exception).__name__, exception)
            )
    problems.extend('warning: {}'.format(warning.message) for warning in caught)
    problems.extend('untranslated: {}'.format(error) for error in generator.errors)

    try:
        xml = lxml.etree.fromstring(zlib.decompress(base64.urlsafe_b64decode(code)))
    except Exception as exception:  # noqa: BLE001
        return Result(
            entry,
            'failed',
            'undecodable pob code: {}: {}'.format(type(exception).__name__, exception),
            problems,
        )

    expected = expected_contents(items, tree)
    stats = {
        'level': items['character']['level'],
        'class': items['character']['class'],
        'items': len(xml.xpath('/PathOfBuilding/Items/Item')),
        'gems': len(xml.xpath('/PathOfBuilding/Skills/Skill/Gem')),
        'groups': len(xml.xpath('/PathOfBuilding/Skills/Skill')),
        'nodes': len(tree['hashes']),
        'masteries': len(tree['mastery_effects']),
        'jewels': len(expected['abyss_ids']) + len(tree['items']),
    }

    problems.extend(audit(xml, entry, items, tree, expected))
    if problems:
        return Result(
            entry, 'failed', '{} problem(s)'.format(len(problems)), problems, stats
        )
    return Result(entry, 'ok', '', (), stats)


def expected_contents(items, tree):
    """What the export must account for, derived from the raw API payload.

    Mirrors the exclusions POBGenerator documents -- inventory, map device and
    cursor items, master crafting slots, and frame types it has no rarity for
    -- so that anything else silently disappearing shows up as a problem.
    """
    item_ids = set()
    tree_jewel_ids = set()
    abyss_ids = set()
    gems = collections.Counter()
    groups = collections.defaultdict(list)
    slots = {}
    for item in list(tree['items']) + list(items['items']):
        inventory_id = item['inventoryId']
        if inventory_id in INVENTORY_BLACKLIST or inventory_id.endswith(
            'MasterCrafting'
        ):
            continue
        if item['frameType'] not in RARITY_MAP:
            continue
        item_ids.add(item['id'])
        if inventory_id == 'PassiveJewels':
            tree_jewel_ids.add(item['id'])
            continue
        if inventory_id == 'Flask':
            slot = 'Flask {}'.format(item['x'] + 1)
        else:
            slot = SLOT_MAP.get(inventory_id, inventory_id)
        slots[item['id']] = slot
        by_group = collections.Counter()
        for socketed in item.get('socketedItems', ()):
            socket = item['sockets'][socketed['socket']]
            if socket['sColour'] == 'A':
                abyss_ids.add(socketed['id'])
            else:
                gems[describe_gem(socketed)] += 1
                by_group[socket['group']] += 1
        if by_group:
            groups[slot] = sorted(by_group.values())
    return {
        'item_ids': item_ids,
        'tree_jewel_ids': tree_jewel_ids,
        'abyss_ids': abyss_ids,
        'gems': gems,
        'groups': dict(groups),
        'slots': slots,
    }


def audit(xml, entry, items, tree, expected):
    """Structural checks on the generated build, beyond "it did not crash"."""
    problems = []
    character = items['character']

    levels = xml.xpath('/PathOfBuilding/Build/@level')
    if levels != [str(character['level'])]:
        problems.append(
            'Build/@level is {!r}, character is level {}'.format(
                levels, character['level']
            )
        )

    exported_items = audit_items(xml, expected, problems)
    problems.extend(audit_skills(xml, expected))

    specs = xml.xpath('/PathOfBuilding/Tree/Spec')
    if len(specs) != 1:
        problems.append('expected one Tree/Spec, found {}'.format(len(specs)))
        return problems
    problems.extend(audit_tree(specs[0], entry, character, tree, exported_items,
                               expected))

    if 'void_battery_' in lxml.etree.tostring(xml, encoding='unicode'):
        problems.append('export contains a translation-failure placeholder')
    return problems


def audit_items(xml, expected, problems):
    """Every item the API reported must appear, and every slot must resolve.

    Returns the exported items as {PoB item id: game item id}, which the tree
    audit needs to resolve jewel sockets.
    """
    exported = {}
    for element in xml.xpath('/PathOfBuilding/Items/Item'):
        match = UNIQUE_ID.search(element.text or '')
        if match is None:
            problems.append('exported item {} has no Unique ID line'.format(
                element.get('id')))
            continue
        exported[element.get('id')] = match.group(1)

    wanted = expected['item_ids'] | expected['abyss_ids']
    missing = wanted - set(exported.values())
    if missing:
        problems.append(
            '{} item(s) missing from the export: {}'.format(
                len(missing), ', '.join(sorted(item_id[:8] for item_id in missing))
            )
        )
    extra = set(exported.values()) - wanted
    if extra:
        problems.append(
            '{} item(s) exported that the API did not report: {}'.format(
                len(extra), ', '.join(sorted(item_id[:8] for item_id in extra))
            )
        )

    # POB equips by Slot: an item with no Slot lands in the build's stash
    # instead of on the character, and one in the wrong Slot is a different
    # build.  So check the whole mapping, not just that the references resolve.
    placed = {}
    for slot in xml.xpath('/PathOfBuilding/Items/Slot'):
        item_id = exported.get(slot.get('itemId'))
        if item_id is None:
            problems.append(
                'slot {!r} points at item {!r}, which was not exported'.format(
                    slot.get('name'), slot.get('itemId')
                )
            )
        else:
            placed[item_id] = slot.get('name')

    for item_id, slot in sorted(expected['slots'].items()):
        if item_id not in placed:
            problems.append(
                'item {} belongs in slot {!r} but was not equipped'.format(
                    item_id[:8], slot
                )
            )
        elif placed[item_id] != slot:
            problems.append(
                'item {} equipped in slot {!r}, expected {!r}'.format(
                    item_id[:8], placed[item_id], slot
                )
            )
    return exported


def describe_gem(socketed):
    """A socketed gem as (name, level, quality, alternate quality).

    Read straight off the API payload, independently of pobgen, so that a gem
    exported at the wrong level -- or as the wrong gem -- is a mismatch rather
    than something the counts happen to hide.
    """
    alternate, name = re.match(
        r'({})(.+)'.format(alt_matcher), socketed['typeLine']
    ).groups()
    try:
        english = nebuloch.names.translate_gem(name)
    except TranslateError:
        english = None
    level, quality = 20, 0
    for prop in socketed.get('properties', ()):
        if prop['name'] == '等級':
            level = int(prop['values'][0][0].replace('（最高等級）', ''))
        elif prop['name'] == '品質':
            quality = int(prop['values'][0][0].lstrip('+').rstrip('%'))
    return (english, str(level), str(quality), ALTERNATE_MAP[alternate])


def audit_skills(xml, expected):
    """Gems must survive with their socket grouping and their names intact."""
    problems = []
    gems = xml.xpath('/PathOfBuilding/Skills/Skill/Gem')
    exported = collections.Counter(
        (
            gem.get('nameSpec'),
            gem.get('level'),
            gem.get('quality'),
            gem.get('qualityId'),
        )
        for gem in gems
    )
    for gem, count in sorted(
        (expected['gems'] - exported).items(), key=lambda item: str(item[0])
    ):
        problems.append(
            '{} socketed gem(s) missing from the export: {}'.format(count, gem)
        )
    for gem, count in sorted(
        (exported - expected['gems']).items(), key=lambda item: str(item[0])
    ):
        problems.append(
            '{} exported gem(s) the character does not have: {}'.format(count, gem)
        )

    # POB links gems by socket group, so a build whose groups were merged or
    # split has the wrong skills even though every gem is present.
    exported_groups = collections.defaultdict(list)
    for skill in xml.xpath('/PathOfBuilding/Skills/Skill'):
        exported_groups[skill.get('slot')].append(len(skill.xpath('Gem')))
    for slot, sizes in sorted(expected['groups'].items()):
        found = sorted(exported_groups.get(slot, []))
        if found != sizes:
            problems.append(
                'slot {!r} has socket groups {}, exported {}'.format(
                    slot, sizes, found
                )
            )
    return problems


def audit_tree(spec, entry, character, tree, exported_items, expected):
    problems = []

    # The ladder reports the class in English and the character API in
    # Traditional Chinese, so this cross-checks pobgen's CLASS_MAP against a
    # second, independent source.
    ladder_class = entry['character']['class']
    encoded = (int(spec.get('classId')), int(spec.get('ascendClassId')))
    if ladder_class in CLASS_AND_ASCENDANCY_CLASS_IDS:
        wanted = CLASS_AND_ASCENDANCY_CLASS_IDS[ladder_class]
        if wanted != encoded:
            problems.append(
                'class {!r} ({!r}) encoded as {}, ladder says {}'.format(
                    character['class'], ladder_class, encoded, wanted
                )
            )
    else:
        problems.append('ladder class {!r} is unknown to pobgen'.format(ladder_class))

    allocated = [int(node) for node in tree['hashes']]
    nodes = [node for node in (spec.get('nodes') or '').split('.') if node]
    if [int(node) for node in nodes] != allocated:
        problems.append(
            'Spec/@nodes does not match the {} allocated passives'.format(
                len(allocated)
            )
        )

    urls = spec.xpath('URL/text()')
    if len(urls) != 1 or '/passive-skill-tree/' not in urls[0]:
        problems.append('missing or malformed passive tree URL: {!r}'.format(urls))
    else:
        problems.extend(audit_tree_url(urls[0], encoded, allocated, tree))

    problems.extend(audit_sockets(spec, tree, exported_items, expected))
    problems.extend(audit_overrides(spec, tree))
    return problems


def audit_sockets(spec, tree, exported_items, expected):
    """Every tree jewel must reach a distinct socket holding a real jewel.

    Not checked: whether the socket node is allocated.  A jewel can sit in a
    cluster jewel's expansion socket, whose node is generated when POB rebuilds
    the cluster graphs and so is absent from the character's allocated nodes.
    """
    problems = []
    sockets = spec.xpath('Sockets/Socket')
    if len(sockets) != len(tree['items']):
        problems.append(
            '{} jewel socket(s) encoded, the character has {} tree jewels'.format(
                len(sockets), len(tree['items'])
            )
        )
    node_ids = [int(socket.get('nodeId')) for socket in sockets]
    if len(set(node_ids)) != len(node_ids):
        problems.append('two tree jewels were socketed into the same passive')

    socketed = []
    for socket in sockets:
        item_id = exported_items.get(socket.get('itemId'))
        if item_id is None:
            problems.append(
                'jewel socket {} points at item {!r}, which was not exported'.format(
                    socket.get('nodeId'), socket.get('itemId')
                )
            )
        else:
            socketed.append(item_id)
    # Each jewel exactly once: duplicating one while dropping another keeps
    # the count right and the build wrong.
    if sorted(socketed) != sorted(expected['tree_jewel_ids']):
        problems.append(
            'sockets hold {} distinct tree jewel(s), the character has {}'.format(
                len(set(socketed)), len(expected['tree_jewel_ids'])
            )
        )
    return problems


def audit_overrides(spec, tree):
    """Tattoos replace a passive's stats, so both node and name must survive."""
    wanted = {}
    for node, override in tree.get('skill_overrides', {}).items():
        if not override.get('isTattoo'):
            continue
        try:
            wanted[node] = nebuloch.names.translate(override['name'])
        except TranslateError:
            wanted[node] = None  # untranslatable: reported as an error already
    exported = {
        element.get('nodeId'): element.get('dn')
        for element in spec.xpath('Overrides/Override')
    }
    problems = []
    if sorted(exported) != sorted(wanted):
        problems.append(
            'exported tattoo override(s) on {} passive(s), the character has {}'
            .format(len(exported), len(wanted))
        )
    for node, name in sorted(wanted.items()):
        if name is not None and exported.get(node) != name:
            problems.append(
                'tattoo on passive {} exported as {!r}, expected {!r}'.format(
                    node, exported.get(node), name
                )
            )
    return problems


def audit_tree_url(url, encoded_class, allocated, tree):
    """Decode the tree code back out and confirm it round-trips.

    Node ids are what PoB actually reads; a count-only check would pass a
    build whose every passive was wrong.
    """
    try:
        blob = base64.urlsafe_b64decode(url.rpartition('/')[2])
    except Exception as exception:  # noqa: BLE001
        return ['undecodable tree URL: {}'.format(exception)]
    if len(blob) < 7:
        return ['tree URL payload is only {} bytes'.format(len(blob))]

    problems = []
    version = int.from_bytes(blob[0:4], 'big')
    if version != TREE_URL_VERSION:
        problems.append(
            'tree URL version is {}, expected {}'.format(version, TREE_URL_VERSION)
        )
    if (blob[4], blob[5]) != encoded_class:
        problems.append(
            'tree URL class {} disagrees with Spec {}'.format(
                (blob[4], blob[5]), encoded_class
            )
        )

    count = blob[6]
    end = 7 + 2 * count
    if len(blob) < end:
        return problems + ['tree URL is truncated: {} nodes claimed'.format(count)]
    nodes = [
        int.from_bytes(blob[offset:offset + 2], 'big')
        for offset in range(7, end, 2)
    ]
    if nodes != allocated:
        problems.append(
            'tree URL encodes {} nodes, the character allocated {}{}'.format(
                len(nodes),
                len(allocated),
                '' if len(nodes) != len(allocated) else ' (different ids)',
            )
        )

    if len(blob) < end + 2:
        return problems + ['tree URL has no mastery section']
    mastery_count = blob[end + 1]
    masteries = {}
    for offset in range(end + 2, end + 2 + 4 * mastery_count, 4):
        effect = int.from_bytes(blob[offset:offset + 2], 'big')
        node = int.from_bytes(blob[offset + 2:offset + 4], 'big')
        masteries[node] = effect
    wanted = {int(node): effect for node, effect in tree['mastery_effects'].items()}
    if masteries != wanted:
        problems.append(
            'tree URL encodes {} mastery effect(s), the character has {}'.format(
                len(masteries), len(wanted)
            )
        )
    return problems


STATUS_ORDER = ['ok', 'failed', 'private', 'missing', 'unavailable']


def report(results, league, wanted, stopped_early):
    print()
    print('League: {}'.format(league))
    print('=' * 78)
    for result in results:
        summary = ''
        if result.stats:
            summary = (
                '  lv{level} {class} | {items} items, {gems} gems in {groups} '
                'groups, {nodes} nodes, {masteries} masteries, {jewels} jewels'
            ).format(**result.stats)
        print(
            '[{:<11}] #{:<5} {} / {}{}'.format(
                result.status,
                result.entry['rank'],
                result.account,
                result.character,
                summary,
            )
        )
        if result.detail:
            print('              {}'.format(result.detail))
        for problem in result.problems:
            print('              - {}'.format(problem))
    print('=' * 78)

    counts = collections.Counter(result.status for result in results)
    print(
        'checked {} ladder entries: {}'.format(
            len(results),
            ', '.join(
                '{} {}'.format(counts[status], status)
                for status in STATUS_ORDER
                if counts[status]
            ),
        )
    )
    if stopped_early:
        print('note: {}'.format(stopped_early))
    if counts['failed']:
        print('FAIL: {} character(s) did not export cleanly'.format(counts['failed']))
        return 1
    if counts['ok'] < wanted:
        print(
            'FAIL: verified {} public character(s), wanted {}'.format(
                counts['ok'], wanted
            )
        )
        return 1
    print('PASS: {} public character(s) exported cleanly'.format(counts['ok']))
    return 0


def positive(text):
    value = int(text)
    if value <= 0:
        raise argparse.ArgumentTypeError('must be a positive integer')
    return value


def main():
    parser = argparse.ArgumentParser(
        description=__doc__.splitlines()[0],
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument('--count', type=positive, default=10,
                        help='public characters to verify (default: 10)')
    parser.add_argument('--attempts', type=positive,
                        help='ladder entries to try (default: count * 6)')
    parser.add_argument('--max-private', type=positive, default=25,
                        help='stop after this many non-public accounts')
    parser.add_argument('--league', help='league id (default: current challenge)')
    parser.add_argument('--ladder-size', type=positive, default=100,
                        help='ladder entries per page (max 200)')
    parser.add_argument('--offsets', default='200,1500,4000,9000',
                        help='ladder ranks to sample from, comma separated')
    parser.add_argument('--utilization', type=float, default=0.5,
                        help='fraction of each advertised rate limit to use')
    parser.add_argument('--cache-dir',
                        default=os.path.join(
                            os.path.dirname(os.path.abspath(__file__)),
                            '..', '.ladder-cache'),
                        help='where API responses and rate limit state live')
    parser.add_argument('--offline', action='store_true',
                        help='fail instead of making uncached requests')
    parser.add_argument('--refresh', action='store_true',
                        help='ignore cached responses and refetch')
    parser.add_argument('-v', '--verbose', action='store_true')
    args = parser.parse_args()

    if not 0 < args.utilization <= 1:
        parser.error('--utilization must be in (0, 1]')
    try:
        offsets = [int(offset) for offset in args.offsets.split(',') if offset.strip()]
    except ValueError:
        parser.error('--offsets must be a comma separated list of integers')
    if not offsets or any(offset < 0 for offset in offsets):
        parser.error('--offsets must be non-negative integers')

    client = poe_tw.Client(
        args.cache_dir,
        utilization=args.utilization,
        offline=args.offline,
        refresh=args.refresh,
        verbose=args.verbose,
    )
    league = args.league or current_league(client)
    entries = ladder_entries(client, league, offsets, min(args.ladder_size, 200))
    candidates = by_class_round_robin(entries)

    attempts = args.attempts or args.count * 6
    results = []
    verified = 0
    private = 0
    stopped_early = ''
    for entry in candidates[:attempts]:
        if verified >= args.count:
            break
        if private >= args.max_private:
            stopped_early = (
                'stopped after {} non-public accounts to stay well clear of the '
                'invalid-request limit'.format(private)
            )
            break
        try:
            result = check_character(client, entry)
        except poe_tw.RateLimited as exception:
            stopped_early = 'stopped early: {}'.format(exception)
            break
        results.append(result)
        if result.status == 'ok':
            verified += 1
        elif result.status in ('private', 'missing') and not result.cached:
            private += 1

    status = report(results, league, args.count, stopped_early)
    print(
        '{} request(s) made, {} served from {}'.format(
            client.requests_made, client.cache_hits, args.cache_dir
        )
    )
    return status


if __name__ == '__main__':
    sys.exit(main())
