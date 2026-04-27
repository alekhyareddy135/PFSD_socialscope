"""
SocialScope v4.0 — Flask Backend
NLP Engine + MongoDB Atlas Integration
ALL FEATURES: Chat Analysis, Mood Check-in, AI Chatbot, Biometric, Voice/Face
"""

from flask import Flask, request, jsonify, render_template
import re, math, os, datetime, uuid, json, random

# ─── MONGODB SETUP ───────────────────────────────────────────────────────────
from pymongo import MongoClient, DESCENDING
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError

MONGO_URI = "mongodb+srv://alekhya:abcd12345@cluster0.0drbf38.mongodb.net/?appName=Cluster0"
DB_NAME = "socialscope"

try:
    _client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    _client.admin.command("ping")
    mongo_db = _client[DB_NAME]
    MONGO_CONNECTED = True
    print("MongoDB Atlas connected!")
except (ConnectionFailure, ServerSelectionTimeoutError) as e:
    print(f"MongoDB connection failed: {e}  ->  falling back to in-memory store.")
    mongo_db = None
    MONGO_CONNECTED = False

# ─── IN-MEMORY FALLBACK ───────────────────────────────────────────────────────
_MEM = {
    "analyses":         [],
    "quiz_results":     [],
    "survey_responses": [],
    "voice_analyses":   [],
    "face_analyses":    [],
    "chat_analyses":    [],
    "mood_checkins":    [],
    "chatbot_logs":     [],
    "stats": {
        "total_analyses": 0,
        "positive_count": 0,
        "negative_count": 0,
        "neutral_count":  0,
        "total_visits":   0,
    }
}

# ─── DB HELPERS ───────────────────────────────────────────────────────────────

def _col(name):
    return mongo_db[name] if MONGO_CONNECTED else None


def db_insert(collection, doc):
    c = _col(collection)
    if c is not None:
        result = c.insert_one(doc)
        doc["_id"] = str(result.inserted_id)
    else:
        if collection not in _MEM:
            _MEM[collection] = []
        _MEM[collection].append(doc)
    return doc


def db_find_recent(collection, limit=20):
    c = _col(collection)
    if c is not None:
        return list(c.find({}, {"_id": 0}).sort("timestamp", DESCENDING).limit(limit))
    return list(reversed(_MEM.get(collection, [])[-limit:]))


def db_find_by_field(collection, field, value, limit=30):
    c = _col(collection)
    if c is not None:
        return list(c.find({field: value}, {"_id": 0}).sort("timestamp", DESCENDING).limit(limit))
    filtered = [d for d in _MEM.get(collection, []) if d.get(field) == value]
    return list(reversed(filtered[-limit:]))


def db_count(collection):
    c = _col(collection)
    return c.count_documents({}) if c is not None else len(_MEM.get(collection, []))


def db_aggregate_field(collection, field):
    c = _col(collection)
    if c is not None:
        pipeline = [{"$group": {"_id": f"${field}", "count": {"$sum": 1}}}]
        return {str(r["_id"]): r["count"] for r in c.aggregate(pipeline)}
    freq = {}
    for doc in _MEM.get(collection, []):
        v = str(doc.get(field, "unknown"))
        freq[v] = freq.get(v, 0) + 1
    return freq


def stats_get():
    c = _col("stats")
    if c is not None:
        doc = c.find_one({"_id": "global"}, {"_id": 0})
        if doc is None:
            init = {"_id": "global", "total_analyses": 0, "positive_count": 0,
                    "negative_count": 0, "neutral_count": 0, "total_visits": 0}
            c.insert_one(init)
            return {k: v for k, v in init.items() if k != "_id"}
        return doc
    return dict(_MEM["stats"])


def stats_increment(field, amount=1):
    c = _col("stats")
    if c is not None:
        c.update_one({"_id": "global"}, {"$inc": {field: amount}}, upsert=True)
    else:
        _MEM["stats"][field] = _MEM["stats"].get(field, 0) + amount

# ─────────────────────────────────────────────────────────────────────────────

app = Flask(__name__, template_folder="templates", static_folder="static")
app.config["SECRET_KEY"] = "socialscope-2025"

# ═══════════════════════════════════════════════════════════════════════════
# NLP ENGINE
# ═══════════════════════════════════════════════════════════════════════════

