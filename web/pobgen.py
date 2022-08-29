# -*- coding: utf-8 -*-
from __future__ import unicode_literals


import re
import itertools
import collections
import base64
import struct
import zlib
import json
import logging
import warnings
import functools

from lxml.builder import E
import lxml.etree
import nebuloch.names
from nebuloch.mods import Translator
from nebuloch import TranslateError


_tr = Translator('Traditional Chinese', '')

ALTERNATE_MAP = {
    '異常的 ': 'Alternate1',
    '相異的 ': 'Alternate2',
    '幻影的 ': 'Alternate3',
    '': 'Default',
}
alt_matcher = '|'.join(map(re.escape, ALTERNATE_MAP))


def get_encoded_tree(char, tree):
    head = [0, 0, 0, 6, char['classId'], char['ascendancyClass'], len(tree['hashes'])]
    masteryEffects = []
    for child in tree['mastery_effects']:
        effect = int(child) >> 16
        node = int(child) & 65535
        masteryEffects.append(effect)
        masteryEffects.append(node)

    return base64.urlsafe_b64encode(
        struct.pack(
            '>BBBBBBB{}HBB{}H'.format(len(tree["hashes"]), len(masteryEffects)),
            *itertools.chain(head, tree['hashes'], [0, len(tree['mastery_effects'])], masteryEffects)
        )
    ).decode('ascii')


def Tree(char, tree):
    # from https://web.poe.garena.tw/passive-skill-tree
    # fmt: off
    jewelSlots = [26725, 36634, 33989, 41263, 60735, 61834, 31683, 28475, 6230, 48768, 34483, 7960, 46882, 55190, 61419, 2491, 54127, 32763, 26196, 33631, 21984, 29712, 48679, 9408, 12613, 16218, 2311, 22994, 40400, 46393, 61305, 12161, 3109, 49080, 17219, 44169, 24970, 36931, 14993, 10532, 23756, 46519, 23984, 51198, 61666, 6910, 49684, 33753, 18436, 11150, 22748, 64583, 61288, 13170, 9797, 41876, 59585]
    # fmt: on
    sockets = []

    for id, item in enumerate(tree['items'], 1):
        x = item['x']
        sockets.append(E.Socket(nodeId=str(jewelSlots[x]), itemId=str(id)))

    return E.Tree(
        E.Spec(
            E.URL(
                'https://www.pathofexile.com/passive-skill-tree/'
                + get_encoded_tree(char, tree)
            ),
            E.Sockets(*sockets),
            treeVersion='3_19',
        ),
        activeSpec='1',
    )


RARITY_MAP = {0: 'NORMAL', 1: 'MAGIC', 2: 'RARE', 3: 'UNIQUE', 9: 'RELIC'}

# corresponds to:
# `local slotMap =` in ImportTab.lua in POB
SLOT_MAP = {
    'Amulet': 'Amulet',
    'Belt': 'Belt',
    'BodyArmour': 'Body Armour',
    'Boots': 'Boots',
    'Gloves': 'Gloves',
    'Helm': 'Helmet',
    'Offhand': 'Weapon 2',
    'Offhand2': 'Weapon 2 Swap',
    'Ring': 'Ring 1',
    'Ring2': 'Ring 2',
    'Trinket': 'Trinket',  # https://github.com/PathOfBuildingCommunity/PathOfBuilding/issues/1721
    'Weapon': 'Weapon 1',
    'Weapon2': 'Weapon 1 Swap',
}


def clean_name(name):
    name = name.replace('追憶之 ', '')
    return re.sub(r'\<\<set\:\w+\>\>', '', name)


# XXX since poe 3.8, category is removed
# These are the categories that we are uncapable of handling at the moment
CATEGORY_BLACKLIST = set('gems currency maps cards monsters leaguestones'.split())

# These are the inventoryId's that are causing trouble
INVENTORY_BLACKLIST = set(
    (
        # We are only importing equipped items, and quest items are currently
        # causing troubles, so we are ignoring them for now
        'MainInventory',
        'Map',  # The item is on Zana's Map Device
        'Cursor',  # The item is on the cursor
    )
)


