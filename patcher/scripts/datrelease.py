import json


with open('out/extracted/Words.tc.json') as file:
    data = json.load(file)

words = {}

for m in data[0]['data']:
    words[m[-2].strip()] = m[1].strip()


with open('out/release/words.json', 'wt') as file:
    json.dump(words, file, ensure_ascii=False, indent=0, sort_keys=True)


with open('out/extracted/BaseItemTypes.tc.json') as file:
    data = json.load(file)
z = [m[4].strip() for m in data[0]['data']]


with open('out/extracted/BaseItemTypes.en.json') as file:
    data = json.load(file)
e = [m[4].strip() for m in data[0]['data']]

ze = dict(zip(z, e))

with open('out/release/bases.json', 'wt') as file:
    json.dump(ze, file, ensure_ascii=False, indent=0, sort_keys=True)
