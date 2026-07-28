from pathlib import Path
lines = Path('app/ui/panel/templates/index.html').read_text(encoding='utf-8').splitlines()
for i in range(850, 865):
    print(f'{i+1}: {lines[i]}')
