#!/usr/bin/env python3
"""
Property Search Report Generator - Web Application
Flask backend for processing property search PDFs
"""

from flask import Flask, render_template, request, redirect, url_for, send_file, flash, jsonify, session
from werkzeug.utils import secure_filename
import os
import json
import pdfplumber
from anthropic import Anthropic
from datetime import datetime
import sqlite3
from pathlib import Path
import shutil

app = Flask(__name__)
app.secret_key = 'your-secret-key-change-this-in-production'
# Simple password protection
APP_PASSWORD = "beagle2024"  # Change this to whatever you want

@app.before_request
def check_password():
    if request.endpoint == 'login' or request.endpoint == 'static':
        return None
    if not session.get('authenticated'):
        return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form.get('password') == APP_PASSWORD:
            session['authenticated'] = True
            return redirect(url_for('index'))
        else:
            flash('Incorrect password', 'error')
    return render_template('login.html')
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max file size

# Configuration
ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY', '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')
UPLOAD_FOLDER = 'uploads'
REPORT_FOLDER = 'reports'
DATABASE = 'property_reports.db'

REPORT_PATTERNS = {
    "Environmental": ["environmental", "martello", "climate"],
    "Drainage & Water": ["drainage", "water"],
    "Local Authority": ["local", "authority", "search"]
}

SECTION_ORDER = ["Local Authority", "Environmental", "Drainage & Water"]

# Create folders
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(REPORT_FOLDER, exist_ok=True)

