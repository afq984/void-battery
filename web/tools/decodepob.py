import subprocess
import zlib
import base64

import lxml.etree


print(lxml.etree.tounicode(lxml.etree.fromstring(zlib.decompress(base64.urlsafe_b64decode(subprocess.check_output(['xclip', '-clipboard', '-out'])))), pretty_print=True))