POSITIVE_LEXICON = {
    "connect": 2, "connection": 2, "community": 2, "friendship": 2, "friend": 1,
    "social": 1, "belong": 2, "belonging": 2, "support": 2, "supportive": 2,
    "learn": 2, "education": 2, "educational": 2, "creative": 2, "creativity": 2,
    "knowledge": 2, "skill": 1, "skills": 1, "awareness": 1, "informed": 1,
    "happy": 2, "happiness": 2, "joy": 2, "confident": 2, "confidence": 2,
    "positive": 1, "wellbeing": 2, "healthy": 1, "beneficial": 2,
    "empowering": 2, "empower": 2, "inspire": 2, "motivation": 2, "motivated": 2,
    "express": 1, "expression": 2, "share": 1, "sharing": 1, "create": 1,
    "inclusive": 2, "inclusion": 2, "acceptance": 2, "accepted": 2,
    "helpful": 2, "useful": 1, "valuable": 2, "benefit": 2, "benefits": 2,
    "good": 1, "great": 2, "excellent": 2, "amazing": 2, "wonderful": 2,
    "safe": 2, "safety": 2, "protect": 2, "engage": 1,
    "love": 2, "loved": 2, "grateful": 2, "gratitude": 2, "calm": 2, "relaxed": 2,
    "peaceful": 2, "energetic": 1, "excited": 2, "hopeful": 2, "hope": 2,
}

NEGATIVE_LEXICON = {
    "anxiety": -2, "anxious": -2, "depression": -3, "depressed": -2,
    "stress": -2, "stressed": -2, "harm": -2, "harmful": -3, "danger": -2,
    "dangerous": -2, "risk": -1, "addictive": -3, "addiction": -3,
    "bully": -3, "bullying": -3, "cyberbullying": -3, "harass": -3,
    "harassment": -3, "abuse": -3, "toxic": -3, "hate": -2, "hateful": -2,
    "violence": -3, "threat": -2, "threatening": -2,
    "body image": -2, "eating disorder": -3, "anorexia": -3,
    "comparison": -1, "insecure": -2, "insecurity": -2, "shame": -2,
    "distraction": -1, "addicted": -3, "compulsive": -2, "mindless": -2,
    "passive": -1, "scrolling": -1, "wasted": -1, "manipulative": -2,
    "misinformation": -2, "fake": -1, "isolation": -2, "lonely": -2,
    "loneliness": -2, "sleep": -1, "sleepless": -2, "exhausted": -2,
    "bad": -1, "terrible": -2, "awful": -2, "horrible": -2, "negative": -1,
    "worrying": -1, "concerning": -1, "problem": -1, "issue": -1,
    "exploit": -2, "exploitation": -3, "predator": -3, "grooming": -3,
    "sad": -2, "angry": -2, "anger": -2, "frustrated": -2, "overwhelmed": -2,
    "hopeless": -3, "worthless": -3, "tired": -1, "panic": -2, "fear": -2,
}

TOPICS = {
    "mental_health":    ["depression","anxiety","mental health","wellbeing","stress","happiness","mood","emotional","psychological"],
    "cyberbullying":    ["bully","bullying","cyberbullying","harassment","harass","abuse","toxic","hate"],
    "body_image":       ["body image","appearance","weight","eating","diet","anorexia","bulimia","beauty","thin","fat","body"],
    "education":        ["learn","education","school","study","academic","knowledge","homework","skill","teach"],
    "social_connection":["friend","friendship","connect","social","community","belong","relationship","peer","lonely"],
    "screen_time":      ["screen time","hours","usage","time","addicted","addiction","compulsive","scrolling"],
    "privacy_safety":   ["privacy","safety","safe","secure","data","predator","grooming","exploit","protect"],
    "creativity":       ["creative","creativity","art","music","video","content","create","express","design"],
}


def clean_text(text):
    return re.sub(r'[^a-z0-9 ]', ' ', text.lower())

def tokenize(text):
    return clean_text(text).split()

def analyze_sentiment(text):
    tokens = tokenize(text)
    text_lower = text.lower()
    score, matched_pos, matched_neg = 0, [], []

    for phrase, val in {**POSITIVE_LEXICON, **NEGATIVE_LEXICON}.items():
        if ' ' in phrase and phrase in text_lower:
            score += val
            (matched_pos if val > 0 else matched_neg).append(phrase)

    for token in tokens:
        if token in POSITIVE_LEXICON:
            score += POSITIVE_LEXICON[token]; matched_pos.append(token)
        elif token in NEGATIVE_LEXICON:
            score += NEGATIVE_LEXICON[token]; matched_neg.append(token)

    negation_words = {"not","never","no","neither","nor","barely","hardly",
                      "isn't","aren't","wasn't","doesn't","don't"}
    if any(t in negation_words for t in tokens):
        score = -score * 0.5

    word_count = max(len(tokens), 1)
    normalized = max(-1.0, min(1.0, (score / math.sqrt(word_count)) / 3.0))

    if normalized >= 0.22:
        label, emoji, color = "positive", "😊", "#22c55e"
    elif normalized <= -0.18:
        label, emoji, color = "negative", "😟", "#ef4444"
    else:
        label, emoji, color = "neutral",  "😐", "#f59e0b"

    return {
        "score": round(normalized, 3),
        "label": label, "emoji": emoji, "color": color,
        "confidence": min(99, int(abs(normalized) * 100 + 30)),
        "keywords_positive": list(set(matched_pos))[:6],
        "keywords_negative": list(set(matched_neg))[:6],
        "word_count": word_count,
    }

