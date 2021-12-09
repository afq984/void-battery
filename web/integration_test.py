import base64
import contextlib
import os
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
EXTENSION_NAME = 'Path of Building Exporter'


def create_zip(dst: pathlib.Path, src: pathlib.Path):
    with zipfile.ZipFile(dst, 'x', compression=zipfile.ZIP_STORED) as z:

        def add_to_zip(path: pathlib.Path, zippath: pathlib.Path):
            if path.is_file():
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
def app(chrome: Chrome):
    # HACK: override app extension ID
    main.EXTENSION_ID = get_chrome_extension_id(chrome)
    return main.app


@pytest.fixture(scope='function')
def pob_url(live_server):
    return url_for('pob', _external=True)


def get_chrome_extension_id(chrome: Chrome):
    chrome.get('chrome://extensions')
    extensions = chrome.execute_script('return await chrome.management.getAll()')
    for extension in extensions:
        if extension['name'] == EXTENSION_NAME:
            return extension['id']


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
    result = submit(chrome, pob_url, 'afg984', 'GPGPU')

    z = base64.urlsafe_b64decode(result)
    x = zlib.decompress(z)
    t = lxml.etree.fromstring(x)

    assert t.xpath('/PathOfBuilding/Build')
    assert t.xpath('/PathOfBuilding/Build/@level') == ['92']
    assert t.xpath('/PathOfBuilding/Build/@targetVersion')
    assert t.xpath('/PathOfBuilding/Skills')
    assert t.xpath('/PathOfBuilding/Tree')
    assert t.xpath('/PathOfBuilding/Items')


def test_bad_character(chrome: Chrome, pob_url: str):
    result = submit(chrome, pob_url, '--bad--', '--character--')

    assert result == '錯誤：帳號或角色名稱不正確（區分大小寫）'
