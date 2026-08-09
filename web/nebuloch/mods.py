from __future__ import unicode_literals

import re
import warnings
import itertools
import collections
import json
from decimal import Decimal

from . import datapath, TranslateError, names


R = re.compile(r'(?:(\+?){([^}]*)})|((?<!\d)[+-]?\d+(?:\.\d+)?)')
M = re.compile(r'((?<!\d)[+-]?\d+(?:\.\d+)?)')


class MulFlag:
    def __init__(self, mul):
        self.mul = mul

    def apply(self, value):
        return value * self.mul

    def unapply(self, value):
        return value / self.mul


class DivFlag:
    def __init__(self, div):
        self.div = div

    def apply(self, value):
        return value / self.div

    def unapply(self, value):
        return value * self.div


class UnknownFlag(UserWarning):
    pass


class NoMatchingTranslation(UserWarning):
    pass


# How the game scales a stat's raw value before showing it.  Reading a mod
# back the other way undoes this, and the undone value is what the variant's
# ranges are expressed in -- so a missing entry does not merely misformat a
# number, it makes the mod fail to match its own translation.
FLAGS = {
    'negate': MulFlag(-1),
    'double': MulFlag(2),
    'negate_and_double': MulFlag(-2),
    'times_twenty': MulFlag(20),
    'divide_by_two': DivFlag(2),
    'divide_by_three': DivFlag(3),
    'divide_by_four': DivFlag(4),
    'divide_by_five': DivFlag(5),
    'divide_by_six': DivFlag(6),
    'divide_by_ten': DivFlag(10),
    'divide_by_twelve': DivFlag(12),
    'divide_by_fifteen': DivFlag(15),
    'divide_by_twenty': DivFlag(20),
    'divide_by_one_hundred': DivFlag(100),
    'divide_by_one_thousand': DivFlag(1000),
    'deciseconds_to_seconds': DivFlag(10),
    'milliseconds_to_seconds': DivFlag(1000),
    'per_minute_to_per_second': DivFlag(60),
}

# Deliberately absent, because only transforms that round-trip exactly belong
# here.  A mod is read by undoing the source variant's scaling and re-applying
# the target's, and variants that merely share a symbolic key get tried too --
# so an inexact transform corrupts unrelated mods, not just its own:
#
#   divide_by_twenty_then_double_0dp  POB renders `round(value / 20) * 2`
#                                     (StatDescriber.lua), which is many-to-one.
#   times_one_point_five,             Non-terminating in decimal: undoing and
#   30%_of_value, 60%_of_value        redoing 10 yields 9.999...9, which leaked
#                                     into ordinary Block and Suppression mods.
#
# Left unknown, a mod that needs one of these fails loudly instead of
# translating to a number that is quietly wrong.

# These suffixes only say how many decimal places to print, so a flag ending
# in one scales exactly like the flag without it.  Resolving them this way
# covers the whole family -- milliseconds_to_seconds_2dp and friends -- rather
# than waiting for each spelling to show up as an untranslatable mod.
PRECISION_SUFFIXES = ('_if_required', '_0dp', '_1dp', '_2dp', '_3dp', '_4dp')


def resolve_flag(flag):
    """The value transform a flag applies, or None if it does not scale."""
    while flag not in FLAGS:
        for suffix in PRECISION_SUFFIXES:
            if flag.endswith(suffix):
                flag = flag[: -len(suffix)]
                break
        else:
            return None
    return FLAGS[flag]

# These mark a placeholder that the game fills with a gem name rather than a
# number -- Dragonfang's Flight's "+3 to Level of all Arc Gems", or a Pearl
# Ring's random support.  The rendered line therefore carries a name where the
# stat description has `{1}`, which the numeric matcher cannot recover, so
# those placeholders are matched as text instead.  See Variant.indexable.
INDEXABLE_FLAGS = frozenset(
    (
        'display_indexable_skill',
        'display_indexable_support',
        'display_indexable_non_active_support',
    )
)

# Of those, the ones whose template supplies the support suffix itself, so the
# spliced-in name arrives without it.  Which of the two it is decides how the
# name resolves -- see nebuloch.names.translate_gem.
INDEXABLE_SUPPORT_FLAGS = frozenset(
    ('display_indexable_support', 'display_indexable_non_active_support')
)