def detect_topics(text):
    text_lower, tokens = text.lower(), set(tokenize(text))
    found = []
    for topic, keywords in TOPICS.items():
        hits = sum(1 for kw in keywords if kw in text_lower or kw in tokens)
        if hits:
            found.append({"topic": topic.replace("_", " ").title(), "relevance": min(100, hits * 25)})
    return sorted(found, key=lambda x: -x["relevance"])[:4]

def extract_key_phrases(text):
    stop = {"the","a","an","is","are","was","were","be","been","being","have","has","had",
            "do","does","did","will","would","could","should","may","might","shall","can",
            "this","that","these","those","i","you","he","she","it","we","they","and","or",
            "but","in","on","at","to","for","of","with","by","from","as","up","about","into",
            "through","during","before","after","above","below","between","out","off","over",
            "then","than","so","if","not","no","nor","just","very","also","when","where"}
    phrases = [w for w in tokenize(text) if w not in stop and len(w) > 3]
    freq = {}
    for p in phrases:
        freq[p] = freq.get(p, 0) + 1
    return sorted(freq, key=lambda x: -freq[x])[:8]

def full_nlp_analysis(text):
    sentiment = analyze_sentiment(text)
    readability = min(100, max(10, 120 - (len(text.split()) / max(len(re.findall(r'[.!?]', text)), 1)) * 2))
    return {
        "id": str(uuid.uuid4())[:8],
        "text_preview": text[:120] + ("..." if len(text) > 120 else ""),
        "sentiment": sentiment,
        "topics": detect_topics(text),
        "key_phrases": extract_key_phrases(text),
        "readability_score": round(readability),
        "age_level": "Child (8-12)" if readability > 80 else "Teen (13-17)" if readability > 55 else "Adult (18+)",
        "word_count": sentiment["word_count"],
        "timestamp": datetime.datetime.utcnow().isoformat(),
    }

# ═══════════════════════════════════════════════════════════════════════════
# PAGE ROUTES
# ═══════════════════════════════════════════════════════════════════════════

@app.route('/')
def index():
    stats_increment("total_visits")
    return render_template('index.html')

@app.route('/impacts')
def impacts(): return render_template('impacts.html')

@app.route('/model')
def model(): return render_template('model.html')

@app.route('/analyzer')
def analyzer(): return render_template('analyzer.html')

@app.route('/quiz')
def quiz(): return render_template('quiz.html')

@app.route('/cases')
def cases(): return render_template('cases.html')

@app.route('/solutions')
def solutions(): return render_template('solutions.html')

@app.route('/dashboard')
def dashboard(): return render_template('dashboard.html')

@app.route('/about')
def about(): return render_template('about.html')

@app.route('/wellness')
def wellness(): return render_template('wellness.html')

@app.route('/biometric')
def biometric(): return render_template('biometric.html')

@app.route('/chat-analysis')
def chat_analysis(): return render_template('chat_analysis.html')

@app.route('/mood-checkin')
def mood_checkin(): return render_template('mood_checkin.html')

@app.route('/chatbot')
def chatbot_page(): return render_template('chatbot.html')

# ═══════════════════════════════════════════════════════════════════════════
# API: CORE NLP
# ═══════════════════════════════════════════════════════════════════════════

@app.route('/api/analyze', methods=['POST'])
def api_analyze():
    data = request.get_json()
    text = (data or {}).get('text', '').strip()
    if not text or len(text) < 10:
        return jsonify({"error": "Please enter at least 10 characters"}), 400
    if len(text) > 5000:
        return jsonify({"error": "Text too long (max 5000 chars)"}), 400
    result = full_nlp_analysis(text)
    db_insert("analyses", result)
    stats_increment("total_analyses")
    stats_increment(result["sentiment"]["label"] + "_count")
    result.pop("_id", None)
    return jsonify(result)

@app.route('/api/analyses', methods=['GET'])
def api_analyses():
    docs = db_find_recent("analyses", limit=20)
    for d in docs: d.pop("_id", None)
    return jsonify(docs)

@app.route('/api/stats', methods=['GET'])
def api_stats():
    s = stats_get()
    s.pop("_id", None)
    return jsonify(s)

