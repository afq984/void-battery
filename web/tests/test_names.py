# -*- encoding: utf-8 -*-

from __future__ import unicode_literals

import pytest

from nebuloch import names


def test_translate():
    assert names.translate('無形火炬') == 'The Formless Flame'


def test_translate_unknown():
    with pytest.raises(names.CannotTranslateName):
        names.translate('這不是一個名字')


def test_gem_keeps_the_bare_english_name():
    assert names.translate_gem('三體輔助') == 'Trinity'


@pytest.mark.parametrize(
    'name, english',
    [
        ('自動化輔助', 'Automation'),
        ('自動竭盡輔助', 'Autoexertion'),
        ('將軍戰吼輔助', "General's Cry"),
    ],
)
def test_gem_that_kept_its_active_skill_name(name, english):
    """These three became supports without their base item being renamed.

    The character API spells them with the support suffix; BaseItemTypes still
    has them without it, in both languages.
    """
    assert names.translate_gem(name) == english


def test_gem_without_the_suffix():
    """Stat lines that splice a support in leave the suffix to the template."""
    assert names.translate_gem('急凍') == 'Hypothermia'


def test_gem_unknown():
    with pytest.raises(names.CannotTranslateName):
        names.translate_gem('這不是一個寶石')


@pytest.mark.parametrize(
    'bare, active_skill, support',
    [
        ('分裂', 'Forked', 'Fork'),
        ('嗜血', 'Thirst for Blood', 'Bloodlust'),
        ('掠奪者', 'Plunder', 'Predator'),
    ],
)
def test_gem_name_collides_with_an_active_skill(bare, active_skill, support):
    """Seventeen names mean one thing bare and another with the suffix.

    A stat template that supplies 輔助 itself hands over the bare name, so
    without the hint these resolve to an unrelated active skill -- and POB has
    no gem by that name at all.
    """
    assert names.translate_gem(bare) == active_skill
    assert names.translate_gem(bare, support=True) == support
    assert names.translate_gem(bare + '輔助') == support


def test_gem_name_known_not_to_be_a_support():
    # display_indexable_skill splices an active skill; adding the suffix could
    # only find the wrong gem.
    assert names.translate_gem('電弧', support=False) == 'Arc'
    with pytest.raises(names.CannotTranslateName):
        names.translate_gem('急凍', support=False)
