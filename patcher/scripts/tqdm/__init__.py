"""Stub tqdm module for Bazel builds (no progress bar)."""


class tqdm:
    def __init__(self, **kwargs):
        pass

    def update(self, n=1):
        pass

    def close(self):
        pass
