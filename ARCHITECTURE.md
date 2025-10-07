# Property Search Report Generator - Architecture Documentation

**Generated:** 7 October 2025  
**Version:** 1.0  
**Status:** Production-ready (local), deployed to Render.com  
**Last Updated:** 7 October 2025

---

## 🏗️ System Architecture

### **Tech Stack**
- **Backend:** Python 3 + Flask web framework
- **AI/ML:** Anthropic Claude Sonnet 4 API
- **PDF Processing:** pdfplumber library
- **Database:** SQLite (local file-based)
- **Frontend:** HTML + Tailwind CSS (CDN)
- **Hosting:** Render.com (free tier)

---

## 📁 Project Structure

```
property-search-app/
├── app.py                          # Main Flask application
├── requirements.txt                # Python dependencies
├── README.md                       # Setup documentation
├── ARCHITECTURE.md                 # This file
├── property_reports.db             # SQLite database (auto-created)
├── templates/                      # HTML templates
│   ├── login.html                 # Password protection page
│   ├── upload.html                # Main upload interface
│   ├── results.html               # Report download page
│   └── history.html               # Report history view
├── uploads/                       # Temporary PDF storage (auto-deleted)
│   └── YYYYMMDD_HHMMSS/          # Timestamped folders per upload
├── reports/                       # Generated HTML reports (persistent)
│   └── YYYYMMDD_HHMMSS/          # Timestamped folders per property
└── venv/                         # Python virtual environment (local only)
```

---

## 🔄 Data Flow

### **1. Upload Process**
```
User uploads 3 PDFs
    ↓
Flask receives files
    ↓
Save to temporary folder (uploads/YYYYMMDD_HHMMSS/)
    ↓
Identify report types by filename patterns
    ↓
Extract text using pdfplumber
    ↓
Send text to Claude API for analysis
    ↓
Claude returns structured JSON with signals
    ↓
Consolidate signals from all 3 reports
    ↓
Generate 2 HTML reports (internal + client)
    ↓
Save reports to reports/YYYYMMDD_HHMMSS/
    ↓
Store metadata in SQLite database
    ↓
Delete temporary uploaded PDFs
    ↓
Redirect to results page
```

### **2. Report Generation Logic**
```
Raw PDFs → pdfplumber → Plain text
    ↓
Plain text → Claude API → Structured signals (JSON)
    ↓
Signals → Python processing → HTML generation
    ↓
Single dataset → 2 report modes:
    - Internal: All signals (red/amber/green) + technical language
    - Client: Only red/amber signals + plain English
```

---

## 🗄️ Database Schema

### **Table: reports**
```sql
CREATE TABLE reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    property_address TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    internal_report_path TEXT,
    client_report_path TEXT,
    signal_count INTEGER,
    red_count INTEGER,
    amber_count INTEGER,
    green_count INTEGER
);
```

**Purpose:** Tracks all generated reports for history/retrieval

---

## 🤖 AI Integration (Claude API)

### **Model Used**
- Claude Sonnet 4 (claude-sonnet-4-20250514)
- 8,000 max tokens output
- Temperature: Default 1.0 (can be tuned to 0.3 for consistency)

### **Prompt Structure**
Each PDF type (Local Authority, Environmental, Drainage & Water) has a **custom extraction prompt** that:

1. **Defines output format** (JSON with specific fields)
2. **Sets risk grading rules** (red/amber/green criteria)
3. **Provides extraction guidelines** (what to look for)
4. **Includes example actions** (for consistency)

**Key Prompt Components:**
- `propertyAddress`: Extracted address (Title Case)
- `signals[]`: Array of findings with:
  - `signal`: Short title
  - `category`: Local Authority | Environmental | Drainage & Water
  - `description`: Technical description with evidence quote
  - `impact`: Effect on transaction/client/lender
  - `trafficLight`: red | amber | green
  - `recommendedAction`: Technical action for conveyancers
  - `clientExplanation`: Plain English for clients

**Extraction Prompt Location:** `get_extraction_prompt()` function in app.py (lines ~50-200)

---

## 📊 Report Types

