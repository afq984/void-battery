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

# tools/gen_class_ids.py
CLASS_AND_ASCENDANCY_CLASS_IDS = {
    'Scion': (0, 0),
    'Ascendant': (0, 1),
    'Reliquarian': (0, 2),
    'Marauder': (1, 0),
    'Juggernaut': (1, 1),
    'Berserker': (1, 2),
    'Chieftain': (1, 3),
    'Ranger': (2, 0),
    'Warden': (2, 1),
    'Deadeye': (2, 2),
    'Pathfinder': (2, 3),
    'Witch': (3, 0),
    'Occultist': (3, 1),
    'Elementalist': (3, 2),
    'Necromancer': (3, 3),
    'Duelist': (4, 0),
    'Slayer': (4, 1),
    'Gladiator': (4, 2),
    'Champion': (4, 3),
    'Templar': (5, 0),
    'Inquisitor': (5, 1),
    'Hierophant': (5, 2),
    'Guardian': (5, 3),
    'Shadow': (6, 0),
    'Assassin': (6, 1),
    'Trickster': (6, 2),
    'Saboteur': (6, 3),
}

# TW class name -> EN class name
# Names come from the TW passive skill tree: https://pathofexile.tw/passive-skill-tree
# (look for the "classes" key in the inline JSON)
CLASS_MAP = {
    '貴族': 'Scion',
    '昇華使徒': 'Ascendant',
    '遺守使徒': 'Reliquarian',
    '野蠻人': 'Marauder',
    '勇士': 'Juggernaut',
    '暴徒': 'Berserker',
    '酋長': 'Chieftain',
    '遊俠': 'Ranger',
    '守林人': 'Warden',
    '銳眼': 'Deadeye',
    '追獵者': 'Pathfinder',
    '女巫': 'Witch',
    '秘術家': 'Occultist',
    '元素使': 'Elementalist',
    '死靈師': 'Necromancer',
    '決鬥者': 'Duelist',
    '處刑者': 'Slayer',
    '衛士': 'Gladiator',
    '冠軍': 'Champion',
    '聖堂武僧': 'Templar',
    '判官': 'Inquisitor',
    '聖宗': 'Hierophant',
    '守護者': 'Guardian',
    '暗影刺客': 'Shadow',
    '刺客': 'Assassin',
    '詐欺師': 'Trickster',
    '破壞者': 'Saboteur',
}


def _translate_class(name):
    return CLASS_MAP.get(name, name)


def get_encoded_tree(char, tree):
    classId, ascendancyClass = CLASS_AND_ASCENDANCY_CLASS_IDS[_translate_class(char['class'])]
    head = [0, 0, 0, 6, classId, ascendancyClass, len(tree['hashes'])]
    masteryEffects = []
    for child in tree['mastery_effects']:
        effect = tree['mastery_effects'][child]
        node = int(child)
        masteryEffects.append(effect)
        masteryEffects.append(node)

    return base64.urlsafe_b64encode(
        struct.pack(
            '>BBBBBBB{}HBB{}H'.format(len(tree["hashes"]), len(masteryEffects)),
            *itertools.chain(
                head, tree['hashes'], [0, len(tree['mastery_effects'])], masteryEffects
            ),
        )
    ).decode('ascii')


def Tree(char, tree):
    # from https://web.poe.garena.tw/passive-skill-tree
    # fmt: off
    jewelSlots = [26725, 36634, 33989, 41263, 60735, 61834, 31683, 28475, 6230, 48768, 34483, 7960, 46882, 55190, 61419, 2491, 54127, 32763, 26196, 33631, 21984, 29712, 48679, 9408, 12613, 16218, 2311, 22994, 40400, 46393, 61305, 12161, 3109, 49080, 17219, 44169, 24970, 36931, 14993, 10532, 23756, 46519, 23984, 51198, 61666, 6910, 49684, 33753, 18436, 11150, 22748, 64583, 61288, 13170, 9797, 41876, 59585, 43670, 29914, 18060]
    # fmt: on
    sockets = []
    overrides = []
    classId, ascendancyClass = CLASS_AND_ASCENDANCY_CLASS_IDS[_translate_class(char['class'])]

    for id, item in enumerate(tree['items'], 1):
        x = item['x']
        sockets.append(E.Socket(nodeId=str(jewelSlots[x]), itemId=str(id)))

    for nodeId in tree['skill_overrides']:
        item = tree['skill_overrides'][nodeId]
        if not item.get('isTattoo'):
            continue
        try:
            name = nebuloch.names.translate(item['name'])
        except TranslateError as e:
            # todo: handle error
            continue
        overrides.append(E.Override(dn=str(name), nodeId=str(nodeId)))

    return E.Tree(
        E.Spec(
            E.URL(
                'https://www.pathofexile.com/passive-skill-tree/'
                + get_encoded_tree(char, tree)
            ),
            E.Sockets(*sockets),
            E.Overrides(*overrides),
            ascendClassId=str(ascendancyClass),
            classId=str(classId),
            nodes='.'.join(str(node) for node in tree['hashes']),
            treeVersion='3_28',
        ),
        activeSpec='1',
    )


