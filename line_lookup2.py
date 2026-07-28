from pathlib import Path
lines = Path('app/ui/panel/templates/index.html').read_text(encoding='utf-8').splitlines()
for i in range(820, 880):
    if i < len(lines):
        print(f'{i+1}: {lines[i]}')
