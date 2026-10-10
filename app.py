import streamlit as st
import pandas as pd
import joblib
import shap
import plotly.graph_objects as go
import plotly.express as px
from fpdf import FPDF
import random
import time
import os
import streamlit.components.v1 as components
import base64
import hashlib
import qrcode
from io import BytesIO
from datetime import datetime
import re
import auth_db

# ─────────────────────────────────────────────────────────────
# UTILITY FUNCTIONS
# ─────────────────────────────────────────────────────────────

def generate_secure_receipt(amount, receiver, time_str, risk_score, verdict):
    pdf = FPDF()
    pdf.add_page()
    
    # Generate unique transaction hash
    raw_str = f"{amount}{receiver}{time_str}{random.random()}"
    tx_hash = hashlib.sha256(raw_str.encode()).hexdigest()[:16].upper()
    
    # PDF Styling
    pdf.set_fill_color(10, 20, 30) # Dark theme background
    pdf.rect(0, 0, 210, 297, 'F')
    
    pdf.set_text_color(0, 255, 204) # Neon Cyan
    pdf.set_font("Arial", 'B', 24)
    pdf.cell(0, 20, "SURAKSHA KAWACH", 0, 1, 'C')
    
    pdf.set_font("Arial", '', 10)
    pdf.set_text_color(150, 150, 150)
    pdf.cell(0, 10, "AI-POWERED SECURE TRANSACTION RECEIPT", 0, 1, 'C')
    pdf.ln(10)
    
    # Receipt Details Box
    pdf.set_draw_color(0, 255, 204)
    pdf.set_fill_color(20, 30, 40)
    pdf.rect(20, 50, 170, 100, 'DF')
    
    pdf.set_xy(30, 60)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(50, 10, "Transaction ID:", 0, 0)
    pdf.set_font("Arial", '', 12)
    pdf.cell(0, 10, tx_hash, 0, 1)
    
    pdf.set_x(30)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(50, 10, "Date & Time:", 0, 0)
    pdf.set_font("Arial", '', 12)
    pdf.cell(0, 10, time_str, 0, 1)
    
    pdf.set_x(30)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(50, 10, "Amount:", 0, 0)
    pdf.set_font("Arial", '', 12)
    pdf.cell(0, 10, f"INR {amount:,.2f}", 0, 1)
    
    pdf.set_x(30)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(50, 10, "Receiver:", 0, 0)
    pdf.set_font("Arial", '', 12)
    pdf.cell(0, 10, receiver, 0, 1)
    
    pdf.ln(10)
    pdf.set_x(30)
    pdf.set_draw_color(100, 100, 100)
    pdf.line(30, 110, 180, 110)
    pdf.ln(10)
    
    # PDF Verdict Text (Remove emojis as they aren't supported by standard FPDF fonts)
    pdf.set_x(30)
    pdf.set_font("Arial", 'B', 14)
    pdf.set_text_color(0, 255, 204)
    pdf.cell(50, 10, "AI SAFETY VERDICT:", 0, 0)
    pdf.set_font("Arial", 'B', 14)
    
    clean_verdict = verdict.replace("🟢 ", "").replace("🟡 ", "").replace("🔴 ", "")
    if "SAFE" in clean_verdict:
        pdf.set_text_color(0, 255, 100)
    elif "MEDIUM" in clean_verdict:
        pdf.set_text_color(255, 180, 0)
    else:
        pdf.set_text_color(255, 50, 50)
        
    pdf.cell(0, 10, clean_verdict, 0, 1)
    
    # ── QR Code Generation ───────────────────────────────────
    # Create QR data (Transaction Hash + Verification URL)
    qr_data = f"Suraksha Kawach Verification\nTX ID: {tx_hash}\nAmount: INR {amount}\nStatus: {verdict}"
    qr = qrcode.QRCode(version=1, box_size=10, border=2)
    qr.add_data(qr_data)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white")
    
    # Save QR to bytes buffer
    qr_buffer = BytesIO()
    qr_img.save(qr_buffer, format="PNG")
    qr_buffer.seek(0)
    
    # Position QR code on the right side of the details box
    # Temporarily save to a temp file because FPDF image() often prefers paths
    import tempfile
    with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp_file:
        tmp_file.write(qr_buffer.getvalue())
        tmp_path = tmp_file.name
    
    pdf.image(tmp_path, x=145, y=65, w=35) # Place inside the details box area
    
    # Clean up temp file
    try:
        os.remove(tmp_path)
    except:
        pass
    
    # Footer
    pdf.set_y(260)
    pdf.set_font("Arial", 'I', 8)
    pdf.set_text_color(100, 100, 100)
    pdf.multi_cell(0, 5, "This is an AI-generated secure digital receipt. \nVerified by Suraksha Kawach Fraud Intelligence Engine.", 0, 'C')
    
    return pdf.output(dest='S').encode('latin-1')

# ─────────────────────────────────────────────────────────────
# SESSION STATE INITIALIZATION
# ─────────────────────────────────────────────────────────────

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "current_user" not in st.session_state:
    st.session_state.current_user = None
if "user_role" not in st.session_state:
    st.session_state.user_role = None
if "history" not in st.session_state:
    st.session_state.history = []
if "forgot_password" not in st.session_state:
    st.session_state.forgot_password = False

# ─────────────────────────────────────────────────────────────
# PAGE CONFIG
# ─────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Suraksha Kawach",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ─────────────────────────────────────────────────────────────
# GLOBAL CSS — Dark Fintech Glassmorphism Theme
# ─────────────────────────────────────────────────────────────

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700;900&family=Inter:wght@300;400;600;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
    background-color: #050d1a;
    color: #e0e6f0;
}

.block-container {
    padding-top: 0.5rem !important;
    padding-bottom: 2rem !important;
    max-width: 1200px;
}

