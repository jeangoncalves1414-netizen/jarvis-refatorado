from pathlib import Path
from html.parser import HTMLParser
text = Path('app/ui/panel/templates/index.html').read_text(encoding='utf-8')
start = text.index('<section id="screen-chat"')
end = text.index('</section>', start) + len('</section>')
snippet = text[start:end]

class DebugParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.stack = []
        self.events = []
    def handle_starttag(self, tag, attrs):
        if tag not in ('area','base','br','col','embed','hr','img','input','link','meta','param','source','track','wbr'):
            self.stack.append(tag)
        self.events.append(('start', tag, self.getpos(), len(self.stack)))
    def handle_endtag(self, tag):
        if self.stack:
            top = self.stack[-1]
        else:
            top = None
        self.events.append(('end', tag, self.getpos(), top, len(self.stack)))
        if self.stack and self.stack[-1] == tag:
            self.stack.pop()
        else:
            if self.stack:
                self.stack.pop()
    def handle_data(self, data):
        if data.strip():
            self.events.append(('data', data.strip()[:40], self.getpos()))

parser = DebugParser()
parser.feed(snippet)
parser.close()
for idx, ev in enumerate(parser.events):
    if ev[0] in ('end',) and ev[1] == 'div' or ev[0] == 'start' and ev[1] == 'section':
        print(idx, ev)
print('remaining stack', parser.stack)
print('total events', len(parser.events))
