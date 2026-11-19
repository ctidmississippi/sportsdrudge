# Sideline Wire

A Drudge-style sports front page that rebuilds itself every day from ~120 RSS feeds.

## How it works
1. `build.py` downloads every feed in `feeds.json` in parallel (a dead feed is skipped, never fatal).
2. Headlines about the same story are grouped. A story carried by many outlets ranks higher, newer beats older.
3. The top stories become the big headline block and top-left links. The rest fill three columns by sport (set in `config.json`). Stories run by 5+ outlets show in red.
4. The page is written to `public/index.html`, and GitHub Pages publishes it.
5. `feed_report.json` lists which feeds worked, so you can prune dead ones.

If fewer than 20 items come back (for example, a network outage), the build stops and the last good page stays live.

## Set it up (about 10 minutes, one time)
1. Create a free GitHub account, then a **new public repository** (any name).
2. Upload everything in this folder to it (**Add file > Upload files**, drag the whole folder contents, including the hidden `.github` folder).
3. In the repo go to **Settings > Pages** and set **Source** to **GitHub Actions**.
4. Go to the **Actions** tab, open **Update front page**, click **Run workflow**.
5. When it finishes (about a minute), your site is at `https://YOURNAME.github.io/REPONAME/`. The same page shows the URL.
6. Open the finished run and download the **feed-report** artifact (or read the "Show feed health" step). It lists every feed that failed. Remove those from `feeds.json` or fix the URLs.

After that it refreshes by itself every day at 11:00 UTC. Edit the `cron` line in `.github/workflows/update.yml` to change times.

## Change things
- Site name, columns, how many items, how old is too old: `config.json`
- Add or remove sources: `feeds.json` (`tag` = sport, `w` = source weight)
- Lead photo: replace `assets/lead.jpg`
- Look and feel: `style.css`

## Test locally
`python3 build.py --fixtures tests/fixtures --out /tmp/test.html`

## Notes
- Feed URLs were written from memory and are unverified. Expect some to fail on the first run.
- The Athletic feed may work without a login (headlines only). If it doesn't, drop it.
- X has no free feed, so it is not included.
- Headlines link to the original outlets. Hover one to see which outlets ran the story.
