import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))
import update

d = update.parse((Path(__file__).parent / 'fixtures/topic.html').read_text())
assert d['versions'] == {'most_recent': '1.6.4', 'minimum_recommended': '1.6.3', 'minimum_supported': '1.6.2'}
assert [r['version'] for r in d['releases']] == ['1.6.4', '1.6.3']
assert d['releases'][0]['notes'] == '- Fix & tweak', d['releases'][0]['notes']
assert d['releases'][0]['tags'] == ['SECURITY', 'IMPORTANT']
assert d['releases'][1]['notes'] == '- Older change'
assert d['download_link'].endswith('1.6.4.zip')

# 累積:原帖刪掉的舊 release 要保留,同版本以新抓到的為準
old = [{'version': '1.5.0', 'date': '2019-01-01', 'tags': [], 'notes': 'gone from thread'},
       {'version': '1.6.3', 'date': '2024-01-02', 'tags': [], 'notes': 'stale'}]
m = update.merge_releases(old, d['releases'])
assert [r['version'] for r in m] == ['1.6.4', '1.6.3', '1.5.0'], m
assert m[1]['notes'] == '- Older change' and m[2]['notes'] == 'gone from thread'
print('ok')