IGNORED_FLAGS = {
    'reminderstring',
    'ReminderTextLifeLeech',
    '2reminderstring',
}

PLACEHOLDER = '#'

TRADITIONAL_CHINESE = 'Traditional Chinese'


class ConfigurationError(Exception):
    pass


def qualify_range(value, r):
    if r.startswith('!'):
        assert '|' not in r
        return value != int(r[1:])
    low, sep, up = r.partition('|')
    if not sep:
        if low == '#':
            return True
        return value == int(low)
    if low != '#':
        if int(low) > value:
            return False
    if up != '#':
        if int(up) < value:
            return False
    return True


def range_default_value(r):
    if r.startswith('!'):
        assert '|' not in r
        return int(r[1:]) + 1
    low, sep, up = r.partition('|')
    if low != '#':
        return int(low)
    if up and up != '#':
        return int(up)
    return 1


def fix_source(source):
    if '%d%' not in source:
        return source
    splitted = source.split('%d%')
    return splitted[0] + ''.join(
        '%{}%{}'.format(*spec) for spec in enumerate(splitted[1:], 1)
    )


class Variant:
    def __init__(self, source, ranges, flags):
        source = fix_source(source)

        self.source = source
        self.symbolic = R.sub('#', source)

        self.ranges = ranges
        self.default_values = [range_default_value(r) for r in ranges]
        self.value_count = len(self.ranges)

        self.flags = [set() for r in ranges]
        for flag, idx1 in flags:
            if (
                resolve_flag(flag) is None
                and flag not in IGNORED_FLAGS
                and flag not in INDEXABLE_FLAGS
            ):
                warnings.warn(flag, UnknownFlag)
            if flag in IGNORED_FLAGS:
                continue
            if idx1 is None:
                continue
            self.flags[int(idx1) - 1].add(flag)

        self.indexable = frozenset(
            position
            for position, flags in enumerate(self.flags)
            if flags & INDEXABLE_FLAGS
        )

        self.formatter = R.sub(repl_formatter, source)

        matcher_string_first, *matcher_string_others = map(
            re.escape, R.split(source)[::4]
        )
        matcher_regex_parts = []
        self.matcher_positions = matcher_positions = []

        for match in R.finditer(source):
            prefix, format_spec, const = match.groups()

            if const is not None:
                matcher_regex_parts.append(re.escape(const))
                continue

            pos, col, options = format_spec.partition(':')
            if pos != '' and int(pos) in self.indexable:
                # A gem name, not a number.  Non-greedy so the literal text
                # that follows still anchors the match.
                matcher_regex_parts.append(r'(.+?)')
            elif not prefix:
                if '+' in options:
                    matcher_regex_parts.append(r'([+-]\d+(?:\.\d+)?)')
                else:
                    matcher_regex_parts.append(r'(\-?\d+(?:\.\d+)?)')
            else:
                assert '+' not in options, (options, source)
                matcher_regex_parts.append(
                    r'(' + re.escape(prefix) + r'\-?\d+(?:\.\d+)?)'
                )

            if pos == '':
                matcher_positions.append(None)
            else:
                matcher_positions.append(int(pos))

        if all(p is None for p in matcher_positions):
            matcher_positions[:] = range(len(matcher_positions))
        else:
            assert all(p is not None for p in matcher_positions), source

        assert len(matcher_regex_parts) == len(matcher_string_others)
        assert all(pos < self.value_count for pos in matcher_positions), (
            source,
            self.value_count,
        )
        self.matcher = matcher_string_first + ''.join(
            itertools.chain.from_iterable(
                zip(matcher_regex_parts, matcher_string_others)
            )
        )

    def __str__(self):
        return '{} {} {}'.format(
            ' '.join(self.ranges),
            json.dumps(self.source, ensure_ascii=False),
            self.flags,
        )

    def __repr__(self):
        return '<Variant {}>'.format(self)

    def qualify(self, values):
        return all(
            position in self.indexable or qualify_range(value, r)
            for position, (value, r) in enumerate(zip(values, self.ranges))
        )

    def apply_flags(self, values):
        updated_values = []
        for value, flags in zip(values, self.flags):
            for flag in flags:
                transform = resolve_flag(flag)
                if transform is not None:
                    value = transform.apply(value)
            updated_values.append(value)
        return updated_values

    def unapply_flags(self, values):
        updated_values = []
        for value, flags in zip(values, self.flags):
            for flag in flags:
                transform = resolve_flag(flag)
                if transform is not None:
                    value = transform.unapply(value)
            updated_values.append(value)
        return updated_values

    def format(self, values):
        assert len(values) == self.value_count, (len(values), self.value_count)
        return self.formatter.format(*self.apply_flags(values))

    def match(self, mod_string, anchored=False):
        # `anchored` matters where a placeholder matches free text: without it
        # `全部 電弧 寶石等級 +3 junk` would translate as though the junk were
        # not there.  The numeric matchers are reached through an exact index
        # key, so they do not need it.
        match = re.match(self.matcher + (r'\Z' if anchored else ''), mod_string)
        if match is None:
            return match
        values = self.default_values[:]
        for position, matched in zip(self.matcher_positions, match.groups()):
            if position in self.indexable:
                values[position] = matched
            else:
                values[position] = Decimal(matched)
        return self.unapply_flags(values)


