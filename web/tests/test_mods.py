# -*- encoding: utf-8 -*-

from __future__ import unicode_literals

import pytest

from nebuloch.mods import CannotTranslateMod, Variant, Translator, M


tr = Translator('Traditional Chinese', '')
rt = Translator('', 'Traditional Chinese')


def test_roundtrip_1():
    v = Variant(
        "While your Passive Skill Tree connects to a class' starting location, you gain:\nMarauder: Melee Skills have %1%%% increased Area of Effect\nDuelist: %2%%% of Attack Damage Leeched as Life\nRanger: %3%%% increased Movement Speed\nShadow: %4$+d%% to Critical Strike Chance\nWitch: %5%%% of maximum Mana Regenerated per second\nTemplar: Damage Penetrates %6%%% Elemental Resistances\nScion: %7$+d to All Attributes",
        ['#'] * 7,
        [],
    )
    assert v.match(v.format([0, 1, 2, 3, 4, 5, 6])) is not None


def test_prev_failed():
    assert (
        tr('每顆暴擊球 +0.3% 暴擊率')
        == '+0.3% to Critical Strike Chance per Power Charge'
    )
    assert tr('增加 15% 地雷傷害') == '15% increased Mine Damage'
    assert (
        tr('0.27% 物理攻擊傷害偷取魔力') == '0.27% of Physical Attack Damage Leeched as Mana'
    )
    assert (
        tr('插槽中寶石被等級 18 的急凍輔助')
        == 'Socketed Gems are Supported by Level 18 Hypothermia'
    )


def test_per_minute_to_per_second_2dp_if_required():
    assert tr('每秒回復 0.47% 生命') == 'Regenerate 0.47% of Life per second'


def test_d_format():
    v = Variant('{:d}% 機率使敵人逃跑', ['1|#'], [])
    assert v.symbolic == '#% 機率使敵人逃跑'
    assert tr('10% 機率使敵人逃跑') == '10% chance to Cause Monsters to Flee'


def test_explicit_sign():
    v = Variant('每個綠色插槽 +{0}% 全域暴擊加成', ['#'], [])
    assert v.symbolic == '每個綠色插槽 #% 全域暴擊加成'
    assert (
        tr('每個綠色插槽 +10% 全域暴擊加成')
        == '+10% to Global Critical Strike Multiplier per Green Socket'
    )


def test_sign_in_constant():
    v = Variant('玩家每 {0} 等級，插槽中的技能寶石等級 +1', ['1|#'], [])
    assert v.symbolic == '玩家每 # 等級，插槽中的技能寶石等級 #'
    assert M.sub('#', '玩家每 25 等級，插槽中的技能寶石等級 +1') == '玩家每 # 等級，插槽中的技能寶石等級 #'
    assert (
        tr('玩家每 25 等級，插槽中的技能寶石等級 +1')
        == '+1 to Level of Socketed Skill Gems per 25 Player Levels'
    )


def test_s1d():
    v = Variant(
        'Chill Enemy for {0:d} seconds when Hit, reducing their Action Speed by 30%',
        ['#'],
        [],
    )
    assert (
        v.formatter
        == 'Chill Enemy for {0:} seconds when Hit, reducing their Action Speed by 30%'
    )
    assert (
        tr('被擊中時冰緩敵人 1 秒，減少 30% 他們的行動速度')
        == 'Chill Enemy for 1 second when Hit, reducing their Action Speed by 30%'
    )
    assert (
        tr('被擊中時冰緩敵人 2 秒，減少 30% 他們的行動速度')
        == 'Chill Enemy for 2 seconds when Hit, reducing their Action Speed by 30%'
    )


def test_range_looks_like_negative():
    assert (
        rt(
            'Attacks with this Weapon deal 80 to 120 added Chaos Damage against\n'
            'Enemies affected by at least 5 Poisons'
        )
        == '使用此武器攻擊至少有 5 層中毒的敵人，附加 80 至 120 混沌傷害'
    )


def test_not_translated():
    return
    # This was fixed
    assert (
        tr(
            'Adds 154 to 209 Fire Damage to Hits with this Weapon against Blinded Enemies'
        )
        == 'Adds 154 to 209 Fire Damage to Hits with this Weapon against Blinded Enemies'
    )


def test_negative_unsigned():
    # This is a fixed translation bug
    assert tr('30% 更少幻化武器時間') == '30% less Animate Weapon Duration'


def test_divide_by_ten_0dp():
    assert (
        tr('若範圍內含 40 點敏捷，冰霜射擊穿透 5 個額外目標')
        == 'With at least 40 Dexterity in Radius, Ice Shot Pierces 5 additional Targets'
    )


def test_float_literal():
    v = Variant('當你使用弓攻擊時觸發插槽中的 1 個法術，有 0.3 秒冷卻時間', ['100|#'], [])
    assert v.symbolic == '當你使用弓攻擊時觸發插槽中的 # 個法術，有 # 秒冷卻時間'
    assert (
        tr('當你使用弓攻擊時觸發插槽中的 1 個法術，有 0.3 秒冷卻時間')
        == 'Trigger a Socketed Spell when you Attack with a Bow, with a 0.3 second Cooldown'
    )


