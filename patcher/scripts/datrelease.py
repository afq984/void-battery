import json
import collections
import sys
import argparse
import os


def getjson(input_dir, name, lang):
    out = []
    with open(os.path.join(input_dir, f'{name}.{lang}.jsonl'), encoding='utf8') as file:
        for line in file:
            out.append(json.loads(line))
    return out


def generate_words(input_dir, output_dir):
    data = getjson(input_dir, 'Words', 'tc')

    words = {}

    for m in data:
        words[m['Text2'].strip()] = m['Text'].strip()

    write_to_file(words, os.path.join(output_dir, 'words.json'))


def getnames(input_dir, fn, lang, fieldname):
    data = getjson(input_dir, fn, lang)
    return [m[fieldname].strip() for m in data]


def generate_bases(input_dir, output_dir):
    z = getnames(input_dir, 'BaseItemTypes', 'tc', 'Name')
    e = getnames(input_dir, 'BaseItemTypes', 'en', 'Name')
    z.extend(getnames(input_dir, 'ActiveSkills', 'tc', 'DisplayedName'))
    e.extend(getnames(input_dir, 'ActiveSkills', 'en', 'DisplayedName'))

    ze = build_mapping(z, e)

    # XXX Overrides
    ze['龍骨細劍'] = 'Dragonbone Rapier'
    ze['鏽劍'] = 'Rusted Sword'
    ze['奉獻'] = 'The Offering'

    write_to_file(ze, os.path.join(output_dir, 'bases.json'))


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


def generate_passives(input_dir, output_dir):
    z = getnames(input_dir, 'PassiveSkills', 'tc', 'Name')
    e = getnames(input_dir, 'PassiveSkills', 'en', 'Name')
    ze = build_mapping(z, e)
    write_to_file(ze, os.path.join(output_dir, 'passives.json'))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input-dir', default='out/extracted')
    parser.add_argument('--output-dir', default='out/release')
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)

    generate_words(args.input_dir, args.output_dir)
    generate_bases(args.input_dir, args.output_dir)
    generate_passives(args.input_dir, args.output_dir)


if __name__ == '__main__':
    main()
