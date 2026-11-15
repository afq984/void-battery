# -*- encoding: utf-8 -*-
"""Unit tests for 3.30 stat description syntax (ranges and multi-number flags)."""

import os
import tempfile
import unittest

from statparse import getTextType, parse_stat_files, TokenType


def write_csd(text):
    fd, path = tempfile.mkstemp(suffix='.csd')
    os.close(fd)
    with open(path, 'w', encoding='utf-16') as file:
        file.write(text)
    return path


class GetTextTypeTest(unittest.TestCase):
    def test_existing_ranges(self):
        self.assertEqual(getTextType('#'), TokenType.Range)
        self.assertEqual(getTextType('1|#'), TokenType.Range)
        self.assertEqual(getTextType('1|99'), TokenType.Range)
        self.assertEqual(getTextType('100|#'), TokenType.Range)
        self.assertEqual(getTextType('12'), TokenType.Number)

    def test_hash_suffixed_bounds(self):
        self.assertEqual(getTextType('99#'), TokenType.Range)
        self.assertEqual(getTextType('1|99#'), TokenType.Range)
        self.assertEqual(getTextType('1|100#'), TokenType.Range)


class ParseStatFilesTest(unittest.TestCase):
    def tearDown(self):
        for path in getattr(self, '_tmps', []):
            try:
                os.remove(path)
            except OSError:
                pass

    def _csd(self, text):
        path = write_csd(text)
        self._tmps = getattr(self, '_tmps', []) + [path]
        return path

    def test_multi_number_flags(self):
        path = self._csd(
            'description\n'
            '\t4 local_unique_jewel_alternate_tree_version '
            'local_unique_jewel_alternate_tree_seed '
            'local_unique_jewel_alternate_tree_keystone '
            'local_unique_jewel_alternate_tree_internal_revision\n'
            '\t1\n'
            '\t\t1 # # # "Bathed in the blood of {1} sacrificed in the name of {2}\\n'
            'Passives in radius are Conquered by the {0}" '
            'alternate_tree_version_name 1 '
            'alternate_tree_version_keystone 3 1 4 '
            'reminderstring ReminderTextConqueredPassives\n'
        )
        parsed = parse_stat_files([path], lang_whitelist={'', 'Traditional Chinese'})
        self.assertEqual(len(parsed), 1)
        variant = parsed[0]['langs'][''][0]
        flags = {name: value for name, value in variant['flags']}
        self.assertEqual(flags['alternate_tree_version_name'], 1)
        self.assertEqual(flags['alternate_tree_version_keystone'], [3, 1, 4])
        self.assertEqual(flags['reminderstring'], 'ReminderTextConqueredPassives')
        self.assertEqual(variant['ranges'], ['1', '#', '#', '#'])

    def test_hash_suffixed_range_tokens(self):
        path = self._csd(
            'description\n'
            '\t1 chance_to_gain_arohonguis_embrace_%_on_kill\n'
            '\t2\n'
            '\t\t1|99# "{0}% chance to Trigger Foo on Kill"\n'
            '\t\t100|# "Trigger Foo on Kill"\n'
        )
        parsed = parse_stat_files([path], lang_whitelist={'', 'Traditional Chinese'})
        self.assertEqual(len(parsed), 1)
        variants = parsed[0]['langs']['']
        self.assertEqual(variants[0]['ranges'], ['1|99#'])
        self.assertEqual(
            variants[0]['source'], '{0}% chance to Trigger Foo on Kill'
        )
        self.assertEqual(variants[1]['ranges'], ['100|#'])
        self.assertEqual(variants[1]['source'], 'Trigger Foo on Kill')


if __name__ == '__main__':
    unittest.main()
