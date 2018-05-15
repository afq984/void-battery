"""
ggpkfs: module supporting reading .ggpk files
"""

import posixpath
import os
import mmap
import struct
import builtins
import weakref
import collections


# size vs length naming convension
# size: counting in bytes
# length: counting in number of objects


class cached_property:
    def __init__(self, func):
        self.__doc__ = func.__doc__
        self.func = func

    def __get__(self, obj, cls):
        if obj is None:
            return self
        value = obj.__dict__[self.func.__name__] = self.func(obj)
        return value


def open(filename):
    with builtins.open(filename, 'rb') as file:
        fd = file.fileno()
        size = os.fstat(fd).st_size
        m = mmap.mmap(fd, size, access=mmap.ACCESS_READ)
    return GGPKFilesystem(m, m.close)


class GGPKFilesystem:
    def __init__(self, data, finalizer=None):
        self.data = memoryview(data)
        self.finalizer = finalizer
        self.ggpk_inode = new(weakref.proxy(self), 0)
        self.root, self.free_list = self.ggpk_inode.objects

    def get(self, path):
        parts = [part for part in path.split('/') if part]
        f = self.root
        for i, part in enumerate(parts):
            try:
                f = f.entries[part]
            except KeyError:
                raise Exception(
                    'No such file or directory /{}'.format(
                        '/'.join(parts[:i])))
        return f

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.finalizer is not None:
            self.data = None
            self.finalizer()


class Unpacker:
    """
    Helper class to calculate offset during unpack
    """
    def __init__(self, fs, offset):
        self.fs = fs
        self.offset = offset

    def unpack(self, fmt):
        r = struct.unpack_from(fmt, self.fs.data, self.offset)
        self.offset += struct.calcsize(fmt)
        return r


class Inode:
    """
    Base class of a object in a `GGPKFilesystem`
    """
    def __init__(self, fs, offset, size):
        """
        fs: GGPKFileSystem
        fs.data[offset:offset+size] is where the data is stored
        """
        self.fs = fs
        self.offset = offset
        self.size = size
        self.init_data(Unpacker(fs, offset + _head_struct.size))

    def init_data(self, u: Unpacker):
        pass


class GGPK(Inode):
    def init_data(self, u):
        n_records, = u.unpack('<i')
        if n_records != 2:
            raise Corrupted(
                'The GGPK inode should have exactly 2 records; '
                'it has {n_records} instead')
        offsets = u.unpack('<{}q'.format(n_records))
        self.objects = []
        for offset in offsets:
            self.objects.append(new(self.fs, offset))


class Corrupted(Exception):
    """Either the file is corrupted, or the code is bugged"""


def read_name(u, name_length):
    nameb, nullb = u.unpack('<{}s2s'.format(2 * name_length - 2))
    if nullb != '\0'.encode('utf-16le'):
        raise Corrupted(
            'name null termination check failed (got {!r})'
            .format(nullb))
    return nameb.decode('utf-16le')


class Directory(Inode):
    def __repr__(self):
        return f'<Directory {self.name!r} at {hex(id(self))}>'

    def init_data(self, u):
        (
            name_length,
            self._entries_length,
            self.hash,
        ) = u.unpack('<ii32s')
        self.name = read_name(u, name_length)
        self._entries_offset = u.offset

    @cached_property
    def entries(self):
        u = Unpacker(self.fs, self._entries_offset)
        r = collections.OrderedDict()
        for i in range(self._entries_length):
            dirent = DirectoryEntry(self.fs, *u.unpack('<Iq'))
            r[dirent.name] = dirent
        return r

    def __getitem__(self, key):
        return self.entries[key]


class DirectoryEntry:
    def __init__(self, fs, hash, offset):
        self.fs = fs
        self.hash = hash
        self.offset = offset

    def __repr__(self):
        return (
            '<DirectoryEntry of '
            f'{self.inode.__class__.__name__} {self.name!r}>')

    @cached_property
    def inode(self):
        return new(self.fs, self.offset)

    @property
    def name(self) -> str:
        return self.inode.name

    @property
    def entries(self):
        return self.inode.entries

    @property
    def data(self):
        return self.fs.data[self.inode.data_start:self.inode.data_stop]

    def isdir(self):
        return isinstance(self.inode, Directory)

    def isfile(self):
        return isinstance(self.inode, File)

    def __getitem__(self, key):
        return self.inode[key]


class File(Inode):
    def __repr__(self):
        return f'<File {self.name!r} at {hex(id(self))}>'

    def init_data(self, u):
        (
            name_length,
            self.hash
        ) = u.unpack('<i32s')
        self.name = read_name(u, name_length)
        self.data_start = u.offset
        self.data_stop = self.offset + self.size


class FreeList(Inode):
    ...
    # TODO


_head_struct = struct.Struct('<i4s')
_record_types = {
    b'GGPK': GGPK,
    b'PDIR': Directory,
    b'FILE': File,
    b'FREE': FreeList,
}


def new(fs, offset):
    size, tag = _head_struct.unpack_from(fs.data, offset)
    return _record_types[tag](fs, offset, size)


def extract_recursive(file_or_dir, target_name):
    if file_or_dir.isfile():
        with builtins.open(target_name, 'wb') as file:
            file.write(file_or_dir.data)
        print(target_name)
    else:
        if not os.path.isdir(target_name):
            os.mkdir(target_name)
        print(f'{target_name}/')
        for name, member in file_or_dir.entries.items():
            extract_recursive(member, os.path.join(target_name, name))


class FSCLI:
    def __init__(self, ggpk='Content.ggpk'):
        self.ggpk = ggpk

    def ls(self, directory=''):
        with open(self.ggpk) as ggpk:
            dirent = ggpk.get(directory)
            for name, subent in dirent.entries.items():
                if subent.isdir():
                    suffix = '/'
                else:
                    suffix = ''
                print(subent.name + suffix)

    def extract(self, path, out='.'):
        basename = posixpath.basename(path)
        with open(self.ggpk) as ggpk:
            f = ggpk.get(path)
            if basename == '':
                # The path argument indicates it is a directory
                if not f.isdir():
                    raise SystemExit('{} is not a directory'.format(path))
            else:
                out = os.path.join(out, f.name)
            extract_recursive(f, out)


def main():
    import fire
    fire.Fire(FSCLI)


if __name__ == '__main__':
    main()
