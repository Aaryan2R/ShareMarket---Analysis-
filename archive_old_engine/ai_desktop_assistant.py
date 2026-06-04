# ai_trading_assistant_ui.py
# Save into project root and run: python ai_trading_assistant_ui.py
import tkinter as tk
from tkinter import ttk, messagebox
import requests, json, sqlite3, threading, traceback
from pathlib import Path
from datetime import datetime, date, time, timedelta
import pandas as pd

# optional plotting
try:
    import matplotlib
    matplotlib.use("TkAgg")
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    MATPLOTLIB_AVAILABLE = True
except Exception:
    MATPLOTLIB_AVAILABLE = False

try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None

# ---------------- CONFIG ----------------
API_URL = "http://localhost:1234/v1/chat/completions"
MODEL_NAME = "meta-llama-3.1-8b-instruct"

DATA_PATH = Path("data/cleaned/_daily_intelligence.json")
REGIME_PATH = Path("data/cleaned/_market_regime.json")
RAW_PATH = Path("data/raw")
DB_PATH = Path("assistant.db")
NEWS_PATH = Path("data/cleaned/_news.json")

BG = "#0f1115"
CARD = "#1a1d23"
ACCENT = "#3b82f6"
USER_COLOR = "#4FC3F7"
AI_COLOR = "#E5E7EB"
TEXT = "#e5e7eb"
SUBTLE = "#9ca3af"

FONT_MAIN = ("Segoe UI", 13)
FONT_HEADER = ("Segoe UI", 16, "bold")
FONT_META = ("Segoe UI", 10)

