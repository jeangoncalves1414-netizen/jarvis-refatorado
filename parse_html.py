from pathlib import Path
from html.parser import HTMLParser

class Parser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.stack=[]
        self.errors=[]
        self.ignored=[]

    def handle_starttag(self, tag, attrs):
        if tag in ('script','style'):
            self.ignored.append(tag)
            return
        if self.ignored:
            return
        if tag in ('area','base','br','col','embed','hr','img','input','link','meta','param','source','track','wbr'):
            return
        self.stack.append((tag, self.getpos()))

    def handle_endtag(self, tag):
        if tag in ('script','style') and self.ignored and self.ignored[-1]==tag:
            self.ignored.pop()
            return
        if self.ignored:
            return
        if not self.stack:
            self.errors.append(('extra_close', tag, self.getpos()))
            return
        top=self.stack.pop()
        if top[0]!=tag:
            self.errors.append(('mismatch', top[0], tag, top[1], self.getpos()))

    def handle_comment(self, data):
        pass

    def close(self):
        super().close()
        if self.stack:
            self.errors.append(('unclosed', [s[0] for s in self.stack]))

text = Path('app/ui/panel/templates/index.html').read_text(encoding='utf-8')
parser = Parser()
parser.feed(text)
parser.close()
print('errors', parser.errors[:50])
print('remaining', len(parser.stack), parser.stack[-10:])
