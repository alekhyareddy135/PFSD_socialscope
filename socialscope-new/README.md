# SocialScope v2 — Full Stack Research Platform
## Social Media Has Both Positive and Negative Impacts on Children & Adolescents

---

## 🗂️ PROJECT STRUCTURE

```
socialscope/
│
├── app.py                    ← Flask backend + NLP engine + REST API
├── requirements.txt          ← Python dependencies (Flask only!)
├── README.md                 ← This file
│
├── templates/                ← Jinja2 HTML templates
│   ├── base.html             ← Shared layout (nav, footer, cursor glow)
│   ├── index.html            ← Homepage
│   ├── impacts.html          ← Impact analysis page
│   ├── model.html            ← Interactive working model
│   ├── analyzer.html         ← NLP Sentiment Analyzer ⭐ NEW
│   ├── quiz.html             ← 10-question knowledge quiz ⭐ NEW
│   ├── cases.html            ← 6 real-world case studies
│   ├── solutions.html        ← Stakeholder recommendations
│   ├── dashboard.html        ← Live analytics dashboard ⭐ NEW
│   └── about.html            ← Methodology & references
│
└── static/
    ├── css/
    │   └── main.css          ← Dark glassmorphism design system
    └── js/
        └── main.js           ← Cursor, nav, animations, API utils
```

---

## ⚡ QUICK START (3 steps)

### Step 1 — Install Flask
```bash
pip install flask
```
> That's the ONLY dependency. No npm, no webpack, no build step.

### Step 2 — Run the server
```bash
cd socialscope
python app.py
```

### Step 3 — Open your browser
```
http://localhost:5000
```

---

## 🗄️ MONGODB INTEGRATION

### Current state
The app runs fully with **in-memory storage** by default — no MongoDB required to start. All API endpoints work identically. Data resets on server restart.

### Connecting to MongoDB (3 steps)

**Step 1 — Install pymongo:**
```bash
pip install pymongo
```

**Step 2 — Get a MongoDB connection string:**
- Local: `mongodb://localhost:27017/`
- Atlas (free cloud): https://www.mongodb.com/cloud/atlas → Create free cluster → Get connection string

**Step 3 — Edit `app.py`:**

Find this section near the top of `app.py`:
```python
DB = {
    "analyses": [],
    "quiz_results": [],
    ...
}
```

Replace with:
```python
from pymongo import MongoClient

# Option A: Local MongoDB
client = MongoClient("mongodb://localhost:27017/")

# Option B: MongoDB Atlas
client = MongoClient("mongodb+srv://USERNAME:PASSWORD@cluster.mongodb.net/")

db = client["socialscope"]

# Now use db instead of the dict:
# db["analyses"].insert_one(doc)        instead of DB["analyses"].append(doc)
# db["analyses"].find().limit(20)       instead of DB["analyses"][-20:]
# db["stats"].find_one({"_id":"main"})  instead of DB["stats"]
```

### MongoDB Collections Schema

```
socialscope (database)
│
├── analyses          ← NLP results from /api/analyze
│   ├── id            (string, 8-char UUID)
│   ├── text_preview  (string, first 120 chars)
│   ├── sentiment     (object: score, label, emoji, confidence, keywords)
│   ├── topics        (array: [{topic, relevance}])
│   ├── key_phrases   (array of strings)
│   ├── readability_score (int)
│   ├── age_level     (string)
│   ├── word_count    (int)
│   └── timestamp     (ISO string)
│
├── quiz_results      ← Quiz submissions from /api/quiz
│   ├── id, score, total, pct, timestamp
│
├── survey_responses  ← Community survey from /api/survey
│   ├── id, age_group, daily_hours, platform, mood_effect, timestamp
│
└── stats             ← Aggregated counters
    ├── total_analyses, positive_count, negative_count
    ├── neutral_count, total_visits
```

---

## 🧠 NLP ENGINE

The custom NLP engine (built in pure Python, zero dependencies) includes:

| Feature | Description |
|---------|-------------|
| **Sentiment scoring** | 150+ word lexicon with positive/negative weights |
| **Negation handling** | Detects "not", "never", "isn't" etc. and flips polarity |
| **Topic detection** | 8 topic clusters (mental health, cyberbullying, body image, education, etc.) |
| **Key phrase extraction** | Stop-word filtered token frequency ranking |
| **Readability scoring** | Sentence-length based Flesch-style score |
| **Age-level estimation** | Maps readability to child/teen/adult |
| **Score normalisation** | sqrt(word_count) dampener prevents long-text bias |

