# 🐀 Los Ratones Match Calendar

Auto-updating ICS calendar feed for [Los Ratones](https://liquipedia.net/leagueoflegends/Los_Ratones) League of Legends matches.

## 📅 Subscribe to the Calendar

Once deployed, add this URL to your calendar app:

```
https://YOUR_USERNAME.github.io/los-ratones-calendar/los_ratones.ics
```

(or use my link) https://alexvbp.github.io/Los-Ratones-Calendar/los_ratones.ics

Works with:
- Google Calendar (Settings → Add calendar → From URL)
- Apple Calendar (File → New Calendar Subscription)
- Outlook (Add calendar → Subscribe from web)
- Any app that supports ICS feeds

## 🚀 Quick Setup

### 1. Create the Repository

Click "Use this template" or fork this repo, or create a new repo and copy the files.

### 2. Enable GitHub Pages

1. Go to your repo's **Settings** → **Pages**
2. Under "Build and deployment", select **GitHub Actions** as the source
3. Save

### 3. Run the Workflow

The calendar will automatically update every 6 hours. To trigger immediately:

1. Go to **Actions** tab
2. Select "Update Calendar" workflow
3. Click **Run workflow**

### 4. Get Your Calendar URL

After the first successful run, your calendar will be available at:

```
https://YOUR_USERNAME.github.io/los-ratones-calendar/los_ratones.ics
```

## 🔧 Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Generate calendar
python generate_calendar.py

# Output will be in ./public/
```

## 📁 Project Structure

```
├── .github/
│   └── workflows/
│       └── update-calendar.yml  # GitHub Actions workflow
├── generate_calendar.py          # Main script
├── requirements.txt              # Python dependencies
└── README.md
```

## ⚙️ Customization

### Change Update Frequency

Edit `.github/workflows/update-calendar.yml`:

```yaml
schedule:
  - cron: '0 */6 * * *'  # Every 6 hours
  # - cron: '0 * * * *'  # Every hour
  # - cron: '0 0 * * *'  # Daily at midnight
```

### Add More Teams

Modify `generate_calendar.py` to scrape additional team pages and merge the calendars.

## 📊 Data Source

Match data is scraped from [Liquipedia](https://liquipedia.net/leagueoflegends/Los_Ratones).

## 📄 License

MIT - Feel free to adapt for other esports teams!
