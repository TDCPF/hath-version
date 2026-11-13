# hath-version

每天一次抓 [H@H 版本公告帖](https://forums.e-hentai.org/index.php?showtopic=234458),把版本資訊與更新紀錄存成 `api/*.json`,以 GitHub Pages 呈現。**只存資訊,不存任何 client 檔案。**

- 抓取:`scripts/update.py`,經 FlareSolverr(Cloudflare managed challenge 只有真 Chrome 過得了;curl_cffi 實測仍 403)。
- 本地測試解析:`python3 tests/test_parse.py`。
- 部署:建 repo → Settings → Pages 選 GitHub Actions → 手動跑一次 workflow。

## JSON API

基底 `https://tdcpf.github.io/hath-version/api/`(Pages 預設帶 CORS `*`,時間一律 UTC):

- `info.json`:三個版本指標、來源帖網址、`updated_at`。
- `latest.json`:最新版本(版本、日期、標籤、說明)與下載連結。
- `releases.json`:所有已知 releases,新到舊。**累積保存**:原帖刪掉舊內容後這裡仍保留,同版本以最新抓到的為準。
- `history.json`:版本指標變動紀錄,以 UTC 時間為鍵,值為當時三個指標的內容,只在變動時追加。