class POBGenerator:
    def __init__(self):
        self.errors = []

    def tr_with_report(self, function, text):
        try:
            return function(text)
        except TranslateError as e:
            return self._report_error(e)

    def _report_error(self, e):
        logging.exception('Translation failed')
        self.errors.append(e)
        return f'void_battery_{e.__class__.__name__}_{len(self.errors)}'

    tr_mod = functools.partialmethod(tr_with_report, _tr)
    tr_name = functools.partialmethod(tr_with_report, nebuloch.names.translate)

    def export(self, items, tree):
        char = items['character']
        items, skills = self.ItemsSkills(tree['items'] + items['items'])
        if not len(skills):
            L0 = ('nil', None)
        else:
            L0 = max(enumerate(skills, 1), key=lambda m: len(m[1]))
        defsock, maxlink_skill = L0
        pob = E.PathOfBuilding(
            E.Build(
                level=str(char['level']),
                targetVersion='3_0',
                mainSocketGroup=str(defsock),
            ),
            skills,
            Tree(char, tree),
            items,
        )
        return base64.urlsafe_b64encode(zlib.compress(lxml.etree.tostring(pob))).decode(
            'ascii'
        )

    def ItemsSkills(self, items):
        item_list = []
        slot_list = []
        skill_list = []
        abyss_todo = []
        for id, item in enumerate(items, 1):
            strid = str(id)
            inventoryId = item['inventoryId']
            if inventoryId in INVENTORY_BLACKLIST or inventoryId.endswith(
                'MasterCrafting'
            ):
                pass
            elif item['frameType'] not in RARITY_MAP:
                warnings.warn(
                    'frameType = {!r}, inventoryId = {!r}'.format(
                        item['frameType'], inventoryId
                    )
                )
            else:
                pob = self.item_to_pob(item)
                item_list.append(E.Item(pob, id=strid))
                if inventoryId != 'PassiveJewels':
                    if inventoryId == 'Flask':
                        slot = 'Flask {}'.format(item['x'] + 1)
                    else:
                        slot = SLOT_MAP[inventoryId]
                    slot_list.append(E.Slot(name=slot, itemId=strid))
                    local_skills, abyss = self.import_socketed_items(item, slot)
                    skill_list.extend(local_skills)
                    if abyss:
                        abyss_todo.append((slot, abyss))
        for parent_slot, abyss_jewels in abyss_todo:
            for socknum, abyss_jewel in enumerate(abyss_jewels, 1):
                id += 1
                strid = str(id)
                item_list.append(E.Item(abyss_jewel, id=strid))
                slot = '%s Abyssal Socket %d' % (parent_slot, socknum)
                slot_list.append(E.Slot(name=slot, itemId=strid))
        return (
            E.Items(*(item_list + slot_list)),
            E.Skills(*skill_list, sortGemsByDPS='true'),
        )

    def Gem(self, item):
        match = re.match(r'(%s)(.+)' % alt_matcher, item['typeLine'])
        alternate, gemName = match.groups()
        nameSpec = self.tr_name(gemName).replace(' Support', '')
        qualityId = ALTERNATE_MAP[alternate]
        level = 20
        quality = 0
        for prop in item['properties']:
            if prop['name'] == '等級':
                level = int(prop['values'][0][0].replace('（最高等級）', ''))
            elif prop['name'] == '品質':
                quality = int(prop['values'][0][0].lstrip('+').rstrip('%'))
        return E.Gem(
            level=str(level),
            quality=str(quality),
            enabled='true',
            nameSpec=nameSpec,
            qualityId=qualityId,
        )

    def item_to_pob(self, item):
        return '\n'.join(self.i_item_to_pob(item))

    def parse_magic(self, item):
        twbase = clean_name(item['typeLine']).rpartition('精良的 ')[-1]
        parts = re.findall('([^的之]+[的之]?)', twbase)
        accumulated = ''
        for part in reversed(parts):
            accumulated = part + accumulated
            try:
                translated = nebuloch.names.translate(accumulated)
            except nebuloch.names.CannotTranslateName:
                continue
            return 'MAGIC {} {}'.format(translated, item["id"][-7:])
        raise nebuloch.names.CannotTranslateName(item['typeLine'])

    def i_item_to_pob(self, item):
        rarity = RARITY_MAP[item['frameType']]
        yield 'Rarity: {}'.format(rarity)
        if rarity == 'RARE':
            yield '{} {}'.format(rarity, item["id"][-7:])
        elif rarity in ('UNIQUE', 'RELIC'):
            yield self.tr_name(clean_name(item['name']))
        if rarity == 'MAGIC':
            yield self.tr_with_report(self.parse_magic, item)
        else:
            yield self.tr_name(
                item['typeLine'].rpartition('精良的 ')[-1].rpartition('追憶之 ')[-1]
            )
        yield "Unique ID: {}".format(item['id'])
        yield "Item Level: {}".format(item['ilvl'])
        quality = 0
        radius = None
        for prop in item.get('properties', ()):
            if prop['name'] == '品質':
                quality = prop['values'][0][0].lstrip('+').rstrip('%')
            if prop['name'] == '範圍':
                radius = {'小': 'Small', '中': 'Medium', '大': 'Large', '可變的': 'Variable'}[
                    prop['values'][0][0]
                ]
        yield 'Quality: {}'.format(quality)
        if radius is not None:
            yield 'Radius: {}'.format(radius)
        if 'sockets' in item:
            socketgroups = collections.defaultdict(list)
            for socket in item['sockets']:
                socketgroups[socket['group']].append(socket['sColour'])
            sockstr = ' '.join('-'.join(colors) for colors in socketgroups.values())
            yield 'Sockets: ' + sockstr
        if item.get('corrupted'):
            yield 'Corrupted'
        n_implicits = len(item.get('implicitMods', ())) + len(
            item.get('enchantMods', ())
        )
        yield 'Implicits: {}'.format(n_implicits)
        for mod in itertools.chain(
            item.get('implicitMods', ()),
            item.get('enchantMods', ()),
            item.get('explicitMods', ()),
        ):
            loc = mod.find('\n附加的小型天賦給予：')
            if loc != -1:
                yield self.tr_mod(mod[:loc])
                yield self.tr_mod(mod[loc + 1 :])
            else:
                yield self.tr_mod(mod)
        for cmod in item.get('craftedMods', ()):
            yield '{crafted}' + self.tr_mod(cmod)
        for fmod in item.get('fracturedMods', ()):
            yield '{fractured}' + self.tr_mod(fmod)
        if item.get('shaper'):
            yield 'Shaper Item'
        if item.get('elder'):
            yield 'Elder Item'
        if item.get('fractured'):
            yield 'Fractured Item'
        if item.get('synthesised'):
            yield 'Synthesised Item'

    def import_socketed_items(self, item, slot):
        """returns [skills], [abyss jewels]"""
        if 'socketedItems' not in item:
            return [], []
        groups = collections.defaultdict(list)
        jewels = []
        for socketedItem in item['socketedItems']:
            socket = item['sockets'][socketedItem['socket']]
            groupId = socket['group']
            socketColor = socket['sColour']
            if socketColor == 'A':  # Abyss jewel
                jewels.append(self.item_to_pob(socketedItem))
            else:
                groups[groupId].append(self.Gem(socketedItem))
        gems = [
            E.Skill(
                *gems,
                enabled='true',
                slot=slot,
                mainActiveSkillCalcs='nil',
                mainActiveSkill='nil',
            )
            for gems in groups.values()
        ]
        return gems, jewels


def export(items, tree):
    generator = POBGenerator()
    return generator.export(items, tree)


def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('a')
    parser.add_argument('b')
    parser.add_argument('--poesessid')
    args = parser.parse_args()
    a = args.a
    b = args.b
    if a.lower().endswith('.json') and b.lower().endswith('.json'):
        with open(a) as af, open(b) as bf:
            items = json.load(af)
            tree = json.load(bf)
        print(export(items, tree))


if __name__ == '__main__':
    main()
