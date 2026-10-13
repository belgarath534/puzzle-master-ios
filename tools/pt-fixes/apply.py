# Applies the Portuguese question fixes in this folder to www/index.html.
# Usage: python3 tools/pt-fixes/apply.py   (run from the repo root)
import json, importlib.util, glob, os
root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
path = os.path.join(root, 'www', 'index.html')
lines = open(path, encoding='utf-8').read().split('\n')
i = next(n for n, l in enumerate(lines) if l.startswith('const ALL_PUZZLES = {'))
line = lines[i]
end = line.rstrip().rstrip(';').rindex('}') + 1
data = json.loads(line[line.index('{'):end])
changed = 0
for f in sorted(glob.glob(os.path.join(os.path.dirname(__file__), 'cat*.py'))):
    cat = str(int(os.path.basename(f)[3:-3]))
    spec = importlib.util.spec_from_file_location('m', f); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    puzzles = data['pt'][cat]['puzzles']
    for idx, (q, choices, answer) in m.FIXES.items():
        assert answer in choices, (cat, idx, answer)
        assert len(set(choices)) == len(choices) == 4, (cat, idx)
        p = puzzles[idx]
        if q: p['question'] = q
        p['choices'] = choices
        p['correct'] = choices.index(answer)
        changed += 1
lines[i] = 'const ALL_PUZZLES = ' + json.dumps(data, ensure_ascii=False, separators=(',', ':')) + ';'
open(path, 'w', encoding='utf-8').write('\n'.join(lines))
print('updated', changed, 'Portuguese questions')
