# LPE Mealviewer → Apple Calendar

Automatically publishes Laureate Park Elementary's **lunch menu** as an
Apple Calendar subscription, so it shows up on your iPhone and stays
current on its own — no manual re-import, ever.

How it works, end to end:

1. `generate_ics.py` calls MealViewer's public JSON API directly
   (`api.mealviewer.com`, no login/API key needed) and pulls the lunch
   menu for roughly the next 2.5 months.
2. It writes a standard `.ics` calendar file to `docs/lpe_lunch_menu.ics`
   — one all-day event per school day, titled with the entree(s), with
   the full menu (entrees, sides, fruit, milk) in the event description.
3. A GitHub Actions workflow (`.github/workflows/update-calendar.yml`)
   runs that script automatically every day and commits the refreshed
   file back to this repo.
4. GitHub Pages serves the `docs/` folder as a public URL. Apple
   Calendar subscribes to that URL and re-checks it periodically on its
   own — so as the menu changes week to week, your phone just updates.

No servers to maintain, no accounts beyond GitHub, nothing to remember
to run.

## One-time setup (~5 minutes)

**1. Create a GitHub repository and push this folder.**

From inside this folder:

```bash
git init
git add .
git commit -m "Initial commit: LPE lunch calendar generator"
gh repo create lpe-mealviewer --public --source=. --push
```

(No `gh` CLI? Create an empty **public** repo at github.com/new named
`lpe-mealviewer`, then `git remote add origin <url>` and `git push -u
origin main`. The repo must be public for the free tier of GitHub Pages
used here.)

**2. Enable GitHub Pages.**

On GitHub: your repo → **Settings** → **Pages** → under "Build and
deployment", set **Source** to "Deploy from a branch", **Branch** to
`main`, folder to `/docs` → **Save**.

GitHub will show you the live URL, something like:

```
https://<your-username>.github.io/lpe-mealviewer/
```

Your calendar feed will be at:

```
https://<your-username>.github.io/lpe-mealviewer/lpe_lunch_menu.ics
```

Give it a minute after the first push for Pages to build. You can watch
progress under the repo's **Actions** tab.

**3. Subscribe on your iPhone.**

Easiest: open that URL in **Safari on your iPhone** and tap **Subscribe**
when prompted.

Or manually: **Settings → Calendar (previously "Calendars") → Accounts →
Add Account → Other → Add Subscribed Calendar**, then enter the URL
above but swap `https://` for `webcal://`:

```
webcal://<your-username>.github.io/lpe-mealviewer/lpe_lunch_menu.ics
```

The events will appear in the Calendar app under a calendar named
"LPE Lunch Menu."

## Keeping it fresh

- GitHub Actions regenerates the feed daily at ~6am ET automatically —
  nothing to do.
- Apple's Calendar app decides on its own how often to re-poll a
  subscribed calendar (typically every few hours to once a day); there's
  no way to force a faster interval from our side. If you want to force
  an immediate refresh on your phone: pull down in the Calendar app's
  list view, or remove and re-add the subscription.
- To trigger an update manually (e.g. right after the school posts a new
  month's menu): go to the repo's **Actions** tab → "Update LPE Lunch
  Calendar" → **Run workflow**.

## Customizing

Open `generate_ics.py` and edit the constants near the top:

- `MEAL_BLOCK_NAME` — switch to `"Breakfast"` for breakfast instead of
  lunch (or run the script twice with two output filenames if you want
  both as separate subscribable calendars).
- `DAYS_BEHIND` / `DAYS_AHEAD` — how wide a window to pull from
  MealViewer each run.
- `ITEM_TYPE_ORDER` — which menu categories appear, and in what order,
  in each event's description.

Run `python3 generate_ics.py` locally any time to preview
`docs/lpe_lunch_menu.ics` before pushing.

## Notes

- MealViewer's endpoint (`api.mealviewer.com/api/v4/school/<schoolKey>/<start>/<end>/`)
  is undocumented but public and requires no authentication. It was
  confirmed by reverse-engineering the open-source
  [MMM-MealViewer](https://github.com/KevinGlinski/MMM-MealViewer)
  MagicMirror module and by testing directly against Laureate Park
  Elementary's data.
- If the school ever changes MealViewer platforms/URLs, update
  `SCHOOL_KEY` at the top of `generate_ics.py` (it's the slug from
  `https://schools.mealviewer.com/school/<schoolKey>`).
- Only school days with a published menu get events; weekends/holidays
  with no MealViewer data are silently skipped.
