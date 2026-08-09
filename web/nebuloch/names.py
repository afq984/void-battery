import json

from . import datapath, TranslateError


with open(datapath('bases.json')) as file:
    BASES = json.load(file)


with open(datapath('words.json')) as file:
    WORDS = json.load(file)


NAME_MAP = dict()
NAME_MAP.update(WORDS)
NAME_MAP.update(BASES)


class CannotTranslateName(TranslateError):
    pass


def translate(name):
    name = name.strip()
    try:
        return NAME_MAP[name]
    except KeyError:
        raise CannotTranslateName(name)


# Whether a gem's name carries the support suffix depends on who is spelling
# it.  The character API appends it to every support gem, while a stat line
# that splices a support gem in leaves it to the surrounding template
# ('插槽中的寶石被等級 {0} 的 {1} 輔助').  The game data disagrees with both for
# the gems that used to be active skills -- Automation (自動化), Autoexertion
# (自動竭盡), General's Cry (將軍戰吼) -- whose BaseItemTypes rows kept a bare
# name in either language.
SUPPORT_SUFFIX_TC = '輔助'
SUPPORT_SUFFIX_EN = ' Support'


def translate_gem(name, support=None):
    """Translate a gem name, with or without the localised support suffix.

    Always returns the bare English name, which is what both PoB's `nameSpec`
    and the stat templates that splice a gem in want.

    `support` says whether the caller already knows this is a support gem --
    true when a stat template supplied the suffix itself, so the name arrived
    bare.  It has to be honoured rather than guessed: seventeen gem names read
    as an active skill without the suffix and a different support with it, so
    分裂 alone is Forked while 分裂輔助 is Fork Support.  Trying the bare name
    first for those would name the wrong gem entirely -- 嗜血 is Thirst for
    Blood, but 嗜血輔助 is Bloodlust.
    """
    name = name.strip()
    if support and not name.endswith(SUPPORT_SUFFIX_TC):
        candidates = (name + SUPPORT_SUFFIX_TC, name)
    elif support is False:
        candidates = (name,)
    elif name.endswith(SUPPORT_SUFFIX_TC):
        candidates = (name, name[: -len(SUPPORT_SUFFIX_TC)])
    else:
        candidates = (name, name + SUPPORT_SUFFIX_TC)
    for candidate in candidates:
        try:
            translated = NAME_MAP[candidate]
        except KeyError:
            continue
        if translated.endswith(SUPPORT_SUFFIX_EN):
            return translated[: -len(SUPPORT_SUFFIX_EN)]
        return translated
    raise CannotTranslateName(name)
