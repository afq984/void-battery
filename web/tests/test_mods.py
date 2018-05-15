# -*- encoding: utf-8 -*-

from __future__ import unicode_literals

from nebuloch.mods import Variant, Translator


tr = Translator('Traditional Chinese', '')
rt = Translator('', 'Traditional Chinese')


def test_roundtrip_1():
    v = Variant(
        "While your Passive Skill Tree connects to a class' starting location, you gain:\nMarauder: Melee Skills have %1%%% increased Area of Effect\nDuelist: %2%%% of Attack Damage Leeched as Life\nRanger: %3%%% increased Movement Speed\nShadow: %4$+d%% to Critical Strike Chance\nWitch: %5%%% of maximum Mana Regenerated per second\nTemplar: Damage Penetrates %6%%% Elemental Resistances\nScion: %7$+d to All Attributes",
        ['#'] * 7,
        []
    )
    assert v.match(v.format([0, 1, 2, 3, 4, 5, 6])) is not None


def test_prev_failed():
    assert tr('每顆暴擊球 +0.3% 暴擊率') == '+0.3% Critical Strike Chance per Power Charge'
    assert tr('增加 15% 地雷傷害') == '15% increased Mine Damage'
    assert tr('每個耐力球增加 0.4% 每秒最大生命回復') == '0.4% of maximum Life Regenerated per second per Endurance Charge'
    assert tr('0.27% 所造成的物理攻擊傷害偷取魔力') == '0.27% of Physical Attack Damage Leeched as Mana'
    assert tr('此物品插槽中寶石由等級 18 的急凍輔助') == 'Socketed Gems are Supported by Level 18 Hypothermia'


def test_per_minute_to_per_second_2dp_if_required():
    assert tr('每秒回復 0.47% 生命') == '0.47% of Life Regenerated per second'


def test_d_format():
    assert tr('10% 機率使敵人逃跑') == '10% chance to Cause Monsters to Flee'


def test_explicit_sign():
    assert tr('每個綠色插槽 +10% 全域暴擊加成') == '+10% to Global Critical Strike Multiplier per Green Socket'


def test_sign_in_constant():
    assert tr('每 25 等角色等級使插槽的主動技能寶石等級 +1') == '+1 to Level of Socketed Active Skill Gems per 25 Player Levels'


def test_s1d():
    v = Variant('Chill Enemy for %1$d second when Hit, slowing them by 30%%', ['#'], [])
    assert v.formatter == 'Chill Enemy for {0:} second when Hit, slowing them by 30%'
    assert tr('擊中時冰緩敵人 1 秒，緩速敵人 30%') == 'Chill Enemy for 1 second when Hit, slowing them by 30%'
    assert tr('擊中時冰緩敵人 2 秒，緩速敵人 30%') == 'Chill Enemy for 2 seconds when Hit, slowing them by 30%'


def test_range_looks_like_negative():
    assert rt(
        'Attacks with this Weapon deal 80-120 added Chaos Damage against\n'
        'Enemies affected by at least 5 Poisons') == '使用此武器攻擊中毒 5 層以上的敵人\n附加 80 至 120 混沌傷害'


def test_not_translated():
    return
    # This was fixed
    assert tr('Adds 154 to 209 Fire Damage to Hits with this Weapon against Blinded Enemies') == 'Adds 154 to 209 Fire Damage to Hits with this Weapon against Blinded Enemies'


def test_negative_unsigned():
    # This is a fixed translation bug
    assert tr('30% 較少幻化武器時間') == '30% less Animate Weapon Duration'


def test_divide_by_ten_0dp():
    assert tr('若範圍內含 40 點敏捷，冰霜射擊穿透 5 個額外目標') == 'With at least 40 Dexterity in Radius, Ice Shot Pierces 5 additional Targets'
