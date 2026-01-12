# 🔥 Dropshipping Trend Detection System

Automated system for detecting trending products suitable for dropshipping by analyzing Amazon Best Sellers and Google Trends data.

## ✨ Features

- **Automated Daily Scans**: Runs at 6am UTC daily
- **Multi-Source Analysis**: Scrapes Amazon Best Sellers + Google Trends
- **AI-Powered Insights**: Google Gemini provides product analysis
- **Smart Scoring Algorithm**: 0-100 score based on velocity, recency, price, and competition
- **Discord Notifications**: Get notified of hot products (score ≥70)
- **Supabase Storage**: All data stored in PostgreSQL for historical tracking
- **Production Ready**: Runs on Render free tier with error handling and retries

## 🏗️ Architecture

```
┌─────────────────┐
│   Render Cron   │ (6am UTC daily)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  FastAPI App    │
│   + Scheduler   │
└────────┬────────┘
         │
         ├─► Amazon Scraper (Playwright)
         │   └─► Top 50 in 5 categories
         │
         ├─► Google Trends API (pytrends)
         │   └─► Search volume & velocity
         │
         ├─► Google Gemini AI
         │   └─► Product insights
         │
         ├─► Trend Analyzer
         │   └─► Calculate 0-100 scores
         │
         ├─► Supabase Database
         │   └─► Store top 10 products
         │
         └─► Discord Webhook
             └─► Notify team
```

## 📋 Prerequisites

- Python 3.11+
- Supabase account (free tier)
- Discord webhook URL
- Google Gemini API key
- Render account (free tier)
- GitHub account

## 🚀 Quick Start - Deploy to Render

### Step 1: Clone and Setup Repository

```bash
# Navigate to project directory
cd "Daniel Dropshipping"

# Initialize git
git init
git add .
git commit -m "Initial commit - Dropshipping Trend Detector"

# Create GitHub repo and push
# (Create repo on GitHub first, then run these commands)
git remote add origin https://github.com/YOUR_USERNAME/dropshipping-trend-detector.git
git branch -M main
git push -u origin main
```

### Step 2: Setup Supabase Database

