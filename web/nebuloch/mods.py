from __future__ import unicode_literals

import re
import warnings
import itertools
import collections
import json
from decimal import Decimal

from . import datapath, TranslateError


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


FLAGS = {
    'negate': MulFlag(-1),
    'divide_by_one_hundred': DivFlag(100),
    'per_minute_to_per_second': DivFlag(60),
    'per_minute_to_per_second_2dp_if_required': DivFlag(60),
    'per_minute_to_per_second_2dp': DivFlag(60),
    'milliseconds_to_seconds': DivFlag(1000),
    'divide_by_ten_0dp': DivFlag(10),
}

IGNORED_FLAGS = {
    'reminderstring',
    'ReminderTextLifeLeech',
    '2reminderstring',
}

PLACEHOLDER = '#'


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
            if flag not in FLAGS and flag not in IGNORED_FLAGS:
                warnings.warn(flag, UnknownFlag)
            if flag in IGNORED_FLAGS:
                continue
            if idx1 is None:
                continue
            self.flags[int(idx1) - 1].add(flag)

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
            if not prefix:
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
        return all(qualify_range(value, r) for (value, r) in zip(values, self.ranges))

    def apply_flags(self, values):
        updated_values = []
        for value, flags in zip(values, self.flags):
            for flag in flags:
                if flag in FLAGS:
                    value = FLAGS[flag].apply(value)
            updated_values.append(value)
        return updated_values

    def unapply_flags(self, values):
        updated_values = []
        for value, flags in zip(values, self.flags):
            for flag in flags:
                if flag in FLAGS:
                    value = FLAGS[flag].unapply(value)
            updated_values.append(value)
        return updated_values

    def format(self, values):
        assert len(values) == self.value_count, (len(values), self.value_count)
        return self.formatter.format(*self.apply_flags(values))

    def match(self, mod_string):
        match = re.match(self.matcher, mod_string)
        if match is None:
            return match
        values = self.default_values[:]
        for position, matched in zip(self.matcher_positions, match.groups()):
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
        self.index = build_index(source_lang, dest_lang, mods=mods)
        self.passives = build_passives_index()

    def __call__(self, mod):
        return translate(mod, self.index, self.passives)


def build_passives_index():
    with open(datapath('passives.json')) as file:
        return json.load(file)


def build_index(source_lang, dest_lang, mods=None):
    if mods is None:
        mods = load_mods()
    index = collections.defaultdict(list)
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
            index[variant.symbolic].append((variant, target))
    return dict(index)


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


def translate(mod, index, passives):
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
            raise CannotTranslateMod(mod) from None
    for tc, defaults in variants:
        match = tc.match(mod)
        if match is None:
            continue
        if not tc.qualify(match):
            continue
        for default in defaults:
            if default.qualify(match):
                if cluster:
                    return GH_ISSUE3_EN + default.format(match)
                else:
                    return default.format(match)
        warnings.warn(
            'Matched TC {!r} has no corresponding ' 'default translations'.format(tc)
        )
    raise CannotTranslateMod(mod) from None


def debug(mod):
    index = build_index('Traditional Chinese', '')
    print('Translating:', mod)
    query_key = M.sub('#', mod)
    print('Query Key:', query_key)
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
