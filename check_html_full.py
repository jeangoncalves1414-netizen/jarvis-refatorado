from pathlib import Path
import re

text = Path('app/ui/panel/templates/index.html').read_text(encoding='utf-8')
void = {'area','base','br','col','embed','hr','img','input','link','meta','param','source','track','wbr'}
pattern = re.compile(r'<(/?)([a-zA-Z0-9_-]+)([^>]*)>')
stack=[]
errors=[]
line_starts=[0]
for m in re.finditer(r'\n', text):
    line_starts.append(m.end())
def lineno(pos):
    l = 1
    for start in line_starts:
        if start > pos:
            break
        l += 1
    return l
for m in pattern.finditer(text):
    closing = bool(m.group(1))
    tag = m.group(2).lower()
    if closing:
        if not stack:
            errors.append(('extra_close', tag, lineno(m.start()), m.group(0)))
        else:
            top = stack.pop()
            if top[0] != tag:
                errors.append(('mismatch', top[0], tag, lineno(m.start()), top[1], m.group(0)))
    else:
        if tag not in void:
            stack.append((tag, lineno(m.start()), m.group(0)))

print('errors', errors[:50])
print('stack remaining', [(t[0], t[1]) for t in stack[-20:]])
