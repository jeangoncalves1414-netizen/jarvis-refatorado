from html.parser import HTMLParser
from pathlib import Path

s = Path(r"app/ui/panel/templates/index.html").read_text(encoding='utf-8')

class Checker(HTMLParser):
    def __init__(self):
        super().__init__()
        self.stack = []
        self.errors = []

    def handle_starttag(self, tag, attrs):
        if tag in ('meta','img','br','hr','input','link','area','col','embed','source','track','wbr'): return
        self.stack.append((tag, self.getpos()))

    def handle_startendtag(self, tag, attrs):
        pass

    def handle_endtag(self, tag):
        if not self.stack:
            self.errors.append(('extra_end', tag, self.getpos()))
            return
        last, pos = self.stack.pop()
        if last != tag:
            self.errors.append(('mismatch', last, tag, pos, self.getpos()))

    def close(self):
        super().close()
        while self.stack:
            self.errors.append(('unclosed', self.stack.pop()))

checker = Checker()
checker.feed(s)
checker.close()
print('errors:', len(checker.errors))
for e in checker.errors:
    print(e)
