import base64
import pathlib
import time
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


@pytest.fixture(scope='session')
def chrome():
    opts = ChromeOptions()
    # Chrome 142+ requires BiDi for extension loading
    # See: https://github.com/SeleniumHQ/selenium/issues/15788
    opts.enable_bidi = True
    opts.enable_webextensions = True

    chrome = Chrome(options=opts)
    chrome.implicitly_wait(3)

    # Install extension via BiDi after driver creation
    extension_result = chrome.webextension.install(path=str(EXTENSION_DIR))
    extension_id = extension_result.get('extension')

    # Override the app's extension ID to match the installed extension
    main.EXTENSION_ID = extension_id

    try:
        yield chrome
    finally:
        chrome.quit()


@pytest.fixture(scope='session')
def app(chrome: Chrome):
    # chrome fixture must run first to set main.EXTENSION_ID
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