def test_float_literal2():
    v = Variant('近戰暴擊時觸發 1 個插槽中的冰冷法術，有 0.25 秒冷卻時間', ['#'], [])
    assert v.symbolic == '近戰暴擊時觸發 # 個插槽中的冰冷法術，有 # 秒冷卻時間'
    assert (
        tr('近戰暴擊時觸發 1 個插槽中的冰冷法術，有 0.25 秒冷卻時間')
        == 'Trigger a Socketed Cold Spell on Melee Critical Strike, with a 0.25 second Cooldown'
    )


def test_starts_with_plus():
    assert tr('+79 最大生命') == '+79 to maximum Life'


def test_swap():
    v = Variant('one {1:d} zero {0:d}', ['#', '#'], [])
    assert v.symbolic == 'one # zero #'
    assert v.format([0, 1]) == 'one 1 zero 0'


def test_swap_with_const():
    v = Variant('one {1:d} 999 zero {0:d}', ['#', '#'], [])
    assert v.symbolic == 'one # # zero #'
    assert v.format([0, 1]) == 'one 1 999 zero 0'


def test_default_with_const():
    v = Variant('zero {} 999 one {}', ['#', '#'], [])
    assert v.symbolic == 'zero # # one #'
    assert v.format([0, 1]) == 'zero 0 999 one 1'


def test_negative():
    v = Variant('範圍內每 1 點配置敏捷為 {0} 敏捷', ['#', '#'], [])
    assert v.symbolic == '範圍內每 # 點配置敏捷為 # 敏捷'
    assert (
        tr('範圍內每 1 點配置敏捷為 -1 敏捷')
        == '-1 Dexterity per 1 Dexterity on Allocated Passives in Radius'
    )


def test_indexable_skill_name():
    """Dragonfang's Flight rolls a skill name into the line itself.

    The stat description has `全部 {1} 寶石等級 +{0}`, so the rendered mod
    carries a gem name where the matcher expects a number.
    """
    assert tr('全部 電弧 寶石等級 +3') == '+3 to Level of all Arc Gems'
    assert tr('全部 火球 寶石等級 +2') == '+2 to Level of all Fireball Gems'


def test_indexable_unknown_skill_name():
    with pytest.raises(CannotTranslateMod):
        tr('全部 不是技能 寶石等級 +3')


def test_precision_suffixed_flag():
    """`milliseconds_to_seconds_2dp` scales like `milliseconds_to_seconds`.

    Getting this wrong does not merely misformat the number: the unscaled
    value falls outside the variant's range and the mod stops matching.
    """
    assert (
        tr('格擋時觸發 1 個插槽中的元素法術，冷卻時間為 0.25 秒')
        == 'Trigger a Socketed Elemental Spell on Block, with a 0.25 second Cooldown'
    )


def test_resolve_flag_strips_precision_suffixes():
    from nebuloch.mods import FLAGS, resolve_flag

    assert resolve_flag('milliseconds_to_seconds_2dp') is FLAGS['milliseconds_to_seconds']
    assert resolve_flag('per_minute_to_per_second_2dp_if_required') is FLAGS[
        'per_minute_to_per_second'
    ]
    assert resolve_flag('divide_by_ten_0dp') is FLAGS['divide_by_ten']
    assert resolve_flag('not_a_flag') is None


def test_impossible_escape():
    """Reworded in 3.29; the notable's name is looked up in the passive data."""
    assert (
        tr('天賦樹中在範圍祭血術內未連結的天賦仍然可以配置\n通途')
        == 'Passive Skills in Radius of Blood Magic can be Allocated\n'
           'without being connected to your tree\nPassage'
    )


def test_impossible_escape_unknown_notable():
    # Used to raise KeyError, which pobgen turns into a 500 rather than a
    # reported translation failure.
    with pytest.raises(CannotTranslateMod):
        tr('天賦樹中在範圍不是天賦內未連結的天賦仍然可以配置\n通途')


def test_indexable_does_not_swallow_trailing_text():
    with pytest.raises(CannotTranslateMod):
        tr('全部 電弧 寶石等級 +3 還有別的')


def test_non_invertible_flag_is_left_unknown():
    """POB renders this as `round(value / 20) * 2`, which is many-to-one.

    Treating it as a plain ratio would translate the mod to a number that is
    quietly wrong; leaving it unknown fails loudly instead.
    """
    from nebuloch.mods import resolve_flag

    assert resolve_flag('divide_by_twenty_then_double_0dp') is None


@pytest.mark.parametrize(
    'mod, english',
    [
        ('10% 法術傷害格擋率', '10% Chance to Block Spell Damage'),
        ('+10% 壓抑法術傷害率', '+10% chance to Suppress Spell Damage'),
    ],
)
def test_no_decimal_artifacts_from_shared_symbolic_keys(mod, english):
    """A legacy variant sharing this key must not corrupt the ordinary mod.

    Scaling by a fraction that does not terminate in decimal used to render
    these as 9.999999999999999999999999999%.
    """
    assert tr(mod) == english


def test_indexable_support_prefers_the_support_gem():
    """The template supplies 輔助, so 分裂 here is Fork Support, not Forked."""
    assert (
        tr('插槽中的寶石被等級 20 的 分裂 輔助')
        == 'Socketed Gems are Supported by Level 20 Fork'
    )
    assert (
        tr('插槽中的寶石被等級 20 的 嗜血 輔助')
        == 'Socketed Gems are Supported by Level 20 Bloodlust'
    )