@app.route('/api/quiz', methods=['POST'])
def api_quiz():
    data = request.get_json()
    score, total = data.get('score', 0), data.get('total', 10)
    result = {"id": str(uuid.uuid4())[:8], "score": score, "total": total,
              "pct": round(score / total * 100), "timestamp": datetime.datetime.utcnow().isoformat()}
    db_insert("quiz_results", result)
    result.pop("_id", None)
    return jsonify({"message": "Saved", "result": result})

@app.route('/api/survey', methods=['POST'])
def api_survey():
    data = request.get_json()
    data["timestamp"] = datetime.datetime.utcnow().isoformat()
    data["id"] = str(uuid.uuid4())[:8]
    db_insert("survey_responses", data)
    return jsonify({"message": "Survey saved", "id": data["id"]})

@app.route('/api/survey/results', methods=['GET'])
def api_survey_results():
    count = db_count("survey_responses")
    if count == 0:
        return jsonify({"count": 0, "averages": {}})
    keys = ["age_group", "daily_hours", "platform", "mood_effect"]
    return jsonify({"count": count, "aggregates": {k: db_aggregate_field("survey_responses", k) for k in keys}})

# ═══════════════════════════════════════════════════════════════════════════
# API: BIOMETRIC (VOICE + FACE)
# ═══════════════════════════════════════════════════════════════════════════

@app.route('/api/voice-analyze', methods=['POST'])
def api_voice_analyze():
    data = request.get_json()
    text = (data or {}).get('text', '').strip()
    if not text or len(text) < 3:
        return jsonify({"error": "No speech detected or text too short"}), 400
    result = full_nlp_analysis(text)
    result["source"] = "voice"
    doc = {"id": result["id"], "source": "voice", "text_preview": result["text_preview"],
           "sentiment": result["sentiment"], "word_count": result["word_count"], "timestamp": result["timestamp"]}
    db_insert("voice_analyses", doc)
    stats_increment("total_analyses")
    stats_increment(result["sentiment"]["label"] + "_count")
    result.pop("_id", None)
    return jsonify(result)

@app.route('/api/face-analyze', methods=['POST'])
def api_face_analyze():
    data = request.get_json() or {}
    emotion = data.get('emotion', 'neutral').lower()
    confidence = float(data.get('confidence', 0))
    expressions = data.get('expressions', {})
    POSITIVE_EMOTIONS = {'happy', 'surprised'}
    NEGATIVE_EMOTIONS = {'sad', 'angry', 'fearful', 'disgusted'}
    if emotion in POSITIVE_EMOTIONS:
        label, emoji, color = 'positive', '😊', '#22c55e'
    elif emotion in NEGATIVE_EMOTIONS:
        label, emoji, color = 'negative', '😟', '#ef4444'
    else:
        label, emoji, color = 'neutral', '😐', '#f59e0b'
    doc = {"id": str(uuid.uuid4())[:8], "source": "face", "raw_emotion": emotion,
           "mood": label, "emoji": emoji, "color": color,
           "confidence": round(confidence * 100, 1), "expressions": expressions,
           "timestamp": datetime.datetime.utcnow().isoformat()}
    db_insert("face_analyses", doc)
    doc.pop("_id", None)
    return jsonify(doc)

@app.route('/api/voice-analyses', methods=['GET'])
def api_voice_analyses():
    docs = db_find_recent("voice_analyses", limit=20)
    for d in docs: d.pop("_id", None)
    return jsonify(docs)

@app.route('/api/face-analyses', methods=['GET'])
def api_face_analyses():
    docs = db_find_recent("face_analyses", limit=20)
    for d in docs: d.pop("_id", None)
    return jsonify(docs)

# ═══════════════════════════════════════════════════════════════════════════
# API: CHAT EMOTION ANALYSIS
# ═══════════════════════════════════════════════════════════════════════════

def parse_whatsapp_chat(raw_text):
    """Parse WhatsApp export or plain conversation into structured messages."""
    lines = raw_text.strip().split('\n')
    messages = []
    wa_pattern = re.compile(
        r'^(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4}),?\s*\d{1,2}:\d{2}'
        r'(?::\d{2})?(?:\s*[APap][Mm])?\s*[-\u2013]\s*([^:]+):\s*(.+)$'
    )
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if any(skip in line for skip in ['<Media omitted>', 'This message was deleted', 'Messages and calls are end-to-end encrypted']):
            continue
        m = wa_pattern.match(line)
        if m:
            messages.append({"date": m.group(1).strip(), "sender": m.group(2).strip(), "text": m.group(3).strip()})
        elif ':' in line and len(line.split(':')[0]) < 30:
            parts = line.split(':', 1)
            messages.append({"date": None, "sender": parts[0].strip(), "text": parts[1].strip()})
        else:
            messages.append({"date": None, "sender": "User", "text": line})
    return messages


