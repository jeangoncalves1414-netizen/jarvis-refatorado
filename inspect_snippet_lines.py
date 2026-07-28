from pathlib import Path
text = Path('app/ui/panel/templates/index.html').read_text(encoding='utf-8')
start = text.index('<section id="screen-chat"')
end = text.index('</section>', start) + len('</section>')
snippet = text[start:end]
lines = snippet.splitlines()
for i, line in enumerate(lines, start=1):
    print(f'{i:03}: {line}')
