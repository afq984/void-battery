import requests
import json


data = requests.get('https://www.pathofexile.com/passive-skill-tree', headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}).text
data, _ = data.split(',\n    "groups": {')
_, data = data.split('\n    "classes": ')
data = json.loads(data)

out = {}
for cindex, cdata in enumerate(data, 0):
    out[cdata['name']] = (cindex, 0)
    for aindex, adata in enumerate(cdata['ascendancies'], 1):
        out[adata['name']] = (cindex, aindex)
print(out)

