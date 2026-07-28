from pathlib import Path
import re
text = Path('app/ui/panel/templates/index.html').read_text(encoding='utf-8')
start = text.index('<section id="screen-chat"')
end = text.index('</section>', start) + len('</section>')
snippet = text[start:end]
lines = snippet.splitlines()
print('Snippet length', len(lines))
pattern = re.compile(r'<(/?)([a-zA-Z0-9_-]+)([^>]*)>')
void = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'param', 'source', 'track', 'wbr'}
stack=[]
errors=[]
for i, line in enumerate(lines, start=1):
    for m in pattern.finditer(line):
        closing = bool(m.group(1))
        tag = m.group(2).lower()
        raw = m.group(0)
        if closing:
            if not stack:
                errors.append((i, 'extra_close', tag, raw, stack.copy()))
            else:
                top=stack.pop()
                if top[0]!=tag:
                    errors.append((i, 'mismatch', top[0], tag, raw, top, stack.copy()))
        else:
            if tag not in void and not raw.endswith('/>'):
                stack.append((tag, i, raw))
    # print debugging for line 857 maybe
    if i in (50, 70, 80, 90, 100, 110):
        print('line', i, 'stack', [t[0] for t in stack])
print('final stack length', len(stack), [t[0] for t in stack[-10:]])
print('errors', errors)