def analyze_chat_emotions(messages):
    """Analyze emotions day-by-day and overall."""
    from collections import defaultdict
    daily = defaultdict(list)
    for msg in messages:
        key = msg.get("date") or "today"
        if msg["text"] and len(msg["text"]) > 2:
            s = analyze_sentiment(msg["text"])
            daily[key].append(s["score"])

    daily_summary = []
    for day, scores in sorted(daily.items())[-7:]:
        avg = sum(scores) / len(scores)
        if avg >= 0.22:
            mood, emoji = "positive", "😊"
        elif avg <= -0.18:
            mood, emoji = "stressed/low", "😟"
        else:
            mood, emoji = "neutral", "😐"
        daily_summary.append({"date": day, "avg_score": round(avg, 3), "mood": mood, "emoji": emoji, "count": len(scores)})

    all_scores = [s for scores in daily.values() for s in scores]
    if not all_scores:
        return None

    overall_avg = sum(all_scores) / len(all_scores)
    split = max(1, len(all_scores) - 10)
    recent = all_scores[split:]
    older  = all_scores[:split]
    recent_avg = sum(recent) / len(recent)
    older_avg  = sum(older) / len(older) if older else recent_avg
    trend = "improving 📈" if recent_avg > older_avg + 0.1 else \
            "declining 📉" if recent_avg < older_avg - 0.1 else "stable ➡️"

    insights = []
    if overall_avg <= -0.18:
        insights.append("You seem stressed in recent messages. Consider taking a break 🧘")
    if any(d["mood"] == "stressed/low" for d in daily_summary[-3:]):
        insights.append("Tension detected in last 3 days — try a breathing exercise 💨")
    if recent_avg > older_avg + 0.1:
        insights.append("Your tone has improved recently — great progress! 🌟")
    if overall_avg >= 0.22:
        insights.append("Overall positive vibes in your conversations! Keep it up 😊")
    if not insights:
        insights.append("Your conversations show a balanced emotional tone 😌")

    return {
        "total_messages": len(messages),
        "days_analyzed": len(daily_summary),
        "overall_avg": round(overall_avg, 3),
        "trend": trend,
        "daily": daily_summary,
        "insights": insights,
    }


@app.route('/api/chat-analyze', methods=['POST'])
def api_chat_analyze():
    data = request.get_json() or {}
    raw = data.get('text', '').strip()
    if not raw or len(raw) < 20:
        return jsonify({"error": "Please paste at least some conversation text"}), 400
    if len(raw) > 100000:
        return jsonify({"error": "Text too long (max 100000 chars)"}), 400

    messages = parse_whatsapp_chat(raw)
    if not messages:
        return jsonify({"error": "Could not parse any messages"}), 400

    result = analyze_chat_emotions(messages)
    if not result:
        return jsonify({"error": "Not enough content to analyze"}), 400

    doc = {"id": str(uuid.uuid4())[:8], "total_messages": result["total_messages"],
           "overall_avg": result["overall_avg"], "trend": result["trend"],
           "timestamp": datetime.datetime.utcnow().isoformat()}
    db_insert("chat_analyses", doc)

    return jsonify(result)

# ═══════════════════════════════════════════════════════════════════════════
# API: MOOD CHECK-IN + STREAK
# ═══════════════════════════════════════════════════════════════════════════

MOOD_SUGGESTIONS = {
    "happy": {
        "music": ["Happy - Pharrell Williams 🎵", "Good as Hell - Lizzo 🎵", "Uptown Funk - Bruno Mars 🎵"],
        "activity": ["Share your joy with a friend 📞", "Write 3 things you're grateful for ✍️", "Go for a celebratory walk 🚶"],
        "quote": "Happiness is not something ready made. It comes from your own actions. — Dalai Lama"
    },
    "sad": {
        "music": ["Fix You - Coldplay 🎵", "Breathe (2 AM) - Anna Nalick 🎵", "Someone Like You - Adele 🎵"],
        "activity": ["Watch a comforting movie 🎬", "Call a friend or family member 📱", "Write down your feelings 📓"],
        "quote": "Even the darkest night will end and the sun will rise. — Victor Hugo",
        "breathing": True
    },
    "angry": {
        "music": ["Roar - Katy Perry 🎵", "Fighter - Christina Aguilera 🎵", "Shake It Out - Florence 🎵"],
        "activity": ["Try box breathing (4-4-4-4) 🌬️", "Go for a brisk walk 🏃", "Write it out — then delete it 📝"],
        "quote": "For every minute you remain angry, you give up sixty seconds of peace of mind. — Emerson",
        "breathing": True
    },
    "anxious": {
        "music": ["Weightless - Marconi Union 🎵", "Clair de Lune - Debussy 🎵", "Nature rain sounds 🌧️"],
        "activity": ["4-7-8 breathing technique 🧘", "5-4-3-2-1 grounding exercise 🌿", "Step outside for fresh air 🌤️"],
        "quote": "You don't have to control your thoughts. You just have to stop letting them control you. — Dan Millman",
        "breathing": True
    },
    "neutral": {
        "music": ["Lo-fi hip hop beats 🎵", "Nature sounds playlist 🌿", "Your favorite playlist 🎧"],
        "activity": ["Try something creative today 🎨", "Take a short mindful walk 🚶", "Learn something new 📚"],
        "quote": "The present moment is the only moment available to us. — Thich Nhat Hanh"
    }
}


