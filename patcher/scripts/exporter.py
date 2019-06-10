#!/usr/bin/env python3
import sys
import os
from PyPoE.cli.exporter import util
import tqdm as tqdm_


def tqdm(arg1, *args, **kwargs):
    return arg1


class FileSystemObject:
    def __init__(self, path):
        self.path = path

    def __repr__(self):
        return f'{self.__class__.__name__}({self.path!r})'


class FileSystemNode(FileSystemObject):
    def __getitem__(self, item):
        return FileSystemNode(os.path.join(self.path, item))

    @property
    def record(self):
        return FileSystemRecord(self.path)


class FileSystemRecord(FileSystemObject):
    def extract(self):
        with open(self.path, 'rb') as file:
            return file.read()


def get_content_ggpk(path=None):
    return FileSystemNode('Content.ggpk.d/latest')


util.get_content_ggpk = get_content_ggpk
tqdm_.tqdm = tqdm


if __name__ == '__main__':
    from PyPoE.cli.exporter.core import main
    main()