RARITY_MAP = {0: 'NORMAL', 1: 'MAGIC', 2: 'RARE', 3: 'UNIQUE', 9: 'RELIC', 10: 'RELIC'}

# corresponds to:
# `local slotMap =` in ImportTab.lua in POB
SLOT_MAP = {
    'Amulet': 'Amulet',
    'Belt': 'Belt',
    'BodyArmour': 'Body Armour',
    'Boots': 'Boots',
    'BrequelGrafts': 'Graft 1',
    'BrequelGrafts2': 'Graft 2',
    'Gloves': 'Gloves',
    'Helm': 'Helmet',
    'Offhand': 'Weapon 2',
    'Offhand2': 'Weapon 2 Swap',
    'Ring': 'Ring 1',
    'Ring2': 'Ring 2',
    'Ring3': 'Ring 3',
    'Trinket': 'Trinket',  # https://github.com/PathOfBuildingCommunity/PathOfBuilding/issues/1721
    'Weapon': 'Weapon 1',
    'Weapon2': 'Weapon 1 Swap',
}


def clean_name(name):
    name = name.replace('追憶之 ', '')
    return re.sub(r'\<\<set\:\w+\>\>', '', name)


# The character API used to return every mod list as a list of strings, with
# crafted, fractured and mutated mods split off into a `<flag>Mods` list each.
# Since poe 3.29 it returns implicit/explicit mods as objects instead, and
# folds those three lists back into `explicitMods`, tagged via `flags`:
#   {"description": "+40 最大魔力", "flags": {"crafted": true}}
# Some lists (`enchantMods`, ...) are still plain strings, so handle both.
# See `ImportTab.lua:ImportItemsAndSkills` in PathOfBuilding, which reads the
# same three flags and keeps the same three legacy lists, and `lineFlags` in
# `Item.lua` for the prefixes its item text parser accepts.
MOD_FLAG_PREFIXES = (
    ('crafted', '{crafted}'),
    ('fractured', '{fractured}'),
    ('mutated', '{mutated}'),
)


def mod_description(mod):
    if isinstance(mod, dict):
        return mod['description']
    return mod


def mod_prefix(mod):
    if not isinstance(mod, dict):
        return ''
    flags = mod.get('flags', {})
    return ''.join(prefix for flag, prefix in MOD_FLAG_PREFIXES if flags.get(flag))


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
        'ExpandedMainInventory' # 3.23 Wildwood bag
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

    def tr_mod_lines(self, mod, prefix):
        """Translate one mod into the PoB item text lines it becomes.

        POB tags mods per line -- `ImportTab.lua` splits every mod on newlines
        before applying its flags -- and both the mod and its translation can
        span several lines, so `prefix` goes on each of them.
        """
        description = mod_description(mod)
        loc = description.find('\n附加的小型天賦給予：')
        if loc != -1:
            parts = (description[:loc], description[loc + 1 :])
        else:
            parts = (description,)
        for part in parts:
            for line in self.tr_mod(part).split('\n'):
                if line:
                    yield prefix + line

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
        # `Implicits` counts lines, not mods: a mod whose translation spans
        # several lines contributes one line each, so the lines have to be
        # generated before the count can be emitted.
        implicit_lines = list(
            itertools.chain.from_iterable(
                self.tr_mod_lines(mod, mod_prefix(mod))
                for mod in itertools.chain(
                    item.get('implicitMods', ()),
                    item.get('enchantMods', ()),
                )
            )
        )
        yield 'Implicits: {}'.format(len(implicit_lines))
        if item['name'] in ['禁忌烈焰', '禁忌血肉']:
            requiredClass = item['requirements'][0]['values'][0][0]
            yield 'Requires Class ' + CLASS_MAP[requiredClass]
        for line in implicit_lines:
            yield line
        for mod in item.get('explicitMods', ()):
            for line in self.tr_mod_lines(mod, mod_prefix(mod)):
                yield line
        for flag, prefix in MOD_FLAG_PREFIXES:
            for mod in item.get('{}Mods'.format(flag), ()):
                for line in self.tr_mod_lines(mod, prefix):
                    yield line
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