# Initialize database
def init_db():
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS reports
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  property_address TEXT,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  internal_report_path TEXT,
                  client_report_path TEXT,
                  signal_count INTEGER,
                  red_count INTEGER,
                  amber_count INTEGER,
                  green_count INTEGER)''')
    conn.commit()
    conn.close()

init_db()

# Helper functions from property_report.py
def extract_text_from_pdf(pdf_path):
    """Extract text from PDF"""
    text = ""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                text += page.extract_text() + "\n"
    except Exception as e:
        print(f"Error reading {pdf_path}: {e}")
    return text

def identify_report_type(filename):
    """Identify report type from filename"""
    filename_lower = filename.lower()
    for report_type, keywords in REPORT_PATTERNS.items():
        if any(keyword in filename_lower for keyword in keywords):
            return report_type
    return "Unknown"

def get_extraction_prompt(report_type, text, filename):
    """Generate extraction prompt - simplified version"""
    
    common_rules = f"""Extract signals from this {report_type} search report.

Return JSON:
{{
  "propertyAddress": "<Title Case address>",
  "signals": [
    {{
      "signal": "<Short title>",
      "category": "{report_type}",
      "description": "<What report says with quote>",
      "impact": "<How it affects transaction>",
      "trafficLight": "<red | amber | green>",
      "recommendedAction": "<Technical action>",
      "clientExplanation": "<Plain English using 'you'>"
    }}
  ]
}}"""

    if report_type == "Local Authority":
        type_rules = """
AMBER: Road not adopted, CIL, planning apps, building regs, radon 1-3%, conservation, TPOs
RED: Section 106, enforcement, CPO, radon >3%
GREEN: All clear results
"""
    elif report_type == "Environmental":
        type_rules = """
RED: Flood ≥1%, contaminated land
AMBER: Conservation proximity, climate risks
GREEN: Low radon, no issues
"""
    else:
        type_rules = """
RED: Sewer in boundary, no surface water connection
AMBER: Sewer within 3m/30m, pumping stations
GREEN: All connections confirmed
"""

    return common_rules + type_rules + f"\n\nReport from {filename}:\n{text[:15000]}\n\nReturn ONLY valid JSON."

def extract_signals_from_pdf(pdf_path, report_type):
    """Extract signals using Claude API"""
    text = extract_text_from_pdf(pdf_path)
    if not text.strip():
        return None
    
    client = Anthropic(api_key=ANTHROPIC_API_KEY)
    filename = os.path.basename(pdf_path)
    prompt = get_extraction_prompt(report_type, text, filename)

    try:
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=8000,
            messages=[{"role": "user", "content": prompt}]
        )
        
        response_text = message.content[0].text
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0]
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0]
            
        data = json.loads(response_text.strip())
        data["reportType"] = report_type
        data["sourceFile"] = filename
        
        return data
        
    except Exception as e:
        print(f"Error processing {pdf_path}: {e}")
        return None

def build_html_report(property_address, signals, sources, mode="internal"):
    """Generate HTML report"""
    
    # Count signals
    red = [s for s in signals if s.get("trafficLight") == "red"]
    amber = [s for s in signals if s.get("trafficLight") == "amber"]
    green = [s for s in signals if s.get("trafficLight") == "green"]
    
    severity_order = {"red": 0, "amber": 1, "green": 2}
    signals.sort(key=lambda s: severity_order.get(s.get("trafficLight", "green"), 3))
    
    # For client mode: only red + amber
    if mode == "client":
        signals = red + amber
    
    # Group by category
    grouped = {section: [] for section in SECTION_ORDER}
    for s in signals:
        category = s.get("category", "Environmental")
        if category in grouped:
            grouped[category].append(s)
    
    # Count by section
    all_signals = red + amber + green
    counts = {section: {"red": 0, "amber": 0, "green": 0} for section in SECTION_ORDER}
    for s in all_signals:
        category = s.get("category", "Environmental")
        traffic = s.get("trafficLight", "green")
        if category in counts:
            counts[category][traffic] += 1
    
    # Build actions
    actions = []
    seen = set()
    for s in red + amber:
        action = s.get("clientExplanation" if mode == "client" else "recommendedAction", "").strip()
        if action and action.lower() not in seen:
            seen.add(action.lower())
            actions.append(action)
    actions = actions[:8]
    
    # Styling
    header_bg = "#1d70b8" if mode == "client" else "#2c3e50"
    watermark = "CLIENT REPORT" if mode == "client" else "INTERNAL USE ONLY"
    badge = "FOR CLIENT" if mode == "client" else "INTERNAL ONLY"
    
    # Generate HTML
    html = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Property Search Report – {property_address or 'Property'}</title>
<style>
:root {{
  --color-red: #d4351c;
  --color-amber: #ffb700;
  --color-green: #00823b;
  --header-bg: {header_bg};
}}
body {{ 
  font-family: Arial, sans-serif; 
  margin: 40px; 
  line-height: 1.8;
  font-size: 16px;
  color: #0b0c0c;
}}
.watermark {{
  position: fixed;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%) rotate(-45deg);
  font-size: 120px;
  font-weight: 900;
  color: {'rgba(29, 112, 184, 0.05)' if mode == 'client' else 'rgba(44, 62, 80, 0.05)'};
  z-index: -1;
  pointer-events: none;
}}
.header {{ 
  background: var(--header-bg); 
  padding: 32px; 
  border-radius: 8px; 
  margin-bottom: 40px;
  color: white;
  position: relative;
}}
.mode-badge {{
  position: absolute;
  top: 16px;
  right: 32px;
  background: {'#fff' if mode == 'client' else 'rgba(255,255,255,0.2)'};
  color: {'#1d70b8' if mode == 'client' else '#fff'};
  padding: 8px 16px;
  border-radius: 6px;
  font-weight: 700;
  font-size: 13px;
}}
h1 {{ font-size: 28px; margin: 0; }}
.address {{ font-size: 20px; font-weight: 600; margin-top: 8px; }}
h2 {{ font-size: 22px; border-bottom: 3px solid #ddd; padding-bottom: 12px; margin-top: 32px; }}
h3 {{ font-size: 20px; margin-top: 28px; color: var(--header-bg); }}
.traffic-light-grid {{ display: grid; gap: 20px; margin: 24px 0; }}
.traffic-light-row {{ 
  border: 2px solid #ddd; 
  padding: 20px; 
  border-radius: 8px; 
  display: flex; 
  justify-content: space-between;
}}
.traffic-badge {{ padding: 10px 16px; border-radius: 6px; font-weight: 600; }}
.traffic-badge.red {{ background: #fef1ef; color: #a82315; border: 2px solid var(--color-red); }}
.traffic-badge.amber {{ background: #fffbf0; color: #8a7500; border: 2px solid var(--color-amber); }}
.traffic-badge.green {{ background: #f0f9f4; color: #006838; border: 2px solid var(--color-green); }}
.actions-box {{ 
  background: #fff4e5; 
  border: 3px solid #ff9500; 
  padding: 28px; 
  border-radius: 12px; 
  margin: 32px 0;
}}
.actions-box h2 {{ border: none; color: #d84315; margin-top: 0; }}
.actions-list {{ list-style: none; padding: 0; }}
.actions-list li {{ 
  background: white; 
  padding: 18px 18px 18px 55px; 
  margin: 14px 0; 
  border-left: 5px solid #d84315; 
  position: relative;
}}
.actions-list li::before {{ content: "→"; position: absolute; left: 16px; font-size: 26px; color: #d84315; }}
.signal-card {{ border: 2px solid #ddd; border-radius: 8px; margin: 20px 0; padding: 24px; }}
.signal-card.red {{ border-left: 6px solid var(--color-red); background: #fef9f8; }}
.signal-card.amber {{ border-left: 6px solid var(--color-amber); background: #fffef9; }}
.signal-card.green {{ border-left: 6px solid var(--color-green); }}
.signal-card h4 {{ margin: 0 0 12px; font-size: 19px; }}
.signal-card p {{ margin: 10px 0; }}
</style>
</head>
<body>
<div class="watermark">{watermark}</div>
<div class="header">
  <div class="mode-badge">{badge}</div>
  <h1>Property Search Report</h1>
  <div class="address">{property_address or 'Property'}</div>
</div>
"""

    if mode == "client":
        html += """<div style="background: #f0f4f5; padding: 20px; border-radius: 6px; margin: 20px 0; border-left: 4px solid var(--header-bg);">
  <p><strong>About This Report</strong></p>
  <p>This report summarises key findings from searches on your property. Please read carefully and contact us with any questions.</p>
</div>"""

    html += "<h2>At a Glance</h2><div class=\"traffic-light-grid\">"
    
    for section in SECTION_ORDER:
        c = counts[section]
        html += f"""<div class="traffic-light-row">
    <strong>{section}</strong>
    <div>"""
        if c["red"] > 0:
            html += f'<span class="traffic-badge red">{"⚠️ Action Required" if mode == "client" else "✖ Significant"} ({c["red"]})</span> '
        if c["amber"] > 0:
            html += f'<span class="traffic-badge amber">{"ℹ️ Please Note" if mode == "client" else "! Advisory"} ({c["amber"]})</span> '
        if c["red"] == 0 and c["amber"] == 0:
            html += '<span class="traffic-badge green">✓ Clear</span>'
        html += "</div></div>"
    
    html += "</div>"
    
    if actions:
        html += f"""<div class="actions-box">
  <h2>{"⚠️ Important Points" if mode == "client" else "⚠️ Priority Actions"}</h2>
  <p>{"Please review these items carefully:" if mode == "client" else "Complete before exchange:"}</p>
  <ul class="actions-list">"""
        for action in actions:
            html += f"<li>{action}</li>"
        html += "</ul></div>"
    
    html += f"<h2>{'What We Found' if mode == 'client' else 'Detailed Findings'}</h2>"
    
    for section in SECTION_ORDER:
        section_signals = grouped[section]
        html += f"<h3>{section}</h3>"
        
        if not section_signals:
            html += f"""<div class="signal-card green">
  <h4>✓ No Issues Found</h4>
  <p>All standard checks completed with no issues requiring attention.</p>
</div>"""
        else:
            for s in section_signals:
                html += f"""<div class="signal-card {s.get('trafficLight', 'green')}">
  <h4>{s.get('signal', '')}</h4>"""
                if mode == "client":
                    html += f"<p>{s.get('clientExplanation', s.get('impact', ''))}</p>"
                else:
                    html += f"""<p>{s.get('description', '')}</p>
  <p><strong>Impact:</strong> {s.get('impact', '')}</p>
  <p><strong>Action:</strong> {s.get('recommendedAction', '')}</p>"""
                html += "</div>"
    
    html += f"""<hr style="margin-top: 48px; border: none; border-top: 2px solid #ddd;">
<p style="font-size: 13px; color: #505a5f;">
<strong>Sources:</strong> {'; '.join(f'{k}: {v}' for k, v in sources.items())}<br>
Generated: {datetime.now().strftime('%d %B %Y at %H:%M')}
</p>
</body>
</html>"""
    
    return html

# Routes
@app.route('/')
def index():
    return render_template('upload.html')

@app.route('/upload', methods=['POST'])
def upload():
    try:
        # Get property address
        property_address = request.form.get('property_address', '').strip()
        if not property_address:
            flash('Please enter a property address', 'error')
            return redirect(url_for('index'))
        
        # Get uploaded files
        files = {
            'local': request.files.get('local_authority'),
            'environmental': request.files.get('environmental'),
            'drainage': request.files.get('drainage')
        }
        
        # Check files exist
        if not all(files.values()):
            flash('Please upload all 3 PDF files', 'error')
            return redirect(url_for('index'))
        
        # Create unique folder for this property
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        property_folder = os.path.join(UPLOAD_FOLDER, timestamp)
        os.makedirs(property_folder, exist_ok=True)
        
        # Save uploaded files
        saved_files = {}
        for key, file in files.items():
            if file:
                filename = secure_filename(file.filename)
                filepath = os.path.join(property_folder, filename)
                file.save(filepath)
                saved_files[key] = filepath
        
        # Process PDFs
        all_signals = []
        sources = {}
        
        for filepath in saved_files.values():
            report_type = identify_report_type(os.path.basename(filepath))
            result = extract_signals_from_pdf(filepath, report_type)
            
            if result:
                sources[report_type] = os.path.basename(filepath)
                all_signals.extend(result.get('signals', []))
        
        # Generate reports
        internal_html = build_html_report(property_address, all_signals.copy(), sources, mode="internal")
        client_html = build_html_report(property_address, all_signals.copy(), sources, mode="client")
        
        # Save reports
        report_folder = os.path.join(REPORT_FOLDER, timestamp)
        os.makedirs(report_folder, exist_ok=True)
        
        safe_address = property_address.replace("/", "-").replace("\\", "-")[:50]
        internal_path = os.path.join(report_folder, f"{safe_address}_INTERNAL.html")
        client_path = os.path.join(report_folder, f"{safe_address}_CLIENT.html")
        
        with open(internal_path, 'w', encoding='utf-8') as f:
            f.write(internal_html)
        with open(client_path, 'w', encoding='utf-8') as f:
            f.write(client_html)
        
        # Count signals
        red_count = len([s for s in all_signals if s.get("trafficLight") == "red"])
        amber_count = len([s for s in all_signals if s.get("trafficLight") == "amber"])
        green_count = len([s for s in all_signals if s.get("trafficLight") == "green"])
        
        # Save to database
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute('''INSERT INTO reports 
                     (property_address, internal_report_path, client_report_path, 
                      signal_count, red_count, amber_count, green_count)
                     VALUES (?, ?, ?, ?, ?, ?, ?)''',
                  (property_address, internal_path, client_path, len(all_signals),
                   red_count, amber_count, green_count))
        report_id = c.lastrowid
        conn.commit()
        conn.close()
        
        # Clean up uploaded files
        shutil.rmtree(property_folder)
        
        return redirect(url_for('results', report_id=report_id))
        
    except Exception as e:
        flash(f'Error processing reports: {str(e)}', 'error')
        return redirect(url_for('index'))

@app.route('/results/<int:report_id>')
def results(report_id):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('SELECT * FROM reports WHERE id = ?', (report_id,))
    report = c.fetchone()
    conn.close()
    
    if not report:
        flash('Report not found', 'error')
        return redirect(url_for('index'))
    
    return render_template('results.html', report=report)

@app.route('/download/<int:report_id>/<report_type>')
def download(report_id, report_type):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('SELECT internal_report_path, client_report_path FROM reports WHERE id = ?', (report_id,))
    result = c.fetchone()
    conn.close()
    
    if not result:
        flash('Report not found', 'error')
        return redirect(url_for('index'))
    
    path = result[0] if report_type == 'internal' else result[1]
    return send_file(path, as_attachment=True)

@app.route('/history')
def history():
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('SELECT * FROM reports ORDER BY created_at DESC LIMIT 50')
    reports = c.fetchall()
    conn.close()
    return render_template('history.html', reports=reports)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)
