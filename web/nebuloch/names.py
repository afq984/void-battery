import json

from . import datapath


with open(datapath('bases.json')) as file:
    BASES = json.load(file)


with open(datapath('words.json')) as file:
    WORDS = json.load(file)


NAME_MAP = dict()
NAME_MAP.update(WORDS)
NAME_MAP.update(BASES)


class CannotTranslateName(Exception):
    pass


def translate(name):
    name = name.strip()
    try:
        return NAME_MAP[name]
    except KeyError:
        raise CannotTranslateName(name)
