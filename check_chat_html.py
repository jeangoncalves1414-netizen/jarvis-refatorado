from pathlib import Path
from html.parser import HTMLParser

text = Path('app/ui/panel/templates/index.html').read_text(encoding='utf-8')
start = text.index('<section id="screen-chat"')
end = text.index('</section>', start) + len('</section>')
snippet = text[start:end]
print('SNIPPET FIRST 800:')
print(snippet[:800])
print('SNIPPET LAST 200:')
print(snippet[-200:])

class P(HTMLParser):
    def __init__(self):
        super().__init__()
        self.stack = []
        self.errors = []

    def handle_starttag(self, tag, attrs):
        if tag in ('area','base','br','col','embed','hr','img','input','link','meta','param','source','track','wbr'):
            return
        self.stack.append((tag, self.getpos()))

    def handle_endtag(self, tag):
        if not self.stack:
            self.errors.append(('extra_close', tag, self.getpos()))
            return
        top = self.stack.pop()
        if top[0] != tag:
            self.errors.append(('mismatch', top[0], tag, top[1], self.getpos()))

    def close(self):
        super().close()
        if self.stack:
            self.errors.append(('unclosed', [s[0] for s in self.stack]))

parser = P()
parser.feed(snippet)
parser.close()
print('errors', parser.errors)
print('remaining stack len', len(parser.stack))