### **Internal Report**
- **Audience:** Conveyancers, paralegals
- **Content:** ALL signals (red, amber, green)
- **Language:** Technical, legal terminology
- **Actions:** Specific conveyancing steps
- **Styling:** Dark grey header (#2c3e50), "INTERNAL USE ONLY" watermark
- **Filename suffix:** `_INTERNAL.html`

### **Client Report**
- **Audience:** Property buyers
- **Content:** Only red + amber signals (excludes green "all clear")
- **Language:** Plain English, neurodivergent-friendly
- **Actions:** What client needs to know/do
- **Styling:** Blue header (#1d70b8), "FOR CLIENT" watermark
- **Features:** Intro text explaining the report
- **Filename suffix:** `_CLIENT.html`

---

## 🎨 Signal Categorization

### **Traffic Light System**

#### **RED (Significant - Immediate Action)**
- Section 106 obligations
- Flood risk ≥1% annual probability
- Sewer within property boundary
- Planning enforcement notices
- Not connected to surface water sewer
- Contaminated land notices
- Compulsory purchase orders

#### **AMBER (Advisory - Requires Consideration)**
- Road not adopted by council
- Conservation area restrictions
- Tree Preservation Orders (TPOs)
- Building regulation issues
- CIL applicable
- Radon 1-3%
- Sewer within 3m-30m
- Pumping stations nearby
- Multiple "insured" responses
- Planning applications on record
- Smoke Control Area

#### **GREEN (Clear - No Action Needed)**
- Road IS adopted
- No planning issues
- No flood risk
- All connections confirmed
- Radon <1%
- No conservation restrictions
- No enforcement notices

---

## 🔒 Security Features

### **Password Protection**
- Session-based authentication
- Password: `beagle2024` (hardcoded in app.py line ~21)
- Login required for all pages except `/login`
- No user accounts (single shared password)

**Implementation:**
```python
@app.before_request
def check_password():
    if request.endpoint == 'login' or request.endpoint == 'static':
        return None
    if not session.get('authenticated'):
        return redirect(url_for('login'))
```

### **API Key Security**
- Stored as environment variable: `ANTHROPIC_API_KEY`
- Not hardcoded in code (GitHub Secret Scanning compliance)
- Set via Render.com environment variables in production
- Set via `export` command locally

**Critical:** Never commit API keys to Git. Use environment variables only.

---

## 💰 Cost Structure

### **Per Property Report (3 PDFs)**
- **Claude API:** £0.03-0.05
- **Hosting (Render Free):** £0
- **Hosting (Render Starter):** £0.17 (if 30 properties/month)
- **Storage:** Negligible (~1MB per property)

### **Total Cost Per Report**
- **Free tier:** £0.03-0.05 (API only)
- **Starter tier:** £0.20-0.25 per property
- **Margins at £10/property:** 97-98% profit
- **Margins at £15/property:** 98-99% profit

### **Monthly Cost Examples**
- **100 properties/month:** £3-5 API + £7 hosting = £10-12 total
- **500 properties/month:** £15-25 API + £25 hosting = £40-50 total

---

## 🚀 Deployment

### **Current Setup: Render.com**
- **URL:** https://property-search-app.onrender.com
- **Plan:** Free tier (512MB RAM)
- **Limitations:** 
  - Spins down after 15 mins inactivity (50s cold start)
  - May timeout with large PDFs or concurrent users
  - 502 errors when processing heavy loads
- **Environment Variables:**
  - `ANTHROPIC_API_KEY`: Set in Render dashboard
- **Build Command:** `pip install -r requirements.txt`
- **Start Command:** `gunicorn app:app`

### **Local Development**
```bash
# Setup
cd ~/Desktop/property-search-app
source venv/bin/activate
export ANTHROPIC_API_KEY="your-key"

# Run
python3 app.py

# Access
http://localhost:5001
Password: beagle2024
```

### **GitHub Repository**
- **URL:** https://github.com/NonPerTutti2025/property-search-app
- **Branch:** main
- **Auto-deploy:** Enabled on Render (pushes to main trigger deployment)

---

## 📋 File Type Detection

**Automatic report type identification via filename patterns:**

```python
REPORT_PATTERNS = {
    "Environmental": ["environmental", "martello", "climate"],
    "Drainage & Water": ["drainage", "water"],
    "Local Authority": ["local", "authority", "search"]
}
```

**Case-insensitive matching on filename to determine which extraction prompt to use.**

---

## 🔄 Report Ordering

**All sections follow consistent order:**
1. **Local Authority** (first)
2. **Environmental** (second)
3. **Drainage & Water** (third)

**Applied to:**
- "At a Glance" summary boxes
- "Important Points" action list
- "Detailed Findings" sections

**Controlled by:** 
```python
SECTION_ORDER = ["Local Authority", "Environmental", "Drainage & Water"]
```

**Fixed in:** Version 1.0 (7 Oct 2025) - actions now correctly sorted by category

---

## 🐛 Known Issues & Limitations

### **1. Render Free Tier Issues**
- **502 errors** when processing large PDFs (>20MB combined)
- **Timeouts** after ~2.5 minutes of processing
- **Solution:** Upgrade to Starter plan (£7/month) for 2GB RAM

### **2. AI Consistency**
- Claude may give slightly different results for same PDFs
- Non-deterministic by nature (temperature=1.0 default)
- **Solution:** Add `temperature=0.3` parameter for more consistency
- **Status:** Not yet implemented

### **3. iCloud Drive PDFs**
- Files not fully downloaded locally cause "all clear" false results
- pdfplumber can't read placeholder files
- **Solution:** Download PDFs locally before uploading

### **4. Scanned/Image PDFs**
- pdfplumber can't extract text from image-based PDFs
- Requires OCR (not implemented)
- **Solution:** Ensure PDFs are text-based, not scanned images
- **Future:** Implement pytesseract OCR

### **5. Password Protection**
- Single shared password (not scalable)
- No user accounts or access control
- Session management is basic
- **Solution:** Implement proper auth system in v2

### **6. No Email Delivery**
- Reports must be manually downloaded
- No automated client notifications
- **Solution:** Add email integration (Sendgrid, Postmark)

---

## 🔧 Configuration Variables

### **In app.py:**
```python
ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY')  # Line ~19
APP_PASSWORD = "beagle2024"                               # Line ~21
UPLOAD_FOLDER = 'uploads'                                # Line ~14
REPORT_FOLDER = 'reports'                                # Line ~15
DATABASE = 'property_reports.db'                         # Line ~16
SECTION_ORDER = ["Local Authority", "Environmental", "Drainage & Water"]  # Line ~24
```

### **Flask Settings:**
```python
app.secret_key = 'your-secret-key-change-this-in-production'  # Line ~18
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024          # Line ~19 (50MB max)
```

### **Claude API Settings:**
```python
model="claude-sonnet-4-20250514"  # Model version
max_tokens=8000                   # Response length limit
# temperature not set (defaults to 1.0)
```

---

## 📈 Scalability Considerations

### **Current Capacity**
- **Free tier:** 5-10 properties/day max
- **Starter tier:** 50-100 properties/day
- **Pro tier:** 500+ properties/day

### **Bottlenecks**
1. **Claude API rate limits** (tier-dependent)
2. **RAM constraints** (Render plan limits)
3. **Single-worker gunicorn** (no concurrency)
4. **Synchronous processing** (blocks during PDF processing)

### **Future Improvements**
- Add Redis for caching processed PDFs
- Implement background job queue (Celery/RQ)
- Multi-worker deployment
- Load balancing across multiple instances
- Move to PostgreSQL for better concurrent access
- Add CDN for static assets
- Implement request queuing

---

## 🔐 Environment Variables Required

### **Production (Render.com):**
```
ANTHROPIC_API_KEY=sk-ant-api03-xxx...
```

### **Local Development:**
```bash
export ANTHROPIC_API_KEY="sk-ant-api03-xxx..."
```

### **To Rotate API Key:**
1. Generate new key at https://console.anthropic.com/settings/keys
2. Update environment variable in Render dashboard
3. Trigger manual deploy or wait for auto-deploy
4. Old key can be deleted after successful deployment

---

## 📝 Dependencies (requirements.txt)

```
Flask==3.0.0              # Web framework
anthropic==0.34.0         # Claude API client (upgraded from 0.31.0)
pdfplumber==0.11.0        # PDF text extraction
Werkzeug==3.0.1           # Flask dependency
gunicorn==21.2.0          # Production WSGI server
```

**Note:** `anthropic` library was upgraded on 7 Oct 2025 to fix `proxies` parameter error.

---

## 🎯 Success Metrics

### **Technical:**
- Report generation time: 30-60 seconds per property
- Extraction accuracy: ~95% (manual validation needed)
- PDF compatibility: Text-based PDFs only (no OCR)
- Uptime: 99.9% target (Render free tier: ~95%)

### **Business:**
- Cost per report: £0.03-0.25
- Suggested pricing: £10-15 per property
- Margin: 93-97%
- Break-even: ~5 properties/month on starter tier

---

## 🚧 Roadmap / Future Features

### **Phase 2 (Post-Launch):**
- [ ] Email delivery of client reports (Sendgrid integration)
- [ ] PDF export (HTML → PDF conversion via wkhtmltopdf)
- [ ] OCR for scanned PDFs (pytesseract)
- [ ] User accounts & multi-tenancy
- [ ] Usage analytics dashboard
- [ ] Bulk upload (multiple properties at once)
- [ ] Temperature parameter for consistency (0.3)
- [ ] Better error handling and user feedback

### **Phase 3 (Scale):**
- [ ] API for integrations
- [ ] White-label branding options
- [ ] Stripe payment integration
- [ ] Mobile app (React Native)
- [ ] AI training on custom data
- [ ] Report editing interface
- [ ] Webhook notifications
- [ ] Advanced search/filtering

---

## 📞 Support & Maintenance

### **Current Status:**
- **Built by:** Jason (solo developer)
- **Maintained by:** TBD (ownership discussion pending)
- **Support:** None (self-serve only)
- **Documentation:** This file + README.md

### **Future Needs:**
- Customer support system (Intercom, Zendesk)
- Error monitoring (Sentry)
- Uptime monitoring (UptimeRobot, Pingdom)
- Analytics (Google Analytics, Mixpanel)
- Documentation site (GitBook, Notion)

---

## 🔄 Version History

### **v1.0 - 7 October 2025**
- Initial production release
- Password protection added
- Dual-mode reports (internal + client)
- Report ordering fixed (Local Authority → Environmental → Drainage & Water)
- Deployed to Render.com
- SQLite database for history
- GitHub repository created

### **Planned v1.1:**
- Temperature parameter (0.3)
- Email delivery
- Better error messages
- PDF export

---

## 📖 Related Documentation

- **README.md** - Setup and deployment instructions
- **GitHub Issues** - Bug tracking and feature requests (when created)
- **Anthropic API Docs** - https://docs.anthropic.com
- **Flask Documentation** - https://flask.palletsprojects.com
- **Render Docs** - https://render.com/docs

---

## ⚠️ Important Notes

1. **Never commit API keys** - Always use environment variables
2. **Test locally first** - Don't push breaking changes to production
3. **Backup database regularly** - SQLite file contains all history
4. **Monitor costs** - Claude API usage can add up with high volume
5. **Update this doc** - Keep architecture documentation current

---

## 🆘 Troubleshooting

### **"502 Bad Gateway" Error**
- **Cause:** Out of memory or timeout on Render free tier
- **Fix:** Upgrade to Starter plan or reduce PDF sizes

### **"Authentication failed" Error**
- **Cause:** API key missing or invalid
- **Fix:** Check `ANTHROPIC_API_KEY` environment variable

### **"All Clear" False Results**
- **Cause:** iCloud placeholder files or scanned PDFs
- **Fix:** Download PDFs locally, ensure text-based

### **Reports Not Consistent**
- **Cause:** AI non-determinism (temperature=1.0)
- **Fix:** Add temperature parameter or cache results

### **App Won't Start Locally**
- **Cause:** Missing dependencies or API key
- **Fix:** `pip install -r requirements.txt` and set API key

---

**End of Documentation**

*This architecture document reflects the system as of 7 October 2025.*  
*Update this file whenever significant changes are made to the system.*  
*Version control via Git ensures historical tracking of architecture changes.*