@app.route('/api/mood-checkin', methods=['POST'])
def api_mood_checkin():
    data = request.get_json() or {}
    mood = data.get('mood', 'neutral').lower()
    user_id = data.get('user_id', 'anonymous')
    note = data.get('note', '')

    if mood not in MOOD_SUGGESTIONS:
        mood = 'neutral'

    today = datetime.datetime.utcnow().strftime('%Y-%m-%d')
    doc = {
        "id": str(uuid.uuid4())[:8],
        "user_id": user_id,
        "mood": mood,
        "note": note[:300] if note else '',
        "date": today,
        "timestamp": datetime.datetime.utcnow().isoformat(),
    }
    db_insert("mood_checkins", doc)
    streak = _calculate_streak(user_id)

    return jsonify({
        "mood": mood,
        "suggestions": MOOD_SUGGESTIONS[mood],
        "streak": streak,
        "message": _streak_message(streak),
        "saved": True,
    })


def _calculate_streak(user_id):
    if MONGO_CONNECTED:
        c = mongo_db["mood_checkins"]
        docs = list(c.find({"user_id": user_id}, {"date": 1, "_id": 0}).sort("date", DESCENDING).limit(60))
        dates = [d["date"] for d in docs]
    else:
        dates = [d["date"] for d in _MEM.get("mood_checkins", []) if d.get("user_id") == user_id]

    if not dates:
        return 1
    unique_dates = sorted(set(dates), reverse=True)
    today = datetime.datetime.utcnow().date()
    streak = 0
    for i, d in enumerate(unique_dates):
        try:
            dt = datetime.datetime.strptime(d, '%Y-%m-%d').date()
            if dt == today - datetime.timedelta(days=i):
                streak = i + 1
            else:
                break
        except Exception:
            break
    return max(streak, 1)


def _streak_message(streak):
    if streak >= 30: return f"🏆 Legendary! {streak} day streak!"
    if streak >= 14: return f"🔥 On fire! {streak} day streak!"
    if streak >= 7:  return f"⭐ Amazing! {streak} day streak!"
    if streak >= 5:  return f"🌟 Great! {streak} days in a row!"
    if streak >= 3:  return f"💪 Keep going! {streak} days in a row!"
    if streak == 2:  return "✨ 2 days in a row — building a habit!"
    return "✅ Day 1 — every journey starts here!"


@app.route('/api/mood-history', methods=['GET'])
def api_mood_history():
    user_id = request.args.get('user_id', 'anonymous')
    docs = db_find_by_field("mood_checkins", "user_id", user_id, limit=30)
    return jsonify(docs)


@app.route('/api/mood-stats', methods=['GET'])
def api_mood_stats():
    aggregates = db_aggregate_field("mood_checkins", "mood")
    total = db_count("mood_checkins")
    return jsonify({"total": total, "by_mood": aggregates})

# ═══════════════════════════════════════════════════════════════════════════
# API: AI CHATBOT (SAGE)
# ═══════════════════════════════════════════════════════════════════════════

