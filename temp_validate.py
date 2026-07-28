from pathlib import Path
import re
path = Path(r'c:\Users\maria\Desktop\Jarvis\app\ui\panel\templates\index.html')
text = path.read_text(encoding='utf-8')
void = {'area','base','br','col','embed','hr','img','input','link','meta','param','source','track','wbr'}
stack=[]
errors=[]
for i, m in enumerate(re.finditer(r'<(/?)([a-zA-Z0-9_:-]+)([^>]*)>', text)):
    closing = m.group(1) == '/'
    tag = m.group(2).lower()
    attrs = m.group(3)
    if tag in void or attrs.strip().endswith('/'):
        continue
    if closing:
        if stack and stack[-1][0] == tag:
            stack.pop()
        else:
            errors.append((i, tag, m.start(), m.end(), stack[-5:]))
            break
    else:
        stack.append((tag, m.start()))
print('errors', errors)
print('stack_len', len(stack))
if stack:
    print('top', stack[-1])
    for tag,pos in stack[-10:]:
        print('open', tag, 'at', pos)
if errors:
    idx,tag,start,end,stack_tail = errors[0]
    line = text.count('\n',0,start)+1
    print('error line', line)
    before = text.rfind('\n',0,start)
    after = text.find('\n', end)
    print('error line text:', text[before+1:after])
    print('stack tail', stack_tail)
    context_start = max(0, start-200)
    context_end = min(len(text), end+200)
    print('--- context ---')
    print(text[context_start:context_end])
