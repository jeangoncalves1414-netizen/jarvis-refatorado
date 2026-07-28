import os, glob, zipfile
os.chdir("docs/Documentacao")
files = glob.glob("*.zip")
for p in files:
    print('===', p)
    with zipfile.ZipFile(p) as z:
        for name in z.namelist():
            if name == 'code.html':
                data = z.read(name).decode('utf-8', errors='replace')
                out = open(os.path.basename(p) + '_code.html', 'w', encoding='utf-8')
                out.write(data)
                out.close()
                print('wrote', os.path.basename(p) + '_code.html', 'size', len(data))
