#!/usr/bin/env python3
"""抓 H@H 版本公告帖,只把「資訊」寫進 api/(不下載、不存 client 檔案)。

論壇在 Cloudflare managed challenge 後面,純 HTTP 客戶端(含 curl_cffi)過不了,
因此以 FlareSolverr(真 Chrome)作為唯一取得途徑,網址由 FLARESOLVERR_URL 指定。
產出:
  api/info.json      版本指標(最新/建議/最低支援)、來源帖網址、updated_at
  api/latest.json    最新版本(版本、日期、標籤、說明)與下載連結
  api/releases.json  所有已知 releases,新到舊;累積保存,原帖刪掉舊內容也不會消失
  api/history.json   版本指標變動紀錄:以 UTC 時間為鍵,值為當時三個指標,只在變動時追加
內容沒變就不改檔,讓 Actions 不產生空 commit。

執行:FLARESOLVERR_URL=http://localhost:8191/v1 python3 scripts/update.py [api]
離線解析:python3 scripts/update.py api --html page.html
"""
import html as htmllib
import json
import os
import re
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

TOPIC = 'https://forums.e-hentai.org/index.php?showtopic=234458'


def fetch(url: str) -> str:
    endpoint = os.environ['FLARESOLVERR_URL']
    body = json.dumps({'cmd': 'request.get', 'url': url, 'maxTimeout': 90000}).encode()
    req = urllib.request.Request(endpoint, data=body, headers={'Content-Type': 'application/json'})
    reply = json.load(urllib.request.urlopen(req, timeout=150))
    sol = reply.get('solution') or {}
    if reply.get('status') != 'ok' or sol.get('status') != 200:
        raise RuntimeError(f"FlareSolverr {reply.get('status')}: {reply.get('message')} / HTTP {sol.get('status')}")
    return sol['response']


def plain(fragment: str) -> str:
    return htmllib.unescape(re.sub(r'<[^>]+>', '', re.sub(r'<br\s*/?>', '\n', fragment, flags=re.I)))


def find_download(page: str) -> str:
    """從連結本身解析下載位置,不寫死主機名(曾是 repo.,現為 upld.,日後可能再變)。
    優先:連結文字為 'Hentai@Home x.y.z' 的 <a>;其次:href 指向 HentaiAtHome_*.zip 且非 _src。"""
    anchors = re.findall(r'<a\b[^>]*?href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', page, re.S | re.I)
    for href, label in anchors:
        if re.fullmatch(r'\s*Hentai@Home\s+[0-9.]+\s*', plain(label)):
            return htmllib.unescape(href)
    for href, _ in anchors:
        if re.search(r'HentaiAtHome_[0-9.]+\.zip$', href) and '_src' not in href:
            return htmllib.unescape(href)
    raise ValueError('找不到下載連結')


def parse(page: str) -> dict:
    flat = re.sub(r'\s+', ' ', plain(page))  # 去標籤後比對,不依賴 <b> 之類的排版

    def ver(label):
        m = re.search(rf'The {label} version is\s*([0-9][0-9.]*[0-9])', flat, re.I)
        if not m:
            raise ValueError(f'找不到 {label} version')
        return m.group(1)

    link = find_download(page)

    start = re.search(r"<div class=[\"']postcolor[\"'] id=[\"']post-\d+[\"']>", page)
    if not start:
        raise ValueError('找不到 release notes 貼文')
    end = page.find('</div>', start.end())
    if end == -1:
        raise ValueError('release notes 貼文沒有結尾')
    text = re.sub(r'<br\s*/?>', '\n', page[start.end():end], flags=re.I)
    text = htmllib.unescape(re.sub(r'<[^>]+>', '', text)).strip()

    releases, last = [], 0
    for m in re.finditer(r'([0-9.]+)\s*(?:\[([^\]]*)\])?\s*-\s*(\d{4}-\d{2}-\d{2})', text):
        if releases:
            releases[-1]['notes'] = text[last:m.start()].strip()
        releases.append({'version': m.group(1), 'date': m.group(3), 'tags': [t.strip() for t in (m.group(2) or '').split(',') if t.strip()], 'notes': ''})
        last = m.end()
    if not releases:
        raise ValueError('解析不到任何 release')
    tail = text[last:]
    releases[-1]['notes'] = tail.split('To update an existing client')[0].strip()  # 去掉頁尾樣板
    releases.sort(key=lambda r: r['date'], reverse=True)

    return {
        'topic_url': TOPIC,
        'download_link': link,  # 僅記錄連結,不下載
        'versions': {
            'most_recent': ver('most recent'),
            'minimum_recommended': ver('minimum recommended'),
            'minimum_supported': ver('minimum supported'),
        },
        'releases': releases,
    }


def write_if_changed(path: Path, data) -> bool:
    new = json.dumps(data, ensure_ascii=False, indent=2) + '\n'
    if path.exists() and path.read_text() == new:
        return False
    path.write_text(new)
    return True


def merge_releases(old: list, new: list) -> list:
    """累積保存:原帖可能刪掉舊內容,所以以既有 releases.json 為底,同版本以新抓到的為準。"""
    by_version = {r['version']: r for r in old}
    by_version.update({r['version']: r for r in new})
    return sorted(by_version.values(), key=lambda r: (r['date'], r['version']), reverse=True)


def load(path: Path, default):
    return json.loads(path.read_text()) if path.exists() else default


def main():
    args = sys.argv[1:]
    out = Path(args[0] if args and not args[0].startswith('--') else 'api')
    out.mkdir(exist_ok=True)
    page = Path(args[args.index('--html') + 1]).read_text() if '--html' in args else fetch(TOPIC)
    snap = parse(page)
    v = snap['versions']

    releases = merge_releases(load(out / 'releases.json', []), snap['releases'])
    newest = next((r for r in releases if r['version'] == v['most_recent']), {'version': v['most_recent']})
    info = {'topic_url': snap['topic_url'], 'versions': v}
    latest = {**newest, 'download_link': snap['download_link']}

    # updated_at 只在內容真的變動時更新,否則每天都會產生 commit
    old_info = load(out / 'info.json', {})
    unchanged = (releases == load(out / 'releases.json', None)
                 and latest == load(out / 'latest.json', None)
                 and {k: x for k, x in old_info.items() if k != 'updated_at'} == info)
    if unchanged:
        print('沒有變動')
        return
    now = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%MZ')  # 一律 UTC

    write_if_changed(out / 'info.json', {'updated_at': now, **info})
    write_if_changed(out / 'latest.json', latest)
    write_if_changed(out / 'releases.json', releases)

    # 版本指標變動紀錄:以 UTC 時間為鍵,值為當時三個指標的內容
    hist = load(out / 'history.json', {})
    if not hist or hist[max(hist)] != v:
        hist[now] = v
        write_if_changed(out / 'history.json', hist)
    print('已更新', v)


if __name__ == '__main__':
    main()