1. **Login to Supabase**: [supabase.com/dashboard](https://supabase.com/dashboard)

2. **Create Project** (if needed):
   - Name: `Dropshipping Detector`
   - Database Password: (create strong password)
   - Region: Choose closest region
   - Plan: **Free**

3. **Get API Credentials**:
   - Go to **Settings** → **API**
   - Copy `Project URL` and `anon public` key

4. **Create Database Tables**:
   - Click **SQL Editor** → **New Query**
   - Paste and run this SQL:

```sql
-- Create trending_products table
CREATE TABLE trending_products (
    id SERIAL PRIMARY KEY,
    product_name TEXT NOT NULL,
    category TEXT NOT NULL,
    source_url TEXT NOT NULL,
    trend_score DECIMAL(5,2) NOT NULL,
    search_volume INTEGER DEFAULT 0,
    price_estimate DECIMAL(10,2),
    first_seen_date TIMESTAMP DEFAULT NOW(),
    last_updated TIMESTAMP DEFAULT NOW(),
    status TEXT DEFAULT 'active',
    notes TEXT
);

-- Create trend_history table
CREATE TABLE trend_history (
    id SERIAL PRIMARY KEY,
    product_id INTEGER REFERENCES trending_products(id) ON DELETE CASCADE,
    trend_score DECIMAL(5,2) NOT NULL,
    search_volume INTEGER DEFAULT 0,
    recorded_at TIMESTAMP DEFAULT NOW()
);

-- Create indexes for performance
CREATE INDEX idx_trending_products_status ON trending_products(status);
CREATE INDEX idx_trending_products_score ON trending_products(trend_score DESC);
CREATE INDEX idx_trend_history_product_id ON trend_history(product_id);
CREATE INDEX idx_trend_history_recorded_at ON trend_history(recorded_at DESC);
```

### Step 3: Setup Discord Webhook

1. Open Discord and select your server
2. Go to **Server Settings** → **Integrations** → **Webhooks**
3. Click **New Webhook**
4. Configure:
   - Name: `Trend Detective`
   - Channel: Select notification channel
5. **Copy Webhook URL**
6. Click **Save**

### Step 4: Get Google Gemini API Key

1. Go to [Google AI Studio](https://makersuite.google.com/app/apikey)
2. Sign in with Google account
3. Click **Get API Key** or **Create API Key**
4. Choose **Create API key in new project**
5. **Copy the API key**

### Step 5: Deploy to Render

1. **Login to Render**: [dashboard.render.com](https://dashboard.render.com)

2. **Connect GitHub**:
   - If not connected: **Settings** → **Connect GitHub**
   - Authorize Render

3. **Create Web Service**:
   - Click **New +** → **Web Service**
   - Select your GitHub repository: `dropshipping-trend-detector`
   - Click **Connect**

4. **Configure Service** (auto-detected from render.yaml):
   - Name: `dropshipping-trend-detector`
   - Region: `Oregon (US West)`
   - Branch: `main`
   - Plan: **Free**

5. **Add Environment Variables**:
   
   Scroll to **Environment Variables** and add:

   ```
   SUPABASE_URL=https://xxxxx.supabase.co
   SUPABASE_KEY=eyJhbGc...your-key
   DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
   GEMINI_API_KEY=AIzaSy...your-key
   ```

6. **Click "Create Web Service"**

7. **Wait for deployment** (5-10 minutes)

8. **Verify deployment**:
   - Visit: `https://your-app-name.onrender.com/health`
   - Should see: `{"status": "healthy", ...}`

9. **Check Discord** for notification within 5 minutes!

## 🎯 API Endpoints

### `GET /`
Root endpoint with app info

**Response:**
```json
{
  "name": "Dropshipping Trend Detector",
  "version": "1.0.0",
  "status": "running"
}
```

### `GET /health`
Health check for monitoring

**Response:**
```json
{
  "status": "healthy",
  "environment": "production",
  "cron_schedule": "06:00 UTC"
}
```

### `GET /api/trends?limit=10`
Get top trending products from database

**Response:**
```json
{
  "success": true,
  "count": 10,
  "products": [
    {
      "id": 1,
      "product_name": "...",
      "category": "Electronics",
      "trend_score": 87.5,
      "search_volume": 85,
      "price_estimate": 45.99,
      ...
    }
  ]
}
```

### `POST /api/trigger-scan`
Manually trigger a trend detection scan

**Response:**
```json
{
  "success": true,
  "message": "Trend detection scan started"
}
```

## 📊 Scoring Algorithm

Products are scored 0-100 based on:

### 1. Search Volume Velocity (40%)
Rate of increase in Google Trends
- >100% growth: 25 points
- 50-100%: 20 points
- 20-50%: 15 points
- <20%: 5-10 points

### 2. Recency/Rank (30%)
Position in Amazon Best Sellers
- Top 10: 30 points
- Top 25: 25 points
- Top 50: 20 points

### 3. Price Point (20%)
Dropshipping viability ($15-$150 ideal)
- $25-75: 20 points (sweet spot)
- $15-150: 15 points (good)
- Outside range: 5-10 points

### 4. Competition (10%)
Estimated from search volume
- Low (<30): 10 points
- Medium (30-60): 7 points
- High (>60): 2-4 points

**🔥 Hot Products**: Score ≥70

## ⚙️ Configuration

Create `.env` file (use `.env.example` as template):

```env
# Supabase
SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_KEY=your_anon_key

# Discord
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...

# Google Gemini AI
GEMINI_API_KEY=AIzaSy...

# Schedule (UTC)
CRON_HOUR=6
CRON_MINUTE=0

# Scraping
REQUEST_DELAY=3
MAX_RETRIES=3
TIMEOUT=30
```

## 🔍 Monitoring & Logs

- **Render Logs**: Dashboard → Your Service → Logs
- **Discord Notifications**: Sent after each run
- **Error Notifications**: Sent to Discord on failures
- **Database**: Check Supabase Table Editor

## 🛠️ Local Development (Optional)

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers
playwright install chromium

# Create .env file
cp .env.example .env
# Edit .env with your credentials

# Run locally
uvicorn app.main:app --reload

# Access at: http://localhost:8000
# API docs: http://localhost:8000/docs
```

## 🐛 Troubleshooting

### Amazon Blocking Requests
- Playwright uses real browser to avoid basic blocks
- Increase `REQUEST_DELAY` if needed
- Check Render logs for specific errors
- App continues with Google Trends if Amazon fails

### Google Trends Rate Limiting
- Built-in retry logic with backoff
- 1 second delay between requests
- Reduce products analyzed if persistent

### Playwright on Render
- Chromium installed automatically
- Uses `--with-deps` for system libraries
- Monitor memory usage (512MB on free tier)

### Gemini API Issues
- Check API key is valid
- Free tier: 60 requests/minute
- App works without Gemini (just no AI insights)

### Discord Not Receiving Notifications
- Verify webhook URL is correct
- Test webhook manually in Discord settings
- Check Render logs for error messages

## 💰 Cost Breakdown

- **Render Free Tier**: $0 (750 hours/month)
- **Supabase Free Tier**: $0 (500MB database)
- **Discord Webhooks**: $0
- **Google Gemini**: $0 (free tier)
- **Amazon/Google Scraping**: $0

**Total Monthly Cost**: $0 🎉

## 📁 Project Structure

```
dropshipping-trend-detector/
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI application
│   ├── config.py               # Configuration settings
│   ├── models.py               # Data models
│   ├── database.py             # Supabase operations
│   ├── scheduler.py            # Cron job scheduler
│   ├── scrapers/
│   │   ├── __init__.py
│   │   ├── amazon_scraper.py   # Amazon Best Sellers scraper
│   │   └── google_trends.py    # Google Trends API
│   └── services/
│       ├── __init__.py
│       ├── trend_analyzer.py   # Scoring algorithm
│       ├── gemini_analyzer.py  # AI insights
│       └── discord_notifier.py # Discord notifications
├── requirements.txt            # Python dependencies
├── render.yaml                 # Render deployment config
├── .env.example               # Environment template
├── .gitignore
└── README.md
```

## 🔐 Security Best Practices

1. **Never commit `.env` file** (already in .gitignore)
2. **Use environment variables** for all secrets
3. **Rotate API keys** periodically
4. **Use `anon` key** for Supabase (not service_role)
5. **Keep Discord webhook URL private**

## 🚀 Future Enhancements

- [ ] TikTok trend integration
- [ ] Competitor price tracking
- [ ] Email notifications
- [ ] Web dashboard UI
- [ ] Product profitability calculator
- [ ] Supplier auto-discovery
- [ ] Multi-marketplace support (eBay, Etsy)
- [ ] Historical trend analysis charts

## 📝 Database Schema

### trending_products
| Column | Type | Description |
|--------|------|-------------|
| id | SERIAL | Primary key |
| product_name | TEXT | Product name |
| category | TEXT | Amazon category |
| source_url | TEXT | Amazon product URL |
| trend_score | DECIMAL(5,2) | Score 0-100 |
| search_volume | INTEGER | Google Trends volume |
| price_estimate | DECIMAL(10,2) | Price in USD |
| first_seen_date | TIMESTAMP | First detection |
| last_updated | TIMESTAMP | Last update |
| status | TEXT | active/archived |
| notes | TEXT | Additional info + AI insights |

### trend_history
| Column | Type | Description |
|--------|------|-------------|
| id | SERIAL | Primary key |
| product_id | INTEGER | Foreign key |
| trend_score | DECIMAL(5,2) | Score at time |
| search_volume | INTEGER | Volume at time |
| recorded_at | TIMESTAMP | Record time |

## 🤝 Support

For issues or questions:
1. Check Render logs
2. Verify environment variables
3. Test endpoints individually
4. Check Discord for error notifications

## 📄 License

MIT License - Feel free to modify and use commercially

---

**Built with ❤️ for dropshippers by Uncle Peter**

🔥 Happy dropshipping! 🚀