CHATBOT_RULES = [
    # Greetings
    (["hello", "hi", "hey", "howdy", "hiya", "sup"],
     "Hey there! 👋 I'm Sage, your wellness companion.\n\nI'm here to listen, offer breathing exercises, music suggestions, and motivation. How are you feeling today?"),
    (["bye", "goodbye", "see you", "later", "ciao"],
     "Take care! 💙 Remember, it's okay to check in whenever you need. You've got this! 🌟"),
    (["thank", "thanks", "thank you", "thx"],
     "You're welcome! 🌟 Remember, every small step towards wellbeing counts. I'm always here if you need me."),

    # Crisis — always check first
    (["suicid", "kill myself", "end my life", "don't want to live", "want to die"],
     "I'm really concerned about you 💙. Please reach out right now:\n\n📞 iCall: 9152987821 (India)\n📞 Vandrevala Foundation: 1860-2662-345\n\nYou matter deeply, and people care about you. Please don't be alone right now. 🤗"),

    # Negative emotions
    (["sad", "unhappy", "crying", "cry", "tears", "heartbroken", "miserable"],
     "I'm sorry you're feeling down 💙. It's okay — your feelings are valid.\n\nWould you like to:\n• Try a quick breathing exercise? (say 'breathing')\n• Hear a comforting quote? (say 'quote')\n• Get music suggestions? (say 'music')\n\nI'm here for you. 🌿"),
    (["depressed", "depression", "hopeless", "worthless", "empty inside", "no point"],
     "I hear you, and what you're feeling truly matters 💜. Depression is real, but you don't have to face it alone.\n\nPlease consider talking to a trusted person — friend, family, or counselor. You deserve support.\n\n📞 iCall India: 9152987821 🤗"),
    (["stressed", "stress", "overwhelmed", "pressure", "too much", "burnout", "cant cope"],
     "Stress can feel really heavy 😔. Let's try this together:\n\n🌬️ **Box Breathing:**\n1. Inhale for 4 counts\n2. Hold for 4 counts\n3. Exhale for 4 counts\n4. Hold for 4 counts\n\nRepeat 4 times. How do you feel after? 💙"),
    (["anxious", "anxiety", "nervous", "panic", "worried", "scared", "fear"],
     "Anxiety is tough, but you can get through this 💪.\n\n🌿 **5-4-3-2-1 Grounding:**\n• 5 things you can SEE\n• 4 things you can TOUCH\n• 3 things you can HEAR\n• 2 things you can SMELL\n• 1 thing you can TASTE\n\nThis brings you back to the present. You're safe. 💙"),
    (["angry", "mad", "furious", "rage", "frustrated", "irritated", "annoyed"],
     "Your frustration is valid 😤. Let's channel it:\n\n1. Take 3 slow deep breaths right now\n2. Ask: 'Will this matter in 5 years?'\n3. Try a brisk walk — movement really releases anger 🏃\n\nWant to tell me what happened? I'm listening. 💭"),
    (["lonely", "alone", "isolated", "no friends", "nobody cares", "friendless"],
     "Loneliness is one of the hardest feelings 💙. But reaching out — even here — shows real courage.\n\nTry:\n• Call someone you haven't spoken to in a while\n• Join a club, class, or online community\n• Go for a walk somewhere public\n\nYou matter more than you know. 🌟"),
    (["tired", "exhausted", "fatigue", "sleepy", "no energy", "drained"],
     "Your body and mind are telling you something important 😴.\n\nRest IS productive! Try:\n• Consistent bedtime (same every night)\n• No screens 30 min before bed\n• Even a 20-min nap can restore energy\n\nYou can't pour from an empty cup. Take care of yourself first 💙"),
    (["happy", "great", "amazing", "wonderful", "fantastic", "excited", "joyful", "good day"],
     "That's absolutely wonderful! 🎉✨\n\nSavor this feeling — it's real and you deserve it. Maybe:\n• Share this good energy with someone you love 😊\n• Write it down so you can revisit this moment\n• Do something to celebrate!\n\nKeep that beautiful energy going! 🌟"),
    (["bored", "nothing to do", "boring", "boredom"],
     "Boredom is actually a creative opportunity! 🎨\n\nTry:\n• Learn something new on YouTube 📺\n• Go for a walk and notice something you've never seen before 🚶\n• Write, draw, or make music 🎵\n• Call an old friend 📞\n\nWhat sounds most appealing? 😊"),

    # Activities
    (["breathing", "breathe", "breath exercise", "box breath", "calm down"],
     "Let's do box breathing together: 🌬️\n\n1️⃣ Inhale slowly for **4 counts**\n2️⃣ Hold for **4 counts**\n3️⃣ Exhale slowly for **4 counts**\n4️⃣ Hold for **4 counts**\n\nRepeat 4 times. Focus only on your breath.\nYou can also use the breathing exercise on the Chat Mood page!\n\nHow do you feel? 😊"),
    (["music", "song", "playlist", "what to listen", "recommend music"],
     "Music is amazing for mood! 🎵\n\n• **Stressed/Anxious:** Weightless by Marconi Union 🧘\n• **Sad:** Fix You - Coldplay, Breathe - Anna Nalick 💙\n• **Need energy:** Roar - Katy Perry, Happy - Pharrell 🎉\n• **Calm focus:** Classical music, lo-fi beats, nature sounds 🌿\n\nWhat vibe are you going for? 🎧"),
    (["quote", "motivation", "inspire", "motivate", "encourage", "give me a quote"],
     "Here's one just for you ✨\n\n*\"You are braver than you believe, stronger than you seem, and smarter than you think.\"*\n— A.A. Milne\n\nWould you like another? Just say 'quote' again! 😊"),
    (["help", "support", "what can you do", "how does this work", "features"],
     "I'm Sage, your wellness companion! 💙 Here's what I can do:\n\n🧘 Listen and respond to how you feel\n🌬️ Guide breathing exercises\n✨ Share motivational quotes\n🎵 Suggest mood-boosting music\n💡 Offer coping strategies\n🔥 Tip: try the Mood Check-in page for daily tracking!\n\nJust tell me how you're feeling! 😊"),

    # Social media / tech
    (["social media", "instagram", "tiktok", "snapchat", "scrolling", "phone", "screen time"],
     "Social media affects mood more than we realize 📱.\n\nTry a **30-minute digital detox** today:\n• Put your phone in another room\n• Take a walk, read, or call a friend\n• Notice how you feel before and after!\n\nSmall breaks add up to big changes. 🌿"),
    (["bully", "bullied", "bullying", "harass", "cyberbullying", "being bullied"],
     "Bullying is NEVER okay, and it is not your fault 💙.\n\n🛡️ Steps to take:\n1. Talk to a trusted adult or school counselor TODAY\n2. Screenshot and document the incidents\n3. Block and report the person\n4. Remember — their behavior reflects them, not you\n\nYou deserve to feel completely safe. 🤗"),

    # Meta
    (["who are you", "what are you", "your name", "are you ai", "are you a bot", "are you real"],
     "I'm Sage! 🌿 A wellness AI companion built as part of the SocialScope research project.\n\nI'm not a licensed therapist, but I'm here to offer support, breathing exercises, music, and a listening presence. For serious concerns, please reach out to a professional. 💙"),
]

