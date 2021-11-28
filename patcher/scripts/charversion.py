import sys
import os
import re
import mmap
import collections


c = collections.Counter()
for exe in sys.argv[1:]:
    with open(exe, 'rb') as file:
        with mmap.mmap(file.fileno(), 0, access=mmap.ACCESS_READ) as ma:
            fa = [b.decode() for b in re.findall(rb'tags/(\d+\.\d+\.\d+\w?)', ma)]
            print(exe, fa, file=sys.stderr)
            c.update(fa)
print(c.most_common(1)[0][0])
