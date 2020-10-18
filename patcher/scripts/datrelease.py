import json
import collections
import sys


dats = {}
for lang in ['tc', 'en']:
    with open(f'out/extracted/dat.{lang}.json') as file:
        data = json.load(file)
        for section in data:
            dats[section['filename'], lang] = section


def getjson(name, lang):
    return dats[name, lang]


def generate_words():
    data = getjson('Words.dat', 'tc')

    words = {}

    for m in data['data']:
        words[m[-2].strip()] = m[1].strip()

    write_to_file(words, 'out/release/words.json')


def getnames(fn, lang, fieldname):
    data = getjson(fn, lang)
    index, = [c['rowid'] for c in data['header'] if c['name'] == fieldname]
    return [m[index].strip() for m in data['data']]


def generate_bases():
    z = getnames('BaseItemTypes.dat', 'tc', 'Name')
    e = getnames('BaseItemTypes.dat', 'en', 'Name')
    z.extend(getnames('ActiveSkills.dat', 'tc', 'DisplayedName'))
    e.extend(getnames('ActiveSkills.dat', 'en', 'DisplayedName'))
    z.extend(getnames('SkillGems.dat', 'tc', 'SupportSkillName'))
    e.extend(getnames('SkillGems.dat', 'en', 'SupportSkillName'))

    ze = build_mapping(z, e)

    # XXX Overrides
    ze['龍骨細劍'] = 'Dragonbone Rapier'
    ze['鏽劍'] = 'Rusted Sword'
    ze['奉獻'] = 'The Offering'

    write_to_file(ze, 'out/release/bases.json')


def build_mapping(z, e):
    ze = collections.defaultdict(list)
    for k, v in zip(z, e):
        if v and '(NOT CURRENTLY USED)' not in v:
            ze[k].append(v)

    for k, v in ze.items():
        v = set(v)
        if len(v) > 1:
            print(f'WARNING: {k} has multiple mathces: {v}')
    return {k: v[0] for (k, v) in ze.items()}


def write_to_file(ze, filename):
    with open(filename, 'wt') as file:
        json.dump(ze, file, ensure_ascii=False, indent=0, sort_keys=True)


def generate_passives():
    z = getnames('PassiveSkills.dat', 'tc', 'Name')
    e = getnames('PassiveSkills.dat', 'en', 'Name')
    ze = build_mapping(z, e)
    write_to_file(ze, 'out/release/passives.json')


generate_words()
generate_bases()
generate_passives()
