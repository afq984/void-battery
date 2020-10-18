import sys
import os.path
from PyPoE.poe.file.file_system import FileSystem
from PyPoE.poe.file import bundle

if bundle.ooz is None:
    bundle.ooz = bundle.ffi.dlopen('ooz/build/liblibooz.so')
if __name__ == '__main__':
    file_system = FileSystem(root_path='Content.ggpk.d/latest')

    for filePath in sys.argv[1:]:
        data = file_system.get_file(filePath)

        desPath = os.path.join('out/extracted', os.path.basename(filePath))
        file = open(desPath, 'wb')
        file.write(data)
        file.close()
