import os, sqlite3
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash

app=Flask(__name__)
app.secret_key=os.environ.get("SECRET_KEY","change-this-secret")
DB="og_markets.db"

def db():
    c=sqlite3.connect(DB); c.row_factory=sqlite3.Row; return c
def init_db():
    c=db()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT,email TEXT UNIQUE,password TEXT,role TEXT DEFAULT 'client',balance REAL DEFAULT 10000);
    CREATE TABLE IF NOT EXISTS trades(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER,symbol TEXT,side TEXT,quantity REAL,price REAL,created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS transactions(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER,kind TEXT,amount REAL,status TEXT DEFAULT 'demo',created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS messages(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER,sender TEXT,message TEXT,created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
    """)
    if not c.execute("SELECT id FROM users WHERE email='admin@ogmarkets.local'").fetchone():
        c.execute("INSERT INTO users(name,email,password,role,balance) VALUES(?,?,?,?,?)",("OG MARKETS Admin","admin@ogmarkets.local",generate_password_hash("ChangeMe123!"),"admin",0))
    c.commit(); c.close()
def login_req():
    return "user_id" in session

@app.route("/")
def home(): return render_template("index.html")
@app.route("/register",methods=["GET","POST"])
def register():
    if request.method=="POST":
        try:
            c=db(); c.execute("INSERT INTO users(name,email,password) VALUES(?,?,?)",(request.form["name"],request.form["email"].lower(),generate_password_hash(request.form["password"])))
            c.commit(); c.close(); return redirect(url_for("login"))
        except sqlite3.IntegrityError: flash("Email already registered.")
    return render_template("register.html")
@app.route("/login",methods=["GET","POST"])
def login():
    if request.method=="POST":
        c=db(); u=c.execute("SELECT * FROM users WHERE email=?",(request.form["email"].lower(),)).fetchone(); c.close()
        if u and check_password_hash(u["password"],request.form["password"]):
            session.update(user_id=u["id"],role=u["role"],name=u["name"])
            return redirect(url_for("admin" if u["role"]=="admin" else "dashboard"))
        flash("Invalid login.")
    return render_template("login.html")
@app.route("/logout")
def logout(): session.clear(); return redirect(url_for("home"))
@app.route("/dashboard")
def dashboard():
    if not login_req(): return redirect(url_for("login"))
    c=db(); u=c.execute("SELECT * FROM users WHERE id=?",(session["user_id"],)).fetchone()
    t=c.execute("SELECT * FROM trades WHERE user_id=? ORDER BY id DESC LIMIT 10",(u["id"],)).fetchall(); c.close()
    return render_template("dashboard.html",u=u,trades=t)
@app.route("/trade",methods=["POST"])
def trade():
    if not login_req(): return redirect(url_for("login"))
    c=db(); c.execute("INSERT INTO trades(user_id,symbol,side,quantity,price) VALUES(?,?,?,?,?)",(session["user_id"],request.form["symbol"],request.form["side"],float(request.form["quantity"]),float(request.form["price"]))); c.commit(); c.close()
    flash("Demo order recorded. No real market order was sent."); return redirect(url_for("dashboard"))
@app.route("/funding/<kind>",methods=["GET","POST"])
def funding(kind):
    if not login_req(): return redirect(url_for("login"))
    if kind not in ("deposit","withdrawal"): return redirect(url_for("dashboard"))
    if request.method=="POST":
        c=db(); c.execute("INSERT INTO transactions(user_id,kind,amount,status) VALUES(?,?,?,'pending-demo')",(session["user_id"],kind,float(request.form["amount"]))); c.commit(); c.close()
        flash("Demo funding request submitted. No real money was processed."); return redirect(url_for("dashboard"))
    return render_template("funding.html",kind=kind)
@app.route("/transactions")
def transactions():
    if not login_req(): return redirect(url_for("login"))
    c=db(); tx=c.execute("SELECT * FROM transactions WHERE user_id=? ORDER BY id DESC",(session["user_id"],)).fetchall(); c.close()
    return render_template("transactions.html",tx=tx)
@app.route("/chat",methods=["GET","POST"])
def chat():
    if not login_req(): return redirect(url_for("login"))
    c=db()
    if request.method=="POST":
        c.execute("INSERT INTO messages(user_id,sender,message) VALUES(?,?,?)",(session["user_id"],"client",request.form["message"])); c.commit()
    msgs=c.execute("SELECT * FROM messages WHERE user_id=? ORDER BY id",(session["user_id"],)).fetchall(); c.close()
    return render_template("chat.html",msgs=msgs)
@app.route("/admin")
def admin():
    if session.get("role")!="admin": return redirect(url_for("dashboard"))
    c=db(); users=c.execute("SELECT * FROM users ORDER BY id DESC").fetchall(); trades=c.execute("SELECT trades.*,users.email FROM trades JOIN users ON users.id=trades.user_id ORDER BY trades.id DESC").fetchall(); c.close()
    return render_template("admin.html",users=users,trades=trades)
@app.route("/admin/chat",methods=["GET","POST"])
def admin_chat():
    if session.get("role")!="admin": return redirect(url_for("dashboard"))
    uid=request.args.get("user_id",type=int)
    c=db()
    if request.method=="POST":
        uid=int(request.form["user_id"]); c.execute("INSERT INTO messages(user_id,sender,message) VALUES(?,?,?)",(uid,"admin",request.form["message"])); c.commit()
    users=c.execute("SELECT id,name,email FROM users WHERE role='client' ORDER BY id DESC").fetchall()
    msgs=c.execute("SELECT * FROM messages WHERE user_id=? ORDER BY id",(uid,)).fetchall() if uid else []
    c.close(); return render_template("admin_chat.html",users=users,msgs=msgs,uid=uid)
@app.route("/api/market")
def market():
    return jsonify([{"symbol":"BTCUSD","price":"65000.00","change":"+1.20%"},{"symbol":"EURUSD","price":"1.1650","change":"+0.18%"},{"symbol":"XAUUSD","price":"3390.00","change":"-0.24%"},{"symbol":"US500","price":"6380.00","change":"+0.42%"}])
@app.route("/health")
def health(): return {"status":"ok","mode":"demo"}
if __name__=="__main__":
    init_db(); app.run(host="0.0.0.0",port=int(os.environ.get("PORT",5000)))