def repl_formatter(match):
    prefix, format_spec, const = match.groups()
    if const:
        return const
    pos, col, options = format_spec.partition(':')
    if '+' in format_spec:
        py_format_spec = '+'
    else:
        py_format_spec = ''
    return f'{prefix}{{{pos}:{py_format_spec}}}'


class Translator:
    def __init__(self, source_lang, dest_lang, mods=None):
        self.index, indexable = build_index(source_lang, dest_lang, mods=mods)
        # Resolving a spliced-in gem name goes through the Traditional Chinese
        # name tables, so the fallback only means anything in that direction.
        self.indexable = indexable if source_lang == TRADITIONAL_CHINESE else []
        self.passives = build_passives_index()

    def __call__(self, mod):
        return translate(mod, self.index, self.passives, self.indexable)


def build_passives_index():
    with open(datapath('passives.json')) as file:
        return json.load(file)


def build_index(source_lang, dest_lang, mods=None):
    """Index source variants by their symbolic form.

    Returns the lookup table plus the variants whose text contains a spliced-in
    gem name.  Those cannot be keyed by symbolic form -- the name survives
    symbolisation, so the rendered line never matches the template -- and are
    tried one by one when the lookup misses.
    """
    if mods is None:
        mods = load_mods()
    index = collections.defaultdict(list)
    indexable = []
    for mod in mods:
        keys = mod['keys']
        if dest_lang not in mod['langs']:
            warnings.warn(
                f'{keys} does not have a {dest_lang!r} translation',
                NoMatchingTranslation,
            )
            continue
        raw_target_variants = mod['langs'][dest_lang]
        if source_lang not in mod['langs']:
            warnings.warn(
                f'{keys} does not have a {source_lang!r} translation',
                NoMatchingTranslation,
            )
            raw_source_variants = mod['langs'][dest_lang]
        else:
            raw_source_variants = mod['langs'][source_lang]
        target = [Variant(**v) for v in raw_target_variants]
        for raw_variant in raw_source_variants:
            variant = Variant(**raw_variant)
            if variant.indexable:
                indexable.append((variant, target))
            else:
                index[variant.symbolic].append((variant, target))
    return dict(index), indexable


class CannotTranslateMod(TranslateError):
    pass


def load_mods():
    with open(datapath('stat_descriptions.json')) as file:
        return json.load(file)


_ALLOCATES_TC = '配置 '


# Not all mods that starts with `GH_ISSUE3_TC`
# has a corresponding entry in stats_descriptions.json (at least for now)
# https://github.com/afq984/void-battery/issues/3
# https://github.com/Kyusung4698/PoE-Overlay/issues/324
GH_ISSUE3_TC = '附加的小型天賦給予：'
GH_ISSUE3_EN = 'Added Small Passive Skills grant: '
FORBIDDEN_GEM_RE = re.compile('(若禁忌..上有符合的詞綴，配置 )(.*)')
# Reworded in 3.29; it used to read `範圍 X 內的天賦可以在沒有連結你的天賦樹下被配置`.
IMPOSSIBLE_ESCAPE_RE = re.compile(
    '(天賦樹中在範圍)(.+?)(內未連結的天賦仍然可以配置\n通途)'
)

