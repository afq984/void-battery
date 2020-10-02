import json
import collections


def generate_words():
    with open('out/extracted/Words.tc.json') as file:
        data = json.load(file)

    words = {}

    for m in data[0]['data']:
        words[m[-2].strip()] = m[1].strip()


    with open('out/release/words.json', 'wt') as file:
        json.dump(words, file, ensure_ascii=False, indent=0, sort_keys=True)


def getnames(fn, fieldname):
    with open(fn) as file:
        data = json.load(file)
    index, = [c['rowid'] for c in data[0]['header'] if c['name'] == fieldname]
    return [m[index].strip() for m in data[0]['data']]


def generate_bases():
    z = getnames('out/extracted/BaseItemTypes.tc.json', 'Name')
    e = getnames('out/extracted/BaseItemTypes.en.json', 'Name')
    z.extend(getnames('out/extracted/ActiveSkills.tc.json', 'DisplayedName'))
    e.extend(getnames('out/extracted/ActiveSkills.en.json', 'DisplayedName'))
    z.extend(getnames('out/extracted/SkillGems.tc.json', 'SupportSkillName'))
    e.extend(getnames('out/extracted/SkillGems.en.json', 'SupportSkillName'))

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
    z = getnames('out/extracted/PassiveSkills.tc.json', 'Name')
    e = getnames('out/extracted/PassiveSkills.en.json', 'Name')
    ze = build_mapping(z, e)
    write_to_file(ze, 'out/release/passives.json')


generate_words()
generate_bases()
generate_passives()
