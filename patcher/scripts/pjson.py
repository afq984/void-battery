import json


class PrettyJSONEncoder:
    SIMPLE = (int, float, str, type(None))
    def __init__(self, indent_level=0):
        self.indent = '  '
        self.indent_level = indent_level

    @property
    def nextindent(self):
        return self.__class__(self.indent_level + 1)

    @property
    def break0(self):
        return '\n' + self.indent * self.indent_level

    @property
    def break1(self):
        return '\n' + self.indent * (self.indent_level + 1)

    def kv(self, k, v):
        yield from self.iterencode(k)
        yield ': '
        yield from self.iterencode(v)

    def encode(self, o):
        return ''.join(self.iterencode(o))

    def issimple(self, o):
        if isinstance(o, self.SIMPLE):
            return True
        assert isinstance(o, (tuple, dict, list))
        if isinstance(o, dict):
            return False
        if len(o) < 4 and all(not isinstance(c, dict) for c in o):
            return True
        return False

    def iterencode(self, o):
        if self.issimple(o):
            yield json.dumps(o, ensure_ascii=False)
        elif isinstance(o, (tuple, list)):
            yield '['
            if all(isinstance(p, self.SIMPLE) for p in o):
                items = [self.encode(p) for p in o]
                yield from self.encodeitems(items)
            else:
                *others, last = o
                for item in others:
                    yield self.break1
                    yield from self.nextindent.iterencode(item)
                    yield ','
                yield self.break1
                yield from self.nextindent.iterencode(last)
                yield self.break0
            yield ']'
        elif isinstance(o, dict):
            yield '{'
            if all(isinstance(p, self.SIMPLE) for p in o.values()):
                items = ['{}: {}'.format(*map(self.encode, kv)) for kv in o.items()]
                yield from self.encodeitems(items)
            else:
                *others, last = o.items()
                for k, v in others:
                    yield self.break1
                    yield from self.nextindent.kv(k, v)
                    yield ','
                yield self.break1
                yield from self.nextindent.kv(*last)
                yield self.break0
            yield '}'
        else:
            raise Exception('unsupported type', type(o))

    def encodeitems(self, items):
        if sum(map(len, items)) + 2 * len(items) - 2 < 80:
            yield ', '.join(items)
        else:
            *others, last = items
            for item in others:
                yield self.break1
                yield item
                yield ','
            yield self.break1
            yield last
            yield self.break0


def dump(o, f):
    f.writelines(PrettyJSONEncoder().iterencode(o))
