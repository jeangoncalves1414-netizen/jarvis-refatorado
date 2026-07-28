from pathlib import Path
text = Path('app/ui/panel/templates/index.html').read_text(encoding='utf-8')
lines = text.splitlines()
print('Lines 730-900:')
for i in range(729, 900):
    if i < len(lines):
        print(f'{i+1}: {lines[i]}')

print('\nFirst closing </section> after screen-chat start:')
for i, line in enumerate(lines):
    if '<section id="screen-chat"' in line:
        start = i
        break
else:
    start = None
if start is not None:
    for j in range(start+1, len(lines)):
        if '</section>' in lines[j]:
            print(j+1, lines[j])
            break