### API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/analyze` | Run NLP on submitted text |
| GET | `/api/analyses` | Get last 20 analyses |
| GET | `/api/stats` | Get aggregated sentiment stats |
| POST | `/api/quiz` | Save quiz result |
| POST | `/api/survey` | Save survey response |
| GET | `/api/survey/results` | Get aggregated survey data |
| GET | `/api/health` | Health check |

### Example API call
```javascript
// From any frontend page:
const response = await fetch('/api/analyze', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ text: "Instagram makes teenagers feel anxious..." })
});
const result = await response.json();
// result.sentiment.label → "negative"
// result.sentiment.score → -0.623
// result.topics → [{ topic: "Mental Health", relevance: 75 }]
```

---

## 🌐 WEBSITE PAGES

| Page | URL | Description |
|------|-----|-------------|
| Home | `/` | Hero, features overview, tech stack |
| Impacts | `/impacts` | 6 positive + 6 negative cards + age table |
| Working Model | `/model` | 5-variable interactive simulator |
| **NLP Analyzer** | `/analyzer` | **Paste text → instant AI analysis** |
| **Knowledge Quiz** | `/quiz` | **10-question research-backed quiz** |
| Case Studies | `/cases` | 6 documented real-world cases |
| Solutions | `/solutions` | 4-audience filterable recommendations |
| **Live Dashboard** | `/dashboard` | **Real-time stats + community survey** |
| About | `/about` | Methodology, researchers, 12 references |

---

## 🎨 DESIGN SYSTEM

The UI uses a **dark glassmorphism** aesthetic with:
- **Colors**: Cyan `#00f5d4` accent, dark `#06070d` background
- **Fonts**: Syne (display/headings) + Inter (body)
- **Cards**: `rgba(255,255,255,.04)` glass with blur backdrop
- **Cursor glow**: Radial gradient following mouse
- **Animated background**: Blurred orbs + CSS grid overlay
- **Scroll animations**: IntersectionObserver fade-up
- **Counters**: Animated number counting on scroll

---

## 🚀 DEPLOYMENT

### Option A — Heroku
```bash
# Create Procfile:
echo "web: python app.py" > Procfile

# Deploy:
heroku create socialscope-app
git push heroku main
```

### Option B — Render (free)
1. Push code to GitHub
2. Go to render.com → New Web Service
3. Connect GitHub repo
4. Build command: `pip install -r requirements.txt`
5. Start command: `python app.py`

### Option C — Railway
```bash
railway init
railway add
railway up
```

### For production: change `app.run()` to:
```python
import os
app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=False)
```

---

## ✅ FEATURE CHECKLIST

### Core Requirements
- [x] Social media impact research — both positive & negative
- [x] Interactive working model with real-time outcome prediction
- [x] 6 real-world case studies with citations
- [x] Solutions for 4 stakeholder groups

### Enhanced Features (NEW)
- [x] **NLP Sentiment Analysis** — real backend API
- [x] **10-question Knowledge Quiz** with explanations
- [x] **Live Analytics Dashboard** with auto-refresh
- [x] **Community Survey** with MongoDB-ready storage
- [x] **REST API** with 7 endpoints
- [x] **Dark glassmorphism UI** with cursor glow, animated orbs
- [x] **Counter animations**, scroll reveals, micro-interactions
- [x] **MongoDB schema** — fully documented, swap-ready

### Tech Stack
- [x] Python 3 + Flask backend
- [x] Custom NLP engine (no external ML libraries needed)
- [x] MongoDB-ready architecture (runs in-memory by default)
- [x] Responsive design (mobile + desktop)
- [x] Zero npm dependencies

---

## 🔧 TROUBLESHOOTING

**Port already in use:**
```bash
python app.py --port 5001
# or kill the process using port 5000:
lsof -i :5000 | grep LISTEN | awk '{print $2}' | xargs kill
```

**Fonts not loading:**
→ Check internet connection. Fonts load from Google Fonts CDN.
→ Fallback: system-ui is used if CDN fails.

**NLP returns empty results:**
→ Make sure text is at least 10 characters
→ Check browser console for API errors (F12)

**MongoDB connection refused:**
→ Make sure mongod service is running: `sudo systemctl start mongod`
→ For Atlas: whitelist your IP in Network Access settings

---

*SocialScope v2 · Python + Flask + NLP + MongoDB · Academic Research Project · 2025*
