import json
import zlib
import glob

import pytest

import pobgen


def generate_data():
    for filename in glob.iglob('../failed_samples/*.tracking'):
        with open(filename, 'rb') as file:
            binary = file.read()
        decompressed = zlib.decompress(binary)
        decoded = json.loads(decompressed)
        yield filename, decoded


@pytest.mark.parametrize('filename,data', generate_data())
def test_failed_sample(filename, data):
    pobgen.export(data['items'], data['passive-skills'])
    print(filename)
