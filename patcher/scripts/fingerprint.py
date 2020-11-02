import hashlib

import sys

h = hashlib.sha3_256()
for fn in sorted(sys.argv[1:]):
    h.update(b'---')
    with open(fn, 'rb') as f:
        h.update(f.read())


print(h.hexdigest())
