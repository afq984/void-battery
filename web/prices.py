# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import json
from jinja2 import Template
from fractions import Fraction
from decimal import Decimal
import collections


Groups = [
    ('Currency', '通貨'),
    ('DivinationCard', '命運卡'),
    ('Essence', '精髓'),
    ('Fossil', '化石'),
    ('Fragment', '碎片'),
    ('Map', '地圖'),
    ('Prophecy', '預言'),
    ('Resonator', '鑄新儀'),
    ('UniqueAccessory', '傳奇飾品'),
    ('UniqueArmour', '傳奇防具'),
    ('UniqueFlask', '傳奇藥劑'),
    ('UniqueJewel', '傳奇珠寶'),
    ('UniquePiece', '傳奇碎片'),
    ('UniqueWeapon', '傳奇武器'),
]


def rate_samples(num_samples):
    if num_samples < 8:
        return '很少'
    if num_samples < 32:
        return '少'
    if num_samples < 100:
        return '普通'
    return '充足'


def handleGroup(group, info, is_user_stash=False):
    info.sort(key=lambda i: (-i['value'], -i['samples']))


def getPriceGroups(jsond):
    generated = jsond['generated']
    priceData = jsond['data']
    exaltedPrice = None
    priceGroups = collections.defaultdict(list)

    for discriminator, priceInfo in priceData.items():
        if priceInfo['chaosPrice'] is None:
            print(priceInfo['name'], 'has no price')
            continue
        priceGroups[priceInfo['group']].append(priceInfo)
        if priceInfo['name'] == '崇高石':
            exaltedPrice = Fraction(priceInfo['chaosPrice'])


    for discriminator, p in priceData.items():
        c = Fraction(p['chaosPrice'])
        if c >= exaltedPrice and p['name'] != '崇高石':
            q = c / exaltedPrice
            u = 'exa'
        else:
            q = c
            u = 'chaos'
        if q.denominator == 1:
            q = q.numerator
        elif q.denominator < q.numerator:
            q = round(Decimal(q.numerator) / Decimal(q.denominator), 1)
        elif q.denominator > 100 and q.numerator > 1:
            q = q.limit_denominator(100)
        p['value'] = c
        p['price'] = q
        p['unit'] = u
        p['rated_samples'] = rate_samples(p['samples'])


    for group, info in priceGroups.items():
        handleGroup(group, info)

    return priceGroups, exaltedPrice, generated
