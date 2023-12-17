import json
import collections
import sys


def getjson(name, lang):
    out = []
    with open(f'out/extracted/{name}.{lang}.jsonl', encoding='utf8') as file:
        for line in file:
            out.append(json.loads(line))
    return out


def generate_words():
    data = getjson('Words', 'tc')

    words = {}

    for m in data:
        words[m['Text2'].strip()] = m['Text'].strip()

    write_to_file(words, 'out/release/words.json')


def getnames(fn, lang, fieldname):
    data = getjson(fn, lang)
    return [m[fieldname].strip() for m in data]


def generate_bases():
    z = getnames('BaseItemTypes', 'tc', 'Name')
    e = getnames('BaseItemTypes', 'en', 'Name')
    z.extend(getnames('ActiveSkills', 'tc', 'DisplayedName'))
    e.extend(getnames('ActiveSkills', 'en', 'DisplayedName'))

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
    z = getnames('PassiveSkills', 'tc', 'Name')
    e = getnames('PassiveSkills', 'en', 'Name')
    ze = build_mapping(z, e)
    write_to_file(ze, 'out/release/passives.json')


generate_words()
generate_bases()
generate_passives()
