from flask import Flask, render_template, request, redirect, url_for, jsonify, abort
import sqlite3, secrets, uuid, os, datetime, json, math
from pathlib import Path
from flask import g
from hashlib import sha256
import random

BASE = Path(__file__).resolve().parent
DB = BASE / "raffle.db"
ADMIN_KEY = os.environ.get("RAFFLE_ADMIN_KEY", "change_this_admin_key")

def get_db():
    db = getattr(g, "_db", None)
    if db is None:
        db = g._db = sqlite3.connect(DB)
        db.row_factory = sqlite3.Row
    return db

def init_db():
    db = sqlite3.connect(DB)
    c = db.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS entries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        phone TEXT,
        instagram TEXT,
        referral_code TEXT UNIQUE,
        referred_by TEXT,
        tickets INTEGER DEFAULT 1,
        created_at TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS meta (k TEXT PRIMARY KEY, v TEXT)""")
    # set default end_time if missing (24 hours from now)
    now = datetime.datetime.utcnow()
    default_end = (now + datetime.timedelta(hours=24)).isoformat()
    c.execute("INSERT OR IGNORE INTO meta (k,v) VALUES (?,?)", ("end_time", default_end))
    db.commit()
    db.close()

init_db()

app = Flask(__name__, static_folder='static', template_folder='templates')

@app.teardown_appcontext
def close_conn(exception):
    db = getattr(g, "_db", None)
    if db is not None:
        db.close()

def get_meta(key):
    db = get_db()
    cur = db.execute("SELECT v FROM meta WHERE k=?", (key,))
    r = cur.fetchone()
    return r["v"] if r else None

def set_meta(key, val):
    db = get_db()
    db.execute("INSERT OR REPLACE INTO meta (k,v) VALUES (?,?)", (key, val))
    db.commit()

@app.route("/")
def index():
    ref = request.args.get("ref")
    end_time = get_meta("end_time")
    return render_template("index.html", ref=ref, end_time=end_time)

@app.route("/signup", methods=["POST"])
def signup():
    name = request.form.get("name","").strip()
    phone = request.form.get("phone","").strip()
    insta = request.form.get("instagram","").strip()
    ref = request.form.get("referral_code") or request.args.get("ref")
    if not phone or not insta:
        return jsonify({"ok":False,"error":"phone and instagram required"}),400
    rcode = uuid.uuid4().hex[:8]
    created_at = datetime.datetime.utcnow().isoformat()
    db = get_db()
    # create entry
    try:
        db.execute("INSERT INTO entries (name,phone,instagram,referral_code,referred_by,created_at) VALUES (?,?,?,?,?,?)",
                 (name,phone,insta,rcode,ref,created_at))
        db.commit()
    except Exception as e:
        return jsonify({"ok":False,"error":"db error","detail":str(e)}),500
    # handle referral ticket increment (give referring user +1 ticket)
    if ref:
        cur = db.execute("SELECT id,tickets FROM entries WHERE referral_code=?", (ref,))
        r = cur.fetchone()
        if r:
            db.execute("UPDATE entries SET tickets = tickets + 1 WHERE id=?", (r["id"],))
            db.commit()
    return jsonify({"ok":True,"referral_code":rcode})

@app.route("/api/status")
def status():
    end_time = get_meta("end_time")
    db = get_db()
    cur = db.execute("SELECT COUNT(*) as count, SUM(tickets) as total_tickets FROM entries")
    stats = cur.fetchone()
    return jsonify({"end_time": end_time, "entries": stats["count"], "total_tickets": stats["total_tickets"] or 0})

def weighted_sample_without_replacement(rows, k=3):
    # rows: list of dicts with 'id' and 'tickets'
    population = []
    for r in rows:
        tickets = max(1, int(r["tickets"]))
        population.extend([r["id"]] * tickets)
    if len(population) == 0:
        return []
    winners = []
    # use secrets for randomness
    while len(winners) < min(k, len(set(population))):
        pick = secrets.choice(population)
        if pick not in winners:
            winners.append(pick)
            # remove all instances of pick
            population = [p for p in population if p != pick]
    return winners

@app.route("/admin/draw", methods=["POST"])
def admin_draw():
    key = request.args.get("key") or request.headers.get("X-Admin-Key")
    if key != ADMIN_KEY:
        return abort(403)
    db = get_db()
    cur = db.execute("SELECT id,tickets,name,phone,instagram,referral_code FROM entries")
    rows = cur.fetchall()
    winners_ids = weighted_sample_without_replacement(rows, k=3)
    winners = []
    for wid in winners_ids:
        cur = db.execute("SELECT id,name,phone,instagram,referral_code,tickets FROM entries WHERE id=?", (wid,))
        r = cur.fetchone()
        if r:
            winners.append(dict(r))
    # store winners in meta
    set_meta("winners", json.dumps(winners))
    set_meta("draw_time", datetime.datetime.utcnow().isoformat())
    return jsonify({"ok":True,"winners":winners})

@app.route("/admin/winners")
def admin_winners():
    key = request.args.get("key") or request.headers.get("X-Admin-Key")
    if key != ADMIN_KEY:
        return abort(403)
    winners = get_meta("winners")
    draw_time = get_meta("draw_time")
    return jsonify({"winners": json.loads(winners) if winners else [], "draw_time": draw_time})

@app.route("/admin/set_end", methods=["POST"])
def admin_set_end():
    key = request.args.get("key") or request.headers.get("X-Admin-Key")
    if key != ADMIN_KEY:
        return abort(403)
    new_end = request.json.get("end_time")
    # expect ISO format
    set_meta("end_time", new_end)
    return jsonify({"ok":True,"end_time":new_end})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
