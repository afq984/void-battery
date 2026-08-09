# -*- encoding: utf-8 -*-

from __future__ import unicode_literals

from pobgen import (
    CLASS_AND_ASCENDANCY_CLASS_IDS,
    CLASS_MAP,
    POBGenerator,
    mod_description,
    mod_prefix,
)


def test_mod_description_string():
    assert mod_description('+40 最大魔力') == '+40 最大魔力'


def test_mod_description_object():
    assert mod_description({'description': '+40 最大魔力'}) == '+40 最大魔力'


def test_mod_prefix_string():
    assert mod_prefix('+40 最大魔力') == ''


def test_mod_prefix_no_flags():
    assert mod_prefix({'description': '+40 最大魔力'}) == ''


def test_mod_prefix_crafted():
    mod = {'description': '+40 最大魔力', 'flags': {'crafted': True}}
    assert mod_prefix(mod) == '{crafted}'


def test_mod_prefix_fractured():
    mod = {'description': '+40 最大魔力', 'flags': {'fractured': True}}
    assert mod_prefix(mod) == '{fractured}'


def test_mod_prefix_mutated():
    mod = {'description': '+40 最大魔力', 'flags': {'mutated': True}}
    assert mod_prefix(mod) == '{mutated}'


def item(**kwargs):
    base = {
        'frameType': 2,
        'id': '0' * 64,
        'name': '狂喜 護盔',
        'typeLine': '全罩戰盔',
        'ilvl': 82,
    }
    base.update(kwargs)
    return base


def pob_lines(**kwargs):
    return POBGenerator().item_to_pob(item(**kwargs)).splitlines()


def test_mods_as_strings():
    """The pre-3.29 shape: mod lists are strings, flagged mods are separate."""
    lines = pob_lines(
        implicitMods=['+18 力量和敏捷'],
        explicitMods=['+88 最大生命'],
        craftedMods=['+40 最大魔力'],
        fracturedMods=['+39 最大魔力'],
        mutatedMods=['+37 最大魔力'],
    )
    assert lines[-5:] == [
        '+18 to Strength and Dexterity',
        '+88 to maximum Life',
        '{crafted}+40 to maximum Mana',
        '{fractured}+39 to maximum Mana',
        '{mutated}+37 to maximum Mana',
    ]


def test_mods_as_objects():
    """The current shape: mods are objects, flagged mods live in explicitMods."""
    lines = pob_lines(
        implicitMods=[{'description': '+18 力量和敏捷'}],
        explicitMods=[
            {'description': '+88 最大生命'},
            {'description': '+40 最大魔力', 'flags': {'crafted': True}},
            {'description': '+39 最大魔力', 'flags': {'fractured': True}},
            {'description': '+37 最大魔力', 'flags': {'mutated': True}},
        ],
    )
    assert lines[-5:] == [
        '+18 to Strength and Dexterity',
        '+88 to maximum Life',
        '{crafted}+40 to maximum Mana',
        '{fractured}+39 to maximum Mana',
        '{mutated}+37 to maximum Mana',
    ]


def test_cluster_jewel_mod_as_object():
    """The added-small-passives mod is split into two lines; both keep the prefix."""
    mod = '增加 12% 傷害\n附加的小型天賦給予：增加 12% 傷害'
    lines = pob_lines(explicitMods=[{'description': mod, 'flags': {'crafted': True}}])
    assert lines[-2:] == [
        '{crafted}12% increased Damage',
        '{crafted}Added Small Passive Skills grant: 12% increased Damage',
    ]


def test_multiline_mod_prefixes_every_line():
    """POB tags mods per line, so a multi-line mod needs the prefix on each."""
    mod = '插槽中寶石沒有保留\n你的祝福技能失效'
    lines = pob_lines(explicitMods=[{'description': mod, 'flags': {'fractured': True}}])
    assert lines[-2:] == [
        '{fractured}Socketed Gems have no Reservation',
        '{fractured}Your Blessing Skills are Disabled',
    ]


def test_implicits_counts_lines_not_mods():
    """`Implicits: n` is a line count: a two-line implicit counts as two."""
    lines = pob_lines(
        implicitMods=[{'description': '插槽中寶石沒有保留\n你的祝福技能失效'}],
        explicitMods=[{'description': '+88 最大生命'}],
    )
    assert 'Implicits: 2' in lines
    assert lines[-3:] == [
        'Socketed Gems have no Reservation',
        'Your Blessing Skills are Disabled',
        '+88 to maximum Life',
    ]


def test_league_variant_prefix_is_stripped():
    """Allflame's Foulborn (穢生) prefixes a unique's own name, as Replica does.

    POB knows the unique underneath, not the league variant's composed name.
    """
    lines = pob_lines(frameType=3, name='穢生 無形火炬', typeLine='皇室堅盔')
    assert lines[1] == 'The Formless Flame'


def gem_item(typeLine, level=20, quality=0):
    return {
        'typeLine': typeLine,
        'properties': [
            {'name': '等級', 'values': [[str(level), 0]]},
            {'name': '品質', 'values': [['+{}%'.format(quality), 0]]},
        ],
    }


def test_gem_name_drops_the_support_suffix():
    gem = POBGenerator().Gem(gem_item('三體輔助'))
    assert gem.get('nameSpec') == 'Trinity'


def test_gem_that_kept_its_active_skill_name():
    """自動化輔助 arrives with a suffix its BaseItemTypes row never had."""
    gem = POBGenerator().Gem(gem_item('自動化輔助'))
    assert gem.get('nameSpec') == 'Automation'


def test_gem_level_and_quality():
    gem = POBGenerator().Gem(gem_item('三體輔助', level=21, quality=23))
    assert (gem.get('level'), gem.get('quality')) == ('21', '23')


def test_alternate_quality_gem():
    gem = POBGenerator().Gem(gem_item('異常的 自動化輔助'))
    assert (gem.get('nameSpec'), gem.get('qualityId')) == ('Automation', 'Alternate1')


def test_luminary_is_a_known_class():
    """Scion's third ascendancy, added in 3.29.

    The character API reports it as 'Luminary'; an unknown class used to raise
    KeyError out of export().
    """
    assert CLASS_AND_ASCENDANCY_CLASS_IDS['Luminary'] == (0, 3)
    assert CLASS_MAP['輝耀使徒'] == 'Luminary'
    assert CLASS_AND_ASCENDANCY_CLASS_IDS[CLASS_MAP['輝耀使徒']] == (0, 3)


def test_tree_version_matches_game_data():
    """The exported tree version has to track the data the mods come from.

    A stale version makes POB resolve the node ids against an older tree, which
    silently drops any passive the new league added.  When this fails, check
    that POB ships a tree for the new version before bumping TREE_VERSION.
    """
    import nebuloch
    from pobgen import TREE_VERSION

    major, minor = nebuloch.version.split('.')[:2]
    assert TREE_VERSION == '{}_{}'.format(major, minor)
