from collections import namedtuple, deque
from enum import Enum
import ast
import warnings
import tqdm


class TokenType(Enum):
    Text = 1
    Number = 2
    Range = 3
    String = 4
    Line = 5
    Whitespace = 6
    EOF = 7


def _unescape(
    c,
    _map={
        'n': '\n',
    },
):
    try:
        return _map[c]
    except KeyError:
        if c in 'uU':
            raise Exception('unsupported escape sequence \\{c}')
        print(f'unexpected escape sequence \\{c}', file=sys.stderr)
        return f'\\{c}'


def parse_string(s):
    assert s[0] == '"'
    assert s[-1] == '"'
    siter = iter(s[1:-1])
    return ''.join(_unescape(next(siter)) if c == '\\' else c for c in siter)


class Token(namedtuple('Token', 'string type line column')):
    @property
    def value(self):
        return {TokenType.Number: int, TokenType.String: parse_string,}.get(
            self.type, lambda x: x
        )(self.string)


class Lexer:
    def __init__(self, name, file, size):
        self.name = name
        self.file = file
        self.line = 1
        self.column = 1
        self.stored = []
        self.buffer = deque()
        self.tokens = deque()
        self.state = inSpace
        self.tqdm = tqdm.tqdm(total=size, mininterval=1)

    def posafter(self):
        line = self.line + self.stored.count('\n')
        if line > self.line:
            for column, c in enumerate(reversed(self.stored), 1):
                if c == '\n':
                    break
        else:
            column = self.column + len(self.stored)
        return line, column

    def emit(self, type):
        value = ''.join(self.stored)
        assert (value != '') ^ (type == TokenType.EOF)
        if callable(type):
            type = type(value)
        self.tokens.append(Token(value, type, self.line, self.column))
        self.discard()

    def next(self):
        if not self.buffer:
            buf = self.file.read(4096)
            self.buffer.extend(buf)
            self.tqdm.update(len(buf))
        if not self.buffer:
            r = ''
        else:
            r = self.buffer.popleft()
        self.stored.append(r)
        return r

    def acceptRun(self, chars):
        chars = set(chars)
        while self.next() in chars:
            pass
        self.backup()

    def backup(self):
        self.buffer.appendleft(self.stored.pop())

    def peek(self):
        r = self.next()
        if r != '':
            self.backup()
        return r

    def discard(self):
        self.line, self.column = self.posafter()
        self.stored = []

    def unexpected(self, message):
        c = self.peek()
        if c:
            c = repr(c)
        else:
            c = 'EOF'
        line, column = self.posafter()
        raise Exception(f'{self.name}:{line}:{column}: unexpected {c} ({message})')

    def __iter__(self):
        return self

    def __next__(self):
        while not self.tokens and self.state is not None:
            self.state = self.state(self)
        if self.tokens:
            # print(self.tokens[0])
            r = self.tokens.popleft()
            # workaround for text error
            if r.string == '1attack_damage_+%_while_you_have_fortify':
                self.tokens.appendleft(
                    Token(
                        'attack_damage_+%_while_you_have_fortify',
                        TokenType.Text,
                        r.line,
                        r.column + 2,
                    )
                )
                return Token(1, TokenType.Number, r.line, r.column)
            # workaround for error:
            # 1# "ได้รับ %1% ชาร์จ เมื่อคุณถูกปะทะโดยศัตรู"
            if r.string == '1#':
                return Token('1|#', TokenType.Range, r.line, r.column)
            return r
        raise StopIteration()


def inSpace(lexer):
    lexer.acceptRun(' \t\r')
    lexer.discard()
    stored = lexer.next()
    if stored:
        if stored == '"':
            r = inString
        elif stored == '\n':
            r = inNewLine
        else:
            r = inText
        return r
    else:
        lexer.emit(TokenType.EOF)
        return None


def inNewLine(lexer):
    lexer.acceptRun(' \t\r\n')
    lexer.emit(TokenType.Line)
    return inSpace


def inString(lexer):
    while True:
        c = lexer.next()
        if c == '':
            lexer.unexpected('string not terminated')
        elif c == '\\':
            return inStringEscaped
        elif c == '"':
            lexer.emit(TokenType.String)
            return inSpace
        else:
            return inString


def inStringEscaped(lexer):
    c = lexer.next()
    if c == '':
        lexer.unexpected('string not terminated')
    else:
        return inString


def getTextType(s):
    if s.isdigit():
        return TokenType.Number
    if s[0] == '-' and s[1:].isdigit():
        return TokenType.Number
    if s[0] == '!' and getTextType(s[1:]) == TokenType.Number:
        return TokenType.Range
    if s == '#':
        return TokenType.Range
    if '|' not in s:
        return TokenType.Text
    if all(getTextType(i) in [TokenType.Number, TokenType.Range] for i in s.split('|')):
        return TokenType.Range
    return TokenType.Text


assert getTextType('1|#') == TokenType.Range


def inText(lexer):
    c = lexer.next()
    if c == '':
        lexer.emit(getTextType)
        return inSpace
    elif c.isspace():
        lexer.backup()
        lexer.emit(getTextType)
        return inSpace
    elif c == '\'"':
        lexer.unexpected('character not allowed in text')
    else:
        return inText


