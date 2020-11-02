import os


def datapath(filename):
    return os.path.join(
        os.path.abspath(os.path.dirname(__file__)), 'data', filename)


with open(datapath('version.txt')) as file:
    version = file.read()
del file


with open(datapath('fingerprint.txt')) as file:
    fingerprint = file.read()
del file


class TranslateError(Exception):
    def __init__(self, input):
        self.input = input

    def __str__(self):
        return repr(self.input)