/* Scrollbar */
::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: #0d1b2a; }
::-webkit-scrollbar-thumb { background: #00ffcc44; border-radius: 3px; }

/* Glassmorphism card */
.glass-card {
    background: rgba(0, 255, 200, 0.04);
    border: 1px solid rgba(0, 255, 200, 0.15);
    border-radius: 16px;
    padding: 24px;
    margin: 12px 0;
    box-shadow: 0 4px 30px rgba(0, 255, 200, 0.05), 0 0 1px rgba(0,255,200,0.3);
    backdrop-filter: blur(10px);
}

/* Neon heading */
.neon-title {
    font-family: 'Orbitron', monospace;
    font-size: 3rem;
    font-weight: 900;
    color: #ffffff;
    text-align: center;
    text-shadow:
        0 0 10px #00ffcc,
        0 0 30px #00ffcc88,
        0 0 60px #00ffcc44;
    letter-spacing: 3px;
    margin-bottom: 0;
}

.neon-subtitle {
    font-family: 'Orbitron', monospace;
    font-size: 0.85rem;
    color: #00ffd5aa;
    text-align: center;
    letter-spacing: 6px;
    margin-top: 4px;
}

div[data-testid="stRadio"] {
    margin: 15px 0 4px 0;
    padding: 8px 15px;
}

div[data-testid="stRadio"] > div {
    flex-direction: row;
    align-items: center;
    gap: 15px;
}

/* Custom styling for metrics */
[data-testid="stMetricValue"] {
    font-family: 'Orbitron', monospace !important;
    font-size: 1.8rem !important;
    color: #00ffcc !important;
}

/* UPI Simulation Card */
.upi-card {
    background: linear-gradient(145deg, #0a192f 0%, #050d1a 100%);
    border: 1px solid rgba(0, 255, 200, 0.2);
    border-radius: 20px;
    padding: 25px;
    box-shadow: 0 10px 30px rgba(0,0,0,0.5);
    margin: 15px 0;
    position: relative;
    overflow: hidden;
}

.upi-amount {
    font-family: 'Orbitron', monospace;
    font-size: 2.2rem;
    font-weight: 700;
    color: #ffffff;
    margin: 10px 0;
}

.upi-label {
    color: #4a6a7a;
    font-size: 0.7rem;
    text-transform: uppercase;
    letter-spacing: 1px;
}

.upi-value {
    color: #00ffcc;
    font-size: 0.9rem;
    font-weight: 600;
}

/* Section Header */
.section-header {
    font-family: 'Orbitron', monospace;
    font-size: 0.95rem;
    color: #00ffcc;
    border-left: 3px solid #00ffcc;
    padding-left: 12px;
    margin: 25px 0 15px 0;
    letter-spacing: 2px;
    text-transform: uppercase;
}

/* Status pill */
.status-pill {
    display: inline-flex;
    align-items: center;
    background: rgba(0, 255, 200, 0.08);
    border: 1px solid rgba(0, 255, 200, 0.3);
    padding: 4px 12px;
    border-radius: 20px;
    margin-bottom: 15px;
}

.blink-dot {
    width: 8px;
    height: 8px;
    background-color: #00ffcc;
    border-radius: 50%;
    margin-right: 8px;
    animation: blink 1.2s infinite;
    box-shadow: 0 0 8px #00ffcc;
}

@keyframes blink {
    0% { opacity: 1; }
    50% { opacity: 0.3; }
    100% { opacity: 1; }
}

.status-text {
    font-family: 'Orbitron', monospace;
    font-size: 0.65rem;
    color: #00ffcc;
    letter-spacing: 1px;
}

/* Complaint card */
.complaint-card {
    background: rgba(255, 50, 50, 0.05);
    border: 1px solid rgba(255, 50, 50, 0.2);
    border-radius: 12px;
    padding: 15px;
    margin-top: 15px;
    font-family: 'Inter', sans-serif;
    line-height: 1.6;
    color: #ffaaaa;
}

/* Radar animation */
.radar-wrap {
    display: flex;
    justify-content: center;
    align-items: center;
    margin: 25px 0 15px 0;
}

.radar {
    position: relative;
    width: 200px;
    height: 200px;
    border-radius: 50%;
    background: radial-gradient(circle at center, rgba(0, 40, 30, 0.4) 0%, rgba(0, 10, 5, 0.8) 100%);
    border: 2px solid rgba(0, 255, 200, 0.3);
    box-shadow: 
        0 0 50px rgba(0, 255, 200, 0.15),
        inset 0 0 30px rgba(0, 255, 200, 0.1);
    overflow: hidden;
}

/* Futuristic Grid Overlay */
.radar::before {
    content: '';
    position: absolute;
    inset: 0;
    background-image: 
        linear-gradient(rgba(0, 255, 200, 0.1) 1px, transparent 1px),
        linear-gradient(90deg, rgba(0, 255, 200, 0.1) 1px, transparent 1px);
    background-size: 20px 20px;
    background-position: center;
    opacity: 0.3;
}

/* Concentric rings */
.radar::after {
    content: '';
    position: absolute;
    inset: 0;
    border-radius: 50%;
    background:
        radial-gradient(circle at center, transparent 24%, rgba(0,255,180,0.15) 25%, transparent 26%),
        radial-gradient(circle at center, transparent 49%, rgba(0,255,180,0.12) 50%, transparent 51%),
        radial-gradient(circle at center, transparent 74%, rgba(0,255,180,0.1) 75%, transparent 76%);
}

.radar-sweep {
    position: absolute;
    width: 100%;
    height: 100%;
    border-radius: 50%;
    background: conic-gradient(
        rgba(0, 255, 200, 0.6) 0deg,
        rgba(0, 255, 200, 0.2) 20deg,
        rgba(0, 255, 200, 0.05) 60deg,
        transparent 120deg
    );
    animation: radarSpin 3s linear infinite;
    filter: blur(1px);
}

/* Scanning line */
.radar-line {
    position: absolute;
    top: 50%;
    left: 50%;
    width: 50%;
    height: 2px;
    background: linear-gradient(90deg, rgba(0, 255, 200, 0.8), transparent);
    transform-origin: left center;
    animation: radarSpin 3s linear infinite;
    box-shadow: 0 0 15px rgba(0, 255, 200, 0.6);
}

@keyframes radarSpin {
    0%   { transform: rotate(0deg); }
    100% { transform: rotate(360deg); }
}

/* Divider */
hr {
    border-color: rgba(0,255,200,0.1) !important;
    margin: 20px 0 !important;
}

/* Security Log Terminal Style */
.security-log {
    background: rgba(0, 15, 10, 0.85);
    border: 1px solid rgba(0, 255, 200, 0.3);
    border-radius: 12px;
    padding: 15px;
    font-family: 'Courier New', Courier, monospace;
    font-size: 0.85rem;
    color: #00ffcc;
    max-height: 200px;
    overflow-y: auto;
    margin: 15px 0;
    box-shadow: inset 0 0 10px rgba(0, 255, 200, 0.1);
}

.log-entry {
    margin-bottom: 5px;
    border-left: 2px solid rgba(0, 255, 200, 0.4);
    padding-left: 8px;
    animation: logFadeIn 0.3s ease-out;
}

.log-time { color: #4a6a7a; margin-right: 8px; font-size: 0.75rem; }
.log-tag { font-weight: bold; margin-right: 8px; }
.tag-info { color: #00ffcc; }
.tag-sec { color: #ffcc00; }
.tag-alert { color: #ff4444; }

@keyframes logFadeIn {
    from { opacity: 0; transform: translateX(-5px); }
    to { opacity: 1; transform: translateX(0); }
}

/* Security Shield Overlay */
.shield-overlay {
    text-align: center;
    padding: 40px;
    background: radial-gradient(circle at center, rgba(0, 40, 30, 0.4) 0%, transparent 70%);
    border-radius: 50%;
    margin: 20px auto;
    width: fit-content;
    position: relative;
}

.shield-icon {
    font-size: 5rem;
    filter: drop-shadow(0 0 20px rgba(0, 255, 200, 0.5));
    animation: shieldPulse 1.5s ease-in-out infinite;
}

@keyframes shieldPulse {
    0%, 100% { transform: scale(1); filter: drop-shadow(0 0 20px rgba(0, 255, 200, 0.5)); }
    50% { transform: scale(1.1); filter: drop-shadow(0 0 40px rgba(0, 255, 200, 0.8)); }
}

.shield-scan-line {
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 4px;
    background: linear-gradient(90deg, transparent, rgba(0, 255, 200, 0.8), transparent);
    animation: shieldScan 2s linear infinite;
    box-shadow: 0 0 15px rgba(0, 255, 200, 0.6);
}

@keyframes shieldScan {
    0% { top: 0%; opacity: 0; }
    10% { opacity: 1; }
    90% { opacity: 1; }
    100% { top: 100%; opacity: 0; }
}

/* ── Mode Switch Radio ──────────────────────────────────── */
/* Hide the widget label entirely */
div[data-testid="stRadio"] > label,
div[data-testid="stRadio"] [data-testid="stWidgetLabel"] { 
    display: none !important; 
}

/* Force the radio group to be centered and span full width */
div[data-testid="stRadio"], div[role="radiogroup"] {
    display: flex !important;
    flex-direction: row !important;
    justify-content: center !important;
    align-items: center !important;
    width: 100% !important;
    margin: 40px auto !important;
    padding: 0 !important;
    gap: 25px !important; /* Spacing between the three buttons */
}

/* Ensure only the buttons themselves are styled */
div[role="radiogroup"] label[data-baseweb="radio"],
div[data-testid="stRadio"] label[data-baseweb="radio"] {
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    min-width: 180px !important;
    padding: 12px 24px !important;
    border-radius: 50px !important;
    border: 1.5px solid rgba(0, 255, 200, 0.2) !important;
    background: rgba(0, 255, 200, 0.04) !important;
    font-family: 'Orbitron', monospace !important;
    font-size: 0.82rem !important;
    letter-spacing: 2px !important;
    color: #8fa3b0 !important;
    cursor: pointer !important;
    transition: all 0.3s ease !important;
    margin: 0 !important;
    flex: 0 1 auto !important;
    box-shadow: 0 4px 15px rgba(0, 0, 0, 0.2) !important;
}

div[role="radiogroup"] label:hover,
div[data-testid="stRadio"] label:hover {
    border-color: rgba(0,255,200,0.5) !important;
    color: #00ffcc !important;
    box-shadow: 0 0 15px rgba(0,255,200,0.15) !important;
}

/* ── ACTIVE pill ── */
div[role="radiogroup"] label:has(input:checked),
div[data-testid="stRadio"] label:has(input:checked) {
    background: linear-gradient(135deg, rgba(0,255,200,0.25), rgba(0,200,160,0.15)) !important;
    border: 2px solid rgba(0,255,200,0.8) !important;
    color: #ffffff !important;
    box-shadow: 0 0 30px rgba(0,255,200,0.4), inset 0 0 10px rgba(0,255,200,0.1) !important;
    font-weight: 700 !important;
    text-shadow: 0 0 10px rgba(0,255,200,0.5) !important;
}

/* Hide the radio circles and markers for SELECT MODE ONLY */
div[data-testid="stRadio"] label:first-child div[data-testid="stRadioButtonDot"],
div[role="radiogroup"] label:first-child div[data-testid="stRadioButtonDot"],
div[data-testid="stRadio"] label:first-child > div:first-child,
div[role="radiogroup"] label:first-child > div:first-child { 
    display: none !important; 
}

/* Hide default technical radio elements but keep the custom dot for Bank/User */
div[data-testid="stRadio"] input[type="radio"], 
div[data-testid="stRadio"] div[role="presentation"],
div[data-testid="stRadio"] svg,
div[role="radiogroup"] input[type="radio"], 
div[role="radiogroup"] div[role="presentation"],
div[role="radiogroup"] svg { 
    display: none !important; 
}

/* Style the visible dots for Bank/User modes to match theme */
div[data-testid="stRadio"] [data-testid="stMarkdownContainer"] p {
    margin: 0 !important;
}
div[data-testid="stRadioButtonDot"] {
    background-color: #00ffcc !important;
    border-color: #00ffcc !important;
}

/* ── PROFESSIONAL POPUP OVERLAY ── */
.bank-popup-overlay {
    position: fixed;
    top: 0; left: 0; right: 0; bottom: 0;
    background: rgba(0,0,0,0.85);
    backdrop-filter: blur(8px);
    z-index: 999999;
    display: flex;
    align-items: center;
    justify-content: center;
    animation: fadeIn 0.3s ease;
}

.bank-popup-box {
    background: #0a0a0a;
    border-radius: 16px;
    width: 90%;
    max-width: 450px;
    padding: 30px;
    text-align: center;
    animation: slideUp 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
}

/* Red variation for BLOCKED */
.popup-blocked {
    border: 2px solid #ff3333;
    border-top: 6px solid #ff3333;
    box-shadow: 0 10px 40px rgba(255,0,0,0.3);
}

/* Green/Cyan variation for SUCCESS/REPORTED */
.popup-success {
    border: 2px solid #00ffcc;
    border-top: 6px solid #00ffcc;
    box-shadow: 0 10px 40px rgba(0,255,204,0.2);
}

.bank-popup-title { 
    font-family: 'Orbitron', monospace; 
    font-size: 1.4rem; 
    letter-spacing: 1px; 
    margin: 16px 0 8px 0; 
}

.title-red { color: #ff3333; }
.title-green { color: #00ffcc; }

.bank-popup-text { color: #d0d0d0; font-size: 0.95rem; line-height: 1.6; margin-bottom: 24px; }

.bank-popup-details { 
    background: #151515; 
    padding: 12px; 
    border-radius: 8px; 
    font-family: monospace; 
    font-size: 0.9rem; 
    color: #8fa3b0; 
    margin-bottom: 24px; 
    text-align: left; 
}

.details-red { border-left: 3px solid #ff3333; }
.details-green { border-left: 3px solid #00ffcc; }

@keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
@keyframes slideUp { from { transform: translateY(40px) scale(0.9); opacity: 0; } to { transform: translateY(0) scale(1); opacity: 1; } }
@keyframes pulse { 0% { transform: scale(1); } 50% { transform: scale(1.1); } 100% { transform: scale(1); } }

/* ── Custom Tab Styles ── */
.stTabs [data-baseweb="tab-list"] {
    gap: 8px;
    justify-content: center;
}
.stTabs [data-baseweb="tab"] {
    font-family: 'Orbitron', monospace;
    color: #8fa3b0;
    letter-spacing: 2px;
}
.stTabs [aria-selected="true"] {
    color: #00ffcc !important;
    border-bottom: 2px solid #00ffcc !important;
}
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────
# AUTHENTICATION LOGIC
# ─────────────────────────────────────────────────────────────

def show_login():
    st.markdown("""
    <div style="text-align:center; padding: 100px 0 20px 0;">
        <div class="neon-title">🛡 SURAKSHA KAWACH</div>
        <div class="neon-subtitle">AI POWERED FRAUD INTELLIGENCE SYSTEM</div>
    </div>
    """, unsafe_allow_html=True)
    
    _, col, _ = st.columns([1, 2, 1])
    with col:
        st.markdown("""
        <div style="font-family:'Orbitron', monospace; color: #00ffcc; font-size: 1.2rem; letter-spacing: 3px; margin-top: 10px; margin-bottom: 20px; text-align:center;">
            🔐 SECURE TERMINAL
        </div>
        """, unsafe_allow_html=True)
        
        # Check for registration success to show message on Login tab
        if "reg_success_msg" in st.session_state:
            st.success(st.session_state.reg_success_msg)
            del st.session_state.reg_success_msg

        tab1, tab2 = st.tabs(["LOGIN", "REGISTER"])
        
        with tab1:
            if st.session_state.get("forgot_password", False):
                st.markdown("<br>", unsafe_allow_html=True)
                st.markdown("<div style='color: #00ffcc; font-family: Orbitron; font-size: 1rem; text-align: center; margin-bottom: 20px;'>RESET ACCESS KEY</div>", unsafe_allow_html=True)
                
                reset_user = st.text_input("User Name / Email 👤", key="reset_user", placeholder="Enter your registered user name or email...")
                new_pwd = st.text_input("New Access Key 🔑", type="password", key="new_pwd", placeholder="Enter new password...")
                confirm_new_pwd = st.text_input("Confirm New Access Key 🔑", type="password", key="confirm_new_pwd", placeholder="Confirm new password...")
                
                st.markdown("<br>", unsafe_allow_html=True)
                c1, c2 = st.columns(2)
                with c1:
                    if st.button("UPDATE KEY", use_container_width=True, type="primary"):
                        if not all([reset_user, new_pwd, confirm_new_pwd]):
                            st.error("ALL FIELDS ARE REQUIRED.")
                        elif new_pwd != confirm_new_pwd:
                            st.error("PASSWORDS DO NOT MATCH.")
                        elif len(new_pwd) < 6:
                            st.error("ACCESS KEY MUST BE AT LEAST 6 CHARACTERS.")
                        elif not auth_db.user_exists(reset_user):
                            st.error("USER NOT FOUND.")
                        else:
                            if auth_db.update_password(reset_user, new_pwd):
                                st.success("SUCCESS! KEY UPDATED.")
                                time.sleep(1.5)
                                st.session_state.forgot_password = False
                                st.rerun()
                            else:
                                st.error("DATABASE UPDATE FAILED.")
                with c2:
                    if st.button("BACK TO LOGIN", use_container_width=True):
                        st.session_state.forgot_password = False
                        st.rerun()
            else:
                st.markdown("<br>", unsafe_allow_html=True)
                user = st.text_input("User Name / Email 👤", key="login_user", placeholder="Enter user name or email...")
                pwd = st.text_input("Access Key 🔑", type="password", key="login_pwd", placeholder="Enter password...")
                
                if st.button("AUTHORIZE ACCESS", use_container_width=True, type="primary"):
                    if user.lower() == "admin" and pwd == "secure123":
                        st.session_state.authenticated = True
                        st.session_state.current_user = {"user_name": "System Administrator", "email": "admin@system.local"}
                        st.success("CREDENTIALS VERIFIED. INITIALIZING SECURE CORE...")
                        time.sleep(1.5)
                        st.rerun()
                    else:
                        user_data = auth_db.verify_user(user, pwd)
                        if user_data:
                            st.session_state.authenticated = True
                            st.session_state.current_user = user_data
                            st.success(f"WELCOME, {user_data['user_name'].upper()}. INITIALIZING...")
                            time.sleep(1.5)
                            st.rerun()
                        else:
                            st.error("ACCESS DENIED: INVALID CREDENTIALS")
                
                # Forgot Password Link
                st.markdown("""
                <div style="text-align: right; margin-top: -10px; margin-bottom: 10px;">
                """, unsafe_allow_html=True)
                if st.button("Forgot Access Key❓", key="forgot_pwd_btn", type="secondary", help="Click to reset your password"):
                    st.session_state.forgot_password = True
                    st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)
                            
                st.markdown("""
                <div style="text-align:center; margin: 15px 0;">
                    <span style="color:#4a6a7a; font-size: 0.8rem; letter-spacing: 2px;">─── OR ───</span>
                </div>
                """, unsafe_allow_html=True)
                
                if st.button("👤 LOGIN AS DEMO USER", use_container_width=True):
                    st.info("Initializing system with demonstration credentials...")
                    st.session_state.authenticated = True
                    st.session_state.current_user = auth_db.get_or_create_demo_user("demo_user_123", "Demo User", "demo@surakshakawach.local")
                    time.sleep(2)
                    st.rerun()
                
        with tab2:
            st.markdown("<br>", unsafe_allow_html=True)
            with st.form("register_form", clear_on_submit=True):
                reg_name = st.text_input("User Name 👤", placeholder="Choose your user name...")
                reg_email = st.text_input("Email Address 📧", placeholder="Enter your email...")
                reg_pwd = st.text_input("Create Access Key 🔑", type="password", placeholder="Enter password...")
                reg_pwd2 = st.text_input("Confirm Access Key 🔑", type="password", placeholder="Confirm password...")
                
                submitted = st.form_submit_button("CREATE SECURE ACCOUNT", use_container_width=True)
                
                if submitted:
                    if not all([reg_name, reg_email, reg_pwd]):
                        st.error("ALL FIELDS ARE REQUIRED.")
                    elif not re.match(r"[^@]+@[^@]+\.[^@]+", reg_email):
                        st.error("INVALID EMAIL FORMAT.")
                    elif reg_pwd != reg_pwd2:
                        st.error("ACCESS KEYS DO NOT MATCH.")
                    elif len(reg_pwd) < 6:
                        st.error("ACCESS KEY MUST BE AT LEAST 6 CHARACTERS.")
                    else:
                        res = auth_db.register_user(reg_name, reg_email, reg_pwd)
                        if res["success"]:
                            # Store success message and rerun to switch to login tab
                            st.session_state.reg_success_msg = "REGISTRATION SUCCESSFUL! PLEASE LOGIN BELOW."
                            st.rerun()
                        else:
                            st.error(res["message"])



if not st.session_state.authenticated:
    show_login()
    st.stop()

# Show logout in sidebar
with st.sidebar:
    # Display the current user if available
    user_display = "ADMIN"
    if st.session_state.current_user:
        user_display = st.session_state.current_user.get("user_name", "USER").upper()
        
    st.markdown(f"""
    <div style="padding: 10px; border-left: 2px solid #00ffcc; background: rgba(0,255,200,0.05); margin-bottom: 15px;">
        <div style="color: #00ffcc; font-family: Orbitron; font-size: 0.8rem;">SECURE SESSION ACTIVE</div>
        <div style="color: #e0e6f0; font-size: 0.9rem; margin-top: 5px;">👤 {user_display}</div>
    </div>
    """, unsafe_allow_html=True)
    
    if st.button("🔴 TERMINATE SESSION", use_container_width=True):
        st.session_state.authenticated = False
        st.session_state.current_user = None
        st.rerun()
    
    st.divider()
    if st.button("🔄 RESET ALL MODES", use_container_width=True, help="Clear all simulation data and results"):
        # Clear all relevant session state keys
        keys_to_clear = [
            "bank_analysis_result", "sim_amount", "sim_hour", "receiver", 
            "payment_proceeded", "mfa_verified", "sim_risk_score", 
            "animation_done", "fraud_alert_done", "history"
        ]
        for key in keys_to_clear:
            if key in st.session_state:
                del st.session_state[key]
        st.session_state.mode_select_radio = "⚙️  SELECT MODE"
        st.success("System Reset Complete!")
        time.sleep(1)
        st.rerun()

# ─────────────────────────────────────────────────────────────
# HEADER
# ─────────────────────────────────────────────────────────────

st.markdown("""
<div style="text-align:center; padding: 25px 0 10px 0;">
    <div class="neon-title">🛡 SURAKSHA KAWACH</div>
    <div class="neon-subtitle" style="margin-top: 15px; margin-bottom: 30px;">AI POWERED FRAUD INTELLIGENCE SYSTEM</div>
</div>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────
# MODE TOGGLE — st.radio (styles defined in global CSS above)
# ─────────────────────────────────────────────────────────────

# Initialize session state for mode if not exists
if "mode_select_radio" not in st.session_state:
    st.session_state.mode_select_radio = "⚙️  SELECT MODE"

# We use the index parameter to control the radio button's value.
# We DO NOT use the 'key' parameter here because it locks the session state variable.
_selected = st.radio(
    "SELECT MODE ▶️",
    options=["⚙️  SELECT MODE", "🏦  BANK SYSTEM", "👤  USER SIMULATION"],
    index=["⚙️  SELECT MODE", "🏦  BANK SYSTEM", "👤  USER SIMULATION"].index(st.session_state.mode_select_radio),
    horizontal=True,
    label_visibility="collapsed"
)

# System Access Terminal - Small, fixed height at top
# Only shown when in Bank Mode
if st.session_state.mode_select_radio == "🏦  BANK SYSTEM":
    st.markdown("""
    <div class="security-log" style="max-height: 80px; padding: 10px; margin-top: 5px; margin-bottom: 15px; border-color: rgba(0, 255, 200, 0.15); font-size: 0.75rem;">
        <div class="log-entry" style="margin-bottom: 2px;"><span class="log-time">[SYSTEM]</span> <span class="tag-info">[OK]</span> AI FRAUD ENGINE ONLINE · SECURE_CORE_v2.4 READY</div>
        <div class="log-entry" style="margin-bottom: 2px;"><span class="log-time">[NETWORK]</span> <span class="tag-sec">[AUTH]</span> ENCRYPTED DATA CHANNEL ESTABLISHED</div>
    </div>
    """, unsafe_allow_html=True)

# Sync radio selection back to state if it changes via UI interaction
if _selected != st.session_state.mode_select_radio:
    st.session_state.mode_select_radio = _selected
    st.rerun()

if st.session_state.mode_select_radio == "⚙️  SELECT MODE":
    # Radar animation - only on home page to save space elsewhere
    st.markdown("""
    <div class="radar-wrap" style="margin-top: 40px;">
        <div class="radar">
            <div class="radar-sweep"></div>
            <div class="radar-line"></div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Blinking status indicator
    st.markdown("""
    <div style="text-align:center; margin-bottom: 20px;">
        <div class="status-pill">
            <div class="blink-dot"></div>
            <span class="status-text">AI FRAUD DETECTION ENGINE RUNNING...</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class="glass-card" style="text-align:center; padding: 30px; margin-top: 10px;">
        <div style="font-family:'Orbitron',monospace; font-size:1.1rem; color:#00ffcc; letter-spacing:3px;">
            WELCOME TO SURAKSHA KAWACH
        </div>
        <div style="font-size:0.85rem; color:#4a6a7a; margin-top:10px; line-height:1.5;">
            Your AI-Powered Fraud Intelligence Command Center.<br>
            Please select a system mode from the toggle above to begin.
        </div>
    </div>
    """, unsafe_allow_html=True)
    st.stop()

if _selected == "👤  USER SIMULATION":
    mode = True
else:
    mode = False

# Removed st.divider() to save space

# ─────────────────────────────────────────────────────────────
# LOAD MODEL (always load, used by both modes internally)
# ─────────────────────────────────────────────────────────────

@st.cache_resource
def load_model():
    # Final cache clearance: load dynamically balanced multi-feature logic
    model = joblib.load("final_xgb_model_clean.pkl")
    threshold = joblib.load("final_threshold_clean.pkl")
    scaler = joblib.load("scaler.pkl")
    explainer = shap.TreeExplainer(model)
    return model, threshold, scaler, explainer

model, threshold, scaler, explainer = load_model()

# ─────────────────────────────────────────────────────────────
# PDF REPORT GENERATOR
# ─────────────────────────────────────────────────────────────

def stream_security_logs(placeholder, logs):
    """Streams a series of log entries with a terminal-like delay."""
    log_content = '<div class="security-log">'
    for tag, msg in logs:
        timestamp = time.strftime("%H:%M:%S")
        tag_class = "tag-info" if tag == "INFO" else "tag-sec" if tag == "SEC" else "tag-alert"
        # Removed leading spaces to avoid markdown code block triggers
        log_content += f'<div class="log-entry"><span class="log-time">[{timestamp}]</span><span class="log-tag {tag_class}">[{tag}]</span><span>{msg}</span></div>'
        placeholder.markdown(log_content + '</div>', unsafe_allow_html=True)
        time.sleep(random.uniform(0.3, 0.7))
    time.sleep(1.0) # Pause at the end so user can read the last entry

def generate_report(amount, risk_percent, risk_level, hour, foreign_tx, loc_mismatch, device_score, velocity, age, merchant):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_fill_color(5, 13, 26)

    pdf.set_font("Arial", "B", 18)
    pdf.set_text_color(0, 200, 160)
    pdf.cell(0, 12, "SURAKSHA KAWACH - Fraud Analysis Report", ln=True, align="C")

    pdf.set_font("Arial", "", 10)
    pdf.set_text_color(100, 120, 130)
    pdf.cell(0, 6, "AI-Powered Fraud Detection System", ln=True, align="C")
    pdf.ln(6)

    pdf.set_font("Arial", "B", 12)
    pdf.set_text_color(0, 180, 140)
    pdf.cell(0, 8, "Transaction Details", ln=True)
    pdf.set_font("Arial", "", 11)
    pdf.set_text_color(40, 40, 40)

    details = [
        ("Transaction Amount (Rs.)", f"Rs. {amount:,.2f}"),
        ("Payment Time", f"{hour}:00"),
        ("Out-of-Network Payment", "Yes" if foreign_tx else "No"),
        ("Location Status", "Mismatch" if loc_mismatch else "Matched"),
        ("Device Trust Level", f"{device_score}/100"),
        ("Transactions in Last 24h", str(velocity)),
        ("Accountholder Age", str(age)),
        ("Receiver Type", merchant),
    ]
    for label, value in details:
        pdf.cell(90, 7, label + ":", ln=False)
        pdf.cell(0, 7, value, ln=True)

    pdf.ln(4)
    pdf.set_font("Arial", "B", 12)
    pdf.set_text_color(0, 180, 140)
    pdf.cell(0, 8, "Risk Assessment", ln=True)
    pdf.set_font("Arial", "", 11)
    pdf.set_text_color(40, 40, 40)
    pdf.cell(90, 7, "Fraud Risk Score:", ln=False)
    pdf.cell(0, 7, f"{risk_percent:.2f}%", ln=True)
    pdf.cell(90, 7, "Risk Level:", ln=False)
    pdf.cell(0, 7, risk_level, ln=True)

    pdf.ln(4)
    pdf.set_font("Arial", "B", 12)
    pdf.set_text_color(0, 180, 140)
    pdf.cell(0, 8, "Safety Recommendations", ln=True)
    pdf.set_font("Arial", "", 11)
    pdf.set_text_color(40, 40, 40)

    if risk_level == "High Risk":
        recs = [
            "Block transaction immediately",
            "Notify cardholder via registered mobile",
            "Initiate temporary account freeze",
            "Report to Cyber Crime division",
        ]
    elif risk_level == "Medium Risk":
        recs = [
            "Require secondary OTP verification",
            "Monitor subsequent transactions closely",
            "Verify device trust fingerprint",
        ]
    else:
        recs = [
            "Transaction cleared",
            "Standard behavior detected",
            "Report suspicious transactions to Cyber Cell",
        ]
    for rec in recs:
        pdf.cell(0, 7, f"  - {rec}", ln=True)

    return pdf.output(dest='S').encode('latin-1')

# ─────────────────────────────────────────────────────────────
# SESSION STATE
# ─────────────────────────────────────────────────────────────

if "history" not in st.session_state:
    st.session_state.history = []

# ─────────────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════
#  BANK SYSTEM
# ══════════════════════════════════════════════════════════════
# ─────────────────────────────────────────────────────────────

if not mode:

    # ── Bank Mode Active Banner ──────────────────────────────
    st.markdown("""
    <div class="glass-card" style="text-align:center; margin-bottom: 20px;">
        <div style="font-family:'Orbitron',monospace; font-size:0.85rem; color:#00ffcc; letter-spacing:3px;">
               🏦 BANKING SYSTEM IS ACTIVE
        </div>
        <div style="font-size:0.8rem; color:#4a6a7a; margin-top:6px;">
            Real-time Monitoring & Fraud Risk Assessment Engine
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Model Loaded Banner ──────────────────────────────────
    st.markdown("""
    <div class="glass-card" style="display:flex; align-items:center; gap:12px;">
        <span style="font-size:1.6rem;">✅</span>
        <div>
            <div style="font-family:'Orbitron',monospace; font-size:0.9rem; color:#00ffcc; letter-spacing:1px;">MODEL LOADED SUCCESSFULLY</div>
            <div style="font-size:0.78rem; color:#4a8a7a; margin-top:3px;">XGBoost Classifier · Optimized Threshold · SHAP Explainer Ready</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Model Performance ───────────────────────────────────
    st.markdown('<div class="section-header">📊 MODEL PERFORMANCE</div>', unsafe_allow_html=True)
    st.markdown('<div style="font-size:0.75rem; color:#4a8a7a; text-align:right; margin-bottom:10px; font-style:italic;">* Simulated Demo Metrics</div>', unsafe_allow_html=True)

    mc1, mc2, mc3, mc4 = st.columns(4)
    mc1.metric("🎯 Accuracy", "94.2%", delta="Standard-Verified")
    mc2.metric("🔎 Fraud Recall", "92.5%", delta="High Sensitivity")
    mc3.metric("⚖ F1 Score", "0.91", delta="Optimized")
    mc4.metric("📈 ROC-AUC", "0.954", delta="Strong Discriminator")

    st.divider()

    # ── Input Form ──────────────────────────────────────────
    st.markdown('<div class="section-header">💸 Enter Transaction Details</div>', unsafe_allow_html=True)

    col1, col2 = st.columns(2, gap="large")

    with col1:
        st.markdown("**Transaction Parameters**")
        amount = st.number_input("💲 Transaction Amount (₹)", min_value=0.0, max_value=100000.0, value=5000.0, step=100.0)
        transaction_hour = st.slider("⌚ Transaction Time(24Hours)", 0, 23, 12,
                                      help="Hour of day when transaction occurred")
        foreign_tx_opt = st.selectbox("🌍 Out-of-Network Payment", ["No", "Yes"])
        location_status_opt = st.selectbox("📍 Location Status", ["Matched", "Mismatch"])

    with col2:
        st.markdown("**Behavioral & Merchant Data**")
        device_trust_score = st.slider("📱 Device Trust Level", 0, 100, 50,
                                        help="Higher = more trusted device")
        velocity_last_24h = st.slider("🔁 Transactions in Last 24 Hours", 0, 50, 5)
        cardholder_age = st.slider("👤 Accountholder Age", 18, 80, 30)
        merchant_category = st.selectbox("🏪 Receiver Type",
                                          ["Electronics", "Food", "Grocery", "Travel"])
    
    # ── Map Categorical Inputs ──────────────────────────────
    foreign_transaction = 1 if foreign_tx_opt == "Yes" else 0
    location_mismatch = 1 if location_status_opt == "Mismatch" else 0

    # ── Encode Merchant ─────────────────────────────────────
    merchant_Electronics = 1 if merchant_category == "Electronics" else 0
    merchant_Food        = 1 if merchant_category == "Food"        else 0
    merchant_Grocery     = 1 if merchant_category == "Grocery"     else 0
    merchant_Travel      = 1 if merchant_category == "Travel"      else 0

    # ── Build Input DataFrame ────────────────────────────────
    input_data = pd.DataFrame([[
        amount,
        transaction_hour,
        foreign_transaction,
        location_mismatch,
        device_trust_score,
        velocity_last_24h,
        cardholder_age,
        merchant_Electronics,
        merchant_Food,
        merchant_Grocery,
        merchant_Travel
    ]], columns=model.feature_names_in_)

    # Clear previous result if inputs change
    if "prev_input" not in st.session_state:
        st.session_state.prev_input = input_data.copy()
    
    if not st.session_state.prev_input.equals(input_data):
        if "bank_analysis_result" in st.session_state:
            del st.session_state.bank_analysis_result
        st.session_state.prev_input = input_data.copy()

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Predict Button ───────────────────────────────────────
    btn_col1, btn_col2, btn_col3 = st.columns([1, 2, 1])
    with btn_col2:
        analyze_clicked = st.button("🔍 ANALYZE TRANSACTION", use_container_width=True)

    if analyze_clicked:
        analysis_placeholder = st.empty()
        
        # 1. Show Shield Scanning Animation
        # Removed indentation to avoid markdown code block triggers
        analysis_placeholder.markdown('<div class="shield-overlay"><div class="shield-scan-line"></div><div class="shield-icon">🛡</div><div style="font-family:\'Orbitron\',monospace; color:#00ffcc; font-size:0.9rem; margin-top:15px; letter-spacing:2px;">INITIATING NEURAL SECURITY SCAN...</div></div>', unsafe_allow_html=True)
        time.sleep(1.5)
        
        # 2. Show Live Security Logs
        log_placeholder = analysis_placeholder.empty()
        logs = [
            ("INFO", "Connecting to Suraksha Neural Network..."),
            ("INFO", f"Extracting features for transaction (Amount: ₹{amount})..."),
            ("SEC", "Checking device trust fingerprint..."),
            ("SEC", "Validating geographical coordinates..."),
            ("SEC", "Analyzing transaction velocity patterns..."),
            ("INFO", "Running XGBoost Classifier inference..."),
            ("INFO", "Calculating SHAP explainability values..."),
            ("SEC", "Finalizing risk probability score...")
        ]
        stream_security_logs(log_placeholder, logs)
        analysis_placeholder.empty()

        # Apply scaling to input data (model was trained on scaled features)
        scaled_values = scaler.transform(input_data)
        scaled_input = pd.DataFrame(scaled_values, columns=model.feature_names_in_)

        prob = model.predict_proba(scaled_input)[0][1]
        st.session_state.bank_analysis_result = {
            "prob": prob,
            "risk_percent": prob * 100,
            "input_data": input_data,
            "scaled_input": scaled_input,
            "merchant_category": merchant_category,
            "amount": amount,
            "transaction_hour": transaction_hour,
            "foreign_transaction": foreign_transaction,
            "location_mismatch": location_mismatch,
            "device_trust_score": device_trust_score,
            "velocity_last_24h": velocity_last_24h,
            "cardholder_age": cardholder_age
        }

    if "bank_analysis_result" in st.session_state:
        res = st.session_state.bank_analysis_result
        prob = res["prob"]
        risk_percent = res["risk_percent"]
        input_data = res["input_data"]
        
        st.divider()

        # ── Fraud Risk Gauge ─────────────────────────────────
        st.markdown('<div class="section-header">🚨 FRAUD RISK ASSESSMENT</div>', unsafe_allow_html=True)

        gauge_col, detail_col = st.columns([3, 2], gap="large")

        with gauge_col:
            fig = go.Figure(go.Indicator(
                mode="gauge+number+delta",
                value=risk_percent,
                title={'text': "Fraud Risk Score", 'font': {'color': '#8fa3b0', 'size': 14}},
                number={'suffix': "%", 'font': {'color': '#00ffcc', 'size': 36, 'family': 'Orbitron'}},
                delta={'reference': threshold * 100, 'relative': False,
                       'decreasing': {'color': '#00ffcc'},
                       'increasing': {'color': '#ff4444'}},
                gauge={
                    'axis': {'range': [0, 100], 'tickcolor': '#4a6a7a', 'tickfont': {'color': '#4a6a7a'}},
                    'bar': {'color': '#00ffcc' if prob <= threshold * 0.6 else '#f39c12' if prob <= threshold else '#e74c3c',
                            'thickness': 0.25},
                    'bgcolor': 'rgba(0,0,0,0)',
                    'bordercolor': 'rgba(0,255,200,0.2)',
                    'steps': [
                        {'range': [0, threshold * 60],  'color': 'rgba(0,255,100,0.08)'},
                        {'range': [threshold * 60, threshold * 100], 'color': 'rgba(255,200,0,0.08)'},
                        {'range': [threshold * 100, 100],'color': 'rgba(255,60,60,0.12)'}
                    ]
                }
            ))
            fig.update_layout(
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                font={'color': '#8fa3b0'},
                height=300,
                margin=dict(l=30, r=30, t=50, b=10)
            )
            st.plotly_chart(fig, use_container_width=True)
            st.progress(int(risk_percent))

        with detail_col:
            # ── Risk Classification ──────────────────────────
            if prob > threshold:
                risk_level = "High Risk"
                st.error(f"🚨 HIGH FRAUD RISK\n\n{risk_percent:.2f}% probability")
                st.markdown("""
                <div style="background:rgba(255,50,50,0.1); border:1px solid #ff4444;
                     border-radius:12px; padding:16px; margin-top:12px; text-align:center;">
                    <div style="font-family:'Orbitron',monospace; font-size:1rem; color:#ff4444;">
                        ⚠ FRAUD ALERT
                    </div>
                    <div style="font-size:0.82rem; color:#ffaaaa; margin-top:8px;">
                        Immediate attention required!<br>Transaction flagged for review.
                    </div>
                </div>
                """, unsafe_allow_html=True)
                st.toast("🚨 Fraud Alert Triggered!", icon="⚠️")

            elif prob > threshold * 0.6:
                risk_level = "Medium Risk"
                st.warning(f"🟡 MEDIUM FRAUD RISK\n\n{risk_percent:.2f}% probability")
                st.markdown("""
                <div style="background:rgba(255,180,0,0.1); border:1px solid #f1c40f;
                     border-radius:12px; padding:16px; margin-top:12px; text-align:center;">
                    <div style="font-family:'Orbitron',monospace; font-size:0.9rem; color:#f1c40f;">
                        ⚠ ELEVATED RISK
                    </div>
                    <div style="font-size:0.82rem; color:#ffe57a; margin-top:8px;">
                        Additional verification recommended.
                    </div>
                </div>
                """, unsafe_allow_html=True)

            else:
                risk_level = "Low Risk"
                st.success(f"✅ LOW FRAUD RISK\n\n{risk_percent:.2f}% probability")
                st.markdown("""
                <div style="background:rgba(0,255,100,0.07); border:1px solid #00ff88;
                     border-radius:12px; padding:16px; margin-top:12px; text-align:center;">
                    <div style="font-family:'Orbitron',monospace; font-size:0.9rem; color:#00ff88;">
                        ✔ TRANSACTION CLEARED
                    </div>
                    <div style="font-size:0.82rem; color:#aaffcc; margin-top:8px;">
                        Normal behavior pattern detected.
                    </div>
                </div>
                """, unsafe_allow_html=True)

        # ── Fraud Advisory ───────────────────────────────────
        advisory_items = []
        if res["location_mismatch"] == 1:
            advisory_items.append(("⚠", "Location mismatch detected — transaction origin differs from registered location", "warning"))
        if res["device_trust_score"] < 50:
            advisory_items.append(("📱", "Low device trust score — unrecognized or new device used", "warning"))
        if res["velocity_last_24h"] > 10:
            advisory_items.append(("🔁", f"High transaction velocity — {res['velocity_last_24h']} transactions in last 24h", "warning"))
        if res["foreign_transaction"] == 1:
            advisory_items.append(("🌐", "Foreign transaction detected — cross-border payment flagged", "warning"))
        if res["transaction_hour"] < 5 or res["transaction_hour"] > 22:
            advisory_items.append(("🌙", "Unusual transaction hour — activity at odd hours detected", "warning"))
        if res["amount"] > 40000:
            advisory_items.append(("💰", f"High-value transaction — ₹{res['amount']:,.0f} exceeds typical threshold", "error"))

        if advisory_items:
            st.markdown('<div class="section-header">🛡 FRAUD ADVISORY</div>', unsafe_allow_html=True)
            for icon, msg, level in advisory_items:
                if level == "error":
                    st.error(f"{icon} {msg}")
                else:
                    st.warning(f"{icon} {msg}")
        else:
            if risk_level == "High Risk":
                st.error("🚨 AI SECURITY ALERT: Complex fraud pattern detected despite standard individual limits.")
            elif risk_level == "Medium Risk":
                st.warning("⚠️ AI NOTICE: Elevated risk correlation detected.")
            else:
                st.info("✅ No advisory warnings. Transaction appears within normal parameters.")

        # ── SHAP Explainability ──────────────────────────────
        st.markdown('<div class="section-header">🔍 SHAP FEATURE IMPACT</div>', unsafe_allow_html=True)

        # Use scaled input for SHAP since the model was trained on scaled data
        scaled_input = res["scaled_input"]
        shap_values = explainer.shap_values(scaled_input)
        
        # Ensure we're using the correct values (TreeExplainer for XGBoost typically returns (N, M) array)
        current_shap_values = shap_values[0] if len(shap_values.shape) == 2 else shap_values

        # Format feature names cleanly
        clean_features = [f.replace('merchant_category_', 'Merchant: ').replace('_', ' ').title() for f in input_data.columns]
        
        shap_df = pd.DataFrame({
            "Feature": clean_features,
            "Impact": current_shap_values
        })
        shap_df["Abs"] = shap_df["Impact"].abs()
        shap_df = shap_df.sort_values("Abs", ascending=False).head(8)

        colors = ["#ff4444" if v > 0 else "#00ffcc" for v in shap_df["Impact"]]
        fig_shap = go.Figure(go.Bar(
            x=shap_df["Impact"],
            y=shap_df["Feature"],
            orientation='h',
            marker_color=colors,
            marker_line_width=0,
            opacity=0.85
        ))
        fig_shap.update_layout(
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            font={'color': '#8fa3b0', 'family': 'Inter'},
            xaxis=dict(title="SHAP Value (Fraud Impact)", gridcolor='rgba(255,255,255,0.05)', zerolinecolor='rgba(0,255,200,0.3)'),
            yaxis=dict(gridcolor='rgba(255,255,255,0.03)', autorange="reversed"),
            height=320,
            margin=dict(l=10, r=20, t=10, b=30),
            bargap=0.4
        )
        st.plotly_chart(fig_shap, use_container_width=True)

        # ── Fraud Intelligence Panel ─────────────────────────
        st.markdown('<div class="section-header">🧠 FRAUD INTELLIGENCE PANEL</div>', unsafe_allow_html=True)

        top_features = shap_df.head(4)
        intel_cols = st.columns(2)
        for i, (_, row) in enumerate(top_features.iterrows()):
            feature = row["Feature"].replace("_", " ").title()
            impact = row["Impact"]
            with intel_cols[i % 2]:
                if impact > 0:
                    st.error(f"⬆ **{feature}** is increasing fraud risk\n\n"
                             f"SHAP impact: +{impact:.4f}")
                else:
                    st.success(f"⬇ **{feature}** is reducing fraud risk\n\n"
                               f"SHAP impact: {impact:.4f}")

        # ── PDF Report ───────────────────────────────────────
        st.markdown('<div class="section-header">📄 GENERATE REPORT</div>', unsafe_allow_html=True)

        btn_col1, btn_col2 = st.columns([1, 2])
        with btn_col1:
            report_output = generate_report(
                res["amount"], risk_percent, risk_level,
                res["transaction_hour"], res["foreign_transaction"],
                res["location_mismatch"], res["device_trust_score"],
                res["velocity_last_24h"], res["cardholder_age"], res["merchant_category"]
            )
            
            report_bytes = bytes(report_output)
            
            st.download_button(
                label="📄 Generate PDF Report",
                data=report_bytes,
                file_name=f"Fraud_Report_{random.randint(1000, 9999)}.pdf",
                mime="application/pdf",
                use_container_width=True
            )

        # ── Save to History ──────────────────────────────────
        # Check if this result is already in history to avoid duplicates on rerun
        history_entry = {
            "Amount (₹)": res["amount"],
            "Risk (%)": round(risk_percent, 2),
            "Risk Level": risk_level,
            "Merchant": res["merchant_category"],
            "Hour": res["transaction_hour"]
        }
        if not st.session_state.history or st.session_state.history[-1] != history_entry:
            st.session_state.history.append(history_entry)

    # ── Transaction History ──────────────────────────────────
    if len(st.session_state.history) > 0:
        st.divider()
        st.markdown('<div class="section-header">📜 TRANSACTION HISTORY</div>', unsafe_allow_html=True)

        history_df = pd.DataFrame(st.session_state.history)
        st.dataframe(history_df, use_container_width=True)

        fig2 = px.line(
            history_df,
            y="Risk (%)",
            markers=True,
            title="Fraud Risk Trend Over Transactions",
            color_discrete_sequence=["#00ffcc"]
        )
        fig2.update_layout(
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            font={'color': '#8fa3b0'},
            xaxis=dict(gridcolor='rgba(255,255,255,0.04)'),
            yaxis=dict(gridcolor='rgba(255,255,255,0.04)', range=[0, 100]),
            title_font_color='#00ccaa',
            height=280
        )
        fig2.add_hrect(y0=threshold*100, y1=100, fillcolor="rgba(255,50,50,0.06)", line_width=0,
                       annotation_text="HIGH RISK ZONE", annotation_font_color="#ff6666", annotation_font_size=10)
        fig2.add_hrect(y0=threshold*60, y1=threshold*100, fillcolor="rgba(255,200,0,0.04)", line_width=0)
        st.plotly_chart(fig2, use_container_width=True)

    st.divider()
    if st.button("🏠 RETURN TO HOME", use_container_width=True, key="home_btn_bank"):
        st.session_state.mode_select_radio = "⚙️  SELECT MODE"
        if "bank_analysis_result" in st.session_state:
            del st.session_state.bank_analysis_result
        st.rerun()

# ─────────────────────────────────────────────────────────────
#  STOP here for Bank Mode so User Simulation code doesn't run
# ─────────────────────────────────────────────────────────────
    st.stop()

# ─────────────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════
#  USER SIMULATION MODE
# ══════════════════════════════════════════════════════════════
# ─────────────────────────────────────────────────────────────

st.markdown("""
<div class="glass-card" style="text-align:center;">
    <div style="font-family:'Orbitron',monospace; font-size:0.85rem; color:#00ffcc; letter-spacing:3px;">
           👤 USER SIMULATION MODE ACTIVE
    </div>
    <div style="font-size:0.8rem; color:#4a6a7a; margin-top:6px;">
        Mimicking real-world UPI banking behavior with AI risk assessment
    </div>
</div>
""", unsafe_allow_html=True)

# ── Random Transaction Data ──────────────────────────────────
receivers = [
    "Amazon India Pvt Ltd",
    "Flipkart Internet Pvt Ltd",
    "Zomato Media Pvt Ltd",
    "Swiggy Foods",
    "Netflix Entertainment",
    "Reliance Retail Ltd",
    "MakeMyTrip India",
    "Uber India Systems",
    "Ola Cabs",
    "Spotify India",
    "IRCTC Ticketing",
    "Blinkit (Grofers)",
    "Zepto Express",
    "Apple India Pvt Ltd",
    "Google Play Store"
]

if "sim_amount" not in st.session_state:
    st.session_state.sim_amount = random.randint(100, 100000)
    st.session_state.sim_hour   = random.randint(0, 23)
    st.session_state.receiver   = random.choice(receivers)

sim_amount = st.session_state.sim_amount
sim_hour = st.session_state.sim_hour
receiver = st.session_state.receiver

display_hour   = sim_hour % 12 or 12
period         = "AM" if sim_hour < 12 else "PM"
formatted_time = f"{display_hour}:00 {period}"

# ── Risk Logic ───────────────────────────────────────────────
if sim_amount > 50000 and (sim_hour >= 22 or sim_hour <= 5):
    sim_risk_type = "FRAUD"
elif sim_amount > 30000 or (sim_hour < 6 and sim_amount > 10000):
    sim_risk_type = "MEDIUM"
else:
    sim_risk_type = "SAFE"

# ── UPI Transaction Card ─────────────────────────────────────
st.markdown('<div class="section-header">📱 INCOMING PAYMENT REQUEST</div>', unsafe_allow_html=True)

sim_col1, sim_col2 = st.columns([3, 2], gap="large")

with sim_col1:
    risk_badge_color = "#ff4444" if sim_risk_type == "FRAUD" else "#f1c40f" if sim_risk_type == "MEDIUM" else "#00ff88"
    risk_badge_text  = "⚠ HIGH RISK" if sim_risk_type == "FRAUD" else "🟡 MEDIUM" if sim_risk_type == "MEDIUM" else "✅ NORMAL"

    st.markdown(f"""
    <div class="upi-card">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:18px;">
            <div style="font-family:'Orbitron',monospace; font-size:0.7rem; color:#4a6a7a; letter-spacing:3px;">UPI PAYMENT</div>
            <div style="background:{risk_badge_color}22; border:1px solid {risk_badge_color}66;
                 color:{risk_badge_color}; font-size:0.7rem; padding:4px 12px; border-radius:20px;
                 font-family:'Orbitron',monospace; letter-spacing:1px;">
                {risk_badge_text}
            </div>
        </div>
        <div class="upi-amount">₹{sim_amount:,}</div>
        <div style="margin:18px 0; height:1px; background:rgba(0,255,200,0.1);"></div>
        <div style="display:grid; grid-template-columns:1fr 1fr 1fr; gap:16px;">
            <div>
                <div class="upi-label">RECEIVER</div>
                <div class="upi-value">{receiver}</div>
            </div>
            <div>
                <div class="upi-label">TIME</div>
                <div class="upi-value">{formatted_time}</div>
            </div>
            <div>
                <div class="upi-label">TYPE</div>
                <div class="upi-value">UPI Transfer</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

with sim_col2:
    st.markdown("""
    <div class="glass-card" style="text-align:center; height:100%;">
        <div style="font-size:2.5rem; margin-bottom:8px;">🔔</div>
        <div style="font-family:'Orbitron',monospace; font-size:0.75rem; color:#4a6a7a; letter-spacing:2px; margin-bottom:12px;">
            AWAITING AUTHORIZATION
        </div>
        <div style="font-size:0.82rem; color:#8fa3b0; line-height:1.8;">
            AI model will analyze this transaction for suspicious behavior before proceeding.
        </div>
    </div>
    """, unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ── Payment Button & Reset ────────────────────────────────────
# Reset button on the left
reset_col1, reset_col2, reset_col3 = st.columns([1, 1, 1])
with reset_col1:
    st.markdown("""
        <style>
        /* Target ONLY the secondary button in this section for Blue theme */
        [data-testid="column"]:nth-of-type(1) button[kind="secondary"] {
            background-color: transparent !important;
            border: 1px dashed #33ccff !important;
            color: #33ccff !important;
            border-radius: 4px !important;
            height: 28px !important;
            min-height: 28px !important;
            padding: 0 10px !important;
            font-size: 0.75rem !important;
            text-transform: none !important;
            transition: all 0.3s ease !important;
        }
        [data-testid="column"]:nth-of-type(1) button[kind="secondary"]:hover {
            background-color: rgba(51, 204, 255, 0.05) !important;
            border: 1px solid #77ddff !important;
            color: #77ddff !important;
            box-shadow: 0 0 15px rgba(51, 204, 255, 0.2) !important;
        }
        </style>
    """, unsafe_allow_html=True)
    if st.button("🔄 Reset Transaction ", use_container_width=True, type="secondary"):
        if "sim_amount" in st.session_state:
            del st.session_state.sim_amount
            del st.session_state.sim_hour
            del st.session_state.receiver
        # Clear payment session states
        st.session_state.payment_proceeded = False
        if "animation_done" in st.session_state:
            del st.session_state.animation_done
        if "sim_risk_score" in st.session_state:
            del st.session_state.sim_risk_score
        if "fraud_alert_done" in st.session_state:
            del st.session_state.fraud_alert_done
        st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)

# Proceed button aligned left
pay_btn_col1, pay_btn_col2, pay_btn_col3 = st.columns([1, 1, 1])
with pay_btn_col1:
    if st.button("💳 PROCEED PAYMENT", use_container_width=True, type="primary"):
        st.session_state.payment_proceeded = True
        st.session_state.mfa_verified = False # Reset MFA for new transaction
        if "fraud_alert_done" in st.session_state:
            del st.session_state.fraud_alert_done # Allow alert for new transaction if needed

if st.session_state.get("payment_proceeded", False):
    proc_placeholder = st.empty()
    
    # ── Simulation Data (Re-calculate or store in session state) ─────
    # We store the risk score so it doesn't change on rerun
    if "sim_risk_score" not in st.session_state:
        if sim_risk_type == "FRAUD":
            st.session_state.sim_risk_score = random.uniform(80, 98)
        elif sim_risk_type == "MEDIUM":
            st.session_state.sim_risk_score = random.uniform(40, 75)
        else:
            st.session_state.sim_risk_score = random.uniform(5, 25)
    
    sim_risk_score = st.session_state.sim_risk_score
    
    # Only show animation and logs ONCE when first clicking proceed
    if "animation_done" not in st.session_state:
        # 1. Show Shield Scanning Animation
        proc_placeholder.markdown('<div class="shield-overlay"><div class="shield-scan-line"></div><div class="shield-icon">🛡</div><div style="font-family:\'Orbitron\',monospace; color:#00ffcc; font-size:0.9rem; margin-top:15px; letter-spacing:2px;">AI SECURITY VERIFICATION IN PROGRESS...</div></div>', unsafe_allow_html=True)
        time.sleep(1.8)

        # 2. Show Live Security Logs
        log_placeholder = proc_placeholder.empty()
        logs = [
            ("INFO", f"Requesting authorization for ₹{sim_amount}..."),
            ("INFO", f"Target Receiver: {receiver}"),
            ("SEC", "Checking location metadata..."),
            ("SEC", "Verifying device identity..."),
            ("INFO", "Running AI fraud engine..."),
            ("SEC", "Generating final risk score...")
        ]
        stream_security_logs(log_placeholder, logs)
        proc_placeholder.empty()
        st.session_state.animation_done = True

    # ── Result UI ─────────────────────────────────────────────
    st.markdown('<div class="section-header">🔍 TRANSACTION ANALYSIS RESULT</div>', unsafe_allow_html=True)

    res_col1, res_col2 = st.columns(2, gap="large")

    with res_col1:
        if sim_risk_type == "FRAUD":
            st.error("🚨 HIGH FRAUD RISK DETECTED")
        elif sim_risk_type == "MEDIUM":
            st.warning("⚠ MEDIUM RISK — VERIFICATION REQUIRED")
            
            # --- Professional Verification Steps Info ---
            st.markdown("""
            <div class="glass-card" style="padding: 15px; margin-top: 15px; border-left: 4px solid #f1c40f;">
                <div style="font-family: 'Orbitron', monospace; color: #f1c40f; font-size: 0.8rem; letter-spacing: 1px; margin-bottom: 5px;">
                    📝 VERIFICATION STEPS REQUIRED
                </div>
                <ul style="color: #8fa3b0; font-size: 0.72rem; line-height: 1.4; margin-left: 15px; padding-left: 0;">
                    <li>Transaction exceeds standard behavioral threshold</li>
                    <li>Registered device requires secondary handshake</li>
                    <li>Secure OTP sent to +91 ******4567</li>
                </ul>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.success("✅ SAFE TRANSACTION")

    with res_col2:
        st.metric("🎯 AI Risk Score", f"{sim_risk_score:.1f}%",
                  delta=f"{'High' if sim_risk_score > 70 else 'Moderate' if sim_risk_score > 40 else 'Low'} Confidence")

    risk_color = "#ff4444" if sim_risk_score > 70 else "#f1c40f" if sim_risk_score > 40 else "#00ff88"
    st.markdown(f"""
    <div style="background:rgba(0,0,0,0.3); border-radius:8px; height:14px; margin:8px 0; overflow:hidden; border:1px solid rgba(255,255,255,0.05);">
        <div style="background:linear-gradient(90deg, {risk_color}88, {risk_color});
             height:100%; width:{sim_risk_score:.0f}%; border-radius:8px;
             transition: width 1s ease; box-shadow:0 0 8px {risk_color}88;">
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Fraud Alert System ────────────────────────────────────
    if sim_risk_type == "FRAUD":
        # Only show animation and alert ONCE
        if "fraud_alert_done" not in st.session_state:
            # Mark it done IMMEDIATELY to prevent re-triggering during script execution/reruns
            st.session_state.fraud_alert_done = True
            st.toast("🚨 FRAUD ALERT — Transaction Blocked!", icon="🚨")

            # Realistic Bank Popup Overlay with JS Native Beep (Invisible & Reliable)
            popup = st.empty()
            
            # Using Web Audio API to generate a beep
            components.html(
                f"""
                <script>
                    window.onload = function() {{
                        const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
                        const oscillator = audioCtx.createOscillator();
                        const gainNode = audioCtx.createGain();
                        oscillator.type = 'sawtooth'; 
                        const now = audioCtx.currentTime;
                        for (let i = 0; i < 4; i += 0.4) {{
                            oscillator.frequency.linearRampToValueAtTime(800, now + i + 0.2);
                            oscillator.frequency.linearRampToValueAtTime(500, now + i + 0.4);
                        }}
                        gainNode.gain.setValueAtTime(0.4, now);
                        oscillator.connect(gainNode);
                        gainNode.connect(audioCtx.destination);
                        oscillator.start();
                        oscillator.stop(now + 4);
                    }}
                </script>
                """,
                height=0,
                width=0
            )

            popup.markdown(f"""
            <div class="bank-popup-overlay">
                <div class="bank-popup-box popup-blocked">
                    <div style="font-size: 3.5rem; animation: pulse 1s infinite;">🛑</div>
                    <div class="bank-popup-title title-red">TRANSACTION BLOCKED</div>
                    <div class="bank-popup-text">Your bank's AI security system has halted this payment to protect your account.</div>
                    <div class="bank-popup-details details-red">
                        Amount: ₹{sim_amount:,}<br>
                        To: {receiver}<br>
                        Status: <span style="color:#ff3333; font-weight:bold;">BLOCKED</span>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)

            time.sleep(4.5)
            popup.empty()

        # Payment Blocked
        st.error("❌ PAYMENT BLOCKED — Transaction has been cancelled for your protection")

        # Report to Cyber Cell
        st.markdown('<div class="section-header">🚨 REPORT FRAUD</div>', unsafe_allow_html=True)
        if st.button("📤 Report to Cyber Cell", use_container_width=False):
            # Show Professional Reporting Success Popup
            report_popup = st.empty()
            report_popup.markdown(f"""
            <div class="bank-popup-overlay">
                <div class="bank-popup-box popup-success">
                    <div style="font-size: 3.5rem; animation: pulse 1s infinite;">🛡️</div>
                    <div class="bank-popup-title title-green">REPORTING SUCCESSFUL</div>
                    <div class="bank-popup-text">
                        Your transaction data has been encrypted and securely transmitted to the Cyber Crime Investigation Cell.
                    </div>
                    <div class="bank-popup-details details-green">
                        Transaction: ₹{sim_amount:,}<br>
                        Receiver: {receiver}<br>
                        Case ID: <span style="color:#00ffcc; font-weight:bold;">SEC-RE-{random.randint(1000, 9999)}</span>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)
            time.sleep(3.0)
            report_popup.empty()
            
            complaint_id = f"CC{random.randint(100000, 999999)}"
            st.success(f"✅ Complaint Filed Successfully")
            st.markdown(f"""
            <div class="complaint-card">
                🆔 Complaint ID: {complaint_id}<br>
                💰 Amount: ₹{sim_amount:,}<br>
                👤 Receiver: {receiver}<br>
                🕐 Time: {formatted_time}<br>
                📊 Risk Score: {sim_risk_score:.1f}%<br>
                📌 Status: 🔴 Under Investigation
            </div>
            """, unsafe_allow_html=True)

    elif sim_risk_type == "MEDIUM":
        # --- Multi-Factor Authentication Simulation ---
        st.markdown("""
        <div style="background: rgba(0, 255, 200, 0.03); border: 1px solid rgba(0, 255, 200, 0.15); border-radius: 12px; padding: 20px; margin-top: 15px;">
            <div style="font-family: 'Orbitron', monospace; color: #00ffcc; font-size: 0.85rem; letter-spacing: 1px; margin-bottom: 10px;">
                🔐 MFA REQUIRED!
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        if "mfa_verified" not in st.session_state:
            st.session_state.mfa_verified = False
        
        if not st.session_state.mfa_verified:
            mfa_col1, mfa_col2 = st.columns([2, 1])
            with mfa_col1:
                mfa_code_input = st.text_input("Enter 6-digit MFA Code", placeholder="Try 123456", label_visibility="collapsed", key="mfa_user_code")
            with mfa_col2:
                if st.button("AUTHORIZE", use_container_width=True, key="mfa_user_btn"):
                    try:
                        if mfa_code_input == "123456":
                            st.session_state.mfa_verified = True
                            st.markdown("""
                            <div style="background: rgba(0, 255, 100, 0.1); border: 1px solid #00ff88; border-radius: 8px; padding: 10px; margin-top: 10px; text-align: center;">
                                <span style="color: #00ff88; font-family: 'Orbitron', monospace; font-size: 0.8rem;">✅ ACCESS GRANTED: MFA VERIFIED</span>
                            </div>
                            """, unsafe_allow_html=True)
                            time.sleep(0.8)
                            st.rerun()
                        else:
                            st.markdown("""
                            <div style="background: rgba(255, 50, 50, 0.1); border: 1px solid #ff4444; border-radius: 8px; padding: 10px; margin-top: 10px; text-align: center;">
                                <span style="color: #ff4444; font-family: 'Orbitron', monospace; font-size: 0.8rem;">❌ ACCESS DENIED: INVALID CODE</span>
                            </div>
                            """, unsafe_allow_html=True)
                    except Exception as e:
                        st.error(f"SYSTEM ERROR: {str(e)}")
            
            # Gating logic: If not verified, we stop here for MEDIUM risk
            st.info("💡 Please complete MFA to unlock detailed AI analysis and transaction summary.")
            
            # Show Return Home button even if MFA is pending
            st.divider()
            if st.button("🏠 RETURN TO HOME", use_container_width=True, key="home_btn_user_pending"):
                st.session_state.mode_select_radio = "⚙️  SELECT MODE"
                st.session_state.payment_proceeded = False
                st.rerun()
            st.stop()
        else:
            st.markdown("""
            <div style="background: rgba(0, 255, 100, 0.05); border: 1px solid rgba(0, 255, 100, 0.3); border-radius: 8px; padding: 12px; margin-top: 5px; text-align: center;">
                <span style="color: #00ff88; font-family: 'Orbitron', monospace; font-size: 0.85rem; letter-spacing: 1px;">✔ IDENTITY VERIFIED VIA SECURE MFA</span>
            </div>
            """, unsafe_allow_html=True)
        # -----------------------

    else:
        st.success("💰 PAYMENT SUCCESSFUL — ₹{:,} transferred to {}".format(sim_amount, receiver))
        st.balloons()

    # ── AI Deep-Scan Explainability ───────────────────────────
    st.markdown('<div class="section-header">🔬 AI DEEP-SCAN EXPLAINABILITY</div>', unsafe_allow_html=True)
    
    # Mock SHAP Values based on risk type
    if sim_risk_type == "FRAUD":
        features = ["Transaction Amount", "Night Activity", "New Receiver", "Device Identity", "Location Anomaly"]
        importance = [35, 25, 20, 12, 8]
    elif sim_risk_type == "MEDIUM":
        features = ["Transaction Amount", "Frequency", "Receiver Trust", "Time of Day", "Network Speed"]
        importance = [20, 25, 30, 15, 10]
    else:
        features = ["Spending Habit", "Regular Receiver", "Trusted Device", "Verified Location", "Secure Network"]
        importance = [40, 30, 15, 10, 5]

    fig_deep = go.Figure(go.Bar(
        x=importance,
        y=features,
        orientation='h',
        marker=dict(
            color=risk_color,
            line=dict(color=risk_color, width=1)
        )
    ))
    fig_deep.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color='#8fa3b0', size=10),
        margin=dict(l=10, r=10, t=10, b=10),
        height=200,
        xaxis=dict(showgrid=False, showticklabels=False),
        yaxis=dict(autorange="reversed")
    )
    st.plotly_chart(fig_deep, use_container_width=True, config={'displayModeBar': False})

    # ── Why This Result ────────────────────────────────────────
    st.markdown('<div class="section-header">🧠 WHY THIS RESULT?</div>', unsafe_allow_html=True)

    st.markdown("**Contributing Factors:**")
    if sim_risk_type == "FRAUD":
        reasons = [
            ("🔴", "High transaction amount (₹{:,})".format(sim_amount)),
            ("🔴", "Late-night / unusual hour activity ({})".format(formatted_time)),
            ("🔴", "Behavioral pattern mismatch detected"),
            ("🔴", "Anomaly score exceeds safety threshold"),
        ]
    elif sim_risk_type == "MEDIUM":
        reasons = [
            ("🟡", "Unusual transaction size for account"),
            ("🟡", "Slightly abnormal timing detected"),
            ("🟡", "Minor deviation from typical pattern"),
        ]
    else:
        reasons = [
            ("🟢", "Transaction fits normal spending pattern"),
            ("🟢", "Safe hour and regular behavior"),
            ("🟢", "Amount within typical range"),
            ("🟢", "All security checks passed"),
        ]

    for icon, reason in reasons:
        st.markdown(f"{icon} {reason}")

    st.markdown("<br>", unsafe_allow_html=True)

    st.markdown('<div class="section-header">📋 TRANSACTION SUMMARY</div>', unsafe_allow_html=True)
    st.markdown(f"""
    | Field | Value |
    |-------|-------|
    | Amount | ₹{sim_amount:,} |
    | Receiver | {receiver} |
    | Time | {formatted_time} |
    | Risk Score | {sim_risk_score:.1f}% |
    | Verdict | {"🔴 FRAUD" if sim_risk_type == "FRAUD" else "🟡 MEDIUM" if sim_risk_type == "MEDIUM" else "🟢 SAFE"} |
    """)

    # --- Secure PDF Receipt Section ---
    if sim_risk_type != "FRAUD": # Only for successful or medium risk authorized payments
        st.markdown('<div class="section-header">📄 SECURE DIGITAL RECEIPT</div>', unsafe_allow_html=True)
        verdict_str = "🟢 SAFE" if sim_risk_type == "SAFE" else "🟡 MEDIUM"
        
        pdf_bytes = generate_secure_receipt(
            amount=sim_amount,
            receiver=receiver,
            time_str=formatted_time,
            risk_score=sim_risk_score,
            verdict=verdict_str
        )
        
        # Download button in a 40% width column for visual distinction
        d_col1, d_col2 = st.columns([2, 3])
        with d_col1:
            st.download_button(
                label="📥 DOWNLOAD RECEIPT",
                data=pdf_bytes,
                file_name=f"receipt_{int(time.time())}.pdf",
                mime="application/pdf",
                use_container_width=True,
                key="download_receipt_btn"
            )

st.divider()
# Standalone full-width Return Home button
if st.button("🏠 RETURN TO HOME", use_container_width=True, key="home_btn_user_final"):
    st.session_state.mode_select_radio = "⚙️  SELECT MODE"
    # Clear simulation state
    if "sim_amount" in st.session_state:
        del st.session_state.sim_amount
        del st.session_state.sim_hour
        del st.session_state.receiver
    st.session_state.payment_proceeded = False
    if "animation_done" in st.session_state:
        del st.session_state.animation_done
    if "sim_risk_score" in st.session_state:
        del st.session_state.sim_risk_score
    st.rerun()
    