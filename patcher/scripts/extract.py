import sys
import os.path
from PyPoE.poe.file.file_system import FileSystem

if __name__ == '__main__':
    file_system = FileSystem(root_path='Content.ggpk.d/latest')

    for filePath in sys.argv[1:]:
        try:
            data = file_system.get_file(filePath)
        except FileNotFoundError:
            print('%s not exist' % filePath)
            continue

        desPath = os.path.join('out/release', os.path.basename(filePath))
        file = open(desPath, 'wb')
        file.write(data)
        file.close()
