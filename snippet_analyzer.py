from pathlib import Path
import re
text = Path('app/ui/panel/templates/index.html').read_text(encoding='utf-8')
start = text.index('<section id="screen-chat"')
end = text.index('</section>', start) + len('</section>')
snippet = text[start:end]
lines = snippet.splitlines()
pattern = re.compile(r'<(/?)([a-zA-Z0-9_-]+)([^>]*)>')
void = {'area','base','br','col','embed','hr','img','input','link','meta','param','source','track','wbr'}
stack=[]
rows=[]
for lineno, line in enumerate(lines, start=1):
    for m in pattern.finditer(line):
        tag=m.group(2).lower()
        closing=bool(m.group(1))
        raw=m.group(0)
        if closing:
            if not stack:
                rows.append((lineno, raw, 'extra_close', None, stack.copy()))
            else:
                top=stack[-1]
                if top[0]==tag:
                    stack.pop()
                    rows.append((lineno, raw, 'close', tag, stack.copy()))
                else:
                    rows.append((lineno, raw, 'mismatch', (top[0], tag), stack.copy()))
                    # attempt recovery: pop until match or empty
                    while stack and stack[-1][0]!=tag:
                        stack.pop()
                    if stack and stack[-1][0]==tag:
                        stack.pop()
        else:
            if tag not in void and not raw.endswith('/>'):
                stack.append((tag, lineno))
                rows.append((lineno, raw, 'open', tag, stack.copy()))
            else:
                rows.append((lineno, raw, 'selfclose', tag, stack.copy()))
for row in rows:
    if row[2] != 'selfclose':
        print(row)
print('final stack', stack)
