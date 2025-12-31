import multiprocessing

# Fix for Python 3.14+ where default start method changed to forkserver
# pytest-flask's LiveServer uses a local function that can't be pickled
# See https://github.com/pytest-dev/pytest-flask/issues/104.
multiprocessing.set_start_method('fork', force=True)
