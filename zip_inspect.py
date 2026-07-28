import os, glob, zipfile
os.chdir("docs/Documentacao")
files = glob.glob("*.zip")
print("found", len(files))
for p in files:
    print("===", p)
    with zipfile.ZipFile(p) as z:
        data = z.read("code.html").decode("utf-8", errors="replace")
        keys = ["title>", "System Optimization", "Conversations", "New Task", "Type a message", "Kill Queries", "View Logs", "Aura Core"]
        lines = data.splitlines()
        for i, line in enumerate(lines[:200], 1):
            if any(k in line for k in keys):
                print(i, line)
        print("--- snippet around main content ---")
        for i, line in enumerate(lines, 1):
            if any(k in line for k in ["Type a message", "View Logs", "Kill Queries"]):
                for j in range(max(0, i-5), min(len(lines), i+5)):
                    print(lines[j])
                break
        print()
