#!/usr/bin/env python3
import sys
import os
from PyPoE.cli.exporter import util, config
from PyPoE.poe.file import bundle
import tqdm as tqdm_


def tqdm(arg1, *args, **kwargs):
    return arg1


old_add_option = config.add_option


def add_option(name, *args):
    if name == 'language':
        old_add_option('language', 'option("English", "Traditional Chinese", default="English")')
    else:
        old_add_option(name, *args)


config.add_option = add_option


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
            
def get_content_path():
    return "Content.ggpk.d/latest"

util.get_content_path = get_content_path
tqdm_.tqdm = tqdm


if bundle.ooz is None:
    bundle.ooz = bundle.ffi.dlopen('ooz/build/liblibooz.so')


if __name__ == '__main__':
    from PyPoE.cli.exporter.core import main
    main()