DEFAULT_RESPONSES = [
    "I'm here for you 💙. Tell me more about what's on your mind.",
    "That sounds meaningful. How does that make you feel?",
    "I hear you. Would you like a breathing exercise, a motivational quote, or music suggestions? 🎵",
    "Thanks for sharing that with me. It's okay to feel whatever you're feeling 🌿",
    "I'm listening. What else would you like to talk about? 💭",
    "You're doing great by talking about this. Want a quote, some music, or a breathing exercise? 😊",
    "That's worth exploring. What's weighing on you most right now? 💙",
]


def chatbot_respond(message):
    msg_lower = message.lower()
    for keywords, response in CHATBOT_RULES:
        if any(kw in msg_lower for kw in keywords):
            return response
    # Sentiment-based fallback
    sentiment = analyze_sentiment(message)
    if sentiment["label"] == "negative":
        return "It sounds like you might be going through something tough 💙. I'm here to listen.\n\nCan you tell me more? Or would you prefer a breathing exercise or some music to help right now?"
    elif sentiment["label"] == "positive":
        return "That sounds really positive! 😊 I love hearing that. What's making you feel this way? Keep that energy going! 🌟"
    return random.choice(DEFAULT_RESPONSES)


@app.route('/api/chatbot', methods=['POST'])
def api_chatbot():
    data = request.get_json() or {}
    message = data.get('message', '').strip()
    if not message:
        return jsonify({"error": "Empty message"}), 400
    message = message[:500]

    reply = chatbot_respond(message)
    doc = {
        "id": str(uuid.uuid4())[:8],
        "user_message": message,
        "bot_reply": reply[:1000],
        "timestamp": datetime.datetime.utcnow().isoformat(),
    }
    db_insert("chatbot_logs", doc)
    return jsonify({"reply": reply})

# ═══════════════════════════════════════════════════════════════════════════
# HEALTH CHECK
# ═══════════════════════════════════════════════════════════════════════════

@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({
        "status": "ok",
        "version": "4.0",
        "nlp": "active",
        "db": "MongoDB Atlas" if MONGO_CONNECTED else "in-memory fallback",
        "mongo_connected": MONGO_CONNECTED,
        "features": ["analyzer","chat-analysis","mood-checkin","chatbot","biometric","quiz","survey"],
        "timestamp": datetime.datetime.utcnow().isoformat(),
    })

# ═══════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    print("\n" + "="*55)
    print("  SocialScope v4.0 — All Features Active")
    print("="*55)
    print(f"  DB: {'MongoDB Atlas connected' if MONGO_CONNECTED else 'In-memory fallback'}")
    print("  Active: NLP Analyzer | Chat Emotion | Mood Check-in")
    print("          Sage AI Chatbot | Biometric | Quiz | Dashboard")
    print(f"\n  Open: http://localhost:5000\n")
    app.run(debug=True, port=5000)
