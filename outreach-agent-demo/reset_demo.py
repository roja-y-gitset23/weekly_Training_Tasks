from pathlib import Path

for f in Path(".").glob("demo.db*"):
    f.unlink()
print("Demo database cleared")