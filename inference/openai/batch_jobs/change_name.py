from pathlib import Path

for file in Path(__file__).parent.rglob('*.jsonl'):
    tta, filename = file.name.split("-", 1)
    new_filename = "AttackSeq-" + filename

    file.rename(Path(file.parent, new_filename))