class Parser:
    END = object()

    def __init__(self):
        self.data = []
        self.tokens = None
        self._peek = None

    def parse(self, tokens):
        self.tokens = iter(tokens)
        self.r = []
        state = self.atStart
        while state is not self.END:
            state = state()
        return self.r

    def atStart(self):
        emap = {
            'no_description': self.atNoDescription,
            'description': self.atDescription,
            '': self.END,
        }
        return emap[self.expect(*emap).value]

    def atNoDescription(self):
        self.expect(TokenType.Text)
        self.expect(TokenType.Line)
        return self.atStart

    def atDescription(self):
        if self.peek().type == TokenType.Text:
            self.expect(TokenType.Text)

        self.expect(TokenType.Line)
        self.description = {}
        self.r.append(self.description)
        nKeys = int(self.expect(TokenType.Number).value)
        self.keys = [self.expect(TokenType.Text).value for i in range(nKeys)]
        self.expect(TokenType.Line)
        self.description['keys'] = self.keys
        self.variants = []
        self.langs = self.description['langs'] = {'': self.variants}
        return self.atVariantList

    def atVariantList(self):
        self.variantsRemaining = int(self.expect(TokenType.Number).value)
        self.expect(TokenType.Line)
        return self.atVariant

    def atVariant(self):
        self.variant = variant = {}
        self.variants.append(variant)
        return self.atRanges

    def atRanges(self):
        self.variant['ranges'] = [
            self.expect(TokenType.Number, TokenType.Range).string for k in self.keys
        ]
        return self.atVariantText

    def atVariantText(self):
        self.variant['source'] = self.expect(TokenType.String).value
        self.variantsRemaining -= 1
        return self.atVariantFlags

    def atVariantFlags(self):
        flags = self.variant['flags'] = []
        token = self.expect(TokenType.Line, TokenType.Text)
        while True:
            if token.type == TokenType.Line:
                if self.variantsRemaining:
                    return self.atVariant
                else:
                    emap = {
                        'lang': self.atLang,
                        'description': self.atDescription,
                        'no_description': self.atNoDescription,
                        '': self.END,
                    }
                    return emap[self.expect(*emap).value]
            else:
                nexttok = self.expect(TokenType.Text, TokenType.Number, TokenType.Line)
                if nexttok.type == TokenType.Number or token.string == 'reminderstring':
                    flags.append([token.value, nexttok.value])
                    token = self.expect(TokenType.Text, TokenType.Line)
                else:
                    flags.append([token.value, None])
                    token = nexttok

    def atLang(self):
        self.description['langs'][
            self.expect(TokenType.String).value
        ] = self.variants = []
        self.expect(TokenType.Line)
        return self.atVariantList

    def undo(self, token):
        self._peek = token

    def peek(self):
        self._peek = next(self.tokens)
        return self._peek

    def next(self):
        if self._peek is not None:
            r = self._peek
            self._peek = None
            return r
        return next(self.tokens)

    def expect(self, *values_or_types):
        token = self.next()
        for value_or_type in values_or_types:
            if isinstance(value_or_type, str):
                if token.value == value_or_type:
                    return token
            else:
                if token.type == value_or_type:
                    return token
        self.unexpected(token, f'expecting {", ".join(map(str, values_or_types))}')

    def test(self, *values_or_types):
        try:
            token = self.expect(*values_or_types)
        except:
            return None
        else:
            return token
        finally:
            self.undo(token)

    def unexpected(self, token, message):
        raise Exception(
            f'{token.line}:{token.column}: unexpected {token.type.name} {token.string!r}, {message}'
        )


def file_chars(file):
    c = 0
    while True:
        s = file.read(4096)
        if not s:
            break
        c += len(s)
    return c


def hack(data):
    for item in data:
        if item['keys'] == [
            "local_unique_jewel_projectile_damage_+1%_per_x_dex_in_radius"
        ]:
            for (lang, variants) in item['langs'].items():
                for variant in variants:
                    if variant['source'] == "範圍內每 {0:d} 點已配置敏捷，增加 {1}% 投射物傷害":
                        variant['source'] = "範圍內每 {0:d} 點已配置敏捷，增加 1% 投射物傷害"
        if item['keys'] == ['map_supporter_players_random_movement_velocity_+%_final_when_hit']:
            for (lang, variants) in item['langs'].items():
                for variant in variants:
                    if variant['source'] == '被擊中時，玩家獲得隨機移動速度詞綴，\n從 {0}% 更少至 {1}% 更多，直到再次被擊中':
                        variant['source'] = '被擊中時，玩家獲得隨機移動速度詞綴，\n從 {0}% 更少至 {0}% 更多，直到再次被擊中'


LANG_WHITELIST = {'Traditional Chinese', ''}
import argparse
import sys
import os

sys.path.append(os.path.abspath(os.path.dirname(__file__)))
import pjson

parser = argparse.ArgumentParser()
parser.add_argument('filename')
args = parser.parse_args()
with open(args.filename, encoding='utf-16') as file:
    size = file_chars(file)
    file.seek(0)
    lexer = Lexer(args.filename, file, size=size)
    parser = Parser()
    parsed = parser.parse(lexer)
    for item in parsed:
        langs = item['langs']
        item['langs'] = {k: langs[k] for k in langs if k in LANG_WHITELIST}
        # remove other languages do decrease memory usage on GAE
    hack(parsed)
    sys.stdout.writelines(pjson.PrettyJSONEncoder().iterencode(parsed))
    lexer.tqdm.close()