# ---------------- SQLITE PERSISTENCE ----------------
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT NOT NULL,
        role TEXT NOT NULL,
        message TEXT NOT NULL
    )""")
    cur.execute("""
    CREATE TABLE IF NOT EXISTS snapshots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT NOT NULL,
        data TEXT
    )""")
    conn.commit(); conn.close()

def log_message(role, message):
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("INSERT INTO messages (ts, role, message) VALUES (?, ?, ?)",
                    (datetime.utcnow().isoformat(), role, message))
        conn.commit()
    finally:
        conn.close()

def save_snapshot(data):
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("INSERT INTO snapshots (ts, data) VALUES (?, ?)",
                    (datetime.utcnow().isoformat(), json.dumps(data, default=str)))
        conn.commit()
    finally:
        conn.close()

# ---------------- DATA UTILITIES ----------------
def load_json_safe(path: Path):
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return {}

def build_context():
    return load_json_safe(DATA_PATH)

def compute_company_date_ranges(companies):
    out = {}
    for company in companies:
        file_path = RAW_PATH / company / "prices" / "daily" / "daily.csv"
        if not file_path.exists():
            out[company] = {"earliest": None, "latest": None, "rows": 0}
            continue
        try:
            df = pd.read_csv(file_path)
            date_col = None
            for c in df.columns:
                if c.strip().lower() == "date":
                    date_col = c; break
            if date_col:
                df.rename(columns={date_col: "Date"}, inplace=True)
            if "Date" in df.columns:
                df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
                df = df.dropna(subset=["Date"])
                if len(df):
                    out[company] = {"earliest": df["Date"].min().date().isoformat(),
                                    "latest": df["Date"].max().date().isoformat(),
                                    "rows": int(len(df))}
                else:
                    out[company] = {"earliest": None, "latest": None, "rows": 0}
            else:
                out[company] = {"earliest": None, "latest": None, "rows": int(len(df))}
        except Exception:
            out[company] = {"earliest": None, "latest": None, "rows": 0}
    return out

def get_data_metadata():
    metadata = {"companies": [], "earliest_date": None, "last_available_date": None,
                "data_available": False, "rows_total": 0, "company_date_ranges": {}}
    context = build_context()
    if not context: return metadata
    try:
        companies = [c.get("company") for c in context if isinstance(c, dict) and c.get("company")]
    except Exception:
        companies = []
    metadata["companies"] = companies
    if not companies: return metadata
    metadata["data_available"] = True
    ranges = compute_company_date_ranges(companies)
    metadata["company_date_ranges"] = ranges
    earliest_dates = []
    latest_dates = []
    total_rows = 0
    for comp, v in ranges.items():
        if v.get("earliest"):
            try: earliest_dates.append(datetime.fromisoformat(v["earliest"]))
            except Exception: pass
        if v.get("latest"):
            try: latest_dates.append(datetime.fromisoformat(v["latest"]))
            except Exception: pass
        total_rows += int(v.get("rows", 0))
    if earliest_dates:
        metadata["earliest_date"] = min(earliest_dates).date().isoformat()
    if latest_dates:
        metadata["last_available_date"] = max(latest_dates).date().isoformat()
    metadata["rows_total"] = total_rows
    return metadata

# ---------------- MARKET HOURS ----------------
def market_status_info(tz_name: str = "Asia/Kolkata"):
    try:
        tz = ZoneInfo(tz_name) if ZoneInfo else None
    except Exception:
        tz = None
    now = datetime.now(tz) if tz else datetime.now()
    weekday = now.weekday(); is_weekday = weekday < 5
    def to_dt(d: date, t: time):
        return datetime.combine(d, t).replace(tzinfo=tz) if tz else datetime.combine(d, t)
    today = now.date()
    preopen_start = to_dt(today, time(9, 0)); regular_start = to_dt(today, time(9, 15)); regular_close = to_dt(today, time(15, 30))
    status = {"now": now.isoformat(), "is_open": False, "phase": "CLOSED", "reason": None, "next_open": None, "next_close": None, "timezone": tz_name if tz else "local"}
    if not is_weekday:
        days_ahead = 2 if weekday == 5 else (1 if weekday == 6 else 0)
        status["next_open"] = to_dt(today + timedelta(days=days_ahead), time(9,15)).isoformat()
        status["reason"] = "Weekend"; return status
    if now < preopen_start:
        status.update({"phase":"BEFORE_PREOPEN","next_open":preopen_start.isoformat(),"reason":"Before market pre-open"}); return status
    if preopen_start <= now < regular_start:
        status.update({"phase":"PREOPEN","next_open":regular_start.isoformat(),"reason":"Pre-open (order matching)"}); return status
    if regular_start <= now <= regular_close:
        status.update({"is_open":True,"phase":"REGULAR","next_close":regular_close.isoformat(),"reason":"Market is open"}); return status
    if now > regular_close:
        next_open_date = today + timedelta(days=1)
        if next_open_date.weekday() >= 5:
            offset = 7 - next_open_date.weekday(); next_open_date = next_open_date + timedelta(days=offset)
        status.update({"next_open":to_dt(next_open_date,time(9,15)).isoformat(),"phase":"AFTER_CLOSE","reason":"Market closed for the day"}); return status
    return status

# ---------------- SAFE HELPERS / SQL-LIKE QUERIES ----------------
def compute_positive_close_rate(company: str, days: int = 30):
    """Return percent of days in last N days where Close > Open (proxy 'win rate')."""
    file_path = RAW_PATH / company / "prices" / "daily" / "daily.csv"
    if not file_path.exists():
        return {"error":"file missing"}
    try:
        df = pd.read_csv(file_path)
        # normalize date & columns
        date_col = next((c for c in df.columns if c.strip().lower() == "date"), None)
        close_col = next((c for c in df.columns if c.strip().lower() == "close"), None)
        open_col = next((c for c in df.columns if c.strip().lower() == "open"), None)
        if date_col: df.rename(columns={date_col:"Date"}, inplace=True)
        if close_col: df.rename(columns={close_col:"Close"}, inplace=True)
        if open_col: df.rename(columns={open_col:"Open"}, inplace=True)
        if "Date" not in df.columns or "Close" not in df.columns or "Open" not in df.columns:
            return {"error":"CSV missing Date/Open/Close columns"}
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
        df = df.dropna(subset=["Date"]).sort_values("Date")
        sample = df.tail(days)
        if sample.empty:
            return {"error":"no rows"}
        wins = (sample["Close"] > sample["Open"]).sum()
        win_rate = float(wins) / float(len(sample))
        return {"company": company, "days": int(len(sample)), "wins": int(wins), "total": int(len(sample)), "win_rate": round(win_rate*100,2)}
    except Exception as e:
        return {"error": str(e)}

# ---------------- NEWS (opt-in, RSS) ----------------
def fetch_news_rss(company: str, days: int = 2):
    # uses Google News RSS; opt-in only
    try:
        q = requests.utils.quote(f"{company} stock")
        # when:1d may restrict to 1d; keep days param for user's understanding
        url = f"https://news.google.com/rss/search?q={q}+when:1d&hl=en-IN&gl=IN&ceid=IN:en"
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        # parse RSS (simple xml parse)
        import xml.etree.ElementTree as ET
        root = ET.fromstring(r.content)
        items = []
        for item in root.findall('.//item')[:25]:
            title = item.find('title').text if item.find('title') is not None else ""
            link = item.find('link').text if item.find('link') is not None else ""
            pub = item.find('pubDate').text if item.find('pubDate') is not None else ""
            items.append({"title": title, "link": link, "pubDate": pub})
        # persist minimal news
        NEWS_PATH.parent.mkdir(parents=True, exist_ok=True)
        NEWS_PATH.write_text(json.dumps({company: items}, indent=2), encoding="utf-8")
        return {"company": company, "count": len(items)}
    except Exception as e:
        return {"error": str(e)}

# ---------------- LLM CALL ----------------
def call_llm(question, context, allow_raw=False, selected_company=None, sample_rows=30, ai_manages=True):
    metadata = get_data_metadata()
    system_prompt = (
        "You are a senior quantitative trading intelligence assistant.\n"
        "Use verified structured data only when asked for financial analysis. Do NOT invent data.\n"
        "Expectancy is expressed as R-multiples (statistical edge). Translate technical metrics into practical meaning.\n"
        "If data missing, say so and suggest next steps. Keep answers concise and professional.\n"
        "If ai_manages=True, analyze all companies automatically and provide an actionable summary when asked.\n"
    )
    payload_body = {
        "verified_metadata": metadata,
        "daily_intelligence": context,
        "user_question": question,
        "ai_manages": bool(ai_manages),
        "allow_raw_access": bool(allow_raw),
        "selected_company": selected_company
    }
    # optionally attach raw sample
    if allow_raw and selected_company:
        file_path = RAW_PATH / selected_company / "prices" / "daily" / "daily.csv"
        if file_path.exists():
            try:
                df = pd.read_csv(file_path)
                # normalize date
                for c in df.columns:
                    if c.strip().lower() == "date":
                        df.rename(columns={c:"Date"}, inplace=True); break
                if "Date" in df.columns:
                    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
                    sample = df.tail(sample_rows).to_dict(orient="records")
                else:
                    sample = df.tail(sample_rows).to_dict(orient="records")
                payload_body["raw_sample"] = {"company": selected_company, "rows": len(sample), "sample": sample}
            except Exception as e:
                payload_body["raw_sample"] = {"error": str(e)}
        else:
            payload_body["raw_sample"] = {"error":"file missing"}

    payload = {"model": MODEL_NAME, "messages": [{"role":"system","content":system_prompt},{"role":"user","content":json.dumps(payload_body, default=str)}], "temperature": 0.12}
    try:
        r = requests.post(API_URL, json=payload, timeout=60)
        r.raise_for_status()
        body = r.json()
        return body.get("choices", [{}])[0].get("message", {}).get("content", "No content returned by model.")
    except Exception as e:
        return f"Model connection error: {str(e)}"

# ---------------- UI ----------------
class TradingUI:
    def __init__(self, root):
        self.root = root
        self.root.title("AI Trading Intelligence Terminal")
        self.root.geometry("1150x760")
        self.root.configure(bg=BG)
        init_db()
        self.selected_company = tk.StringVar()
        self.allow_raw = tk.BooleanVar(value=False)
        self.sample_rows = tk.IntVar(value=30)
        self.ai_manages = tk.BooleanVar(value=True)
        self.persist_convo = tk.BooleanVar(value=True)
        self.enable_news_flag = tk.BooleanVar(value=False)
        self.build_layout()
        self.root.after(30000, self.refresh_status)

    def build_layout(self):
        header = tk.Frame(self.root, bg=CARD, height=90)
        header.pack(fill="x")
        tk.Label(header, text="AI Trading Intelligence Terminal", font=FONT_HEADER, bg=CARD, fg=TEXT).pack(side="left", padx=18, pady=12)
        right_col = tk.Frame(header, bg=CARD); right_col.pack(side="right", padx=18, pady=8)
        self.regime_label = tk.Label(right_col, text=self.get_regime_text(), font=("Segoe UI",11), bg=CARD, fg=ACCENT); self.regime_label.pack(anchor="e")
        self.data_meta_label = tk.Label(right_col, text=self.get_data_meta_text(), font=FONT_META, bg=CARD, fg=SUBTLE, justify="right"); self.data_meta_label.pack(anchor="e", pady=(6,0))
        self.market_label = tk.Label(right_col, text=self.get_market_status_text(), font=FONT_META, bg=CARD, fg=SUBTLE, justify="right"); self.market_label.pack(anchor="e", pady=(6,0))

        controls = tk.Frame(self.root, bg=BG, height=54); controls.pack(fill="x", padx=18, pady=(8,0))
        tk.Label(controls, text="Company:", bg=BG, fg=SUBTLE, font=FONT_MAIN).pack(side="left", padx=(6,6))
        self.company_cb = ttk.Combobox(controls, textvariable=self.selected_company, state="readonly", width=42); self.company_cb.pack(side="left", padx=(0,12))
        self.refresh_companies_list()
        tk.Checkbutton(controls, text="AI manages companies (auto)", variable=self.ai_manages, bg=BG, fg=SUBTLE, selectcolor=CARD, activebackground=BG).pack(side="left", padx=(6,6))
        tk.Checkbutton(controls, text="Allow raw price sample", variable=self.allow_raw, bg=BG, fg=SUBTLE, selectcolor=CARD, activebackground=BG).pack(side="left", padx=(10,6))
        tk.Label(controls, text="Sample rows:", bg=BG, fg=SUBTLE, font=FONT_META).pack(side="left", padx=(8,4))
        tk.Spinbox(controls, from_=5, to=200, textvariable=self.sample_rows, width=5).pack(side="left", padx=(0,12))
        ttk.Button(controls, text="Show Chart", command=self.on_show_chart).pack(side="left", padx=(6,6))
        ttk.Button(controls, text="Show Raw Table", command=self.on_show_raw).pack(side="left", padx=(6,6))
        ttk.Button(controls, text="Show All Charts", command=self.on_show_all_charts).pack(side="left", padx=(6,6))
        tk.Checkbutton(controls, text="Enable news (opt-in)", variable=self.enable_news_flag, bg=BG, fg=SUBTLE, selectcolor=CARD, activebackground=BG).pack(side="right", padx=(6,6))

        # conversation area (Text)
        self.output = tk.Text(self.root, bg=BG, fg=TEXT, font=FONT_MAIN, wrap="word", relief="flat", padx=28, pady=22)
        self.output.pack(fill="both", expand=True, padx=18, pady=(10,6))
        self.output.tag_config("user", foreground=USER_COLOR, font=("Segoe UI",13,"bold"))
        self.output.tag_config("ai", foreground=AI_COLOR, font=FONT_MAIN)
        self.output.tag_config("spacing", spacing3=18)

        # bottom entry
        bottom = tk.Frame(self.root, bg=CARD, height=84); bottom.pack(fill="x", padx=18, pady=(0,18))
        self.entry = tk.Entry(bottom, font=FONT_MAIN, bg="#111318", fg=TEXT, insertbackground=TEXT, relief="flat")
        self.entry.pack(side="left", fill="x", expand=True, padx=14, pady=16)
        self.entry.bind("<Return>", self.ask)
        self.entry.bind("<Control-Return>", self.ask)
        tk.Button(bottom, text="Ask", font=("Segoe UI",12), bg=ACCENT, fg="white", relief="flat", padx=22, pady=6, command=self.ask).pack(side="right", padx=14)
        self.status_label = tk.Label(bottom, text="Ready", bg=CARD, fg=SUBTLE, font=FONT_META)
        self.status_label.pack(side="right", padx=(0,12))
        self.entry.focus_set()

    def refresh_companies_list(self):
        context = build_context(); companies = []
        if isinstance(context, list):
            for item in context:
                if isinstance(item, dict) and item.get("company"):
                    companies.append(item["company"])
        self.company_cb["values"] = companies
        if companies and not self.selected_company.get():
            self.selected_company.set(companies[0])

    def refresh_status(self):
        try:
            self.regime_label.config(text=self.get_regime_text())
            self.data_meta_label.config(text=self.get_data_meta_text())
            self.market_label.config(text=self.get_market_status_text())
            self.refresh_companies_list()
            # status
            self.status_label.config(text="Ready")
        except Exception:
            pass
        self.root.after(30000, self.refresh_status)

    def get_regime_text(self):
        regime_data = load_json_safe(REGIME_PATH); regime = regime_data.get("regime","Unknown"); return f"Market Regime: {regime}"
    def get_data_meta_text(self):
        meta = get_data_metadata()
        if not meta["data_available"]: return "Data: none"
        companies = len(meta["companies"]); earliest = meta["earliest_date"] or "N/A"; latest = meta["last_available_date"] or "N/A"; rows = meta["rows_total"]
        return f"Data: {companies} companies  ·  range: {earliest} → {latest}  ·  rows: {rows}"
    def get_market_status_text(self):
        st = market_status_info()
        if st["is_open"]: return f"Market: OPEN (closes at {st.get('next_close')})"
        return f"Market: CLOSED · next open: {st.get('next_open')}"

    def ask(self, event=None):
        question = self.entry.get().strip()
        if not question: return
        self.entry.delete(0, "end")
        self.output.insert("end", "\nYou:\n", "user")
        self.output.insert("end", f"{question}\n\n", ("user","spacing"))
        self.output.see("end")
        log_message("user", question)
        # background processing
        threading.Thread(target=self.process, args=(question,), daemon=True).start()

    def reply(self, message: str):
        self.output.insert("end", "\nAI:\n", "ai")
        self.output.insert("end", f"{message}\n\n", ("ai","spacing"))
        self.output.see("end")
        log_message("ai", message)

    # charts / raw previews
    def on_show_chart(self):
        company = self.selected_company.get()
        if not company: messagebox.showinfo("No company", "Please select a company."); return
        if not MATPLOTLIB_AVAILABLE: messagebox.showerror("Missing", "Install matplotlib to use chart preview."); return
        threading.Thread(target=self.show_chart_window, args=(company,), daemon=True).start()

    def show_chart_window(self, company):
        file_path = RAW_PATH / company / "prices" / "daily" / "daily.csv"
        if not file_path.exists(): messagebox.showinfo("Missing file", f"No daily CSV for {company}"); return
        try:
            df = pd.read_csv(file_path)
            date_col = next((c for c in df.columns if c.strip().lower()=="date"), None)
            if date_col: df.rename(columns={date_col:"Date"}, inplace=True)
            if "Date" not in df.columns or "Close" not in [c.strip().lower() for c in df.columns]:
                messagebox.showinfo("Missing columns", "CSV missing Date or Close"); return
            # normalize
            df["Date"] = pd.to_datetime(df["Date"], errors="coerce"); df = df.dropna(subset=["Date"]).sort_values("Date")
            if "Close" not in df.columns:
                # find case-insensitive close
                close_col = next((c for c in df.columns if c.strip().lower()=="close"), None)
                if close_col: df.rename(columns={close_col:"Close"}, inplace=True)
            win = tk.Toplevel(self.root); win.title(f"{company} — Close Chart")
            fig = Figure(figsize=(10,5), dpi=100); ax = fig.add_subplot(111)
            ax.plot(df["Date"], df["Close"], linewidth=1)
            ax.set_title(f"{company} — Close Price"); ax.set_xlabel("Date"); ax.set_ylabel("Close"); fig.autofmt_xdate()
            canvas = FigureCanvasTkAgg(fig, master=win); canvas.draw(); canvas.get_tk_widget().pack(fill="both", expand=True)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to render chart: {e}")

    def on_show_raw(self):
        company = self.selected_company.get()
        if not company: messagebox.showinfo("No company", "Please select a company."); return
        threading.Thread(target=self.show_raw_window, args=(company,), daemon=True).start()

    def show_raw_window(self, company):
        file_path = RAW_PATH / company / "prices" / "daily" / "daily.csv"
        if not file_path.exists(): messagebox.showinfo("Missing file", f"No daily CSV for {company}"); return
        try:
            df = pd.read_csv(file_path)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open CSV: {e}"); return
        win = tk.Toplevel(self.root); win.title(f"{company} — Raw Price Sample")
        tv = ttk.Treeview(win); tv.pack(fill="both", expand=True)
        columns = list(df.columns[:20]); tv["columns"] = columns; tv["show"]="headings"
        for c in columns: tv.heading(c, text=c); tv.column(c, width=120, anchor="w")
        sample = df.tail(200)
        for _, row in sample.iterrows():
            vals = [str(row.get(c,"")) for c in columns]; tv.insert("", "end", values=vals)
        sb = ttk.Scrollbar(win, orient="vertical", command=tv.yview); tv.config(yscrollcommand=sb.set); sb.pack(side="right", fill="y")

    def on_show_all_charts(self):
        ctx = build_context()
        companies = [c.get("company") for c in ctx if isinstance(c, dict) and c.get("company")]
        if not companies: messagebox.showinfo("No companies", "No companies in daily intelligence."); return
        if not MATPLOTLIB_AVAILABLE: messagebox.showerror("Missing", "matplotlib required for chart preview."); return
        for comp in companies:
            threading.Thread(target=self.show_chart_window, args=(comp,), daemon=True).start()

    # main processing
    def process(self, question):
        try:
            lower_q = question.lower().strip()
            # quick intents
            if lower_q in ("hi","hello","hey"):
                self.reply("Hello — how can I help with trading intelligence today?"); return
            if "date" in lower_q or "time" in lower_q:
                now = datetime.now().strftime("%A, %d %B %Y - %H:%M"); self.reply(f"Current system date & time: {now}"); return
            if "market open" in lower_q or "is market open" in lower_q or "market hours" in lower_q:
                st = market_status_info()
                if st["is_open"]: self.reply(f"Market is OPEN (phase: {st['phase']}). It closes at {st.get('next_close')}."); return
                else: self.reply(f"Market is CLOSED ({st.get('reason')}). Next open: {st.get('next_open')}."); return
            if "enable news" in lower_q or "enable news scraping" in lower_q:
                self.enable_news_flag.set(True); self.reply("News enabled (opt-in). I will fetch recent headlines on request."); return
            if "fetch news" in lower_q or ("news" in lower_q and "show" in lower_q):
                selected = self.selected_company.get() if self.selected_company.get() else None
                if not selected: self.reply("Select a company to fetch news for."); return
                self.reply("Fetching recent headlines (opt-in)...")
                res = fetch_news_rss(selected)
                if res.get("error"): self.reply(f"News fetch failed: {res['error']}")
                else: self.reply(f"Fetched {res.get('count',0)} headlines for {selected}. Use 'show news {selected}' to view.") ; return

            # parse special safe query: show last N days win rate for COMPANY
            import re
            m = re.search(r"last\s+(\d+)\s+days\s+win\s*rate\s+for\s+(.+)", lower_q)
            if m:
                days = int(m.group(1)); company = m.group(2).strip()
                # normalize company: try exact match
                companies = [c.get("company") for c in build_context() if isinstance(c, dict) and c.get("company")]
                match = None
                for c in companies:
                    if c.lower().startswith(company.lower()) or company.lower() in c.lower():
                        match = c; break
                if not match:
                    self.reply("Company not found in universe."); return
                self.reply(f"Computing positive-close rate for {match} over last {days} days...")
                rate = compute_positive_close_rate(match, days)
                if rate.get("error"):
                    self.reply(f"Could not compute: {rate['error']}")
                else:
                    self.reply(f"{match} — last {rate['days']} days: {rate['wins']} up days / {rate['total']} total → win_rate {rate['win_rate']}% (proxy: Close>Open).")
                return

            # fall back to LLM
            context = build_context()
            if not context:
                self.reply("Daily intelligence data is not available."); return
            # optionally save snapshot and allow news/raw per UI
            try:
                save_snapshot(context)
            except Exception:
                pass
            selected = self.selected_company.get() if self.selected_company.get() else None
            allow_raw = bool(self.allow_raw.get())
            ai_manages = bool(self.ai_manages.get())
            # call remote LLM (local server)
            self.reply("Thinking... (LLM)")  # immediate feedback
            answer = call_llm(question, context, allow_raw=allow_raw, selected_company=selected, sample_rows=int(self.sample_rows.get()), ai_manages=ai_manages)
            self.reply(answer)
        except Exception as e:
            tb = traceback.format_exc()
            self.reply(f"Internal error: {e}")
            print(tb)

if __name__ == "__main__":
    root = tk.Tk()
    app = TradingUI(root)
    root.mainloop()