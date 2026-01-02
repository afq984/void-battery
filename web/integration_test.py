import base64
import json
import pathlib
import tempfile
import time
import zipfile
import zlib

import lxml.etree
import pytest
from flask import url_for
from selenium.webdriver import Chrome, ChromeOptions
from selenium.webdriver.common.by import By

import main


BASE_DIR = pathlib.Path(__file__).absolute().parent.parent
WEB_DIR = BASE_DIR / 'web'
EXTENSION_DIR = BASE_DIR / 'chrome_extension'

# Hardcoded extension key for consistent extension ID in tests
EXTENSION_KEY = '''
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAhHPs7jp+O7/M8aFGSTUS
hOAnpUhcJUJj7dYRlhLviQxWTKHY/owrIlLnPAtrXGIOVPGr7iNZD7NJt+J2hH3+
NEb/qRwqxGv1RCcApcYPW6lX5vLgkqo/sm1YrnFNjexFKvkpkH3s2a7CqwKbpHnG
vRrthIfDM9/PjBypacYksa6bqLvAb5HAnHQ+QMukRpX5O/XnFw4eOXcHuelmLmMT
/hDifpbrc+vYF0RGMR3l92+GzlnqiJHEIgLK33cehv0MPcAQTPk6K4MBuoRypgIl
k22WERtSA/+hz0f8MXPn/BBkvG9f74lNfl2S5J6y1pW5H02uiclsQ5c/kfhoAxql
eQIDAQAB
'''.replace('\n', '')


def create_zip(dst: pathlib.Path, src: pathlib.Path):
    with zipfile.ZipFile(dst, 'x', compression=zipfile.ZIP_STORED) as z:

        def add_to_zip(path: pathlib.Path, zippath: pathlib.Path):
            if path.is_file():
                if path.name == 'manifest.json':
                    # Inject the hardcoded key into manifest.json
                    manifest = json.loads(path.read_text())
                    manifest['key'] = EXTENSION_KEY
                    z.writestr(str(zippath), json.dumps(manifest, indent=4))
                else:
                    z.write(path, zippath)
            elif path.is_dir():
                for child in path.iterdir():
                    add_to_zip(child, zippath / child.name)

        add_to_zip(src, pathlib.Path('.'))


@pytest.fixture(scope='session')
def extension_zip():
    with tempfile.TemporaryDirectory() as tempdir:
        zipname = pathlib.Path(tempdir) / 'chrome_extension.zip'
        create_zip(zipname, EXTENSION_DIR)
        yield zipname


@pytest.fixture(scope='session')
def chrome(extension_zip):
    opts = ChromeOptions()
    # crbug.com/706008: No support for extensions in headless mode
    opts.add_extension(extension_zip)

    chrome = Chrome(options=opts)
    chrome.implicitly_wait(3)
    try:
        yield chrome
    finally:
        chrome.close()


@pytest.fixture(scope='session')
def app():
    return main.app


@pytest.fixture(scope='function')
def pob_url(live_server):
    return url_for('pob', _external=True)


def submit(chrome: Chrome, pob_url: str, account_name: str, character: str):
    chrome.get(pob_url)

    account_name_input = chrome.find_element(By.ID, 'accountName')
    character_input = chrome.find_element(By.ID, 'character')
    submit_button = chrome.find_element(By.ID, 'fsubmit')

    def pobcode():
        # avoid selenium StaleElementException by using JS
        return chrome.execute_script(
            'return document.getElementById("pobcode").textContent'
        )

    assert pobcode() == ''

    account_name_input.send_keys(account_name)
    character_input.send_keys(character)
    submit_button.click()

    result = pobcode()
    # poll until pobcode.text becomes non-empty
    for i in range(30):
        if result:
            break
        time.sleep(0.1)
        result = pobcode()
    assert result != ''

    return result


def test_is_valid_base64(chrome: Chrome, pob_url: str):
    result = submit(chrome, pob_url, 'afg984#0342', 'GPGPU')

    z = base64.urlsafe_b64decode(result)
    x = zlib.decompress(z)
    t = lxml.etree.fromstring(x)

    assert t.xpath('/PathOfBuilding/Build')
    assert t.xpath('/PathOfBuilding/Build/@level') == ['92']
    assert t.xpath('/PathOfBuilding/Build/@targetVersion')
    assert t.xpath('/PathOfBuilding/Skills')
    assert t.xpath('/PathOfBuilding/Tree')
    assert t.xpath('/PathOfBuilding/Items')


def test_bad_account(chrome: Chrome, pob_url: str):
    result = submit(chrome, pob_url, '--bad--', '--character--')

    assert result == '錯誤：帳號不正確或角色資訊未公開'


def test_bad_character(chrome: Chrome, pob_url: str):
    result = submit(chrome, pob_url, 'afg984#0342', '--bad-character--')

    assert result == '錯誤：角色名稱不正確'