def translate(mod, index, passives, indexable=()):
    if FORBIDDEN_GEM_RE.match(mod) is not None:
        return translateForbiddenGem(mod, index, passives)
    if IMPOSSIBLE_ESCAPE_RE.match(mod) is not None:
        return translateImpossibleEscape(mod, index, passives)
    if mod.startswith(_ALLOCATES_TC):
        try:
            return 'Allocates ' + passives[mod[len(_ALLOCATES_TC) :].strip()]
        except KeyError:
            raise CannotTranslateMod(mod) from None

    query_key = M.sub('#', mod)
    cluster = False
    try:
        variants = index[query_key]
    except KeyError:
        if query_key.startswith(GH_ISSUE3_TC):
            cluster = True
            query_key = query_key[len(GH_ISSUE3_TC) :]
            mod = mod[len(GH_ISSUE3_TC) :]
            try:
                variants = index[query_key]
            except KeyError:
                raise CannotTranslateMod(mod) from None
        else:
            variants = ()
    translated = translate_variants(mod, variants)
    if translated is None:
        translated = translate_indexable(mod, indexable)
    if translated is None:
        raise CannotTranslateMod(mod) from None
    if cluster:
        return GH_ISSUE3_EN + translated
    return translated


def translate_variants(mod, variants):
    for tc, defaults in variants:
        match = tc.match(mod)
        if match is None:
            continue
        if not tc.qualify(match):
            continue
        for default in defaults:
            if default.qualify(match):
                return default.format(match)
        warnings.warn(
            'Matched TC {!r} has no corresponding ' 'default translations'.format(tc)
        )
    return None


def translate_indexable(mod, indexable):
    """Translate a line that splices a gem name in where a number would go.

    There are only a handful of these, so trying each in turn costs nothing.
    """
    for tc, defaults in indexable:
        match = tc.match(mod, anchored=True)
        if match is None or not tc.qualify(match):
            continue
        try:
            values = [
                names.translate_gem(
                    value, support=bool(tc.flags[position] & INDEXABLE_SUPPORT_FLAGS)
                )
                if position in tc.indexable
                else value
                for position, value in enumerate(match)
            ]
        except TranslateError:
            continue
        for default in defaults:
            if default.qualify(values):
                return default.format(values)
    return None


def translateForbiddenGem(mod, index, passives):
    passive = FORBIDDEN_GEM_RE.match(mod).group(2)
    if passive is None:
        raise CannotTranslateMod(mod) from None
    query_key = FORBIDDEN_GEM_RE.sub(r'\g<1>#', mod)
    return substitute_passive(mod, index, passives, query_key, passive)


def translateImpossibleEscape(mod, index, passives):
    passive = IMPOSSIBLE_ESCAPE_RE.match(mod).group(2)
    if passive is None:
        raise CannotTranslateMod(mod)
    query_key = IMPOSSIBLE_ESCAPE_RE.sub(r'\g<1>#\g<3>', mod)
    return substitute_passive(mod, index, passives, query_key, passive)


def substitute_passive(mod, index, passives, query_key, passive):
    """Render a mod whose only placeholder is a passive skill's name."""
    try:
        variants = index[query_key]
    except KeyError:
        raise CannotTranslateMod(mod) from None
    try:
        name = passives[passive]
    except KeyError:
        # An unknown notable is a translation failure, not a crash: pobgen
        # reports the former and turns the latter into a 500.
        raise CannotTranslateMod(mod) from None
    _, defaults = variants[0]
    return defaults[0].symbolic.replace('#', name)


def debug(mod):
    index, indexable = build_index('Traditional Chinese', '')
    print('Translating:', mod)
    query_key = M.sub('#', mod)
    print('Query Key:', query_key)
    if query_key not in index:
        print('Not indexed; indexable fallback:', translate_indexable(mod, indexable))
        return
    variants = index[query_key]
    for tc, defaults in variants:
        match = tc.match(mod)
        if match is None:
            print('TC not match:', tc)
            continue
        print('TC match:', tc)
        print('Values:', match)
        if not tc.qualify(match):
            print('Match not qualified')
            continue
        print('Match qualified')
        for default in defaults:
            if not default.qualify(match):
                print('Not qualify:', default)
                continue
            print('Qualified:', default)
            print('Translated:', default.format(match))


def main():
    import sys

    debug(sys.argv[1])


if __name__ == '__main__':
    main()
