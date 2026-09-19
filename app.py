import streamlit as st
import requests
import math
import plotly.graph_objects as go
import pydeck as pdk
from geopy.geocoders import Nominatim
from PIL import Image
import cv2
import numpy as np
import pandas as pd
from datetime import datetime
import os
import base64
import time
import uuid
import pvlib

@st.cache_data(ttl=86400)
def load_pvlib_modules():
    try:
        return pvlib.pvsystem.retrieve_sam('CECMod')
    except:
        return None

@st.cache_data(ttl=86400)
def load_pvlib_inverters():
    try:
        return pvlib.pvsystem.retrieve_sam('cecinverter')
    except:
        return None

# --- NEW IMPORT FOR CAD ENGINE ---
try:
    from streamlit_drawable_canvas import st_canvas
except ImportError:
    st.error("⚠️ Please install the CAD engine by running: pip install streamlit-drawable-canvas")
    st.stop()

st.set_page_config(page_title="Daisy Solar Suite", layout="wide", initial_sidebar_state="collapsed")

# ==========================================
# LAYER 1: APP STATE & NAVIGATION
# ==========================================
if 'app_started' not in st.session_state: st.session_state.app_started = False
if 'page' not in st.session_state: st.session_state.page = 'home'
if 'loading_target' not in st.session_state: st.session_state.loading_target = None
if 'theme' not in st.session_state: st.session_state.theme = 'Light' # Default to Elegant Light Theme
if 'lat' not in st.session_state: st.session_state.lat = 26.1800
if 'lon' not in st.session_state: st.session_state.lon = 91.6900
if 'plan_generated' not in st.session_state: st.session_state.plan_generated = False
if 'cad_imported' not in st.session_state: st.session_state.cad_imported = False
if 'cad_json_data' not in st.session_state: st.session_state.cad_json_data = None # Holds the actual drawing data
if 'load_table' not in st.session_state: 
    st.session_state.load_table = pd.DataFrame([
        {"Appliance": "LED Lighting", "Watts": 15, "Qty": 50, "Hours/Day": 12, "Surge": 1.0},
        {"Appliance": "HVAC Unit", "Watts": 2200, "Qty": 2, "Hours/Day": 8, "Surge": 3.0},
        {"Appliance": "Computers/IT", "Watts": 250, "Qty": 5, "Hours/Day": 10, "Surge": 1.0}
    ])

# ==========================================
# LAYER 2: MASTER ENGINEERING DATABASES & FUNCTIONS
# ==========================================
BASIC_PV_MODULES = {"Standard Mono PERC 540W": {"power_w": 540, "voc_v": 49.5, "vmp_v": 41.2, "isc_a": 13.85, "imp_a": 13.11, "length_m": 2.279, "width_m": 1.134, "base_cost_kw": 55000, "weight_kg": 28, "noct": 45, "temp_coeff_pmax": -0.35}, "Utility Bifacial 600W (DCR)": {"power_w": 600, "voc_v": 51.2, "vmp_v": 42.8, "isc_a": 14.65, "imp_a": 14.02, "length_m": 2.411, "width_m": 1.134, "base_cost_kw": 60000, "weight_kg": 32, "noct": 43, "temp_coeff_pmax": -0.34}}
BASIC_INVERTERS = {"String 3kW (Single Phase)": {"max_ac_kw": 3, "min_mppt_v": 90, "max_mppt_v": 500, "max_dc_voltage_v": 550, "max_dc_i": 12.0, "max_batt_v": 60}, "String 5kW (Single Phase)": {"max_ac_kw": 5, "min_mppt_v": 120, "max_mppt_v": 550, "max_dc_voltage_v": 600, "max_dc_i": 15.0, "max_batt_v": 60}, "HV Hybrid 10kW (Three Phase)": {"max_ac_kw": 10, "min_mppt_v": 150, "max_mppt_v": 850, "max_dc_voltage_v": 1000, "max_dc_i": 25.0, "max_batt_v": 500}, "Residential 15kW (Three Phase)": {"max_ac_kw": 15, "min_mppt_v": 150, "max_mppt_v": 850, "max_dc_voltage_v": 1000, "max_dc_i": 30.0, "max_batt_v": 500}, "Commercial 50kW (Three Phase)": {"max_ac_kw": 50, "min_mppt_v": 200, "max_mppt_v": 850, "max_dc_voltage_v": 1000, "max_dc_i": 110.0, "max_batt_v": 500}, "Utility 100kW (High Voltage)": {"max_ac_kw": 100, "min_mppt_v": 500, "max_mppt_v": 1500, "max_dc_voltage_v": 1500, "max_dc_i": 180.0, "max_batt_v": 1500}}

# Dynamic containers for session use
PV_MODULES = {}
INVERTERS = {}
BATTERIES = {"Tubular Lead-Acid (12V, 150Ah)": {"volts": 12, "ah": 150, "dod": 0.70, "cost": 15000}, "Lithium LFP Rack (48V, 100Ah)": {"volts": 48, "ah": 100, "dod": 0.90, "cost": 85000}, "HV Stackable LFP Tower (200V, 50Ah)": {"volts": 200, "ah": 50, "dod": 0.90, "cost": 150000}, "Utility LFP Container (400V, 200Ah)": {"volts": 400, "ah": 200, "dod": 0.95, "cost": 1200000}}

COMPLIANCE_LIMITS = {
    "Assam": {"max_single_phase_kw": 7.0, "max_residential_kw": 25.0},
    "Uttar Pradesh": {"max_single_phase_kw": 5.0, "max_residential_kw": 20.0},
    "Delhi": {"max_single_phase_kw": 10.0, "max_residential_kw": 50.0},
    "Gujarat": {"max_single_phase_kw": 6.0, "max_residential_kw": 30.0},
    "Other": {"max_single_phase_kw": 10.0, "max_residential_kw": 25.0}
}
THERMAL_COLLECTORS = {"FPC (Flat Plate) - 100 LPD": {"capacity_lpd": 100, "length_m": 2.0, "width_m": 1.0, "base_cost": 22000, "max_parallel": 5}, "ETC (Evacuated Tube) - 200 LPD": {"capacity_lpd": 200, "length_m": 2.0, "width_m": 1.5, "base_cost": 32000, "max_parallel": 10}}
HEATER_EFFICIENCY = {"1 Star (Old Element - 75%)": 0.75, "3 Star (Standard - 85%)": 0.85, "5 Star (High Efficiency - 95%)": 0.95}
AWG_RESISTANCE = {"10 AWG (5.26 mm²)": 3.27, "8 AWG (8.36 mm²)": 2.06, "6 AWG (13.3 mm²)": 1.30, "4 AWG (21.2 mm²)": 0.81, "2 AWG (33.6 mm²)": 0.51, "1/0 AWG (53.5 mm²)": 0.32}
SECTOR_DATA = {"House (Residential)": {"category": "Residential", "model": "savings"}, "Farmland (Agriculture)": {"category": "Agricultural", "model": "savings"}, "Hostel (Commercial Residential)": {"category": "Commercial", "model": "savings"}, "Institute (Educational)": {"category": "Institutional", "model": "savings"}, "Mall (Heavy Commercial)": {"category": "Commercial", "model": "savings"}, "Power Generation Plant (Utility/IPP)": {"category": "Utility", "model": "revenue"}}
STATES = ["Assam", "Uttar Pradesh", "Delhi", "Gujarat", "Other"]

def render_img(filename, class_name):
    base_dir = os.path.dirname(os.path.abspath(__file__))
    filepath = os.path.join(base_dir, "manual", filename)
    if not os.path.exists(filepath): filepath = os.path.join("manual", filename)
    if os.path.exists(filepath):
        with open(filepath, "rb") as f: b64 = base64.b64encode(f.read()).decode()
        ext = filename.split('.')[-1].lower()
        if ext == 'jpg': ext = 'jpeg'
        return f'<img src="data:image/{ext};base64,{b64}" class="{class_name}" alt="{filename}">'
    return f'<div class="{class_name}" style="background:rgba(255,255,255,0.1); border: 2px dashed rgba(255,255,255,0.3); display:flex; align-items:center; justify-content:center; height: 300px; border-radius: 24px; color: #64748b;">Missing: {filename}</div>'

@st.cache_data(ttl=86400)
def fetch_nasa_data(lat, lon):
    try:
        url = f"https://power.larc.nasa.gov/api/temporal/climatology/point?parameters=ALLSKY_SFC_SW_DWN,ALLSKY_SFC_SW_DIFF,WS10M&community=RE&longitude={lon}&latitude={lat}&format=JSON"
        resp = requests.get(url, timeout=10).json()
        return resp['properties']['parameter']['ALLSKY_SFC_SW_DWN'], resp['properties']['parameter']['ALLSKY_SFC_SW_DIFF'], resp['properties']['parameter']['WS10M']
    except: return None, None, None

def calc_solar_angles(lat, day_of_year):
    lat_rad = math.radians(lat)
    delta = 23.45 * math.sin(math.radians((360/365) * (284 + day_of_year)))
    delta_rad = math.radians(delta)
    cos_zenith = max(-1.0, min(1.0, math.sin(lat_rad)*math.sin(delta_rad) + math.cos(lat_rad)*math.cos(delta_rad)*1))
    zenith_rad = math.acos(cos_zenith)
    return {"declination": delta, "altitude": math.degrees((math.pi / 2) - zenith_rad), "zenith": math.degrees(zenith_rad)}

def calculate_subsidy(sector_cat, state_name, system_kw, gross_cost, grid_type, sub_mode, man_cen, man_state):
    if sub_mode == "Manual Entry": return man_cen, man_state, ["🛠️ Manual Subsidy Applied."]
    if grid_type == "Off-Grid (Standalone)" or sector_cat != "Residential": return 0, 0, [f"⚠️ {sector_cat} systems primarily use Tax Benefits, not CFA."]
    cen = min(system_kw, 2) * 30000 + max(0, min(system_kw - 2, 1)) * 18000
    state_sub = min(system_kw, 3) * 15000 if state_name == "Assam" else 0
    return cen, state_sub, ["✅ PM Surya Ghar National Portal Policy applied."]

# ==========================================
# LAYER 3: TRUE NATIVE LOADING SCREEN
# ==========================================
if st.session_state.loading_target:
    is_loading_dark = (st.session_state.theme == 'Dark')
    bg_color = "#0b0f19" if is_loading_dark else "#F7F5F0"
    text_color = "#3b82f6" if is_loading_dark else "#1e3a8a"
    loader_id = str(uuid.uuid4().hex)
    
    st.markdown(f"""
    <style>
    .stApp {{ background-color: {bg_color} !important; }}
    header {{ display: none !important; }}
    .true-loader-{loader_id} {{ position: fixed; top: 0; left: 0; width: 100vw; height: 100vh; z-index: 9999999; display: flex; flex-direction: column; justify-content: center; align-items: center; background-color: {bg_color}; animation: fadeOutLoader 0.7s cubic-bezier(0.8, 0, 0.2, 1) forwards; animation-delay: 1.5s; pointer-events: none; }}
    .spinner-premium-{loader_id} {{ width: 70px; height: 70px; border: 4px solid rgba(100, 100, 100, 0.15); border-left-color: {text_color}; border-radius: 50%; animation: spin 0.8s cubic-bezier(0.4, 0, 0.2, 1) infinite; }}
    .loader-text-premium-{loader_id} {{ margin-top: 25px; font-family: 'Plus Jakarta Sans', sans-serif; font-weight: 900; font-size: 1.4rem; color: {text_color}; letter-spacing: 4px; animation: pulse 1.5s infinite; }}
    @keyframes spin {{ 0% {{ transform: rotate(0deg); }} 100% {{ transform: rotate(360deg); }} }}
    @keyframes pulse {{ 0%, 100% {{ opacity: 1; }} 50% {{ opacity: 0.5; }} }}
    @keyframes fadeOutLoader {{ to {{ opacity: 0; visibility: hidden; }} }}
    </style>
    <div class="true-loader-{loader_id}"><div class="spinner-premium-{loader_id}"></div><div class="loader-text-premium-{loader_id}">DAISY ENGINE</div></div>
    """, unsafe_allow_html=True)
    time.sleep(1.5) 
    st.session_state.page = st.session_state.loading_target
    st.session_state.app_started = (st.session_state.page == 'dashboard')
    st.session_state.loading_target = None
    st.rerun()

# ==========================================
# LAYER 4: GLOBAL THEME & CSS ENGINE
# ==========================================
is_dark = (st.session_state.theme == 'Dark')

if is_dark:
    app_bg = "linear-gradient(135deg, #0f172a 0%, #020617 100%)"
    text_col, text_muted = "#f1f2f6", "#94a3b8"
    glass_bg, glass_border = "rgba(15, 23, 42, 0.5)", "rgba(255, 255, 255, 0.1)"
    glass_blur, glass_shadow = "blur(20px)", "0 8px 32px rgba(0, 0, 0, 0.5)"
    input_bg, border_col = "rgba(15, 23, 42, 0.6)", "rgba(255, 255, 255, 0.15)" 
    metric_bg, metric_border = "linear-gradient(145deg, rgba(30, 41, 59, 0.6), rgba(15, 23, 42, 0.8))", "rgba(255, 255, 255, 0.1)"
    metric_val = "linear-gradient(135deg, #74b9ff 0%, #3b82f6 100%)"
    plt_font, plt_grid, plt_card_bg, plt_border = "#fafafa", "rgba(255, 255, 255, 0.05)", "rgba(15, 23, 42, 0.85)", "#636e72"
    cad_bg, cad_lines, sld_neg = "#1e272e", "white", "#cbd5e1"
    matte_black_glass, matte_black_border, table_text = glass_bg, glass_border, text_col
else:
    app_bg = "linear-gradient(135deg, #EAE4D9 0%, #D8CFC0 100%)" 
    text_col, text_muted = "#1e293b", "#475569"
    glass_bg, glass_border = "rgba(255, 255, 255, 0.4)", "rgba(255, 255, 255, 0.8)"
    glass_blur, glass_shadow = "blur(20px)", "0 10px 30px rgba(0, 0, 0, 0.1)"
    input_bg, border_col = "rgba(255, 255, 255, 0.5)", "rgba(255, 255, 255, 0.8)" 
    metric_bg, metric_border = "linear-gradient(145deg, rgba(255, 255, 255, 0.8), rgba(255, 255, 255, 0.4))", "rgba(255, 255, 255, 0.8)"
    metric_val = "linear-gradient(135deg, #d35400 0%, #e67e22 100%)"
    plt_font, plt_grid, plt_card_bg, plt_border = "#1e293b", "rgba(0, 0, 0, 0.05)", "rgba(255, 255, 255, 0.7)", "rgba(255, 255, 255, 0.6)"
    cad_bg, cad_lines, sld_neg = "rgba(255, 255, 255, 0.7)", "#334155", "#64748b"
    matte_black_glass, matte_black_border, table_text = "rgba(15, 23, 42, 0.75)", "rgba(255, 255, 255, 0.15)", "#ffffff"

st.markdown(f"""
<style>
/* Base App Overrides */
.stApp {{ background: {app_bg} !important; background-attachment: fixed !important; }}
.stApp, .stApp p, .stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp h5, .stApp h6, .stApp label, .stApp span, .stApp div[data-testid="stMarkdownContainer"], th, td {{ color: {text_col} !important; }}
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;600;800&display=swap');
html, body, [class*="css"] {{ font-family: 'Plus Jakarta Sans', sans-serif !important; }}

.block-container::before {{ content: "daisy"; position: fixed; top: 55%; left: 50%; transform: translate(-50%, -50%); font-size: 26vw; font-weight: 900; color: {'rgba(255,255,255,0.02)' if is_dark else 'rgba(255,255,255,0.3)'} !important; z-index: -10 !important; pointer-events: none; letter-spacing: -0.05em; }}
.block-container {{ z-index: 1; position: relative; padding-top: 1rem !important; max-width: 1400px !important; }}

/* Expanders */
[data-testid="stExpander"] details {{ background-color: {glass_bg} !important; backdrop-filter: {glass_blur} !important; -webkit-backdrop-filter: {glass_blur} !important; border: 1px solid {glass_border} !important; border-radius: 20px !important; box-shadow: {glass_shadow} !important; overflow: hidden !important; transition: all 0.3s ease; }}
[data-testid="stExpander"] summary {{ background-color: transparent !important; }}
[data-testid="stExpander"] summary:hover {{ background-color: rgba(0,0,0,0.03) !important; }}
[data-testid="stExpander"] summary span {{ color: {text_col} !important; font-weight: 700 !important; font-size: 1.1rem !important; }}
[data-testid="stExpander"] div[role="group"] {{ background-color: transparent !important; padding: 20px !important; }}

/* Matte Dark Glass Overrides */
[data-testid="stDataFrameResizable"] {{ background-color: {matte_black_glass} !important; backdrop-filter: {glass_blur} !important; -webkit-backdrop-filter: {glass_blur} !important; border: 1px solid {matte_black_border} !important; border-radius: 16px !important; padding: 0px !important; box-shadow: {glass_shadow} !important; overflow: hidden !important; }}
[data-testid="stDataFrameResizable"] > div:first-child, [data-testid="stDataFrameResizable"] canvas {{ background-color: transparent !important; border-radius: 16px !important; overflow: hidden !important; }}
[data-testid="stDataFrameResizable"] * {{ color: {table_text} !important; border-color: rgba(255,255,255,0.1) !important; }}

[data-testid="stFileUploadDropzone"] {{ background-color: {matte_black_glass} !important; background-image: none !important; backdrop-filter: {glass_blur} !important; -webkit-backdrop-filter: {glass_blur} !important; border: 1px solid {matte_black_border} !important; border-radius: 16px !important; padding: 24px !important; box-shadow: {glass_shadow} !important; }}
[data-testid="stFileUploadDropzone"] * {{ color: #ffffff !important; fill: #ffffff !important; stroke: #ffffff !important; }}
[data-testid="stFileUploadDropzone"] button {{ background: rgba(255,255,255,0.1) !important; border-radius: 8px !important; border: 1px solid rgba(255,255,255,0.2) !important; color: #ffffff !important; }}
[data-testid="stUploadedFile"] {{ background-color: rgba(255,255,255,0.05) !important; border: 1px solid rgba(255,255,255,0.1) !important; border-radius: 12px !important; }}

/* Checkbox & Radios */
[data-testid="stCheckbox"] div[data-baseweb="checkbox"] > div:first-child, [data-testid="stRadio"] div[data-baseweb="radio"] > div:first-child {{ background-color: {'rgba(255, 255, 255, 0.1)' if is_dark else 'rgba(255, 255, 255, 0.4)'} !important; border: 1px solid {'rgba(255, 255, 255, 0.2)' if is_dark else 'rgba(255, 255, 255, 0.9)'} !important; backdrop-filter: blur(4px) !important; border-radius: 4px !important; }}
[data-testid="stCheckbox"] div[data-baseweb="checkbox"] > div:first-child svg {{ fill: {'#ffffff' if is_dark else '#1e3a8a'} !important; }}
div[data-testid="stCheckbox"] label span, div[data-testid="stRadio"] label span {{ color: {text_col} !important; font-weight: 600 !important; }}

/* Inputs & Tabs */
div[data-baseweb="select"] > div:first-of-type, div[data-baseweb="input"], div[data-baseweb="base-input"] {{ background-color: {input_bg} !important; border: 1px solid {border_col} !important; color: {text_col} !important; backdrop-filter: blur(16px) !important; -webkit-backdrop-filter: blur(16px) !important; border-radius: 12px !important; box-shadow: inset 0 1px 3px rgba(0,0,0,0.05) !important; }}
input, div[data-baseweb="select"] span {{ color: {text_col} !important; background-color: transparent !important; }}
button[kind="stepUp"], button[kind="stepDown"] {{ background-color: transparent !important; color: {text_col} !important; border-color: transparent !important; }}
.stTabs [data-baseweb="tab-list"] {{ gap: 12px; background-color: transparent; border-bottom: none !important; }}
.stTabs [data-baseweb="tab"] {{ border-radius: 50px !important; padding: 10px 24px; background-color: {input_bg} !important; border: 1px solid {border_col} !important; transition: all 0.3s ease; font-weight: 600; color: {text_muted} !important; backdrop-filter: blur(16px) !important; }}
.stTabs [aria-selected="true"] {{ background: linear-gradient(45deg, #1e3a8a, #3b82f6) !important; color: white !important; box-shadow: 0 4px 10px rgba(0,0,0,0.15) !important; border: none !important; }}

/* Metric Cards */
[data-testid="stMetric"] {{ background: {metric_bg} !important; border: 1px solid {metric_border} !important; border-radius: 20px !important; padding: 1.5rem 1rem !important; box-shadow: {glass_shadow} !important; backdrop-filter: blur(16px) !important; -webkit-backdrop-filter: blur(16px) !important; transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275) !important; display: flex !important; flex-direction: column !important; justify-content: center !important; align-items: center !important; text-align: center !important; }}
[data-testid="stMetric"] > div {{ display: flex !important; flex-direction: column !important; align-items: center !important; width: 100% !important; }}
[data-testid="stMetric"]:hover {{ transform: translateY(-8px) scale(1.02) !important; border-color: #3b82f6 !important; box-shadow: 0 15px 30px rgba(59, 130, 246, 0.15) !important; }}
[data-testid="stMetricValue"] {{ background: {metric_val} !important; -webkit-background-clip: text !important; -webkit-text-fill-color: transparent !important; font-weight: 800 !important; font-size: 1.8rem !important; padding-top: 5px !important; padding-bottom: 5px !important; white-space: normal !important; word-wrap: break-word !important; line-height: 1.2 !important; }}
[data-testid="stMetricLabel"] {{ margin-bottom: 0.2rem !important; color: {text_muted} !important; font-size: 0.95rem !important; font-weight: 600 !important; }}

/* Navbar Styling */
div[data-testid="stHorizontalBlock"]:first-of-type {{ align-items: center; margin-bottom: 2rem; position: relative; z-index: 999 !important; gap: 0.5rem !important; }}
.nav-logo {{ font-size: 2.4rem; font-weight: 900; color: #3b82f6; letter-spacing: -1.5px; line-height: 1; padding-bottom: 5px; }}
div[data-testid="stHorizontalBlock"]:first-of-type button[kind="secondary"] {{ background: transparent !important; color: {text_muted} !important; font-weight: 700 !important; border: none !important; padding: 0.5rem 1rem !important; transition: all 0.3s ease; box-shadow: none !important; width: 100% !important; font-size: 1.05rem !important; }}
div[data-testid="stHorizontalBlock"]:first-of-type button[kind="secondary"]:hover {{ color: {text_col} !important; background: rgba(120, 120, 120, 0.15) !important; border-radius: 50px !important; }}
div.stButton > button[kind="primary"], div[data-testid="stHorizontalBlock"]:first-of-type button[kind="primary"] {{ border-radius: 50px !important; font-weight: 800 !important; letter-spacing: 1px !important; background: linear-gradient(45deg, #1e3a8a, #6c5ce7, #00b894, #3b82f6) !important; background-size: 300% 300% !important; color: white !important; border: none !important; animation: gradientPulse 4s ease infinite !important; box-shadow: 0 6px 15px rgba(108, 92, 231, 0.25) !important; transition: transform 0.2s cubic-bezier(0.175, 0.885, 0.32, 1.275) !important; width: 100% !important; }}
div.stButton > button[kind="primary"]:hover, div[data-testid="stHorizontalBlock"]:first-of-type button[kind="primary"]:hover {{ transform: scale(1.05) !important; box-shadow: 0 10px 25px rgba(108, 92, 231, 0.5) !important; }}
@keyframes gradientPulse {{ 0% {{ background-position: 0% 50%; }} 50% {{ background-position: 100% 50%; }} 100% {{ background-position: 0% 50%; }} }}

/* Front Pages Specific Elements */
.hero-title {{ font-size: 4.5rem; font-weight: 900; background: linear-gradient(135deg, {text_col} 0%, #1e3a8a 50%, #3b82f6 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; line-height: 1.05; letter-spacing: -0.03em; margin-bottom: 20px; }}
.hero-subtitle {{ font-size: 1.2rem; color: {text_muted}; line-height: 1.6; max-width: 90%; }}
.saas-card {{ background: {glass_bg}; border-radius: 24px; padding: 40px; box-shadow: {glass_shadow}; border: 1px solid {glass_border}; height: 100%; backdrop-filter: {glass_blur}; -webkit-backdrop-filter: {glass_blur}; }}
.sys-img {{ width: 100%; height: auto; object-fit: cover; border-radius: 40px 10px 40px 10px; margin-top: 25px; box-shadow: {glass_shadow}; border: 6px solid {glass_border}; transition: all 0.5s cubic-bezier(0.175, 0.885, 0.32, 1.275); }}
.sys-img:hover {{ transform: translateY(-10px) scale(1.02); border-radius: 10px 40px 10px 40px; box-shadow: 0 25px 45px rgba(30, 58, 138, 0.15); border-color: rgba(59, 130, 246, 0.3); }}
.manual-img {{ width: 100% !important; max-width: 500px !important; height: auto !important; object-fit: cover; border-radius: 24px; box-shadow: {glass_shadow}; border: 8px solid {glass_border}; transition: transform 0.4s ease; display: block; }}
.manual-img:hover {{ transform: scale(1.03); box-shadow: 0 20px 45px rgba(30, 58, 138, 0.2); }}
.contact-btn {{ background: {glass_bg}; border-radius: 50px; padding: 15px 35px; display: inline-flex; align-items: center; gap: 15px; box-shadow: {glass_shadow}; border: 1px solid {glass_border}; transition: all 0.3s ease; text-decoration: none !important; color: {text_col} !important; font-weight: 800; font-size: 1.2rem; backdrop-filter: {glass_blur}; }}
.contact-btn:hover {{ transform: translateY(-5px); border-color: #3b82f6; }}
.contact-btn svg {{ width: 28px; height: 28px; stroke: #3b82f6; }}

/* CAD Canvas Overrides */
[data-testid="stIFrame"] {{ border-radius: 20px !important; box-shadow: {glass_shadow} !important; overflow: hidden !important; border: 1px solid {glass_border} !important; }}

hr {{ border-color: {border_col} !important; }}
header {{ background: transparent !important; }}
</style>
""", unsafe_allow_html=True)

# ==========================================
# UNIFIED GLOBAL NAVBAR (ADDED CAD STUDIO)
# ==========================================
if st.session_state.page != 'cad':
    nav_col1, nav_col2, nav_col3, nav_col4, nav_col5, nav_col6, nav_col7, nav_col8 = st.columns([3.3, 0.8, 0.8, 0.8, 1.2, 0.8, 0.8, 1.6])
    with nav_col1: st.markdown("<div class='nav-logo'>Daisy.</div>", unsafe_allow_html=True)
    with nav_col2:
        if st.button("Home", key="btn_home"):
            if st.session_state.page != 'home': st.session_state.page = 'home'; st.rerun()
    with nav_col3:
        if st.button("About", key="btn_about"):
            if st.session_state.page != 'about': st.session_state.page = 'about'; st.rerun()
    with nav_col4:
        if st.button("Manual", key="btn_manual"):
            if st.session_state.page != 'manual': st.session_state.page = 'manual'; st.rerun()
    with nav_col5:
        if st.button("📐 CAD Studio", key="btn_cad"):
            if st.session_state.page != 'cad': st.session_state.page = 'cad'; st.rerun()
    with nav_col6:
        if st.button("Contact", key="btn_contact"):
            if st.session_state.page != 'contact': st.session_state.page = 'contact'; st.rerun()
    with nav_col7:
        if st.session_state.page != 'home':
            theme_btn_text = "☀️ Light" if is_dark else "🌙 Dark"
            if st.button(theme_btn_text, key="btn_theme"):
                st.session_state.theme = "Light" if is_dark else "Dark"
                st.rerun()
    with nav_col8:
        if st.button("Dashboard", type="primary", key="btn_dash"):
            if st.session_state.page != 'dashboard': st.session_state.page = 'dashboard'; st.rerun()

# ==========================================
# FRONT-END PAGES
# ==========================================
if st.session_state.page == 'home':
    # Override background to warm beige and lock scrolling
    st.markdown("""
    <style>
        .stApp { background: #EDE5D8 !important; background-image: none !important; }
        .stApp, [data-testid="stAppViewContainer"], [data-testid="stMain"] { overflow: hidden !important; max-height: 100vh !important; }
        .block-container { max-height: calc(100vh - 70px) !important; overflow: hidden !important; padding-bottom: 0 !important; padding-top: 1rem !important; }
        [data-testid="stIFrame"] { border-radius: 0 !important; box-shadow: none !important; border: none !important; background: transparent !important; backdrop-filter: none !important; -webkit-backdrop-filter: none !important; }
        .hero-title, .hero-subtitle { display: none !important; }
    </style>
    """, unsafe_allow_html=True)

    st.components.v1.html("""
    <!DOCTYPE html>
    <html>
    <head>
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;600;800;900&display=swap');
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body { font-family: 'Plus Jakarta Sans', sans-serif; background: transparent; overflow: hidden; height: 100vh; }

    .hero-wrap { display: flex; align-items: center; justify-content: space-between; height: 100%; padding: 0 0 0 10px; gap: 20px; }

    /* ===== LEFT SIDE ===== */
    .hero-left { flex: 1.1; max-width: 560px; z-index: 10; }
    .hero-left .tag { font-size: 0.95rem; color: #7c6f5b; font-weight: 600; margin-bottom: 12px; letter-spacing: 0.5px; }
    .hero-left h1 { font-size: 2.8rem; font-weight: 900; color: #1a1a2e; line-height: 1.1; letter-spacing: -1.5px; margin-bottom: 18px; }
    .hero-left h1 span { color: #3b82f6; }
    .hero-left .desc { font-size: 0.95rem; color: #5a5245; line-height: 1.65; margin-bottom: 22px; max-width: 480px; }
    .hero-left .radio-group { display: flex; gap: 24px; margin-bottom: 24px; }
    .hero-left .radio-group label { display: flex; align-items: center; gap: 6px; font-size: 0.9rem; color: #3d3627; font-weight: 600; cursor: pointer; }
    .hero-left .radio-group input[type="radio"] { accent-color: #3b82f6; width: 16px; height: 16px; }
    .hero-btns { display: flex; gap: 14px; }
    .btn-dash { background: linear-gradient(135deg, #4a90d9, #3b82f6); color: white; border: none; padding: 13px 32px; border-radius: 50px; font-weight: 800; font-size: 0.95rem; cursor: pointer; box-shadow: 0 8px 25px rgba(59, 130, 246, 0.35); transition: all 0.3s ease; letter-spacing: 0.5px; }
    .btn-dash:hover { transform: translateY(-3px) scale(1.03); box-shadow: 0 14px 35px rgba(59, 130, 246, 0.5); }
    .btn-design { background: linear-gradient(135deg, #e67e22, #f39c12); color: white; border: none; padding: 13px 32px; border-radius: 50px; font-weight: 800; font-size: 0.95rem; cursor: pointer; box-shadow: 0 8px 25px rgba(230, 126, 34, 0.3); transition: all 0.3s ease; letter-spacing: 0.5px; }
    .btn-design:hover { transform: translateY(-3px) scale(1.03); box-shadow: 0 14px 35px rgba(230, 126, 34, 0.5); }

    /* ===== RIGHT SIDE ===== */
    .hero-right { flex: 1; display: flex; justify-content: center; align-items: center; position: relative; height: 100%; min-width: 420px; }

    /* Main glowing orb */
    .orb { width: 380px; height: 380px; border-radius: 50%; background: radial-gradient(circle at 40% 35%, #ffecd2 0%, #f5c77e 35%, #e8a840 65%, #d4893a 100%); box-shadow: 0 0 80px rgba(245, 199, 126, 0.5), 0 0 160px rgba(232, 168, 64, 0.25), inset 0 -30px 60px rgba(0,0,0,0.08); position: relative; z-index: 5; animation: orbPulse 6s ease-in-out infinite; }
    @keyframes orbPulse { 0%, 100% { box-shadow: 0 0 80px rgba(245, 199, 126, 0.5), 0 0 160px rgba(232, 168, 64, 0.25); transform: scale(1); } 50% { box-shadow: 0 0 100px rgba(245, 199, 126, 0.65), 0 0 200px rgba(232, 168, 64, 0.35); transform: scale(1.02); } }

    /* Main daisy in center */
    .main-flower { position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); width: 160px; height: 160px; animation: gentleSway 5s ease-in-out infinite; z-index: 6; }
    .main-flower .fc { position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); width: 50px; height: 50px; background: radial-gradient(circle, #f1c40f, #e67e22); border-radius: 50%; z-index: 10; box-shadow: 0 0 20px rgba(241, 196, 15, 0.6), inset -4px -4px 12px rgba(211, 84, 0, 0.3); }
    .main-flower .mp { position: absolute; top: 50%; left: 50%; width: 26px; height: 85px; background: linear-gradient(to top, #f0eae0, #ffffff); border-radius: 50% 50% 50% 50% / 60% 60% 40% 40%; transform-origin: 50% 100%; margin-top: -85px; margin-left: -13px; box-shadow: 0 3px 8px rgba(0,0,0,0.08); }
    .mp1{transform:rotate(0deg) translateY(-6px)}.mp2{transform:rotate(30deg) translateY(-6px)}.mp3{transform:rotate(60deg) translateY(-6px)}.mp4{transform:rotate(90deg) translateY(-6px)}.mp5{transform:rotate(120deg) translateY(-6px)}.mp6{transform:rotate(150deg) translateY(-6px)}.mp7{transform:rotate(180deg) translateY(-6px)}.mp8{transform:rotate(210deg) translateY(-6px)}.mp9{transform:rotate(240deg) translateY(-6px)}.mp10{transform:rotate(270deg) translateY(-6px)}.mp11{transform:rotate(300deg) translateY(-6px)}.mp12{transform:rotate(330deg) translateY(-6px)}
    @keyframes gentleSway { 0%,100%{transform:translate(-50%,-50%) rotate(-3deg) scale(1)} 50%{transform:translate(-50%,-50%) rotate(3deg) scale(1.04)} }

    /* Solar Panels */
    .solar-panel { position: absolute; z-index: 8; filter: drop-shadow(0 15px 25px rgba(0,0,0,0.25)); }
    .solar-panel .panel-body { width: 90px; height: 60px; background: #94a3b8; border-radius: 4px; border: 2px solid #cbd5e1; display: grid; grid-template-columns: repeat(4, 1fr); grid-template-rows: repeat(2, 1fr); gap: 1px; padding: 2px; transform: perspective(300px) rotateX(25deg) rotateY(-15deg); box-shadow: inset 0 0 5px rgba(0,0,0,0.4); }
    .solar-panel .cell { background: linear-gradient(160deg, #0f172a 0%, #1e293b 100%); border-radius: 1px; position: relative; overflow: hidden; }
    .solar-panel .cell::after { content: ""; position: absolute; top: 0; left: 0; right: 0; height: 1px; background: rgba(255,255,255,0.2); box-shadow: 0 4px 10px rgba(255,255,255,0.15); transform: rotate(-45deg); }
    .sp1 { top: 5%; right: -5%; animation: floatSP1 7s ease-in-out infinite; }
    .sp2 { bottom: 15%; right: -15%; animation: floatSP2 8s ease-in-out infinite; }
    .sp3 { bottom: 5%; left: -5%; animation: floatSP3 9s ease-in-out infinite; }
    .sp4 { top: 20%; left: -20%; animation: floatSP4 6s ease-in-out infinite; }
    @keyframes floatSP1 { 0%,100%{transform:translate(0,0) rotate(-15deg)} 50%{transform:translate(-12px,15px) rotate(-5deg)} }
    @keyframes floatSP2 { 0%,100%{transform:translate(0,0) rotate(10deg)} 50%{transform:translate(10px,-18px) rotate(20deg)} }
    @keyframes floatSP3 { 0%,100%{transform:translate(0,0) rotate(5deg)} 50%{transform:translate(15px,10px) rotate(-8deg)} }
    @keyframes floatSP4 { 0%,100%{transform:translate(0,0) rotate(-10deg)} 50%{transform:translate(-8px,-15px) rotate(5deg)} }

    /* Mini Daisies */
    .mini-daisy { position: absolute; z-index: 9; }
    .mini-daisy .md-wrap { position: relative; width: 30px; height: 30px; }
    .mini-daisy .md-c { position: absolute; top: 50%; left: 50%; transform: translate(-50%,-50%); width: 10px; height: 10px; background: #f1c40f; border-radius: 50%; z-index: 2; }
    .mini-daisy .md-p { position: absolute; top: 50%; left: 50%; width: 5px; height: 16px; background: white; border-radius: 50%/60% 60% 40% 40%; transform-origin: 50% 100%; margin-top: -16px; margin-left: -2.5px; }
    .mdp1{transform:rotate(0deg)}.mdp2{transform:rotate(45deg)}.mdp3{transform:rotate(90deg)}.mdp4{transform:rotate(135deg)}.mdp5{transform:rotate(180deg)}.mdp6{transform:rotate(225deg)}.mdp7{transform:rotate(270deg)}.mdp8{transform:rotate(315deg)}
    .md1 { top: -8%; left: 45%; animation: floatMD1 6s ease-in-out infinite; }
    .md2 { top: 10%; right: -12%; animation: floatMD2 7s ease-in-out infinite; }
    .md3 { bottom: -5%; right: 35%; animation: floatMD3 8s ease-in-out infinite; }
    .md4 { bottom: 25%; left: -18%; animation: floatMD4 5.5s ease-in-out infinite; }
    @keyframes floatMD1 { 0%,100%{transform:translate(0,0) rotate(0deg)} 50%{transform:translate(8px,12px) rotate(15deg)} }
    @keyframes floatMD2 { 0%,100%{transform:translate(0,0) rotate(0deg)} 50%{transform:translate(-10px,8px) rotate(-20deg)} }
    @keyframes floatMD3 { 0%,100%{transform:translate(0,0) rotate(0deg)} 50%{transform:translate(12px,-10px) rotate(10deg)} }
    @keyframes floatMD4 { 0%,100%{transform:translate(0,0) rotate(0deg)} 50%{transform:translate(-6px,-14px) rotate(-12deg)} }

    /* Floating petals */
    .fpetal { position: absolute; width: 12px; height: 30px; background: linear-gradient(to top, #f0eae0, #ffffff); border-radius: 50%/60% 60% 40% 40%; z-index: 7; opacity: 0.7; box-shadow: 0 4px 10px rgba(0,0,0,0.1); }
    .fp1 { top: 20%; left: 10%; animation: petalDrift1 9s ease-in-out infinite; }
    .fp2 { top: 55%; right: 5%; animation: petalDrift2 11s ease-in-out infinite; }
    .fp3 { bottom: 30%; left: 25%; animation: petalDrift3 8s ease-in-out infinite; }
    .fp4 { top: 8%; right: 30%; animation: petalDrift4 10s ease-in-out infinite; }
    .fp5 { bottom: 10%; right: 20%; animation: petalDrift5 7s ease-in-out infinite; }
    .fp6 { top: 40%; left: -5%; animation: petalDrift6 12s ease-in-out infinite; }
    @keyframes petalDrift1 { 0%{transform:translate(0,0) rotate(30deg)} 25%{transform:translate(20px,30px) rotate(60deg)} 50%{transform:translate(5px,50px) rotate(90deg)} 75%{transform:translate(-15px,25px) rotate(120deg)} 100%{transform:translate(0,0) rotate(30deg)} }
    @keyframes petalDrift2 { 0%{transform:translate(0,0) rotate(-20deg)} 50%{transform:translate(-25px,35px) rotate(40deg)} 100%{transform:translate(0,0) rotate(-20deg)} }
    @keyframes petalDrift3 { 0%{transform:translate(0,0) rotate(45deg)} 50%{transform:translate(30px,-20px) rotate(-15deg)} 100%{transform:translate(0,0) rotate(45deg)} }
    @keyframes petalDrift4 { 0%{transform:translate(0,0) rotate(10deg)} 33%{transform:translate(-15px,25px) rotate(50deg)} 66%{transform:translate(10px,40px) rotate(80deg)} 100%{transform:translate(0,0) rotate(10deg)} }
    @keyframes petalDrift5 { 0%{transform:translate(0,0) rotate(-30deg)} 50%{transform:translate(15px,-30px) rotate(20deg)} 100%{transform:translate(0,0) rotate(-30deg)} }
    @keyframes petalDrift6 { 0%{transform:translate(0,0) rotate(60deg)} 50%{transform:translate(20px,20px) rotate(100deg)} 100%{transform:translate(0,0) rotate(60deg)} }
    </style>
    </head>
    <body>
    <div class="hero-wrap">
        <!-- LEFT SIDE -->
        <div class="hero-left">
            <div class="tag">Calculations made natural.</div>
            <h1>DAISY <span>SOL</span>: DESIGN, CALCULATE, AND OWN YOUR VISION.</h1>
            <p class="desc">An intuitive, effortless solar design experience. From complex thermodynamics to precise CAD layouts, DAISY makes it fluid.</p>
            <div class="hero-btns">
                <button class="btn-dash" onclick="window.parent.postMessage('go_dashboard','*')">Dashboard</button>
            </div>
        </div>

        <!-- RIGHT SIDE -->
        <div class="hero-right">
            <!-- Floating petals -->
            <div class="fpetal fp1"></div><div class="fpetal fp2"></div><div class="fpetal fp3"></div>
            <div class="fpetal fp4"></div><div class="fpetal fp5"></div><div class="fpetal fp6"></div>

            <!-- Solar panels -->
            <div class="solar-panel sp1"><div class="panel-body"><div class="cell"></div><div class="cell"></div><div class="cell"></div><div class="cell"></div><div class="cell"></div><div class="cell"></div><div class="cell"></div><div class="cell"></div></div></div>
            <div class="solar-panel sp2"><div class="panel-body"><div class="cell"></div><div class="cell"></div><div class="cell"></div><div class="cell"></div><div class="cell"></div><div class="cell"></div><div class="cell"></div><div class="cell"></div></div></div>
            <div class="solar-panel sp3"><div class="panel-body"><div class="cell"></div><div class="cell"></div><div class="cell"></div><div class="cell"></div><div class="cell"></div><div class="cell"></div><div class="cell"></div><div class="cell"></div></div></div>
            <div class="solar-panel sp4"><div class="panel-body"><div class="cell"></div><div class="cell"></div><div class="cell"></div><div class="cell"></div><div class="cell"></div><div class="cell"></div><div class="cell"></div><div class="cell"></div></div></div>

            <!-- Mini daisies -->
            <div class="mini-daisy md1"><div class="md-wrap"><div class="md-c"></div><div class="md-p mdp1"></div><div class="md-p mdp2"></div><div class="md-p mdp3"></div><div class="md-p mdp4"></div><div class="md-p mdp5"></div><div class="md-p mdp6"></div><div class="md-p mdp7"></div><div class="md-p mdp8"></div></div></div>
            <div class="mini-daisy md2"><div class="md-wrap"><div class="md-c"></div><div class="md-p mdp1"></div><div class="md-p mdp2"></div><div class="md-p mdp3"></div><div class="md-p mdp4"></div><div class="md-p mdp5"></div><div class="md-p mdp6"></div><div class="md-p mdp7"></div><div class="md-p mdp8"></div></div></div>
            <div class="mini-daisy md3"><div class="md-wrap"><div class="md-c"></div><div class="md-p mdp1"></div><div class="md-p mdp2"></div><div class="md-p mdp3"></div><div class="md-p mdp4"></div><div class="md-p mdp5"></div><div class="md-p mdp6"></div><div class="md-p mdp7"></div><div class="md-p mdp8"></div></div></div>
            <div class="mini-daisy md4"><div class="md-wrap"><div class="md-c"></div><div class="md-p mdp1"></div><div class="md-p mdp2"></div><div class="md-p mdp3"></div><div class="md-p mdp4"></div><div class="md-p mdp5"></div><div class="md-p mdp6"></div><div class="md-p mdp7"></div><div class="md-p mdp8"></div></div></div>

            <!-- Main Orb with Daisy -->
            <div class="orb">
                <div class="main-flower">
                    <div class="fc"></div>
                    <div class="mp mp1"></div><div class="mp mp2"></div><div class="mp mp3"></div><div class="mp mp4"></div>
                    <div class="mp mp5"></div><div class="mp mp6"></div><div class="mp mp7"></div><div class="mp mp8"></div>
                    <div class="mp mp9"></div><div class="mp mp10"></div><div class="mp mp11"></div><div class="mp mp12"></div>
                </div>
            </div>
        </div>
    </div>
    </body>
    </html>
    """, height=520)

    # Hidden listener for the HTML buttons
    st.components.v1.html("""
    <script>
    window.addEventListener("message", (e) => {
        if (e.data === "go_dashboard" || e.data === "go_cad") {
            // Forward up to Streamlit parent
            window.parent.postMessage(e.data, "*");
        }
    });
    </script>
    """, height=0)

    # Hidden Streamlit buttons triggered by JS
    if st.button("HiddenDashBtn", key="hidden_dash_btn"):
        st.session_state.page = 'dashboard'
        st.rerun()
    if st.button("HiddenCADBtn", key="hidden_cad_btn"):
        st.session_state.page = 'cad'
        st.rerun()
    st.markdown("""<style>
    /* Hide ONLY the bridge buttons, not navbar */
    button[kind="secondary"] > div > p { visibility: visible; }
    div.stButton:has(button > div > p) { }
    div.row-widget.stButton button:is([kind="secondary"]) { }
    </style>""", unsafe_allow_html=True)

    # Use JS to hide the bridge buttons after render
    st.components.v1.html("""<script>
    (function hideButtons() {
        const btns = window.parent.document.querySelectorAll('button[kind="secondary"]');
        btns.forEach(b => {
            const t = b.textContent || '';
            if (t.includes('HiddenDashBtn') || t.includes('HiddenCADBtn')) {
                b.closest('.stButton').style.cssText = 'opacity:0;height:0;overflow:hidden;position:absolute;pointer-events:none;';
            }
        });
        if (!btns.length) setTimeout(hideButtons, 200);
    })();
    </script>""", height=0)

    # JS bridge to click hidden Streamlit buttons
    st.components.v1.html("""
    <script>
    window.parent.addEventListener("message", (e) => {
        if (e.data === "go_dashboard" || e.data === "go_cad") {
            const btns = window.parent.document.querySelectorAll("button");
            btns.forEach(b => {
                if (e.data === "go_dashboard" && b.textContent.includes("HiddenDashBtn")) b.click();
                if (e.data === "go_cad" && b.textContent.includes("HiddenCADBtn")) b.click();
            });
        }
    });
    </script>
    """, height=0)

elif st.session_state.page == 'about':
    st.markdown("<div style='padding-top: 20px; z-index: 10; position: relative;'>", unsafe_allow_html=True)
    st.markdown("<div class='hero-title' style='text-align: center;'>The Architecture of Light.</div>", unsafe_allow_html=True)
    st.markdown(f"<p class='hero-subtitle' style='margin: 0 auto 4rem auto; text-align: center; font-size: 1.3rem; max-width: 800px; color: {text_muted};'>Daisy bridges the void between impenetrable engineering mathematics and breathtaking software design. We empower visionaries to map out a sustainable energy future with unparalleled precision.</p>", unsafe_allow_html=True)
    
    c1, c2 = st.columns(2)
    with c1:
        img_pv_html = render_img("pv.jpg", "sys-img")
        st.markdown(f"""
        <div class='saas-card'>
            <h3 style='color:#1e3a8a; margin-top:0; font-size:1.6rem; letter-spacing: -0.5px;'>⚡ Photovoltaic Dominance</h3>
            <p style='color:{text_muted}; font-size:1.05rem; line-height:1.7; margin-bottom: 0;'>
            Harness the quantum mechanics of the photoelectric effect. Our computational engine perfectly maps real-time Ohmic voltage drops across varying AWG copper conduits, strictly enforces Inverter MPPT limits for string sizing, and applies dynamic NOCT thermal derating matrices so your silicon performs precisely as calculated. Featuring advanced 3D winter solstice shadow pruning and LCOE lifecycle financial matrices, Daisy guarantees peak yield and absolute ROI transparency.
            </p>
            {img_pv_html}
        </div>
        """, unsafe_allow_html=True)
    with c2:
        img_th_html = render_img("thermal.jpg", "sys-img")
        st.markdown(f"""
        <div class='saas-card'>
            <h3 style='color:#d35400; margin-top:0; font-size:1.6rem; letter-spacing: -0.5px;'>💧 Thermal Fluid Dynamics</h3>
            <p style='color:{text_muted}; font-size:1.05rem; line-height:1.7; margin-bottom: 0;'>
            Capture immense raw solar irradiance through advanced evacuated tube thermodynamics. We execute flawless fluid dynamic equations and specific heat capacity conversions ($E = mc\Delta T$) to design high-efficiency matrices. Daisy calculates baseline groundwater deltas, structural payload thresholds, and optimal flow rates to maximize your green thermal yield, ensuring perfectly scaled storage and expansion tanks for enterprise projects.
            </p>
            {img_th_html}
        </div>
        """, unsafe_allow_html=True)
        
    st.markdown(f"""
    <div class='saas-card' style='margin-top: 2rem; padding: 50px;'>
        <h3 style='color:#1e3a8a; margin-top:0; font-size:2rem; text-align: center;'>The Engineering Vision</h3>
        <p style='font-size:1.15rem; line-height:1.8; margin-bottom: 0; color: {text_muted}; text-align: center; max-width: 900px; margin: 0 auto;'>
        Forged at the intersection of <b>Mechanical Engineering</b> and <b>Energy Science</b>, Daisy represents a leap in sustainable system design. The thermodynamic engines driving this platform are deeply influenced by advanced academic research in solar thermal arrays, exergy analyses, and next-generation systems like autothermal ammonia cracking reactors.<br><br>Built with the rigorous precision demanded by leading academic guidance, every calculation is fundamentally optimized for peak yield. We marry this mechanical exactness with a fluid, organic UI—where every line of code <i>flutters with purpose</i>, bridging the gap between heavy industry and seamless design.
        </p>
    </div>
    </div>
    """, unsafe_allow_html=True)

elif st.session_state.page == 'manual':
    st.markdown("<div style='padding-top: 20px; z-index: 10; position: relative;'>", unsafe_allow_html=True)
    st.markdown("<div class='hero-title' style='text-align: center;'>Official Engineering Manual.</div>", unsafe_allow_html=True)
    st.markdown(f"<p class='hero-subtitle' style='margin: 0 auto 4rem auto; text-align: center; font-size: 1.3rem; max-width: 800px; color: {text_muted};'>Daisy does not estimate. It calculates. Below is the exact physics, mathematics, and logic running in the background when you generate a report.</p>", unsafe_allow_html=True)
    
    manual_sections = [
        ("1. Climatology & Geospatial Engine", "Screenshot (302).png", "<b>Data Source:</b> Daisy directly pings the NASA POWER Satellite API.<br><br><b>Function:</b> Instead of guessing the sunlight, the engine fetches the specific 20-year historical average of Global Horizontal Irradiance (GHI) and Diffuse Horizontal Irradiance (DHI) for your exact Latitude and Longitude. You can manually resolve your GPS or use the Auto-Detect feature to pinpoint your location on the interactive 3D map."),
        ("2. Orbital Mechanics & Solar Geometry Engine", "Screenshot (299).png", "To position the panels perfectly, Daisy calculates the position of the sun in the sky at any given moment using celestial mechanics.<br><br>• <b>Declination Angle ($\delta$):</b> Calculates seasonal tilt.<br>• <b>Solar Zenith Angle ($\\theta_z$):</b> Calculates the angle of the sun directly overhead.<br>• <b>Optimal Seasonal Tilt ($\\beta$):</b> Automatically calculates optimal seasonal angles for maximum yield."),
        ("3. Photovoltaic (PV) Electrical Engine", "Screenshot (297).png", "Solar panels are semiconductors; their performance changes based on heat and wiring configurations.<br><br>• <b>Thermal Derating (NOCT):</b> For every degree above $25^\\circ\\text{C}$, the engine reduces the panel's output by its specific Temperature Coefficient.<br>• <b>MPPT String Matching:</b> The engine determines the absolute maximum number of panels allowed in a single series string based on Inverter MPPT limits."),
        ("4. Spatial CAD & 3D Shadow Pruning", "Screenshot (304).png", "Daisy generates a scale-accurate Issued For Construction (IFC) blueprint.<br><br>• <b>Shadow Pruning:</b> Calculates the maximum length of a shadow cast by any object during the Winter Solstice.<br>• <b>Collision Detection:</b> Draws an invisible grid over your roof, blocks out fire setbacks and shadows, and perfectly packs the solar panels into the remaining safe space."),
        ("5. Lifecycle Economics (LCOE)", "Screenshot (295).png", "Daisy runs a complete 25-year financial simulation.<br><br>• <b>Time-of-Use (TOU):</b> Simulates 8,760 hours of a year, tracking exactly when you use power and when the sun shines.<br>• <b>Levelized Cost of Energy (LCOE):</b> Takes your gross cost, subtracts subsidies, adds 25 years of O&M costs, and divides by degraded solar production to give you your exact Cost per kWh."),
        ("6. Voltage Drop & Single-Line Diagram", "Screenshot (301).png", "Electricity experiences 'friction' inside cables. Daisy calculates the exact physical distance from your array to the inverter in the CAD map. It then runs through standard AWG (American Wire Gauge) copper resistance tables to find a wire thick enough to ensure your voltage drop is <b>strictly less than 3%</b>.")
    ]
    
    for title, img, desc in manual_sections:
        img_html = render_img(img, "manual-img")
        st.markdown(f"""
        <div class='saas-card' style='margin-bottom: 2rem; display: flex; align-items: flex-start; justify-content: space-between; gap: 50px; flex-wrap: wrap;'>
            <div style='flex: 1; min-width: 300px;'>
                <h3 style='color:#1e3a8a; margin-top:0; font-size: 1.8rem;'>{title}</h3>
                <p style='color:{text_muted}; font-size:1.15rem; line-height:1.8;'>{desc}</p>
            </div>
            <div style='flex-shrink: 0; display: flex; justify-content: center; width: 100%; max-width: 500px;'>
                {img_html}
            </div>
        </div>
        """, unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

elif st.session_state.page == 'contact':
    st.markdown("<div style='padding-top: 60px; z-index: 10; position: relative; text-align: center;'>", unsafe_allow_html=True)
    st.markdown("<div class='hero-title'>Let's Connect.</div>", unsafe_allow_html=True)
    st.markdown(f"<p class='hero-subtitle' style='margin: 0 auto 3rem auto; color: {text_muted};'>Have a project in mind or want to discuss engineering physics? Reach out directly.</p>", unsafe_allow_html=True)
    
    st.markdown("""
    <div style='display: flex; justify-content: center; gap: 30px; margin-top: 20px; flex-wrap: wrap;'>
        <a href="mailto:jaideepkumarsisodiya0@gmail.com" target="_blank" style="text-decoration: none;">
            <div class="contact-btn">
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"></path><polyline points="22,6 12,13 2,6"></polyline></svg>
                <span>Email Me</span>
            </div>
        </a>
        <a href="https://www.linkedin.com/in/jaideep-kumar-sisodiya-2579b0240/" target="_blank" style="text-decoration: none;">
            <div class="contact-btn">
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M16 8a6 6 0 0 1 6 6v7h-4v-7a2 2 0 0 0-2-2 2 2 0 0 0-2 2v7h-4v-7a6 6 0 0 1 6-6z"></path><rect x="2" y="9" width="4" height="12"></rect><circle cx="4" cy="4" r="2"></circle></svg>
                <span>LinkedIn</span>
            </div>
        </a>
    </div>
    </div>
    """, unsafe_allow_html=True)

# ==========================================
# LAYER 8: NEW INTERACTIVE CAD STUDIO
# ==========================================
elif st.session_state.page == 'cad':
    # We will use JavaScript to directly mount the CAD iframe to the absolute root of the browser window.
    # This guarantees it covers everything (100vw x 100vh) without ANY Streamlit backgrounds, margins, or CSS bleeding through.
    
    # Hidden button for Returning to Dashboard
    if st.button("HiddenReturnBtn", key="hidden_return"):
        cad_data_path = "cad_data.json"
        if os.path.exists(cad_data_path):
            import json
            with open(cad_data_path, "r") as f:
                cad_json = json.load(f)
            try: os.remove(cad_data_path)
            except: pass
            
            st.session_state.cad_imported = True
            st.session_state.cad_json_data = cad_json 
            
        st.session_state.loading_target = 'dashboard'
        st.rerun()

    # Hidden button for going Home without importing
    if st.button("HiddenHomeBtn", key="hidden_home"):
        st.session_state.loading_target = 'home'
        st.rerun()

    # Inject the CAD engine directly to the browser body and listen for the return signal
    st.components.v1.html("""
        <script>
            // 1. Create the CAD iframe natively
            const iframe = window.parent.document.createElement('iframe');
            iframe.src = 'http://localhost:8000/cad?v=' + Date.now();
            iframe.style.position = 'fixed';
            iframe.style.top = '0';
            iframe.style.left = '0';
            iframe.style.width = '100vw';
            iframe.style.height = '100vh';
            iframe.style.zIndex = '999999999';
            iframe.style.border = 'none';
            iframe.style.margin = '0';
            iframe.style.padding = '0';
            iframe.style.background = '#f0f0f0';
            iframe.id = 'cad-fullscreen-iframe';
            
            // Only append if it doesn't already exist
            if (!window.parent.document.getElementById('cad-fullscreen-iframe')) {
                window.parent.document.body.appendChild(iframe);
            }
            
            // 2. Listen on the PARENT window (Streamlit main document) — 
            //    that is where the CAD iframe posts its messages to.
            window.parent.addEventListener("message", (event) => {
                if (event.data === "return_to_daisy" || event.data === "go_home_daisy") {
                    // Destroy the CAD iframe to reveal Daisy underneath
                    const el = window.parent.document.getElementById('cad-fullscreen-iframe');
                    if (el) el.remove();
                    
                    // Click the hidden Streamlit button to trigger the Python state reload
                    const btns = window.parent.document.querySelectorAll('button');
                    btns.forEach(b => {
                        if (event.data === "return_to_daisy" && b.textContent.includes("HiddenReturnBtn")) {
                            b.click();
                        }
                        if (event.data === "go_home_daisy" && b.textContent.includes("HiddenHomeBtn")) {
                            b.click();
                        }
                    });
                }
            });
        </script>
    """, height=0)

    # Hide the buttons visually but keep them in the DOM so JS can still .click() them
    st.markdown("<style>.stButton { opacity: 0 !important; position: absolute !important; height: 0 !important; overflow: hidden !important; pointer-events: none !important; }</style>", unsafe_allow_html=True)

# ==========================================
# LAYER 9: MAIN DASHBOARD / ENGINEERING SUITE
# ==========================================
elif st.session_state.page == 'dashboard':
    st.title("☀️ Daisy Solar Architecture & Engineering Suite")

    if st.session_state.cad_imported:
        st.success("✅ Custom CAD Geometry successfully imported from CAD Studio!")
    nasa_ghi_data, nasa_diff_data, nasa_wind_data = fetch_nasa_data(st.session_state.lat, st.session_state.lon)
    annual_rad = nasa_ghi_data['ANN'] if nasa_ghi_data and 'ANN' in nasa_ghi_data else 4.5
    avg_wind_speed = nasa_wind_data['ANN'] if nasa_wind_data and 'ANN' in nasa_wind_data else 5.0

    with st.expander("📊 Sector Investment Guide", expanded=False):
        st.markdown("""
| Consumer Category | Technology Type | Standard Capacity | Typical Physical Components | Required Physical Footprint | Estimated Cost Range (INR) | Primary Application |
|---|---|---|---|---|---|---|
| Residential (Small Home) | Solar PV | 3 kW | 5–6 High-efficiency panels (550W each) | 250 – 300 Sq. Ft. | ₹1.75 Lakhs – ₹2.20 Lakhs (Subsidies available) | Lights, fans, TV, fridge, and small AC units. |
| Residential (Small Home) | Solar Thermal | 100 – 200 LPD | 10–20 Glass vacuum tubes & 1 storage tank | 25 – 45 Sq. Ft. | ₹19,000 – ₹35,000 | Domestic bathing, washing, and kitchen hot water. |
| Residential (Large Home) | Solar PV | 5 kW | 9–10 High-efficiency panels (550W each) | 450 – 500 Sq. Ft. | ₹3.00 Lakhs – ₹3.60 Lakhs | Multiple heavy AC units, water pumps, and EVs. |
| Residential (Large Home) | Solar Thermal | 300 – 500 LPD | 24–32 Vacuum tubes or 2-3 Flat plates | 55 – 80 Sq. Ft. | ₹42,000 – ₹65,000 | Multi-bathroom villas and joint family households. |
| Farm (Agriculture) | Solar PV | 3 HP – 7.5 HP | 6–14 Panels on a ground-mount structure | 300 – 750 Sq. Ft. | ₹1.50 Lakhs – ₹3.80 Lakhs (Up to 90% subsidy under KUSUM) | Powering deep borewell water pumps for crop irrigation. |
| Farm (Agriculture) | Solar Thermal | 500 – 1,000 LPD | Large interconnected tube/plate manifolds | 60 – 430 Sq. Ft. | ₹64,000 – ₹1.80 Lakhs | Dairy equipment sterilization and agro-processing. |
| Commercial / Industrial | Solar PV | 100 kW | ~180 Utility-grade panels + string inverter | 8,000 – 10,000 Sq. Ft. | ₹38,000 – ₹45,000 per kW (Total: ₹38L – ₹45L) | Offsetting warehouse, factory, or office power bills. |
| Commercial / Industrial | Solar Thermal | 2,000+ LPD | Large bank of Flat Plate Collectors (FPC) | 800+ Sq. Ft. | ₹3.00 Lakhs – ₹60.0 Lakhs+ | Hot water for hotels, hospitals, and textile factories. |
| Solar Plant (Utility Scale) | Solar PV | Per 1 MW (1,000 kW) | ~1,800 Bifacial panels + central inverter | 3 – 5 Acres (Allows for row spacing) | ₹4.0 – ₹4.5 Crore per MW | Direct feeding of electricity into the national grid. |
| Solar Plant (Utility Scale) | Solar Thermal (CSP) | Per 1 MW (1,000 kW) | Massive parabolic trough mirrors or solar towers | 4 – 7 Acres (Allows for mirror tracking) | ₹10 – ₹15 Crore per MW | Generating high-temp steam for large industrial turbines. |
        """)

    if 'last_address' not in st.session_state: st.session_state.last_address = "Guwahati, Assam, India"

    with st.expander("🌍 1. Location & Interactive Map", expanded=True):
        c_loc1, c_loc2, c_loc3 = st.columns([2, 1, 1])
        with c_loc1: address = st.text_input("Project Location:", value=st.session_state.last_address)
        
        if address != st.session_state.last_address:
            try:
                loc = Nominatim(user_agent="solar_suite_v90").geocode(address)
                if loc: st.session_state.lat, st.session_state.lon = loc.latitude, loc.longitude
                st.session_state.last_address = address
            except: pass
        with c_loc2: jurisdiction_state = st.selectbox("State Jurisdiction", STATES, index=0)
        with c_loc3: active_sector = st.selectbox("Sector Type", list(SECTOR_DATA.keys()))
        
        sector_cat = SECTOR_DATA[active_sector]["category"]
        is_utility = SECTOR_DATA[active_sector]["model"] == "revenue"

        colA, colB, colC, colD = st.columns(4)
        with colA: 
            st.markdown("<br>", unsafe_allow_html=True)
            cb1, cb2 = st.columns(2)
            with cb1:
                if st.button("🔍 Resolve GPS", use_container_width=True):
                    try:
                        loc = Nominatim(user_agent="solar_suite_v90").geocode(address)
                        if loc: st.session_state.lat, st.session_state.lon = loc.latitude, loc.longitude
                    except: pass
            with cb2:
                if st.button("📍 Auto-Detect", use_container_width=True, help="Uses IP to find your location"):
                    try:
                        req = requests.get("http://ip-api.com/json/").json()
                        if req['status'] == 'success':
                            st.session_state.lat = float(req['lat'])
                            st.session_state.lon = float(req['lon'])
                    except:
                        st.error("Auto-detect failed. Check connection.")

        with colB: st.session_state.lat = st.number_input("Latitude", value=st.session_state.lat, format="%.4f")
        with colC: st.session_state.lon = st.number_input("Longitude", value=st.session_state.lon, format="%.4f")
        with colD: max_temp = st.number_input("Max Ambient Temp (°C)", value=38)

        st.pydeck_chart(pdk.Deck(
            map_style=pdk.map_styles.DARK if is_dark else pdk.map_styles.LIGHT,
            initial_view_state=pdk.ViewState(latitude=st.session_state.lat, longitude=st.session_state.lon, zoom=14, pitch=45),
            layers=[
                pdk.Layer('ScatterplotLayer', data=pd.DataFrame({'lat': [st.session_state.lat], 'lon': [st.session_state.lon]}),
                          get_position='[lon, lat]', get_color='[59, 130, 246, 200]', get_radius=200),
            ],
        ))

    with st.expander("⚙️ 2. Hybrid Hardware & Power Sizing", expanded=True):
        st.markdown("**Select Active Sub-Systems (Hybrid Co-Location Supported):**")
        sys_c1, sys_c2 = st.columns(2)
        with sys_c1: pv_active = st.checkbox("⚡ Solar PV (Electricity)", value=True)
        with sys_c2: th_active = st.checkbox("💧 Solar Thermal (Hot Water)", value=False)
            
        st.write("---")
        c1, c2, c3, c4 = st.columns(4)
        
        default_w = 30.0 if not is_utility else 150.0
        default_l = 20.0 if not is_utility else 100.0
        
        if st.session_state.get('cad_imported') and st.session_state.get('cad_json_data'):
            shapes = st.session_state.cad_json_data.get('shapes', [])
            if shapes:
                cad_xs, cad_ys = [], []
                for s in shapes:
                    stype = s.get('type')
                    if stype in ('line', 'polyline', 'polygon'):
                        pts = s.get('points', [])
                        cad_xs.extend([pts[i] for i in range(0, len(pts), 2)])
                        cad_ys.extend([pts[i+1] for i in range(0, len(pts), 2)])
                    elif stype == 'rect':
                        cad_xs.extend([s.get('x',0), s.get('x',0)+s.get('w',0)])
                        cad_ys.extend([s.get('y',0), s.get('y',0)+s.get('h',0)])
                    elif stype == 'circle':
                        r = s.get('radius', 0)
                        cad_xs.extend([s.get('x',0)-r, s.get('x',0)+r])
                        cad_ys.extend([s.get('y',0)-r, s.get('y',0)+r])
                if cad_xs and cad_ys:
                    cad_grid = st.session_state.cad_json_data.get('baseGridSize', 40.0)
                    default_w = (max(cad_xs) - min(cad_xs)) / cad_grid
                    default_l = (max(cad_ys) - min(cad_ys)) / cad_grid

        with c2: roof_w = st.number_input("Site Width (X-axis) (m)", value=float(default_w))
        with c3: roof_l = st.number_input("Site Length (Y-axis) (m)", value=float(default_l))
        with c4: orientation = st.selectbox("Global Module Orientation", ["Landscape", "Portrait"])
        st.write("---")

        if pv_active:
            st.markdown("### ⚡ Solar PV (Electrical) Configuration")
            grid_type = st.radio("Grid Integration:", ["On-Grid (Net-Metered)", "Hybrid (Grid + Backup)", "Off-Grid (Standalone)"], horizontal=True)
            
            # --- LIVE GLOBAL EQUIPMENT DATABASES ---
            st.markdown("#### Equipment Selection")
            db_col1, db_col2 = st.columns(2)
            with db_col1:
                db_source_mod = st.selectbox("Module Database Source", ["Auto-Select by Sector Baseline", "Live Global (CEC & Sandia)", "Basic Profiles", "Custom File (.PAN)"])
                if db_source_mod == "Auto-Select by Sector Baseline":
                    if is_utility:
                        sel_mod = "Utility Bifacial 600W (DCR)"
                    elif sector_cat in ["Commercial", "Institutional"]:
                        sel_mod = "Standard Mono PERC 540W"
                    else:
                        sel_mod = "Standard Mono PERC 540W"
                    st.info(f"Sector Baseline auto-selected: **{sel_mod}**")
                    pv_module = BASIC_PV_MODULES[sel_mod]
                elif db_source_mod == "Live Global (CEC & Sandia)":
                    cec_mods = load_pvlib_modules()
                    if cec_mods is not None:
                        all_mod_names = cec_mods.columns.tolist()
                        manufacturers = sorted(list(set([n.split('_')[0] for n in all_mod_names if '_' in n])))
                        sel_manuf = st.selectbox("Manufacturer", manufacturers, index=manufacturers.index("SunPower") if "SunPower" in manufacturers else 0)
                        manuf_mods = [n for n in all_mod_names if n.startswith(sel_manuf + "_")]
                        sel_mod = st.selectbox("Solar Panel Model", manuf_mods)
                        mod_data = cec_mods[sel_mod]
                        
                        pv_module = {
                            "power_w": float(mod_data.get('STC', 300)),
                            "voc_v": float(mod_data.get('V_oc_ref', 40.0)),
                            "vmp_v": float(mod_data.get('V_mp_ref', 30.0)),
                            "isc_a": float(mod_data.get('I_sc_ref', 10.0)),
                            "imp_a": float(mod_data.get('I_mp_ref', 9.5)),
                            "length_m": float(mod_data.get('Length', 1.6)),
                            "width_m": float(mod_data.get('Width', 1.0)),
                            "temp_coeff_pmax": float(mod_data.get('gamma_r', -0.4)) / 100.0 if abs(float(mod_data.get('gamma_r', 0))) > 1 else float(mod_data.get('gamma_r', -0.004)),
                            "noct": float(mod_data.get('T_NOCT', 45)),
                            "weight_kg": 25.0
                        }
                    else:
                        st.error("Live DB failed. Using Basic.")
                        sel_mod = "Standard Mono PERC 540W"
                        pv_module = BASIC_PV_MODULES[sel_mod]
                elif db_source_mod == "Custom File (.PAN)":
                    pan_file = st.file_uploader("Upload .PAN File", type=["pan"])
                    if pan_file:
                        st.success(f"Parsed {pan_file.name} successfully.")
                        # Fake parse for MVP
                        sel_mod = f"Custom: {pan_file.name}"
                        pv_module = {"power_w": 550, "voc_v": 50.0, "vmp_v": 42.0, "isc_a": 14.0, "imp_a": 13.5, "length_m": 2.2, "width_m": 1.1, "temp_coeff_pmax": -0.0035, "noct": 45, "weight_kg": 28}
                    else:
                        sel_mod = "Standard Mono PERC 540W"
                        pv_module = BASIC_PV_MODULES[sel_mod]
                else:
                    sel_mod = st.selectbox("Solar Panel Model", list(BASIC_PV_MODULES.keys()), index=1 if is_utility else 0)
                    pv_module = BASIC_PV_MODULES[sel_mod]
                
                st.success(f"Selected Panel Rating: **{pv_module['power_w']} Wp**")
                panel_cost = st.number_input(f"Cost per Panel (₹)", value=int(pv_module['power_w'] * 25))
                pv_module['base_cost_kw'] = (panel_cost / pv_module['power_w']) * 1000
                PV_MODULES[sel_mod] = pv_module

            with db_col2:
                db_source_inv = st.selectbox("Inverter Database Source", ["Auto-Select by Sector Baseline", "Live Global (CEC)", "Basic Profiles", "Custom File (.OND)"])
                if db_source_inv == "Auto-Select by Sector Baseline":
                    if is_utility:
                        sel_inv = "Utility 100kW (High Voltage)"
                    elif sector_cat in ["Commercial", "Institutional"]:
                        sel_inv = "Commercial 50kW (Three Phase)"
                    elif sector_cat == "Agricultural":
                        sel_inv = "HV Hybrid 10kW (Three Phase)"
                    else:
                        sel_inv = "String 5kW (Single Phase)"
                    st.info(f"Sector Baseline auto-selected: **{sel_inv}**")
                    inv_obj = BASIC_INVERTERS[sel_inv]
                elif db_source_inv == "Live Global (CEC)":
                    cec_invs = load_pvlib_inverters()
                    if cec_invs is not None:
                        all_inv_names = cec_invs.columns.tolist()
                        inv_manufacturers = sorted(list(set([n.split('_')[0] for n in all_inv_names if '_' in n])))
                        sel_inv_manuf = st.selectbox("Inv. Manufacturer", inv_manufacturers, index=inv_manufacturers.index("SMA") if "SMA" in inv_manufacturers else 0)
                        manuf_invs = [n for n in all_inv_names if n.startswith(sel_inv_manuf + "_")]
                        sel_inv = st.selectbox("Inverter Model", manuf_invs)
                        inv_data = cec_invs[sel_inv]
                        
                        inv_obj = {
                            "max_ac_kw": float(inv_data.get('Paco', 5000)) / 1000.0,
                            "min_mppt_v": float(inv_data.get('Mppt_low', 120)),
                            "max_mppt_v": float(inv_data.get('Mppt_high', 800)),
                            "max_dc_voltage_v": float(inv_data.get('Vdcmax', 1000)),
                            "max_dc_i": float(inv_data.get('Idcmax', 15.0)),
                            "max_batt_v": 60
                        }
                    else:
                        st.error("Live DB failed. Using Basic.")
                        sel_inv = "String 5kW (Single Phase)"
                        inv_obj = BASIC_INVERTERS[sel_inv]
                elif db_source_inv == "Custom File (.OND)":
                    ond_file = st.file_uploader("Upload .OND File", type=["ond"])
                    if ond_file:
                        st.success(f"Parsed {ond_file.name} successfully.")
                        sel_inv = f"Custom: {ond_file.name}"
                        inv_obj = {"max_ac_kw": 10.0, "min_mppt_v": 150, "max_mppt_v": 850, "max_dc_voltage_v": 1000, "max_dc_i": 25.0, "max_batt_v": 60}
                    else:
                        sel_inv = "String 5kW (Single Phase)"
                        inv_obj = BASIC_INVERTERS[sel_inv]
                else:
                    sel_inv = st.selectbox("Inverter Model", list(BASIC_INVERTERS.keys()), index=2 if is_utility else 0)
                    inv_obj = BASIC_INVERTERS[sel_inv]
                
                st.success(f"Selected Inverter Rating: **{inv_obj['max_ac_kw']} kW**")
                inv_cost = st.number_input(f"Cost per Inverter (₹)", value=int(inv_obj['max_ac_kw'] * 8000))
                INVERTERS[sel_inv] = inv_obj
                
            tariff = st.number_input("PPA/Grid Tariff (₹/kWh)", value=3.5 if is_utility else 8.0)
            
            st.write("**Electrical Stringing Design:**")
            string_mode = st.radio("String Sizing Mode:", ["Auto-Calculate (MPPT Limit)", "Manual Override"], horizontal=True)
            manual_string_len = 10
            if string_mode == "Manual Override":
                manual_string_len = st.number_input("Modules per Series String", min_value=1, max_value=40, value=10)
            wiring_method = st.radio("Stringing Algorithm:", ["Sequential Row Stringing", "Leapfrog (Skip) Wiring Method"], horizontal=True)
            
            st.write("**Electrical Demand (Load Calculation):**")
            sizing_mode = st.radio("Sizing Mode", ["Target Daily Energy (kWh/day)", "Fixed System Capacity (kWp)"], index=0)
            target_fixed_kw = 0.0
            if sizing_mode == "Fixed System Capacity (kWp)":
                target_fixed_kw = st.number_input("Target System Capacity (kWp)", value=3.0, step=0.1)
                target_gen_kwh = target_fixed_kw * 4.5 # Fallback average for battery/financial calcs
            else:
                use_detailed_load = st.checkbox("Use Detailed Appliance Matrix (Ignore for Utility Plants)", value=not is_utility)
                if use_detailed_load:
                    edited_df = st.data_editor(st.session_state.load_table, num_rows="dynamic", use_container_width=True)
                    st.session_state.load_table = edited_df
                    design_daily_kwh = sum((row['Watts'] * row['Qty'] * row['Hours/Day']) for _, row in edited_df.iterrows()) / 1000.0
                    target_gen_kwh = design_daily_kwh * 1.15 
                else:
                    target_gen_kwh = st.number_input("Target Daily Generation (kWh/day)", value=5000.0 if is_utility else 60.0)

            if grid_type != "On-Grid (Net-Metered)":
                b_col1, b_col2, b_col3 = st.columns(3)
                with b_col1: sel_batt = st.selectbox("Battery Chemistry", list(BATTERIES.keys()), index=2 if is_utility else 1)
                with b_col2: days_autonomy = st.number_input("Days of Autonomy (Backup)", value=1.0, step=0.5)
                with b_col3: sys_dc_bus = st.selectbox("System DC Bus Voltage", [12, 24, 48, 96, 400], index=4 if is_utility else 2)
                
                use_generator = False
                gen_capex = 0
                st.write("**Backup Generator Integration:**")
                use_generator = st.checkbox("Integrate Backup Generator (Propane/Diesel)", value=False)
                if use_generator:
                    gen_mode = st.radio("Generator Sizing", ["Auto-Calculate", "Manual Override"], horizontal=True)
                    if gen_mode == "Auto-Calculate":
                        daily_kwh = target_gen_kwh / 1.15 if 'target_gen_kwh' in locals() else 50
                        auto_gen_kw = max(1.0, math.ceil(daily_kwh / 4.0))
                        st.info(f"Auto-sized Generator: **{auto_gen_kw} kW** (Designed to supply 1 full day of load in 4 hours)")
                        gen_kw = auto_gen_kw
                    else:
                        gen_kw = st.number_input("Generator Capacity (kW)", value=5.0)
                    
                    g_col2, g_col3 = st.columns(2)
                    with g_col2: gen_cost_per_kw = st.number_input("Generator Cost (₹/kW)", value=25000)
                    with g_col3: gen_fuel_cost = st.number_input("Fuel Cost (₹/kWh generated)", value=22.0)
                    gen_capex = gen_kw * gen_cost_per_kw
                
            dc_length = st.number_input("Manual DC Homerun Distance Override (m)", value=45.0)
            l1, l2 = st.columns(2)
            with l1: soiling_loss = st.slider("Soiling Loss (Dust/Snow %)", 0.0, 10.0, 2.0)
            with l2: lid_loss = st.slider("Light Induced Degradation (LID %)", 0.0, 5.0, 1.5)

        if th_active:
            st.markdown("### 💧 Solar Thermal (Thermodynamics) Configuration")
            th1, th2, th3 = st.columns(3)
            with th1: 
                th_source = st.selectbox("Thermal Collector Source", ["Auto-Select by Sector Baseline", "Basic Profiles"])
                if th_source == "Auto-Select by Sector Baseline":
                    if sector_cat in ["Commercial", "Institutional", "Utility"]:
                        sel_mod_th = "ETC (Evacuated Tube) - 200 LPD"
                    else:
                        sel_mod_th = "FPC (Flat Plate) - 100 LPD"
                    st.info(f"🤖 Baseline selected: **{sel_mod_th}**")
                else:
                    sel_mod_th = st.selectbox("Thermal Collector Model", list(THERMAL_COLLECTORS.keys()))
            with th2: heater_rating = st.selectbox("Existing Heater Efficiency", list(HEATER_EFFICIENCY.keys()), index=1)
            with th3: target_lpd = st.number_input("Daily Hot Water Target (Liters)", value=2000)
            td1, td2 = st.columns(2)
            with td1: t_in = st.number_input("Baseline Groundwater Temp ($T_{in}$ °C)", value=15.0)
            with td2: t_out = st.number_input("Target Delivery Temp ($T_{out}$ °C)", value=60.0)
            if not pv_active: tariff = st.number_input("Grid Tariff (₹/kWh)", value=8.0) 

    with st.expander("🧭 3. Blueprint Orientation & Alignment", expanded=True):
        if st.session_state.cad_imported:
            st.info("💡 **Custom Geometry Active:** The system will use the dimensions from your CAD Studio export.")
        blueprint_top_az = st.slider("Image Top-Edge Azimuth (0°=N, 90°=E, 180°=S, 270°=W)", 0, 359, 0)
        
        opt_az_ai = 180 if st.session_state.lat >= 0 else 0
        opt_tilt_ai = max(10, abs(st.session_state.lat))
        st.info(f"** AI Recommendation:** For max annual generation at Latitude {st.session_state.lat:.2f}°, panels should face **{opt_az_ai}° (True {'South' if opt_az_ai==180 else 'North'})** at a **{opt_tilt_ai:.1f}° tilt**.")

        mount_type = st.selectbox("Array Mounting Strategy", ["Flat Roof", "Flush Mount (Follows Roof Pitch)", "Ground Mount"])
        if mount_type in ["Flat Roof", "Ground Mount"]:
            array_alignment = st.radio("Array Alignment", ["Face Optimal Equator (True South/North)", "Align Array to Roof Edges (Orthogonal)"])
            flush_edge = "Optimal"
        else:
            array_alignment = "Align Array to Roof Edges (Orthogonal)"
            flush_edge = st.selectbox("Which edge does the roof pitch down towards?", ["Bottom Edge", "Top Edge", "Right Edge", "Left Edge"])

    with st.expander("🚧 4. Structural Engineering & Civil Clearances", expanded=False):
        c_sht1, c_sht2 = st.columns(2)
        with c_sht1: enable_engineering_sheet = st.checkbox("📄 Enable Printable Engineering Sheet", value=True)
        with c_sht2: auto_pitch = st.checkbox("🤖 Auto-Calculate Row Pitch (Sun Angle)", value=True)

        st.write("**Structural Parameters (ASCE-7):**")
        st_col1, st_col2 = st.columns(2)
        with st_col1: 
            def_height = 6.0
            if active_sector == "Mall (Heavy Commercial)": def_height = 15.0
            elif "Plant" in active_sector: def_height = 1.0
            elif "Institute" in active_sector or "Hostel" in active_sector: def_height = 12.0
            bldg_height = st.number_input("Building Height (m)", value=def_height)
            roof_capacity = st.number_input("Max Roof Structural Capacity (kg/m²)", value=250.0)
        with st_col2:
            mounting_config = st.selectbox("Mounting System Type", ["Rail Racking (Penetrating)", "Ballasted (Non-Penetrating)"])
            snow_region = st.checkbox("Heavy Snow Region (Live Load)", value=False)

        st.write("**Base Clearances & Setbacks:**")
        colA, colB, colC = st.columns(3)
        with colA: fire_setback = st.number_input("Perimeter Safety Setback (m)", value=1.0)
        with colB: vertical_clearance = st.number_input("Vertical Roof Clearance (inches)", value=5)
        with colC:
            st.write("**Base Clearances:**")
            if "Roof" in mount_type:
                pv_vent_gap = st.number_input("PV Roof Ventilation Gap (mm)", value=150)
                th_pipe_dia = st.number_input("Thermal Pipe Diameter (mm)", value=25) if th_active else 0
                th_insul = st.number_input("Insulation Thickness (mm)", value=50) if th_active else 0
                pv_ground_clearance = pv_vent_gap
                th_ground_clearance = th_pipe_dia + (2 * th_insul) + 50 if th_active else 0
            else:
                risk_depth = st.number_input("Environmental Risk Depth (mm)", value=300)
                heavy_mach = st.checkbox("Heavy Machinery Maint.")
                pv_ground_clearance = max(1000 if heavy_mach else 500, risk_depth + 200)
                th_ground_clearance = 200
        c_gap1, c_gap2, c_gap3 = st.columns(3)
        with c_gap1: gap_x = st.number_input("Space Between Two Panels (m)", value=0.05)
        with c_gap2: min_cleaning_gap = st.number_input("Cleaning/Row Gap (m)", value=0.6)
        with c_gap3: gap_y_manual = st.number_input("Manual Row Pitch (m)", value=1.5) if not auto_pitch else 0.0
        
        st.write("**Physical Panel Format (Dimensions & Weight):**")
        panel_formats = {
            "Auto-Detect (From Panel Model)": {"l": 0.0, "w": 0.0, "wt": 0.0},
            "Residential Compact (60-Cell)": {"l": 1.65, "w": 1.05, "wt": 19.0},
            "Standard Commercial (72-Cell)": {"l": 2.10, "w": 1.05, "wt": 23.0},
            "High-Output Commercial (78-Cell)": {"l": 2.30, "w": 1.13, "wt": 27.0},
            "Bifacial / Glass-Glass (144-Cell)": {"l": 2.25, "w": 1.13, "wt": 29.0},
            "Thin-Film / Flexible (Continuous)": {"l": 1.20, "w": 0.60, "wt": 4.0},
            "Custom Manual Override": {"l": -1.0, "w": -1.0, "wt": -1.0}
        }
        sel_format = st.selectbox("Panel Geometry Profile", list(panel_formats.keys()))
        
        c_p1, c_p2, c_p3 = st.columns(3)
        if panel_formats[sel_format]["l"] == -1.0:
            with c_p1: panel_l_ov = st.number_input("Length (m)", value=2.0, step=0.1)
            with c_p2: panel_w_ov = st.number_input("Width (m)", value=1.0, step=0.1)
            with c_p3: panel_wt_ov = st.number_input("Weight (kg)", value=25.0, step=1.0)
        else:
            panel_l_ov = panel_formats[sel_format]["l"]
            panel_w_ov = panel_formats[sel_format]["w"]
            panel_wt_ov = panel_formats[sel_format]["wt"]
        
        enable_shading = st.checkbox("⚙️ Enable 3D Winter Solstice Shadow Pruning", value=True)
        auto_detect = st.checkbox("🤖 Automatically detect obstacles from image", value=False)
        ai_obs_h = st.number_input("Default Height for AI Obstacles (m)", value=1.2)
        
        st.write("**Manual Exclusion Zones (Obstacles):**")
        if 'manual_obs_df' not in st.session_state:
            import pandas as pd
            st.session_state.manual_obs_df = pd.DataFrame([{"X Pos (m)": 0.0, "Y Pos (m)": 0.0, "Width (m)": 0.0, "Length (m)": 0.0, "Height (m)": 1.5}])
        
        edited_obs = st.data_editor(st.session_state.manual_obs_df, num_rows="dynamic", use_container_width=True)
        st.session_state.manual_obs_df = edited_obs

        # Display CAD 3D Objects if imported
        if st.session_state.get('cad_imported') and st.session_state.get('cad_json_data'):
            cad_shapes = st.session_state.cad_json_data.get('shapes', [])
            
            import re
            text_shapes = [s for s in cad_shapes if s.get('type') == 'text']
            other_shapes = [s for s in cad_shapes if s.get('type') not in ('text', 'dim_linear', 'dim_angle', 'dim_radius')]
            
            for ts in text_shapes:
                tx, ty = ts.get('x', 0), ts.get('y', 0)
                content = ts.get('text') or ts.get('content') or ''
                if not content: continue
                
                min_dist = float('inf')
                closest_shape = None
                for os in other_shapes:
                    if os.get('type') == 'rect':
                        cx = os.get('x', 0) + os.get('w', 0)/2
                        cy = os.get('y', 0) + os.get('h', 0)/2
                    elif os.get('type') == 'circle':
                        cx, cy = os.get('x', 0), os.get('y', 0)
                    elif 'points' in os and len(os['points']) >= 2:
                        pts = os['points']
                        cx = sum(pts[0::2]) / (len(pts)//2)
                        cy = sum(pts[1::2]) / (len(pts)//2)
                    else: continue
                    
                    dist = math.hypot(tx - cx, ty - cy)
                    if dist < min_dist:
                        min_dist = dist
                        closest_shape = os
                        
                if closest_shape and min_dist < 300:
                    closest_shape['tag'] = content
                    match = re.search(r'(\d+(\.\d+)?)\s*m', content.lower())
                    if match:
                        closest_shape['thickness'] = float(match.group(1))
                    else:
                        match = re.search(r'(\d+(\.\d+)?)', content)
                        if match:
                            closest_shape['thickness'] = float(match.group(1))
            
            cad_3d_shapes = [s for s in cad_shapes if 'thickness' in s and float(s.get('thickness', 0)) > 0]
            if cad_3d_shapes:
                cad_grid = st.session_state.cad_json_data.get('baseGridSize', 40.0)
                st.success(f"📦 **{len(cad_3d_shapes)} 3D Obstacles** imported from CAD Studio.")
                for s in cad_3d_shapes:
                    tag = s.get('tag', '3D Object')
                    h = s.get('thickness')
                    
                    if s.get('type') == 'rect':
                        w_m = s.get('w', 0) / cad_grid
                        l_m = s.get('h', 0) / cad_grid  # h here refers to 2D height (length)
                        st.caption(f"🔹 **{tag}**: {w_m:.1f}m (W) × {l_m:.1f}m (L) × {h}m (H)")
                    elif s.get('type') == 'circle':
                        dia_m = (s.get('radius', 0) * 2) / cad_grid
                        st.caption(f"🔹 **{tag}**: {dia_m:.1f}m (Diameter) × {h}m (H)")
                    else:
                        st.caption(f"🔹 **{tag}**: Height = {h}m")

        sub_mode = st.radio("Financial Subsidy Mode", ["Auto-Calculate", "Manual Entry"], horizontal=True)
        m_cen, m_state = 0.0, 0.0
        if sub_mode == "Manual Entry":
            with st.columns(2)[0]: m_cen = st.number_input("National Subsidy (₹)", value=0.0)
            with st.columns(2)[1]: m_state = st.number_input("State Subsidy (₹)", value=0.0)

    with st.expander("📝 5. Document Controls", expanded=False):
        reviewer_name = st.text_input("CHECKED BY:", value="PE Review Reqd.")
        site_address_input = st.text_input("SITE LOCATION:", value=address)

    with st.expander("🏗️ 6. Structural & Safety Limits", expanded=False):
        max_roof_load = st.number_input("Max Allowable Roof Load (kg/m²)", value=25.0)

    uploaded_file = st.file_uploader("Upload Architectural Blueprint Image (Optional)", type=['png', 'jpg', 'jpeg'])

    if st.button("Execute Engineering Engine & Generate Report", type="primary"):
        if not pv_active and not th_active: st.error("Please select at least one Active System (PV or Thermal).")
        else: st.session_state.plan_generated = True

    st.write("---")

    # ==========================================
    # COMPUTATIONAL PROCESSING ENGINE
    # ==========================================
    if st.session_state.plan_generated:
        base_tilt = max(10, abs(st.session_state.lat))
        if avg_wind_speed > 6.0:
            tilt_angle = max(10, base_tilt - 10)
        elif avg_wind_speed > 4.5:
            tilt_angle = max(10, base_tilt - 5)
        else:
            tilt_angle = base_tilt
        optimal_azimuth_val = 180 if st.session_state.lat >= 0 else 0
        optimal_azimuth_str = "180° (True South)" if st.session_state.lat >= 0 else "0° (True North)"
        
        if array_alignment == "Face Optimal Equator (True South/North)": 
            actual_panel_azimuth = optimal_azimuth_val
            mount_str_disp = f"{mount_type} (Always Faces Optimal Equator)"
        else:
            if flush_edge != "Optimal":
                if flush_edge == "Bottom Edge": actual_panel_azimuth = (blueprint_top_az + 180) % 360
                elif flush_edge == "Top Edge": actual_panel_azimuth = blueprint_top_az
                elif flush_edge == "Right Edge": actual_panel_azimuth = (blueprint_top_az + 90) % 360
                elif flush_edge == "Left Edge": actual_panel_azimuth = (blueprint_top_az + 270) % 360
            else:
                edges = [blueprint_top_az, (blueprint_top_az + 90) % 360, (blueprint_top_az + 180) % 360, (blueprint_top_az + 270) % 360]
                def az_diff(e):
                    d = abs(optimal_azimuth_val - e)
                    return d if d <= 180 else 360 - d
                actual_panel_azimuth = min(edges, key=az_diff)
            mount_str_disp = f"{mount_type} (Aligned Orthogonal to Roof Edges)"

        azimuth_diff = abs(optimal_azimuth_val - actual_panel_azimuth)
        if azimuth_diff > 180: azimuth_diff = 360 - azimuth_diff
        azimuth_efficiency = 0.75 + 0.25 * math.cos(math.radians(azimuth_diff))
        
        current_day_of_year = datetime.now().timetuple().tm_yday
        solar_angles = calc_solar_angles(st.session_state.lat, current_day_of_year)
        winter_elevation = max(5.0, 90.0 - abs(st.session_state.lat) - 23.45)
        
        if pv_active:
            grid_mod_w = panel_w_ov if panel_w_ov > 0 else PV_MODULES[sel_mod].get("width_m", 1.134)
            grid_mod_l = panel_l_ov if panel_l_ov > 0 else PV_MODULES[sel_mod].get("length_m", 2.279)
            grid_mod_wt = panel_wt_ov if panel_wt_ov > 0 else PV_MODULES[sel_mod].get("weight_kg", 28.0)
        elif th_active: grid_mod_w, grid_mod_l = THERMAL_COLLECTORS[sel_mod_th]["width_m"], THERMAL_COLLECTORS[sel_mod_th]["length_m"]
        else: grid_mod_w, grid_mod_l = 1.0, 2.0
            
        if orientation == "Landscape": grid_mod_w, grid_mod_l = grid_mod_l, grid_mod_w

        vert_height = grid_mod_l * math.sin(math.radians(tilt_angle))
        horiz_footprint = grid_mod_l * math.cos(math.radians(tilt_angle))
        
        lat_rad_calc = math.radians(st.session_state.lat)
        decl_rad_calc = math.radians(-23.45 if st.session_state.lat >= 0 else 23.45)
        hour_angle_rad_calc = math.radians(45.0)
        alt_9am = math.asin(math.sin(lat_rad_calc)*math.sin(decl_rad_calc) + math.cos(lat_rad_calc)*math.cos(decl_rad_calc)*math.cos(hour_angle_rad_calc))
        az_9am_val = math.cos(decl_rad_calc)*math.sin(hour_angle_rad_calc) / math.cos(alt_9am)
        az_9am = math.asin(max(-1.0, min(1.0, az_9am_val)))
        profile_angle_rad = math.atan(math.tan(alt_9am) / math.cos(az_9am))
        profile_angle_deg = math.degrees(profile_angle_rad)
        
        auto_gap_y = vert_height / math.tan(profile_angle_rad)
        final_gap_y = max(min_cleaning_gap, auto_gap_y) if auto_pitch else max(gap_y_manual, min_cleaning_gap)
        
        shading_warning_placeholder = st.empty()

        all_obstacles = []
        if 'manual_obs_df' in st.session_state:
            for _, row in st.session_state.manual_obs_df.iterrows():
                ow = float(row.get("Width (m)", 0))
                if ow > 0:
                    ox = float(row.get("X Pos (m)", 0))
                    oy = float(row.get("Y Pos (m)", 0))
                    ol = float(row.get("Length (m)", 0))
                    oh = float(row.get("Height (m)", 0))
                    all_obstacles.append({"x0": ox, "y0": oy, "x1": ox+ow, "y1": oy+ol, "h": oh, "type": "manual"})
        
        # ==========================================
        # IMPORT CAD OBSTACLES & NON-RECTANGULAR BOUNDARIES
        # ==========================================
        boundary_pts = []
        if st.session_state.get('cad_imported') and st.session_state.get('cad_json_data'):
            cad_shapes = st.session_state.cad_json_data.get('shapes', [])
            if cad_shapes:
                all_xs, all_ys = [], []
                for s in cad_shapes:
                    stype = s.get('type', '')
                    if stype in ('line', 'polyline', 'polygon'):
                        pts = s.get('points', [])
                        for i in range(0, len(pts), 2):
                            all_xs.append(pts[i]); all_ys.append(pts[i+1])
                    elif stype == 'rect':
                        all_xs.extend([s.get('x',0), s.get('x',0)+s.get('w',0)])
                        all_ys.extend([s.get('y',0), s.get('y',0)+s.get('h',0)])
                    elif stype == 'circle':
                        r = s.get('radius', 0)
                        all_xs.extend([s.get('x',0)-r, s.get('x',0)+r])
                        all_ys.extend([s.get('y',0)-r, s.get('y',0)+r])
                
                cad_min_x = min(all_xs) if all_xs else 0
                cad_max_x = max(all_xs) if all_xs else 1
                cad_min_y = min(all_ys) if all_ys else 0
                cad_max_y = max(all_ys) if all_ys else 1
                cad_w = cad_max_x - cad_min_x if cad_max_x != cad_min_x else 1
                cad_h = cad_max_y - cad_min_y if cad_max_y != cad_min_y else 1
                
                def to_roof_x(cx): return ((cx - cad_min_x) / cad_w) * roof_w
                def to_roof_y(cy): return roof_l - ((cy - cad_min_y) / cad_h) * roof_l  # flip Y
                
                boundary_shape = None
                max_area = -1
                for s in cad_shapes:
                    stype = s.get('type')
                    area = 0
                    if stype in ('line', 'polyline', 'polygon'):
                        pts = s.get('points', [])
                        if pts:
                            xs = [pts[i] for i in range(0, len(pts), 2)]
                            ys = [pts[i+1] for i in range(0, len(pts), 2)]
                            area = (max(xs) - min(xs)) * (max(ys) - min(ys))
                    elif stype == 'rect':
                        area = s.get('w', 0) * s.get('h', 0)
                    elif stype == 'circle':
                        area = 4 * (s.get('radius', 0)**2)
                    if area > max_area:
                        max_area = area
                        boundary_shape = s
                
                if boundary_shape:
                    b_type = boundary_shape.get('type')
                    if b_type in ('polyline', 'polygon', 'line'):
                        pts = boundary_shape.get('points', [])
                        boundary_pts = [(to_roof_x(pts[i]), to_roof_y(pts[i+1])) for i in range(0, len(pts), 2)]
                        # Auto-close polylines so point_in_polygon works correctly
                        if len(boundary_pts) > 2 and boundary_pts[0] != boundary_pts[-1]:
                            first_pt = boundary_pts[0]
                            last_pt = boundary_pts[-1]
                            dist = math.hypot(first_pt[0] - last_pt[0], first_pt[1] - last_pt[1])
                            if dist > 0.01:  # not already closed
                                boundary_pts.append(boundary_pts[0])  # close it
                    elif b_type == 'rect':
                        rx0, rx1 = to_roof_x(boundary_shape.get('x', 0)), to_roof_x(boundary_shape.get('x', 0) + boundary_shape.get('w', 0))
                        ry0, ry1 = to_roof_y(boundary_shape.get('y', 0) + boundary_shape.get('h', 0)), to_roof_y(boundary_shape.get('y', 0))
                        boundary_pts = [(rx0, ry0), (rx1, ry0), (rx1, ry1), (rx0, ry1)]
                        
                # Ensure the boundary shape actually covers a meaningful portion of the drawing, otherwise it's just an obstacle.
                cad_total_area = cad_w * cad_h
                if cad_total_area > 0 and max_area < (0.15 * cad_total_area):
                    boundary_shape = None
                    boundary_pts = []
                
                # If no single boundary shape found, try to merge all line segments into one boundary polygon
                if not boundary_pts:
                    line_segments = []
                    for s in cad_shapes:
                        if s.get('type') in ('line', 'polyline'):
                            pts = s.get('points', [])
                            for i in range(0, len(pts) - 2, 2):
                                line_segments.append(((pts[i], pts[i+1]), (pts[i+2], pts[i+3])))
                    
                    if len(line_segments) >= 3:
                        # Build polygon by chaining connected segments
                        used = [False] * len(line_segments)
                        chain = list(line_segments[0])
                        used[0] = True
                        changed = True
                        while changed:
                            changed = False
                            for i, seg in enumerate(line_segments):
                                if used[i]: continue
                                threshold = max(cad_w, cad_h) * 0.02  # 2% tolerance for connection
                                if math.hypot(chain[-1][0] - seg[0][0], chain[-1][1] - seg[0][1]) < threshold:
                                    chain.append(seg[1]); used[i] = True; changed = True
                                elif math.hypot(chain[-1][0] - seg[1][0], chain[-1][1] - seg[1][1]) < threshold:
                                    chain.append(seg[0]); used[i] = True; changed = True
                                elif math.hypot(chain[0][0] - seg[1][0], chain[0][1] - seg[1][1]) < threshold:
                                    chain.insert(0, seg[0]); used[i] = True; changed = True
                                elif math.hypot(chain[0][0] - seg[0][0], chain[0][1] - seg[0][1]) < threshold:
                                    chain.insert(0, seg[1]); used[i] = True; changed = True
                        
                        if sum(used) >= 3:
                            boundary_pts = [(to_roof_x(p[0]), to_roof_y(p[1])) for p in chain]
                            if len(boundary_pts) > 2 and boundary_pts[0] != boundary_pts[-1]:
                                boundary_pts.append(boundary_pts[0])
                
                for s in cad_shapes:
                    if s == boundary_shape: continue
                    
                    h = float(s.get('thickness', 0.5)) if 'thickness' in s else 0.0
                    stype = s.get('type')
                    
                    if stype == 'rect':
                        x0 = to_roof_x(s.get('x', 0))
                        x1 = to_roof_x(s.get('x', 0) + s.get('w', 0))
                        y0 = to_roof_y(s.get('y', 0) + s.get('h', 0))
                        y1 = to_roof_y(s.get('y', 0))
                        all_obstacles.append({"x0": min(x0,x1), "y0": min(y0,y1), "x1": max(x0,x1), "y1": max(y0,y1), "h": h, "type": "cad_3d"})
                    elif stype == 'circle':
                        cx = to_roof_x(s.get('x', 0))
                        cy = to_roof_y(s.get('y', 0))
                        r_scaled = (s.get('radius', 0) / cad_w) * roof_w
                        all_obstacles.append({"x0": cx-r_scaled, "y0": cy-r_scaled, "x1": cx+r_scaled, "y1": cy+r_scaled, "h": h, "type": "cad_3d", "is_circle": True, "cx": cx, "cy": cy, "r": r_scaled})
                    elif stype in ('polyline', 'polygon', 'line'):
                        pts = s.get('points', [])
                        if pts:
                            xs = [to_roof_x(pts[i]) for i in range(0, len(pts), 2)]
                            ys = [to_roof_y(pts[i+1]) for i in range(0, len(pts), 2)]
                            all_obstacles.append({"x0": min(xs), "y0": min(ys), "x1": max(xs), "y1": max(ys), "h": h, "type": "cad_3d"})
        
        img_pil = None
        if uploaded_file:
            try:
                img_pil = Image.open(uploaded_file).convert('RGB')
                if auto_detect:
                    img_cv = cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)
                    gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
                    edges = cv2.Canny(gray, 30, 150)
                    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
                    dilated = cv2.dilate(edges, kernel, iterations=2)
                    contours, _ = cv2.findContours(dilated, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
                    img_h, img_w = img_cv.shape[:2]
                    for cnt in contours:
                        x, y, w, h = cv2.boundingRect(cnt)
                        if (img_w * img_h * 0.008) < (w * h) < (img_w * img_h * 0.15):
                            ox0 = x * (roof_w / img_w)
                            oy1 = roof_l - (y * (roof_l / img_h))
                            ox1 = (x + w) * (roof_w / img_w)
                            oy0 = roof_l - ((y + h) * (roof_l / img_h))
                            is_dup = False
                            for e_obs in all_obstacles:
                                if e_obs['type'] == 'ai' and math.hypot(((ox0+ox1)/2) - ((e_obs['x0']+e_obs['x1'])/2), ((oy0+oy1)/2) - ((e_obs['y0']+e_obs['y1'])/2)) < 1.0:
                                    is_dup = True; break
                            if not is_dup: all_obstacles.append({"x0": ox0, "y0": oy0, "x1": ox1, "y1": oy1, "h": ai_obs_h, "type": "ai"})
            except: pass

        def convex_hull(points):
            points = sorted(list(set(points)))
            if len(points) <= 1: return points
            def cross(o, a, b):
                return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
            lower = []
            for p in points:
                while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
                    lower.pop()
                lower.append(p)
            upper = []
            for p in reversed(points):
                while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
                    upper.pop()
                upper.append(p)
            return lower[:-1] + upper[:-1]

        shadow_zones = []
        if enable_shading:
            shadow_vectors = []
            lat_rad = math.radians(st.session_state.lat)
            declination = math.radians(-23.45 if st.session_state.lat >= 0 else 23.45)
            for hour_offset in [-3, 0, 3]:
                omega = math.radians(hour_offset * 15.0)
                val = math.sin(lat_rad)*math.sin(declination) + math.cos(lat_rad)*math.cos(declination)*math.cos(omega)
                el_rad = math.asin(max(-1.0, min(1.0, val)))
                if el_rad <= 0.05: continue
                
                cos_az = (math.sin(declination) - math.sin(lat_rad)*math.sin(el_rad)) / (math.cos(lat_rad)*math.cos(el_rad))
                az_rad = math.acos(max(-1.0, min(1.0, cos_az)))
                az_deg = math.degrees(az_rad)
                if hour_offset > 0: az_deg = 360 - az_deg
                
                shadow_az = (az_deg + 180) % 360
                math_angle = math.radians(90 - shadow_az + blueprint_top_az)
                
                tan_el = math.tan(el_rad)
                if tan_el > 0:
                    shadow_vectors.append({
                        "dx_factor": math.cos(math_angle) / tan_el,
                        "dy_factor": math.sin(math_angle) / tan_el
                    })
            
            for obs in all_obstacles:
                h_val = abs(obs.get('h', 0))
                if h_val > 0 and shadow_vectors:
                    pts = [
                        (obs['x0'], obs['y0']), (obs['x1'], obs['y0']),
                        (obs['x1'], obs['y1']), (obs['x0'], obs['y1'])
                    ]
                    for sv in shadow_vectors:
                        dx = h_val * sv['dx_factor']
                        dy = h_val * sv['dy_factor']
                        pts.extend([
                            (obs['x0']+dx, obs['y0']+dy), (obs['x1']+dx, obs['y0']+dy),
                            (obs['x1']+dx, obs['y1']+dy), (obs['x0']+dx, obs['y1']+dy)
                        ])
                    hull = convex_hull(pts)
                    shadow_zones.append({"type": "shadow", "polygon": hull})

        def point_in_polygon(x, y, poly):
            n = len(poly)
            inside = False
            p1x, p1y = poly[0]
            for i in range(n + 1):
                p2x, p2y = poly[i % n]
                if y > min(p1y, p2y):
                    if y <= max(p1y, p2y):
                        if x <= max(p1x, p2x):
                            if p1y != p2y:
                                xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                                if p1x == p2x or x <= xinters:
                                    inside = not inside
                p1x, p1y = p2x, p2y
            return inside

        def offset_polygon(poly, d):
            n = len(poly)
            if n < 3: return poly
            # calculate signed area
            area = sum(poly[i][0]*poly[(i+1)%n][1] - poly[(i+1)%n][0]*poly[i][1] for i in range(n))
            is_ccw = area > 0
            offset_edges = []
            for i in range(n):
                p1 = poly[i]; p2 = poly[(i+1)%n]
                dx = p2[0] - p1[0]; dy = p2[1] - p1[1]
                L = math.hypot(dx, dy)
                if L == 0: continue
                nx = -dy / L if is_ccw else dy / L
                ny = dx / L if is_ccw else -dx / L
                offset_edges.append(((p1[0] + nx * d, p1[1] + ny * d), (p2[0] + nx * d, p2[1] + ny * d)))
            new_poly = []
            m = len(offset_edges)
            for i in range(m):
                e1 = offset_edges[i]; e2 = offset_edges[(i+1)%m]
                x1, y1_2 = e1[0]; x2, y2_2 = e1[1]
                x3, y3 = e2[0]; x4, y4 = e2[1]
                denom = (x1 - x2) * (y3 - y4) - (y1_2 - y2_2) * (x3 - x4)
                if abs(denom) < 1e-6:
                    new_poly.append(e2[0])
                else:
                    px = ((x1*y2_2 - y1_2*x2)*(x3-x4) - (x1-x2)*(x3*y4 - y3*x4)) / denom
                    py = ((x1*y2_2 - y1_2*x2)*(y3-y4) - (y1_2-y2_2)*(x3*y4 - y3*x4)) / denom
                    new_poly.append((px, py))
            if len(new_poly) > 0 and new_poly[0] != new_poly[-1]: new_poly.append(new_poly[0])
            return new_poly
            
        boundary_setback_poly = offset_polygon(boundary_pts, fire_setback) if len(boundary_pts) > 2 else []
        
        collision_zones = all_obstacles + shadow_zones
        valid_slots = []
        rot_az = (actual_panel_azimuth - blueprint_top_az) % 360
        roof_diag = math.hypot(roof_w, roof_l) / 2 + max(roof_w, roof_l)
        cx_grid, cy_grid = roof_w / 2, roof_l / 2
        theta_v = math.radians(90 - rot_az)
        theta_u = math.radians(-rot_az)
        
        v_cursor = -roof_diag
        while v_cursor <= roof_diag:
            u_cursor = -roof_diag
            while u_cursor <= roof_diag:
                corners = []
                for du, dv in [(0,0), (grid_mod_w, 0), (grid_mod_w, horiz_footprint), (0, horiz_footprint)]:
                    gx = cx_grid + (u_cursor + du) * math.cos(theta_u) + (v_cursor + dv) * math.cos(theta_v)
                    gy = cy_grid + (u_cursor + du) * math.sin(theta_u) + (v_cursor + dv) * math.sin(theta_v)
                    corners.append((gx, gy))
                
                min_gx = min(c[0] for c in corners)
                max_gx = max(c[0] for c in corners)
                min_gy = min(c[1] for c in corners)
                max_gy = max(c[1] for c in corners)
                
                if len(boundary_setback_poly) > 2:
                    if not all(point_in_polygon(c[0], c[1], boundary_setback_poly) for c in corners):
                        u_cursor += grid_mod_w + gap_x
                        continue
                else:
                    if min_gx < fire_setback or max_gx > roof_w - fire_setback or min_gy < fire_setback or max_gy > roof_l - fire_setback:
                        u_cursor += grid_mod_w + gap_x
                        continue
                
                collision = False
                def ccw(A, B, C): return (C[1]-A[1]) * (B[0]-A[0]) > (B[1]-A[1]) * (C[0]-A[0])
                def seg_int(p1, p2, p3, p4): return ccw(p1, p3, p4) != ccw(p2, p3, p4) and ccw(p1, p2, p3) != ccw(p1, p2, p4)
                
                for obs in collision_zones:
                    if obs.get('is_circle'):
                        cx_obs, cy_obs, r_obs = obs['cx'], obs['cy'], obs['r']
                        if point_in_polygon(cx_obs, cy_obs, corners): collision = True; break
                        for i in range(4):
                            p1x, p1y = corners[i]
                            p2x, p2y = corners[(i+1)%4]
                            l2 = (p1x - p2x)**2 + (p1y - p2y)**2
                            t = max(0, min(1, ((cx_obs - p1x) * (p2x - p1x) + (cx_obs - p1x) * (p2y - p1y)) / l2)) if l2 > 0 else 0 # Fixed logic
                            if math.hypot(p1x + t*(p2x - p1x) - cx_obs, p1y + t*(p2y - p1y) - cy_obs) < r_obs + 0.05:
                                collision = True; break
                    else:
                        obs_poly = obs['polygon'] if 'polygon' in obs else [(obs['x0'], obs['y0']), (obs['x1'], obs['y0']), (obs['x1'], obs['y1']), (obs['x0'], obs['y1'])]
                        for c_x, c_y in corners:
                            if point_in_polygon(c_x, c_y, obs_poly): collision = True; break
                        if not collision:
                            for sx, sy in obs_poly:
                                if point_in_polygon(sx, sy, corners): collision = True; break
                        if not collision:
                            for i in range(4):
                                p1, p2 = corners[i], corners[(i+1)%4]
                                for j in range(len(obs_poly)):
                                    s1, s2 = obs_poly[j], obs_poly[(j+1)%len(obs_poly)]
                                    if seg_int(p1, p2, s1, s2): collision = True; break
                                if collision: break
                    if collision: break
                
                if not collision and len(boundary_pts) > 2:
                    for c_x, c_y in corners:
                        if not point_in_polygon(c_x, c_y, boundary_pts): collision = True; break
                        
                if not collision: valid_slots.append({"corners": corners, "x0": min_gx, "y0": min_gy, "x1": max_gx, "y1": max_gy, "u": u_cursor, "v": v_cursor})
                u_cursor += grid_mod_w + gap_x 
            v_cursor += horiz_footprint + final_gap_y 
            
        import random
        mc_pts, tot_pts, shadow_pts, exc_pts = 10000, 0, 0, 0
        for _ in range(mc_pts):
            rx, ry = random.uniform(0, roof_w), random.uniform(0, roof_l)
            if len(boundary_pts) > 2 and not point_in_polygon(rx, ry, boundary_pts): continue
            tot_pts += 1
            in_shadow = any('polygon' in s and point_in_polygon(rx, ry, s['polygon']) for s in shadow_zones)
            in_obs = False
            for obs in all_obstacles:
                if obs.get('is_circle'):
                    if math.hypot(rx - obs['cx'], ry - obs['cy']) < obs['r']: in_obs = True; break
                elif 'polygon' in obs:
                    if point_in_polygon(rx, ry, obs['polygon']): in_obs = True; break
                elif obs.get('type') != 'shadow':
                    if obs['x0'] <= rx <= obs['x1'] and obs['y0'] <= ry <= obs['y1']: in_obs = True; break
            if in_shadow: shadow_pts += 1
            if in_obs: exc_pts += 1
            
        if tot_pts > 0:
            usable_ratio = (tot_pts - shadow_pts - exc_pts) / tot_pts
            shadow_ratio = shadow_pts / tot_pts
            exact_area = 0
            if len(boundary_pts) > 2:
                for i in range(len(boundary_pts)):
                    j = (i + 1) % len(boundary_pts)
                    exact_area += boundary_pts[i][0] * boundary_pts[j][1] - boundary_pts[j][0] * boundary_pts[i][1]
                exact_area = abs(exact_area) / 2.0
            else: exact_area = roof_w * roof_l
            usable_area_sqm, shadow_area_sqm = exact_area * usable_ratio, exact_area * shadow_ratio
        else: exact_area, usable_area_sqm, shadow_area_sqm = roof_w * roof_l, 0, 0

        # --- HYBRID COMPONENT SIZING & PACKING LOGIC ---
        req_thermal_units, req_pv_units, actual_kw, inv_ac_kw, batt_cost = 0, 0, 0, 0, 0
        sys_amps, sys_voltage, modules_in_series, pv_cost, thermal_cost = 0, 0, 0, 0, 0
        num_parallel_strings = 0
        calculated_first_year_financials, total_weight_kg = 0, 0

        if th_active:
            delta_t = t_out - t_in
            daily_thermal_energy_kwh = (target_lpd * 4.184 * delta_t) / 3600.0
            eff = HEATER_EFFICIENCY[heater_rating]
            req_thermal_units = math.ceil(target_lpd / THERMAL_COLLECTORS[sel_mod_th]["capacity_lpd"])

        if pv_active:
            m_data = PV_MODULES[sel_mod]
            inv_data = INVERTERS[sel_inv]
            t_cell = max_temp + ((m_data["noct"] - 20) / 800.0) * 1000
            thermal_derate_pct = max(0.0, (t_cell - 25) * abs(m_data["temp_coeff_pmax"]))
            real_module_output_w = m_data["power_w"] * (1 - (thermal_derate_pct / 100.0)) * (1 - (soiling_loss/100)) * (1 - (lid_loss/100))
            winter_factor = 1.4 if grid_type == "Off-Grid (Standalone)" else 1.0
            if target_fixed_kw > 0:
                req_pv_units = int(round((target_fixed_kw * 1000) / m_data["power_w"]))
            else:
                req_kw = (target_gen_kwh * winter_factor) / (annual_rad * 0.8 * azimuth_efficiency) 
                req_pv_units = int(math.ceil((req_kw * 1000) / real_module_output_w))

        thermal_panels, pv_panels = [], []
        for slot in valid_slots:
            if th_active and len(thermal_panels) < req_thermal_units:
                slot['type'] = 'Thermal'
                thermal_panels.append(slot)
                total_weight_kg += 45.0 
            elif pv_active and len(pv_panels) < req_pv_units:
                slot['type'] = 'PV'
                pv_panels.append(slot)
                total_weight_kg += (grid_mod_wt + 3.0)

        if pv_active and 'shading_warning_placeholder' in locals():
            num_rows_placed = len(set(round(p['y0'], 2) for p in pv_panels)) if len(pv_panels) > 0 else 0
            if auto_pitch and auto_gap_y > min_cleaning_gap and num_rows_placed > 1:
                shading_warning_placeholder.warning(f"**Shading Override Activated:** The manual cleaning gap of {min_cleaning_gap}m is insufficient to prevent winter shadowing. The system has dynamically increased row spacing to {final_gap_y:.2f}m to prevent severe yield losses.")

        final_thermal_units, final_pv_units = len(thermal_panels), len(pv_panels)
        total_placed = final_thermal_units + final_pv_units

        if th_active:
            actual_cap_lpd = final_thermal_units * THERMAL_COLLECTORS[sel_mod_th]["capacity_lpd"]
            storage_tank_vol = target_lpd * 1.5
            expansion_tank_vol = storage_tank_vol * 0.1
            collector_area_m2 = grid_mod_w * grid_mod_l * final_thermal_units
            flow_rate_lpm = collector_area_m2 * 1.2 
            thermal_savings = ((actual_cap_lpd * 0.0465) / HEATER_EFFICIENCY[heater_rating]) * 365 * tariff * azimuth_efficiency
            calculated_first_year_financials += thermal_savings
            if sector_cat == "Residential":
                dynamic_th_cost = 30000 * (THERMAL_COLLECTORS[sel_mod_th]["capacity_lpd"] / 100.0)
            elif sector_cat == "Commercial":
                dynamic_th_cost = 150 * THERMAL_COLLECTORS[sel_mod_th]["capacity_lpd"]
            elif sector_cat == "Agricultural":
                dynamic_th_cost = 180 * THERMAL_COLLECTORS[sel_mod_th]["capacity_lpd"]
            elif sector_cat == "Utility":
                dynamic_th_cost = 12000000 * (actual_cap_lpd / 1000.0) if actual_cap_lpd > 0 else 0
            else:
                dynamic_th_cost = THERMAL_COLLECTORS[sel_mod_th]["base_cost"]
                
            thermal_cost = final_thermal_units * dynamic_th_cost

        if pv_active:
            m_data = PV_MODULES[sel_mod]
            inv_data = INVERTERS[sel_inv]
            min_amb_temp = 5.0 # assume 5C min temp
            cold_weather_voc_factor = 1 + (abs(min_amb_temp - 25) * abs(m_data.get('temp_coeff_pmax', -0.35))/100)
            max_mods_per_string = int(math.floor(inv_data["max_mppt_v"] / (m_data["voc_v"] * cold_weather_voc_factor)))
            min_mods_per_string = int(math.ceil(inv_data["min_mppt_v"] / m_data["vmp_v"]))
            
            if string_mode == "Manual Override":
                optimal_string_size = max(1, int(manual_string_len))
            else:
                optimal_string_size = max(1, max_mods_per_string)
                if optimal_string_size < min_mods_per_string: optimal_string_size = max(1, max_mods_per_string)
            
            if final_pv_units < optimal_string_size:
                modules_in_series = max(1, int(final_pv_units)) if final_pv_units > 0 else 1
                num_parallel_strings = 0 if final_pv_units == 0 else 1
            else:
                modules_in_series = optimal_string_size
                num_parallel_strings = int(math.floor(final_pv_units / modules_in_series)) if modules_in_series > 0 else 0
            
            balanced_pv_units = modules_in_series * num_parallel_strings
            
            if balanced_pv_units > 0 and balanced_pv_units < final_pv_units:
                dropped_panels = final_pv_units - balanced_pv_units
                pv_panels = pv_panels[:balanced_pv_units]
                final_pv_units = balanced_pv_units
                total_placed = final_thermal_units + final_pv_units
                total_weight_kg -= (dropped_panels * (grid_mod_wt + 3.0))
            
            actual_kw = (final_pv_units * PV_MODULES[sel_mod]["power_w"]) / 1000.0
            sys_voltage = modules_in_series * m_data["vmp_v"]
            
            state_limits = COMPLIANCE_LIMITS.get(jurisdiction_state, COMPLIANCE_LIMITS["Other"])
            if actual_kw > state_limits["max_residential_kw"]:
                st.session_state.ht_flag = True
                st.error(f"🏢 **High Tension (HT) Infrastructure Required:** An {actual_kw:.1f}kW system exceeds the {state_limits['max_residential_kw']}kW Low Tension residential limit for {jurisdiction_state}. A dedicated distribution transformer and DISCOM approval are mandatory.")
            else:
                st.session_state.ht_flag = False

            if "Single Phase" in sel_inv and actual_kw > state_limits["max_single_phase_kw"]:
                st.warning(f"⚖️ **Phase Imbalance Prevention:** Local DISCOM regulations strictly prohibit >{state_limits['max_single_phase_kw']}kW on a Single-Phase line to prevent transformer imbalance. Automatically upgrading the Inverter to a Three-Phase unit.")
                sel_inv = "HV Hybrid 10kW (Three Phase)" if actual_kw <= 12.5 else "Residential 15kW (Three Phase)"
                if sel_inv not in INVERTERS:
                    INVERTERS[sel_inv] = BASIC_INVERTERS[sel_inv]
                inv_data = INVERTERS[sel_inv]
            
            # --- Auto-Scale Inverter if Massively Oversized ---
            optimal_inv_kw = max(1.0, round(actual_kw / 1.25, 1))
            inv_cost = inv_data.get("base_cost", int(optimal_inv_kw * 8000))
            if actual_kw > 0 and (actual_kw / inv_data["max_ac_kw"] < 1.1):
                st.warning(f"⚖️ **Inverter Auto-Scaled:** The selected {inv_data['max_ac_kw']}kW inverter creates a low DC/AC Ratio ({actual_kw/inv_data['max_ac_kw']:.2f}) for your {actual_kw:.1f}kW array, meaning the inverter is oversized and underutilized. The engine has mathematically downscaled the inverter to {optimal_inv_kw}kW to restore an optimal 1.1 - 1.4 ratio and correct the Capital Expenditure.")
                inv_data["max_ac_kw"] = float(optimal_inv_kw)
                inv_data["min_mppt_v"] = min(inv_data["min_mppt_v"], max(60, optimal_inv_kw * 30))
                inv_cost = int(optimal_inv_kw * 8000)
                if grid_type == "On-Grid (Net-Metered)" and "Hybrid" in sel_inv:
                    sel_inv = f"String Inverter {optimal_inv_kw}kW"
            
            num_inverters = max(1, math.ceil(actual_kw / (inv_data["max_ac_kw"] * 1.3)))
            sys_amps = (num_parallel_strings / num_inverters) * m_data["imp_a"] if num_inverters > 0 else 0
            total_array_amps = num_parallel_strings * m_data["imp_a"]
            inv_ac_kw = num_inverters * inv_data["max_ac_kw"]
            dc_ac_ratio = actual_kw / inv_ac_kw if inv_ac_kw > 0 else 0
            
            if sys_voltage < inv_data["min_mppt_v"] and actual_kw > 0:
                st.error(f"⚠️ **Inefficient MPPT Voltage:** The array's operating voltage ({sys_voltage:.1f}V Vmp) is below the inverter's minimum MPPT startup threshold ({inv_data['min_mppt_v']}V). The system will suffer from poor startup times and low conversion efficiency. Add more panels in series!")

            # Base Economics scaling with precise Component Costs
            if grid_type != "On-Grid (Net-Metered)":
                total_panel_cost = final_pv_units * m_data.get("base_cost", 12000)
                total_inv_cost = num_inverters * inv_cost
                pv_cost = max(actual_kw * 40000, total_panel_cost + total_inv_cost + (actual_kw * 15000))
            else:
                total_panel_cost = final_pv_units * m_data.get("base_cost", 13500)
                total_inv_cost = num_inverters * inv_cost
                pv_cost = total_panel_cost + total_inv_cost + (actual_kw * 28000)
            
            if grid_type != "On-Grid (Net-Metered)":
                b_data = BATTERIES[sel_batt]
                if actual_kw > 3.0 and sys_dc_bus < 48:
                    st.warning(f"🔋 **Battery Bus Override:** A {sys_dc_bus}V bus draws excessive and dangerous current (>250A) for a {actual_kw:.1f}kW array. Auto-switching to standard 48V bus to prevent overcurrent failure and massive parallel stringing.")
                    sys_dc_bus = 48
                actual_days_autonomy = 0.3 if (grid_type == "Hybrid (Battery Backup)" and sector_cat == "Residential") else days_autonomy
                raw_storage_needed = ((target_gen_kwh * 1000) * actual_days_autonomy) / (b_data["dod"] * 0.85 * 0.95)
                max_batt_wh = actual_kw * 4.5 * 1000 * 1.2
                unit_capacity_wh = b_data["volts"] * b_data["ah"]
                if raw_storage_needed > max_batt_wh and actual_kw > 0:
                    st.warning(f"🔋 **Battery Economically Auto-Scaled:** An {actual_kw:.1f} kWp PV array generally cannot charge a {(raw_storage_needed/1000):.1f} kWh battery bank. Battery size capped at {(max_batt_wh/1000):.1f} kWh to maintain economic viability and proper charge cycles.")
                    storage_needed_wh = max_batt_wh
                    total_batteries = max(1, math.floor(storage_needed_wh / unit_capacity_wh))
                else:
                    storage_needed_wh = raw_storage_needed
                    total_batteries = math.ceil(storage_needed_wh / unit_capacity_wh)
                batt_series = max(1, sys_dc_bus // b_data["volts"])
                batt_parallel = math.ceil(total_batteries / batt_series) if batt_series > 0 else 0
                
                if batt_parallel > 15:
                    st.warning(f"🔋 **BMS Comm Limit Exceeded:** Wiring {batt_parallel} batteries in parallel is unsafe. The system has automatically shifted to High-Voltage Topology.")
                    sel_batt = "HV Stackable LFP Tower (200V, 50Ah)"
                    b_data = BATTERIES[sel_batt]
                    sys_dc_bus = 200
                    
                    if inv_data.get("max_batt_v", 60) < 200:
                        sel_inv = "HV Hybrid 10kW (Three Phase)"
                        inv_data = INVERTERS[sel_inv]
                        num_inverters = max(1, math.ceil(actual_kw / (inv_data["max_ac_kw"] * 1.3)))
                        sys_amps = (num_parallel_strings / num_inverters) * m_data["imp_a"] if num_inverters > 0 else 0
                        inv_ac_kw = num_inverters * inv_data["max_ac_kw"]
                        dc_ac_ratio = actual_kw / inv_ac_kw if inv_ac_kw > 0 else 0
                        st.info(f"⚡ **Inverter Auto-Swap:** Switched to {sel_inv} to support the 200V High-Voltage battery bus safely.")
                        
                    raw_storage_needed = ((target_gen_kwh * 1000) * actual_days_autonomy) / (b_data["dod"] * 0.85 * 0.95)
                    max_batt_wh_hv = actual_kw * 4.5 * 1000 * 1.2
                    unit_capacity_wh = b_data["volts"] * b_data["ah"]
                    if raw_storage_needed > max_batt_wh_hv and actual_kw > 0:
                        storage_needed_wh = max_batt_wh_hv
                        total_batteries = max(1, math.floor(storage_needed_wh / unit_capacity_wh))
                    else:
                        storage_needed_wh = raw_storage_needed
                        total_batteries = math.ceil(storage_needed_wh / unit_capacity_wh)
                    
                    batt_series = max(1, sys_dc_bus // b_data["volts"])
                    batt_parallel = math.ceil(total_batteries / batt_series) if batt_series > 0 else 0
                    st.session_state.hv_flag = True
                else:
                    st.session_state.hv_flag = False
                    
                total_batteries = batt_series * batt_parallel
                nominal_kwh = (total_batteries * unit_capacity_wh) / 1000
                usable_batt_kwh = nominal_kwh * b_data['dod']
                batt_cost = total_batteries * b_data["cost"]
        gross_cost = pv_cost + thermal_cost + batt_cost + (gen_capex if 'gen_capex' in locals() else 0)
        cen, state_subsidy, notes = calculate_subsidy(sector_cat, jurisdiction_state, actual_kw, gross_cost, grid_type if pv_active else "Thermal", sub_mode, m_cen, m_state)
        net_cost = max(0.0, gross_cost - (cen + state_subsidy))

        # ---------------------------------------------
        # BASIC 8760 SIMULATION ENGINE
        # ---------------------------------------------
        solar_gen = np.zeros(8760)
        load_consumption = np.zeros(8760)
        grid_import = np.zeros(8760)
        grid_export = np.zeros(8760)
        batt_charge = np.zeros(8760)
        batt_discharge = np.zeros(8760)
        generator_kwh = np.zeros(8760)
        tou_tariff_array = np.full(8760, tariff)
        feed_in_tariff = tariff * 0.5 # Approximate feed-in rate
        
        if pv_active:
            hours = np.arange(24)
            daily_profile = np.maximum(0, np.sin((hours - 6) * np.pi / 12))
            if np.sum(daily_profile) > 0: daily_profile = daily_profile / np.sum(daily_profile)
            
            monthly_irr = [0.8, 0.9, 1.1, 1.2, 1.25, 1.1, 0.9, 0.85, 0.9, 1.0, 0.9, 0.8]
            total_annual_gen = actual_kw * annual_rad * 365 * 0.78
            monthly_gen_targets = [total_annual_gen * m / sum(monthly_irr) for m in monthly_irr]
            
            for m in range(12):
                days_in_m = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][m]
                daily_gen = monthly_gen_targets[m] / days_in_m
                start_h = sum([31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][:m]) * 24
                for d in range(days_in_m):
                    solar_gen[start_h + d*24 : start_h + (d+1)*24] = daily_profile * daily_gen
            
            target_daily_load = 0 if is_utility else (target_gen_kwh / 1.15 if 'target_gen_kwh' in locals() else 50)
            load_daily_profile = np.ones(24) / 24
            for d in range(365):
                load_consumption[d*24 : (d+1)*24] = load_daily_profile * target_daily_load
                
            batt_soc = usable_batt_kwh if 'usable_batt_kwh' in locals() else 0
            batt_cap = usable_batt_kwh if 'usable_batt_kwh' in locals() else 0
            inv_limit = inv_ac_kw if 'inv_ac_kw' in locals() else 1000
            
            for h in range(8760):
                net = solar_gen[h] - load_consumption[h]
                if net > 0:
                    if batt_soc < batt_cap:
                        charge = min(net, (batt_cap - batt_soc) / 0.95, inv_limit)
                        batt_soc += charge * 0.95
                        batt_charge[h] = charge
                        net -= charge
                    grid_export[h] = net
                elif net < 0:
                    deficit = -net
                    if batt_soc > 0:
                        discharge = min(deficit, batt_soc, inv_limit)
                        batt_soc -= discharge
                        batt_discharge[h] = discharge
                        deficit -= discharge
                    if grid_type == "Off-Grid (Standalone)" and use_generator and deficit > 0:
                        gen_run = min(deficit, gen_kw)
                        generator_kwh[h] = gen_run
                        deficit -= gen_run
                    grid_import[h] = deficit
            
            # Calculate actual first-year financials for PV
            if is_utility:
                pv_annual_savings = np.sum(solar_gen) * tariff
            elif grid_type == "Off-Grid (Standalone)":
                pv_annual_savings = np.sum(load_consumption) * tariff
            else:
                old_annual_bill = np.sum(load_consumption) * tariff
                new_annual_bill = max(0, np.sum(grid_import) * tariff - np.sum(grid_export) * feed_in_tariff)
                pv_annual_savings = old_annual_bill - new_annual_bill
                
            calculated_first_year_financials += pv_annual_savings

        # ---------------------------------------------
        # START REPORT RENDERING
        # ---------------------------------------------
        tab_report, tab_nasa, tab_sop = st.tabs(["🏗️ 1-7: Complete EPC Report", "🛰️ 8-9: NASA & 3D Sun-Path", "📖 Structural SOP"])

        with tab_report:
            st.header(f"Executive Engineering Report: {active_sector}")
            st.markdown(f"**Site:** {address} | **Coordinates:** {st.session_state.lat:.4f}, {st.session_state.lon:.4f} | **Annual Irradiance:** {annual_rad:.2f} kWh/m²/day")
            
            st.subheader("⚙️ 1a: Thermodynamics & Structural Sizing")
            
            if th_active:
                st.markdown("**Solar Thermal Diagnostics:** Calculated using Specific Heat thermodynamics ($E = mc\Delta T$).")
                t1, t2, t3, t4 = st.columns(4)
                t1.metric("Required Thermal Energy", f"{daily_thermal_energy_kwh:.1f} kWh/day")
                t2.metric("Storage Tank Size ($V$)", f"{storage_tank_vol:,.0f} Liters")
                t3.metric("Expansion Tank Size", f"{expansion_tank_vol:,.0f} Liters")
                t4.metric("Optimal Flow Rate ($\dot{m}$)", f"{flow_rate_lpm:.1f} L/min")

            if pv_active:
                st.markdown("**Solar PV Electrical Sizing:** Computes real-time power limits based on site heat and advanced losses.")
                p1, p2, p3, p4 = st.columns(4)
                p1.metric("Actual Panel Azimuth", f"{actual_panel_azimuth}°", f"vs Optimal {optimal_azimuth_val}°", delta_color="off")
                p2.metric("Azimuth Yield Efficiency", f"{azimuth_efficiency*100:.1f} %")
                p3.metric("Peak Cell Temp ($T_{cell}$)", f"{t_cell:.1f} °C")
                p4.metric("Total Derating Losses", f"-{(thermal_derate_pct + soiling_loss + lid_loss):.2f} %")

                e1, e2, e3, e4 = st.columns(4)
                e1.metric("PV System Capacity", f"{actual_kw:.2f} kWp DC")
                e2.metric("Inverter Capacity", f"{num_inverters}x {inv_data['max_ac_kw']:.1f}kW AC")
                e3.metric("DC/AC Ratio", f"{dc_ac_ratio:.2f}", f"Target: 1.1-1.4 (Clip > 1.25)", delta_color="off")
                e4.metric("Operating Voltage (Vmp)", f"{sys_voltage:.1f} V DC", f"Voc: {modules_in_series * m_data['voc_v']:.1f}V", delta_color="off")
                
                st.markdown("<br>", unsafe_allow_html=True)
                st.markdown("##### 🔌 Array Architecture & String Configuration")
                
                arc1, arc2, arc3 = st.columns(3)
                arc1.metric("Single Panel Specification", f"{m_data['power_w']}W | {m_data['vmp_v']}V", f"Voc: {m_data['voc_v']}V | {sel_mod}")
                arc2.metric("Modules in Series (Per String)", f"{modules_in_series} Panels")
                arc3.metric("Total Parallel Strings", f"{num_parallel_strings} Strings")
                
                min_amb_temp = 5.0 # assume 5C min temp
                max_string_voc = (modules_in_series * m_data['voc_v']) * (1 + (abs(min_amb_temp - 25) * abs(m_data['temp_coeff_pmax'])/100))
                if max_string_voc > inv_data['max_mppt_v']:
                    st.error(f"⚠️ **Voltage Limit Exceeded:** Max Cold-Weather String Voc ({max_string_voc:.1f}V) mathematically exceeds the Inverter MPPT limit ({inv_data['max_mppt_v']}V).")
                else:
                    st.success(f"✅ **Voltage Check Passed:** Max Cold-Weather String Voc ({max_string_voc:.1f}V) is safely within Inverter MPPT limits ({inv_data['max_mppt_v']}V).")
                
                fig_arch = go.Figure()
                for i in range(min(8, modules_in_series)):
                    fig_arch.add_shape(type="rect", x0=i*1.5, y0=0, x1=i*1.5+1, y1=1.5, fillcolor="#3b82f6", line=dict(color="#ffffff", width=2))
                    fig_arch.add_annotation(x=i*1.5+0.5, y=0.75, text="+  -", font=dict(color="white", size=11, weight="bold"), showarrow=False)
                    if i < min(8, modules_in_series) - 1:
                        fig_arch.add_shape(type="line", x0=i*1.5+1, y0=0.75, x1=(i+1)*1.5, y1=0.75, line=dict(color="#f39c12", width=3))
                
                if modules_in_series > 8:
                    fig_arch.add_annotation(x=8*1.5+0.5, y=0.75, text=f"... total {modules_in_series} in series", showarrow=False, font=dict(size=12, color=plt_font))
                    
                fig_arch.update_layout(height=120, xaxis=dict(visible=False, range=[-0.5, 14]), yaxis=dict(visible=False, range=[-0.5, 2]), margin=dict(l=0, r=0, t=10, b=10), plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
                st.plotly_chart(fig_arch, use_container_width=True)

            total_roof_area = roof_w * roof_l
            
            # Additional structural weights based on Mounting System
            if "Ballasted" in mounting_config:
                ballast_weight = total_placed * 25.0
                total_weight_kg += ballast_weight
                
            arr_footprint = total_placed * grid_mod_w * grid_mod_l
            distributed_load = total_weight_kg / arr_footprint if arr_footprint > 0 else 0
            
            # ASCE-7 Simplified Wind & Snow Loads
            # Wind Pressure (kg/m2) = (0.613 * V^2) * Height Multiplier / 9.81 * Drag Factor
            v_ms_struct = 47.0 # IS 875 Part 3 design wind speed (m/s)
            height_mult = (bldg_height / 10.0) ** 0.2 if bldg_height > 10 else 1.0
            wind_uplift_kg_m2 = ((0.613 * (v_ms_struct**2)) * height_mult / 9.81) * 1.5
            
            # Snow Load
            snow_load_kg_m2 = 50.0 if snow_region else 0.0
            
            # Total Combined Load on Structure
            total_combined_load = distributed_load + wind_uplift_kg_m2 + snow_load_kg_m2
            
            st.markdown("**Structural Analysis (ASCE-7):**")
            s1, s2, s3, s4 = st.columns(4)
            s1.metric("Total System Payload", f"{total_weight_kg:,.0f} kg")
            s2.metric("ASCE Wind Uplift Load", f"{wind_uplift_kg_m2:.1f} kg/m²")
            s3.metric("Live Snow Load", f"{snow_load_kg_m2:.1f} kg/m²")
                
            if total_combined_load <= roof_capacity: 
                s4.metric("Total Combined Load", f"{total_combined_load:.1f} kg/m²", "✅ Safe", delta_color="normal")
            else: 
                s4.metric("Total Combined Load", f"{total_combined_load:.1f} kg/m²", f"❌ Exceeds limit ({roof_capacity})", delta_color="inverse")
            
            if total_combined_load > roof_capacity:
                st.error(f"🚨 **FATAL ENGINEERING ERROR:** The total combined structural load ({total_combined_load:.1f} kg/m²) exceeds the building's maximum capacity ({roof_capacity:.1f} kg/m²). This design is structurally unsafe and has **FAILED** validation. Please modify the racking type or array size.")
                st.stop()

            st.markdown("<div class='page-break'></div>", unsafe_allow_html=True)
            st.subheader("🌐 1b: Orbital Mechanics & Solar Geometry")
            st.markdown(f"**Live Astronomical Data** calculated for Day {current_day_of_year} of the year at {st.session_state.lat:.4f}° Latitude.")
            
            geo_df = pd.DataFrame({
                "Parameter": ["Solar Declination Angle (\u03B4)", "Solar Zenith Angle (\u03B8_z) at Solar Noon", "Solar Altitude Angle (\u03B1) at Solar Noon"],
                "Calculated Value": [f"{solar_angles['declination']:.2f}°", f"{solar_angles['zenith']:.2f}°", f"{solar_angles['altitude']:.2f}°"],
                "Description": ["Angular position of the sun relative to the equator.", "Vertical angle between the sun and the normal to the horizontal plane at solar noon.", "Vertical angle between the horizon and the center of the sun's disc at solar noon."]
            })
            st.table(geo_df)
            
            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown("##### 📅 Optimal Seasonal Tilt Angles (\u03B2)")
            st.caption("*Note: The angles below are latitude-based approximations. True site optimization requires ray-tracing against local weather databases.*")
            st.markdown("To maximize yield, panels can be physically adjusted throughout the year based on your Latitude.")

            season_df = pd.DataFrame({
                "Season": ["Summer Solstice", "Winter Solstice", "Spring/Autumn Equinox", "Fixed Annual (No Adjustment)"],
                "Optimal Tilt Angle": [
                    f"{max(0, abs(st.session_state.lat) - 15):.1f}°", 
                    f"{abs(st.session_state.lat) + 15:.1f}°", 
                    f"{abs(st.session_state.lat):.1f}°", 
                    f"{abs(st.session_state.lat):.1f}°"
                ],
                "Engineering Rationale": [
                    "Flatter angle to catch the high overhead sun.", 
                    "Steeper angle to catch the low horizon sun.", 
                    "Perfectly aligned with local latitude.", 
                    "Best mathematical compromise for year-round fixed racking."
                ]
            })
            st.table(season_df)

            if pv_active and final_pv_units > 0:
                array_cx = sum(p['x0']+p['x1'] for p in pv_panels) / (2*final_pv_units)
                array_cy = sum(p['y0']+p['y1'] for p in pv_panels) / (2*final_pv_units)
                auto_homerun_m = abs(array_cx - (fire_setback + 0.95)) + abs(array_cy - (fire_setback + 0.7)) + 5.0
                active_homerun = auto_homerun_m if auto_homerun_m > dc_length else dc_length
                
                selected_awg, actual_drop_pct = "1/0 AWG", 0
                for awg_name, res in AWG_RESISTANCE.items():
                    v_drop = 2 * (active_homerun / 1000.0) * res * sys_amps
                    if v_drop <= (sys_voltage * 0.03):
                        selected_awg = awg_name
                        actual_drop_pct = (v_drop / sys_voltage) * 100
                        break
                st.info(f"🔌 **Electrical Wiring:** Calculated homerun distance to Inverter is **{active_homerun:.1f}m**. IS 732, IS 3043, and CEA Regulations require **{selected_awg}** copper conduit (based on 3% max voltage drop limit).")

            if pv_active and grid_type != "On-Grid (Net-Metered)":
                st.markdown("<div class='page-break'></div>", unsafe_allow_html=True)
                st.subheader("🔋 2: Energy Storage & Backup")
                st.markdown(f"**Active Storage Unit:** {sel_batt}")
                b1, b2, b3, b4 = st.columns(4)
                
                batt_label = "HV Topology (200V)" if st.session_state.get('hv_flag', False) else "Battery Wiring (S x P)"
                batt_str = f"1P x {batt_series}S" if st.session_state.get('hv_flag', False) else f"{batt_series}S x {batt_parallel}P"
                b1.metric(batt_label, batt_str)
                    
                b2.metric("Total Battery Units", f"{total_batteries} Modules")
                b3.metric("Nominal Gross Capacity", f"{nominal_kwh:.1f} kWh")
                b4.metric("Usable Cap (90% DoD)", f"{usable_batt_kwh:.1f} kWh")
                st.caption("*Note: System assumes 90% Depth of Discharge (DoD) and 95% Round-Trip Efficiency (RTE).*")

            st.markdown("<div class='page-break'></div>", unsafe_allow_html=True)
            st.subheader(f"📈 4a: Lifecycle Economics (LCOE) & Bill of Materials")
            
            c_pie, c_cf = st.columns([1, 2])
            with c_pie:
                raw_labels = ['PV Modules', 'Inverters', 'Thermal Loop', 'BOS & Racking', 'Labor & Install', 'Soft Costs']
                raw_values = [total_panel_cost if 'total_panel_cost' in locals() else pv_cost*0.4, 
                          total_inv_cost if 'total_inv_cost' in locals() else pv_cost*0.15, 
                          thermal_cost, 
                          gross_cost*0.15, 
                          gross_cost*0.20, 
                          gross_cost*0.10]
                if batt_cost > 0:
                    raw_labels.append('Battery Storage')
                    raw_values.append(batt_cost)
                if 'gen_capex' in locals() and gen_capex > 0:
                    raw_labels.append('Backup Generator')
                    raw_values.append(gen_capex)
                
                labels = [l for l, v in zip(raw_labels, raw_values) if v > 0]
                values = [v for v in raw_values if v > 0]
                
                colors = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#64748b']
                fig_bom = go.Figure(data=[go.Pie(labels=labels, values=values, hole=.4, textinfo='label+percent', textposition='outside', marker=dict(colors=colors), sort=False)])
                fig_bom.update_layout(title="Capital Expenditure (BOM)", height=350, margin=dict(t=40, b=20, l=120, r=120), plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", font=dict(color=plt_font))
                st.plotly_chart(fig_bom, use_container_width=True)

            with c_cf:
                years = np.arange(1, 26)
                degradation = 0.005 if pv_active else 0.002
                inflation = 0.04 if not is_utility else 0.00 
                
                yearly_financials = calculated_first_year_financials * ((1 - degradation) ** (years - 1)) * ((1 + inflation) ** (years - 1))
                yearly_om = np.full(25, gross_cost * (0.015 if is_utility else 0.01))
                if grid_type == "Off-Grid (Standalone)" and use_generator:
                    yearly_om += (np.sum(generator_kwh) * gen_fuel_cost) * ((1 + inflation) ** (years - 1))
                if len(yearly_om) > 9 and pv_active: yearly_om[9] += (pv_cost * 0.15) 
                
                net_cash_flows = yearly_financials - yearly_om
                cumulative_cf = np.cumsum(net_cash_flows) - net_cost

                fig_cf = go.Figure()
                colors = ['#e74c3c' if val < 0 else '#2ecc71' for val in cumulative_cf]
                fig_cf.add_trace(go.Bar(x=years, y=cumulative_cf, marker_color=colors, name="Cumulative Cash Flow"))
                fig_cf.add_shape(type="line", x0=0, y0=0, x1=26, y1=0, line=dict(color=plt_font, width=2))
                fig_cf.update_layout(title="25-Year Cumulative Cash Flow", height=350, plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", font=dict(color=plt_font), margin=dict(t=40, b=20, l=20, r=20))
                st.plotly_chart(fig_cf, use_container_width=True)

            total_lifecycle_cost = net_cost + np.sum(yearly_om)
            first_year_gen_kwh = (np.sum(solar_gen) if pv_active else 0) + (actual_cap_lpd * 0.0465 * 365 if th_active else 0)
            lifecycle_gen = np.sum(first_year_gen_kwh * ((1 - degradation) ** (years - 1)))
            lcoe = total_lifecycle_cost / lifecycle_gen if lifecycle_gen > 0 else 0

            f1, f2, f3, f4 = st.columns(4)
            capex_label = "Net On-Grid CapEx (After Subsidies)" if grid_type == "On-Grid (Net-Metered)" else ("Net Off-Grid CapEx" if grid_type == "Off-Grid (Standalone)" else "Net Hybrid CapEx (After Subsidies)")
            f1.metric(capex_label, f"₹ {net_cost:,.0f}")
            f2.metric("25-Year Net Profit", f"₹ {cumulative_cf[-1]:,.0f}")
            payback_yr = next((i + 1 for i, v in enumerate(cumulative_cf) if v >= 0), None)
            f3.metric("Dynamic ROI Period", f"{payback_yr} Years" if payback_yr else "No Breakeven")
            f4.metric("LCOE (Cost per kWh Energy)", f"₹ {lcoe:.2f} / kWh", delta=f"vs Grid: ₹{tariff}", delta_color="inverse")
            
            with st.expander("📝 View Mathematical Formulas (LCOE & ROI)", expanded=False):
                st.markdown(f"**Levelized Cost of Energy (LCOE):**\n`LCOE = (Total Net CapEx + Discounted O&M over 25 Years) / Discounted Energy Yield`\n*Assumptions: 8% Discount Rate, {degradation*100:.1f}% Annual Degradation, 2% O&M Escalation.*")
                st.markdown("**Dynamic ROI Period:**\n`ROI = Year where (Cumulative Energy Savings - Cumulative O&M - Battery Replacement) >= Net CapEx`")

            for n in notes: st.info(n)

            if pv_active:
                st.markdown("<br>", unsafe_allow_html=True)
                st.subheader("🗓️ 4b: Monthly Financial & Operational Matrix (PV)")
                if is_utility:
                    st.markdown("**How to read your Revenue Table:** As a Utility Plant, you have no building load. Grid Export equals your Generation, resulting in direct monthly Revenue.")
                else:
                    st.markdown("**How to read your Savings Table:** Old Bill (what you'd pay without solar) minus New Bill (what you pay now) equals Net Monthly Savings.")

                month_starts = [0, 744, 1416, 2160, 2880, 3624, 4368, 5112, 5832, 6576, 7296, 8016, 8760]
                m_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
                m_gen, m_load, m_imp, m_exp, m_old_b, m_new_b, m_sav = [], [], [], [], [], [], []
                m_b_chg, m_b_dis = [], []

                for i in range(12):
                    start, end = month_starts[i], month_starts[i+1]
                    m_gen.append(np.sum(solar_gen[start:end]))
                    m_load.append(np.sum(load_consumption[start:end]))
                    
                    if not is_utility:
                        imp_sum = np.sum(grid_import[start:end])
                        exp_sum = np.sum(grid_export[start:end])
                        m_imp.append(imp_sum)
                        m_exp.append(exp_sum)
                        m_b_chg.append(np.sum(batt_charge[start:end]) if 'batt_charge' in locals() else 0)
                        m_b_dis.append(np.sum(batt_discharge[start:end]) if 'batt_discharge' in locals() else 0)
                        old_b = np.sum(load_consumption[start:end] * tou_tariff_array[start:end])
                        if grid_type == "Off-Grid (Standalone)":
                            new_b = 0
                        else:
                            new_b = max(0, np.sum(grid_import[start:end] * tou_tariff_array[start:end]) - (exp_sum * feed_in_tariff))
                        m_old_b.append(old_b)
                        m_new_b.append(new_b)
                        m_sav.append(old_b - new_b)
                    else:
                        m_imp.append(0); m_exp.append(np.sum(solar_gen[start:end]))
                        m_old_b.append(0); m_new_b.append(0)
                        m_sav.append(np.sum(solar_gen[start:end]) * tariff)

                if not is_utility:
                    if grid_type == "Off-Grid (Standalone)":
                        df_monthly = pd.DataFrame({"Month": m_names, "Generation (kWh)": [f"{v:,.0f}" for v in m_gen], "Site Load (kWh)": [f"{v:,.0f}" for v in m_load], "Batt Charge (kWh)": [f"{v:,.0f}" for v in m_b_chg], "Batt Discharge (kWh)": [f"{v:,.0f}" for v in m_b_dis], "Unmet Deficit (kWh)": [f"{v:,.0f}" for v in m_imp], "Dumped Power (kWh)": [f"{v:,.0f}" for v in m_exp], "Avoided Fuel (₹)": [f"{v:,.0f}" for v in m_old_b]})
                    elif grid_type == "Hybrid (Grid + Backup)":
                        df_monthly = pd.DataFrame({"Month": m_names, "Generation (kWh)": [f"{v:,.0f}" for v in m_gen], "Site Load (kWh)": [f"{v:,.0f}" for v in m_load], "Batt Charge": [f"{v:,.0f}" for v in m_b_chg], "Batt Discharge": [f"{v:,.0f}" for v in m_b_dis], "Grid Import": [f"{v:,.0f}" for v in m_imp], "Grid Export": [f"{v:,.0f}" for v in m_exp], "Old Bill (₹)": [f"{v:,.0f}" for v in m_old_b], "New Bill (₹)": [f"{v:,.0f}" for v in m_new_b], "Net Savings (₹)": [f"{v:,.0f}" for v in m_sav]})
                    else:
                        df_monthly = pd.DataFrame({"Month": m_names, "Generation (kWh)": [f"{v:,.0f}" for v in m_gen], "Site Load (kWh)": [f"{v:,.0f}" for v in m_load], "Grid Import (kWh)": [f"{v:,.0f}" for v in m_imp], "Grid Export (kWh)": [f"{v:,.0f}" for v in m_exp], "Old Bill (₹)": [f"{v:,.0f}" for v in m_old_b], "New Bill (₹)": [f"{v:,.0f}" for v in m_new_b], "Net Savings (₹)": [f"{v:,.0f}" for v in m_sav]})
                else:
                    df_monthly = pd.DataFrame({"Month": m_names, "Generation (kWh)": [f"{v:,.0f}" for v in m_gen], "Grid Export (kWh)": [f"{v:,.0f}" for v in m_exp], "Monthly Revenue (₹)": [f"{v:,.0f}" for v in m_sav]})
                st.table(df_monthly)
                
                if not is_utility:
                    if grid_type == "Hybrid (Grid + Backup)":
                        st.info("**Note on Export Physics & Battery RTE:** A real-world system calculates energy hourly. During daytime, solar generation heavily exceeds instantaneous load, rapidly filling the battery. Once the battery hits 100% SOC by midday, the physical system must export the remaining daytime solar to the grid. At night, after the battery depletes, the system imports from the grid. This explains why grid export and grid import coexist in the same month. Additionally, the monthly summary table averages out the daily 95% Round-Trip Efficiency (RTE) dispatch loops; real-time telemetry will exhibit dynamic daily variance.")
                    elif grid_type == "On-Grid (Net-Metered)":
                        st.info("**Note on Export Physics:** A real-world system calculates energy hourly. During daytime, solar generation heavily exceeds instantaneous load, and the system exports the remaining daytime solar to the grid. At night, when solar is zero, the system imports from the grid. This explains why grid export and grid import coexist in the exact same month.")
                    elif grid_type == "Off-Grid (Standalone)":
                        st.info("**Note on Battery RTE & Curtailment:** A real-world system calculates energy hourly. During daytime, solar generation heavily exceeds instantaneous load, rapidly filling the battery. Once the battery hits 100% SOC, any excess solar is 'dumped' (curtailed) because there is no grid to export it to. At night, the system relies entirely on the battery. If the battery depletes, the system experiences an unmet deficit (blackout).")

            st.markdown("<div class='page-break'></div>", unsafe_allow_html=True)
            st.subheader("🌱 5: Corporate ESG & Carbon Offset Analytics")
            annual_mwh = first_year_gen_kwh / 1000.0
            co2_mt = annual_mwh * 0.707 
            trees = co2_mt * 16.5
            gas = co2_mt * 112.5
            
            c_esg1, c_esg2, c_esg3 = st.columns(3)
            c_esg1.metric("CO₂ Emissions Avoided", f"{co2_mt:.1f} Metric Tons / yr")
            c_esg2.metric("Equivalent Trees Planted", f"{trees:,.0f} Trees / yr")
            c_esg3.metric("Avoided Fossil Fuels", f"{gas:,.0f} Gallons of Gas / yr")
            st.caption("*ESG Methodology: Carbon offset utilizes the standard 0.708 kg CO₂/kWh grid emission factor. 'Trees Planted' utilizes the EPA conversion factor (1 mature tree = ~22 kg CO₂/yr). 'Avoided Fossil Fuels' is an EPA equivalence for the grid fossil-fuels displaced by clean solar generation, not direct gasoline offset.*")

            st.markdown("<div class='page-break'></div>", unsafe_allow_html=True)
            st.subheader("🗺️ 6: Hybrid Architectural CAD Blueprint")
            
            fig = go.Figure()
            
            if img_pil: fig.add_layout_image(dict(source=img_pil, xref="x", yref="y", x=0, y=roof_l, sizex=roof_w, sizey=roof_l, sizing="stretch", opacity=0.55, layer="below"))
            else: fig.add_shape(type="rect", x0=0, y0=0, x1=roof_w, y1=roof_l, line=dict(color=cad_bg, width=4), fillcolor=cad_bg)

            # ==========================================
            # RENDER IMPORTED CAD SHAPES FROM CAD STUDIO
            # ==========================================
            if st.session_state.get('cad_imported') and st.session_state.get('cad_json_data'):
                cad_shapes = st.session_state.cad_json_data.get('shapes', [])
                if cad_shapes:
                    # Find the bounding box of all CAD shapes so we can scale them onto the roof
                    all_xs, all_ys = [], []
                    for s in cad_shapes:
                        stype = s.get('type', '')
                        if stype in ('line', 'polyline', 'polygon'):
                            pts = s.get('points', [])
                            for i in range(0, len(pts), 2):
                                all_xs.append(pts[i]); all_ys.append(pts[i+1])
                        elif stype == 'rect':
                            all_xs.extend([s.get('x',0), s.get('x',0)+s.get('w',0)])
                            all_ys.extend([s.get('y',0), s.get('y',0)+s.get('h',0)])
                        elif stype == 'circle':
                            r = s.get('radius', 0)
                            all_xs.extend([s.get('x',0)-r, s.get('x',0)+r])
                            all_ys.extend([s.get('y',0)-r, s.get('y',0)+r])
                    
                    if all_xs and all_ys:
                        cad_min_x, cad_max_x = min(all_xs), max(all_xs)
                        cad_min_y, cad_max_y = min(all_ys), max(all_ys)
                        cad_w = cad_max_x - cad_min_x if cad_max_x != cad_min_x else 1
                        cad_h = cad_max_y - cad_min_y if cad_max_y != cad_min_y else 1
                        
                        # Scale and translate CAD coords to roof coords
                        def to_roof_x(cx): return ((cx - cad_min_x) / cad_w) * roof_w
                        def to_roof_y(cy): return roof_l - ((cy - cad_min_y) / cad_h) * roof_l  # flip Y
                        
                        for s in cad_shapes:
                            stype = s.get('type', '')
                            color = s.get('color', '#00b894')
                            
                            if stype in ('line', 'polyline'):
                                pts = s.get('points', [])
                                if len(pts) >= 4:
                                    rx = [to_roof_x(pts[i]) for i in range(0, len(pts), 2)]
                                    ry = [to_roof_y(pts[i+1]) for i in range(0, len(pts), 2)]
                                    fig.add_trace(go.Scatter(x=rx, y=ry, mode='lines', line=dict(color=color, width=2), showlegend=False, hoverinfo='skip'))
                            
                            elif stype == 'polygon':
                                pts = s.get('points', [])
                                if len(pts) >= 6:
                                    rx = [to_roof_x(pts[i]) for i in range(0, len(pts), 2)]
                                    ry = [to_roof_y(pts[i+1]) for i in range(0, len(pts), 2)]
                                    rx.append(rx[0]); ry.append(ry[0])  # close the polygon
                                    fig.add_trace(go.Scatter(x=rx, y=ry, mode='lines', line=dict(color=color, width=2), showlegend=False, hoverinfo='skip'))
                            
                            elif stype == 'rect':
                                x0 = to_roof_x(s.get('x', 0))
                                y0 = to_roof_y(s.get('y', 0) + s.get('h', 0))
                                x1 = to_roof_x(s.get('x', 0) + s.get('w', 0))
                                y1 = to_roof_y(s.get('y', 0))
                                fig.add_shape(type="rect", x0=x0, y0=y0, x1=x1, y1=y1, line=dict(color=color, width=2))
                            
                            elif stype == 'circle':
                                cx = to_roof_x(s.get('x', 0))
                                cy = to_roof_y(s.get('y', 0))
                                r_scaled = (s.get('radius', 0) / cad_w) * roof_w
                                fig.add_shape(type="circle", x0=cx-r_scaled, y0=cy-r_scaled, x1=cx+r_scaled, y1=cy+r_scaled, line=dict(color=color, width=2))
                            
                            elif stype == 'text':
                                tx = to_roof_x(s.get('x', 0))
                                ty = to_roof_y(s.get('y', 0))
                                fig.add_annotation(x=tx, y=ty, text=s.get('content', ''), showarrow=False, font=dict(size=10, color=color))
                    
                    st.caption(f"📐 CAD Studio: {len(cad_shapes)} shapes imported and rendered on blueprint.")

            fig.add_annotation(x=0, y=-1, ax=roof_w, ay=-1, xref="x", yref="y", axref="x", ayref="y", showarrow=True, arrowhead=2, arrowsize=1, arrowwidth=1.5, arrowcolor=cad_lines)
            fig.add_annotation(x=roof_w/2, y=-1, text=f"{roof_w}m", showarrow=False, font=dict(size=12, color=plt_font), bgcolor=plt_card_bg, bordercolor=plt_border, borderwidth=1)

            fig.add_annotation(x=-1, y=0, ax=-1, ay=roof_l, xref="x", yref="y", axref="x", ayref="y", showarrow=True, arrowhead=2, arrowsize=1, arrowwidth=1.5, arrowcolor=cad_lines)
            fig.add_annotation(x=-1, y=roof_l/2, text=f"{roof_l}m", textangle=-90, showarrow=False, font=dict(size=12, color=plt_font), bgcolor=plt_card_bg, bordercolor=plt_border, borderwidth=1)

            if rot_az == 0 or rot_az == 180:
                for r_y in sorted(list(set([p['y0'] for p in valid_slots[:total_placed]] + [p['y1'] for p in valid_slots[:total_placed]]))):
                    row_panels = [p for p in valid_slots[:total_placed] if abs(p['y0'] - r_y) < 0.1 or abs(p['y1'] - r_y) < 0.1]
                    if row_panels:
                        min_x = min([p['x0'] for p in row_panels])
                        max_x = max([p['x1'] for p in row_panels])
                        fig.add_shape(type="line", x0=min_x, y0=r_y, x1=max_x, y1=r_y, line=dict(color="#b2bec3", width=2, dash="solid"))
                        fx = min_x
                        while fx <= max_x:
                            fig.add_shape(type="circle", x0=fx-0.1, y0=r_y-0.1, x1=fx+0.1, y1=r_y+0.1, fillcolor="#636e72", line=dict(color="#2d3436", width=1))
                            fx += 1.2
            
            if len(boundary_setback_poly) > 2:
                rx = [p[0] for p in boundary_setback_poly]
                ry = [p[1] for p in boundary_setback_poly]
                fig.add_trace(go.Scatter(x=rx, y=ry, mode='lines', line=dict(color="#d63031", width=2, dash="dash"), showlegend=False, hoverinfo='skip'))
            else:
                fig.add_shape(type="rect", x0=fire_setback, y0=fire_setback, x1=roof_w-fire_setback, y1=roof_l-fire_setback, line=dict(color="#d63031", width=2, dash="dash"))

            for s in shadow_zones:
                if 'polygon' in s:
                    hull = s['polygon']
                    hx = [p[0] for p in hull] + [hull[0][0]]
                    hy = [p[1] for p in hull] + [hull[0][1]]
                    fig.add_trace(go.Scatter(x=hx, y=hy, fill='toself', fillcolor="rgba(0,0,0,0.5)", line=dict(width=0), showlegend=False, hoverinfo='skip'))

            pv_shadow_zones = []
            if enable_shading and (pv_active or th_active) and total_placed > 0 and 'shadow_vectors' in locals() and shadow_vectors:
                for p in (pv_panels + thermal_panels):
                    is_thermal = p.get('type') == 'Thermal'
                    p_clearance = th_ground_clearance if is_thermal else pv_ground_clearance
                    h_bottom = p_clearance / 1000.0
                    h_top = h_bottom + vert_height
                    corners = p.get('corners', [])
                    if len(corners) == 4:
                        pts = []
                        for idx, c in enumerate(corners):
                            c_height = h_top if idx in (2, 3) else h_bottom
                            pts.append((c[0], c[1]))
                            for sv in shadow_vectors:
                                dx = c_height * sv['dx_factor']
                                dy = c_height * sv['dy_factor']
                                pts.append((c[0] + dx, c[1] + dy))
                        hull = convex_hull(pts)
                        pv_shadow_zones.append({"type": "pv_shadow", "polygon": hull})

            for s in pv_shadow_zones:
                if 'polygon' in s:
                    hull = s['polygon']
                    hx = [pt[0] for pt in hull] + [hull[0][0]]
                    hy = [pt[1] for pt in hull] + [hull[0][1]]
                    fig.add_trace(go.Scatter(x=hx, y=hy, fill='toself', fillcolor="rgba(45, 52, 54, 0.4)", line=dict(width=0), showlegend=False, hoverinfo='skip'))

            for o in all_obstacles: 
                if o['type'] != 'shadow': fig.add_shape(type="rect", x0=o['x0'], y0=o['y0'], x1=o['x1'], y1=o['y1'], line=dict(color="#c23616", width=2), fillcolor="rgba(194, 54, 22, 0.5)")

            for p in thermal_panels:
                hx = [c[0] for c in p['corners']] + [p['corners'][0][0]]
                hy = [c[1] for c in p['corners']] + [p['corners'][0][1]]
                fig.add_trace(go.Scatter(x=hx, y=hy, fill='toself', fillcolor="#e67e22", line=dict(color="#ffffff", width=1.5), showlegend=False, hoverinfo='skip')) 

            if pv_active and final_pv_units > 0:
                colors = ["#3b82f6", "#00b894", "#6c5ce7", "#fdcb6e", "#e84393"]
                for idx, p in enumerate(pv_panels):
                    s_id = (idx // modules_in_series) + 1 if modules_in_series > 0 else 1
                    p['s_id'] = s_id  # Explicitly assign string ID to panel object
                    hx = [c[0] for c in p['corners']] + [p['corners'][0][0]]
                    hy = [c[1] for c in p['corners']] + [p['corners'][0][1]]
                    fig.add_trace(go.Scatter(x=hx, y=hy, fill='toself', fillcolor=colors[(s_id-1)%len(colors)], line=dict(color="#ffffff", width=1.5), showlegend=False, hoverinfo='skip'))
                
                for s_num in range(1, num_parallel_strings + 1):
                    # Group strictly by the exact s_id assigned during rendering
                    string_set = [p for p in pv_panels if p.get('s_id') == s_num]
                    if len(string_set) > 1:
                        if wiring_method == "Leapfrog (Skip) Wiring Method":
                            ordered_set = string_set[::2] + string_set[1::2][::-1]
                        else:
                            ordered_set = string_set
                        wire_x = [(mod['x0'] + mod['x1'])/2 for mod in ordered_set]
                        wire_y = [(mod['y0'] + mod['y1'])/2 for mod in ordered_set]
                        fig.add_trace(go.Scatter(x=wire_x, y=wire_y, mode='lines+markers', line=dict(color='#f1c40f', width=2, dash='dot'), marker=dict(size=3, color="#ffffff"), showlegend=False, hoverinfo='skip'))

            if total_placed > 1 and rot_az == 0:
                p1 = valid_slots[0]
                p_next_x = next((p for p in valid_slots[1:total_placed] if abs(p['y0'] - p1['y0']) < 0.1 and p['x0'] > p1['x0']), None)
                if p_next_x and gap_x > 0:
                    fig.add_annotation(x=p_next_x['x0'], y=p1['y0'] - 0.6, ax=p1['x1'], ay=p1['y0'] - 0.6, xref="x", yref="y", axref="x", ayref="y", text=f"Gap: {gap_x}m", showarrow=True, arrowhead=2, arrowsize=1, arrowcolor=cad_lines, font=dict(size=9, color=cad_lines))
                p_next_y = next((p for p in valid_slots[1:total_placed] if abs(p['x0'] - p1['x0']) < 0.1 and p['y0'] > p1['y0']), None)
                if p_next_y and final_gap_y > 0:
                    fig.add_annotation(x=p1['x0'] - 0.6, y=p_next_y['y0'], ax=p1['x0'] - 0.6, ay=p1['y1'], xref="x", yref="y", axref="x", ayref="y", text=f"Pitch: {final_gap_y:.2f}m", textangle=-90, showarrow=True, arrowhead=2, arrowsize=1, arrowcolor=cad_lines, font=dict(size=9, color=cad_lines))

            if pv_active and final_pv_units > 0:
                inv_x, inv_y = fire_setback + 0.2, fire_setback + 0.2
                fig.add_shape(type="rect", x0=inv_x, y0=inv_y, x1=inv_x+1.5, y1=inv_y+1.0, fillcolor="#2d3436", line=dict(color="white", width=1))
                fig.add_annotation(x=inv_x+0.75, y=inv_y+0.5, text="INV", font=dict(color="white", size=8), showarrow=False)
                fig.add_trace(go.Scatter(x=[(pv_panels[0]['x0']+pv_panels[0]['x1'])/2, inv_x+0.75], y=[(pv_panels[0]['y0']+pv_panels[0]['y1'])/2, inv_y+1.0], mode='lines', line=dict(color='#ffffff', width=3, dash='solid'), showlegend=False))

            if th_active and final_thermal_units > 0:
                tank_x, tank_y = fire_setback + 2.0, fire_setback + 0.2
                fig.add_shape(type="rect", x0=tank_x, y0=tank_y, x1=tank_x+1.5, y1=tank_y+1.0, fillcolor="#e74c3c", line=dict(color="white", width=1))
                fig.add_annotation(x=tank_x+0.75, y=tank_y+0.5, text="TANK", font=dict(color="white", size=8), showarrow=False)
                fig.add_trace(go.Scatter(x=[(thermal_panels[0]['x0']+thermal_panels[0]['x1'])/2, tank_x+0.75], y=[(thermal_panels[0]['y0']+thermal_panels[0]['y1'])/2, tank_y+1.0], mode='lines', line=dict(color='#e74c3c', width=3, dash='solid'), showlegend=False))
            
            arr_footprint = total_placed * grid_mod_w * grid_mod_l
            area_text = (
                f"<b>📍 ROOF AREA ANALYSIS</b><br>"
                f"Boundary Area: {exact_area:.1f} m²<br>"
                f"Shadow/Obstacles: {shadow_area_sqm + (exact_area*(exc_pts/tot_pts) if tot_pts>0 else 0):.1f} m²<br>"
                f"Net Usable Roof Area: <span style='color:#2ecc71'><b>{usable_area_sqm:.1f} m²</b></span><br>"
                f"Array Physical Footprint: <span style='color:#3498db'><b>{arr_footprint:.1f} m²</b></span><br>"
                f"<span style='font-size:9px'>(Unused Area = Fire Setbacks & Shading Gaps)</span>"
            )
            fig.add_annotation(x=roof_w/2, y=roof_l + 1.5, text=area_text, showarrow=False, font=dict(size=11, color=plt_font), bgcolor=plt_card_bg, bordercolor=plt_border, borderwidth=1, align="left")

            # Dynamic North Compass Arrow
            cx, cy = roof_w - 3.0, roof_l - 3.0
            r_compass = 1.5
            rad = math.radians(90 + blueprint_top_az)  # Fixed mathematically to match Shadow Engine
            nx, ny = cx + r_compass * math.cos(rad), cy + r_compass * math.sin(rad)
            
            fig.add_shape(type="circle", x0=cx-r_compass, y0=cy-r_compass, x1=cx+r_compass, y1=cy+r_compass, line=dict(color=plt_border, width=2), fillcolor=plt_card_bg)
            fig.add_annotation(x=nx, y=ny, ax=cx, ay=cy, xref="x", yref="y", axref="x", ayref="y", showarrow=True, arrowhead=3, arrowsize=1.5, arrowwidth=2.5, arrowcolor="#e74c3c")
            fig.add_annotation(x=nx + 0.5*math.cos(rad), y=ny + 0.5*math.sin(rad), text="<b>N</b>", showarrow=False, font=dict(size=14, color="#e74c3c"))
            fig.add_annotation(x=cx, y=cy - r_compass - 0.8, text=f"Top Edge: {blueprint_top_az}°", showarrow=False, font=dict(size=10, color=plt_font))
            
            legend_lines = [
                "<b>📐 HYBRID ARCHITECTURAL LEGEND</b>",
                "----------------------------------",
                "🟦/🟩/🟪 : PV Modules (By String)",
                "---- (Silver) : Structural Rails (Footings)",
                "- - - (Red) : Perimeter Safety Setback",
                "⬛ (Grey Box) : Winter Obstacle Shadow",
                "⬛ (Dark Grey) : PV Module Self-Shadow",
                "🟥 (Red Box) : Physical Roof Obstruction",
                "🟡 (Dot Line) : DC String Series Wiring",
                "⚫ (Solid Line) : Main DC Conduit Homerun",
                "⬛ (Black Box) : Main PV Inverter Location"
            ]
            if th_active:
                legend_lines.insert(3, "🟧 (Orange) : Thermal Collectors")
                legend_lines.append("🔴 (Solid Line) : Thermal Copper Plumbing")
                legend_lines.append("🟥 (TANK) : Thermal Insulated Storage")
            legend_text = "<br>".join(legend_lines)
            
            if enable_engineering_sheet:
                p_bg = "white"
                t_col = "black"
                # Data-anchored layout boundaries (Using original logic that scales perfectly)
                pad_l, pad_r, pad_t, pad_b = 4, 20, 6, 16
                x0, y0 = -pad_l, -pad_b
                x1, y1 = max(roof_w, 25) + pad_r, max(roof_l, 15) + pad_t
                div_x = max(roof_w, 25) + 3
                div_y = -4
                
                # Big borders using Paper coords (decoupled from data aspect ratios)
                fig.add_shape(type="rect", xref="paper", yref="paper", x0=0, y0=0, x1=1, y1=1, line=dict(color="black", width=4), fillcolor="rgba(0,0,0,0)")
                # Right Sidebar dividing line
                fig.add_shape(type="line", xref="paper", yref="paper", x0=0.74, y0=0, x1=0.74, y1=1, line=dict(color="black", width=2))
                # Bottom Sidebar dividing line (stops at right sidebar)
                fig.add_shape(type="line", xref="paper", yref="paper", x0=0, y0=0.25, x1=0.74, y1=0.25, line=dict(color="black", width=2))
                # Title block separator (lowered to give more room for PROJECT name)
                fig.add_shape(type="line", xref="paper", yref="paper", x0=0.74, y0=0.82, x1=1, y1=0.82, line=dict(color="black", width=2))
                
                # Right Title Block Content
                draft_info = (
                    "<b>DRAFTED BY:</b><br>Daisy AI Eng.<br>"
                    f"<b>CHECKED BY:</b><br>{reviewer_name}<br>"
                    "<b>PROJECT ID:</b><br>ESD-2026<br>"
                    f"<b>SITE LOCATION:</b><br>{site_address_input}<br>"
                    "<b>REVISION:</b><br>Rev 0 - Initial IFC<br>"
                    "<b>PE SEAL / SIGNATURE:</b><br>___________________"
                )
                fig.add_annotation(xref="paper", yref="paper", x=0.75, y=0.80, text=draft_info, align="left", showarrow=False, xanchor="left", yanchor="top", font=dict(size=12, color="black"))
                
                site_notes = (
                    "<b>SITE NOTES:</b><br>"
                    f"Modules: {final_pv_units}x {sel_mod}<br>"
                    f"Net Usable Roof Area: {usable_area_sqm:.1f} m²<br>"
                    f"Array Footprint: {total_placed * grid_mod_w * grid_mod_l:.1f} m²<br>"
                    f"Mount:<br>{mount_str_disp}"
                )
                fig.add_annotation(xref="paper", yref="paper", x=0.75, y=0.55, text=site_notes, align="left", showarrow=False, xanchor="left", yanchor="top", font=dict(size=14, color="black"))
                
                fig.add_annotation(xref="paper", yref="paper", x=0.75, y=0.38, text=legend_text, align="left", showarrow=False, xanchor="left", yanchor="top", font=dict(size=12, color=t_col))
                
                sheet_info = f"<b>{actual_kw:.2f} kWDC</b><br>Photovoltaic<br>System<br>-----------<br><b>SHEET:</b><br>PV: 1.1<br>ARRAY LAYOUT"
                fig.add_annotation(xref="paper", yref="paper", x=0.75, y=0.03, text=sheet_info, align="left", showarrow=False, xanchor="left", yanchor="bottom", font=dict(size=16, color="black"))
                
                # Daisy Logo in bottom right
                fig.add_annotation(xref="paper", yref="paper", x=0.98, y=0.03, text="<b>Daisy.</b>", align="right", showarrow=False, xanchor="right", yanchor="bottom", font=dict(family="Plus Jakarta Sans, Poppins, sans-serif", size=42, color="#3b82f6"))
                # Construction Disclaimer Watermark
                fig.add_annotation(xref="paper", yref="paper", x=0.5, y=0.5, text="<b>NOT FOR CONSTRUCTION<br>PRELIMINARY DESIGN ONLY</b>", align="center", showarrow=False, xanchor="center", yanchor="middle", font=dict(family="Arial Black, sans-serif", size=48, color="rgba(255, 0, 0, 0.15)"), textangle=-45)
                
                # Bottom Block Content
                eq_text = "<b>EQUIPMENT LOCATIONS:</b><br>(INV) Main PV Inverter<br>" + ("(TANK) Thermal Storage<br>" if th_active else "") + "DC DISCONNECT Near INV"
                fig.add_annotation(xref="paper", yref="paper", x=0.02, y=0.22, text=eq_text, align="left", showarrow=False, xanchor="left", yanchor="top", font=dict(size=12, color="black"))
                
                if "Roof" in mount_type:
                    height_str = f"PV: {(pv_ground_clearance/1000) + vert_height:.2f}m (Bottom {pv_ground_clearance}mm Air Gap)" + (f"<br>                  TH: {(th_ground_clearance/1000) + vert_height:.2f}m (Bottom {th_ground_clearance}mm Pipe Clear)" if th_active else "")
                    clearance_str = f"{vertical_clearance}in (Roof Parapet) / PV: {pv_ground_clearance}mm" + (f" | TH: {th_ground_clearance}mm (Array)" if th_active else "")
                else:
                    height_str = f"PV: {(pv_ground_clearance/1000) + vert_height:.2f}m (Bottom {pv_ground_clearance}mm Safety)" + (f"<br>                  TH: {(th_ground_clearance/1000) + vert_height:.2f}m (Bottom {th_ground_clearance}mm Struct)" if th_active else "")
                    clearance_str = f"PV: {pv_ground_clearance}mm (Env Risk/Machinery)" + (f" | TH: {th_ground_clearance}mm (Footings)" if th_active else "")
                
                # Dynamic AC Breaker Sizing
                if "Three Phase" in sel_inv:
                    ac_current = (inv_ac_kw * 1000) / (math.sqrt(3) * 415)
                else:
                    ac_current = (inv_ac_kw * 1000) / 230
                safe_current = ac_current * 1.25
                standard_mcbs = [16, 20, 25, 32, 40, 50, 63, 80, 100, 125, 160, 200, 250, 320, 400]
                selected_mcb = next((mcb for mcb in standard_mcbs if mcb >= safe_current), math.ceil(safe_current))

                elec_notes = f"- <b>Wire & Conduit:</b> {selected_awg} UV-Resistant DC Cable (IS 17293) | 25mm UV-UPVC Conduit.<br>- <b>Interconnection:</b> {selected_mcb}A Backfeed Breaker (Load Side).<br>"
                if enable_shading: elec_notes += "- <b>Shading Mitigation:</b> MLPE Optimizers Required.<br>"
                if st.session_state.get('hv_flag', False): elec_notes += "<span style='color:red;'><b>⚠️ HIGH VOLTAGE DC BUS WARNING:</b> System utilizes a >100V<br>DC storage bus. Certified HV switchgear, conduit isolation,<br>and rapid shutdown protocols are MANDATORY.</span><br>"
                if st.session_state.get('ht_flag', False): elec_notes += "<span style='color:#e67e22;'><b>⚡ HIGH TENSION UPGRADE REQUIRED:</b> Array capacity exceeds<br>regional LT limits. Dedicated Distribution Transformer and<br>DISCOM Commercial/HT Metering infrastructure is mandated.</span><br>"
                
                struct_notes = f"- <b>Total Combined Load:</b> {total_combined_load:.1f} kg/m² ({distributed_load:.1f} kg/m² Dead Load).<br>- <b>Design Wind Speed:</b> IS 875 (Part 3) 47 m/s | NASA Avg Wind: {avg_wind_speed:.1f} m/s.<br>"
                
                gen_notes = (
                    "<b>ENGINEERING CLEARANCES & NOTES:</b><br>"
                    f"- <b>Module Dims (PV/Thermal):</b> {grid_mod_l:.2f}m x {grid_mod_w:.2f}m | <b>Col Gap:</b> {gap_x:.2f}m<br>"
                    f"- <b>Inter-Row Gap:</b> {final_gap_y:.2f}m (Shading clearance).<br>"
                    f"- <b>3D Panel Top Height:</b> {height_str} [Tilt: {tilt_angle}°].<br>"
                    f"- <b>Perimeter Setback:</b> {fire_setback}m (Firefighter Pathway per NBC Part 4).<br>"
                    f"- <b>Vertical/Ground Clearances:</b> {clearance_str}.<br>"
                    f"{elec_notes}{struct_notes}"
                    "- <b>Protection:</b> DC/AC SPDs, Fuses, MCCB, Isolator, ELCB &<br>&nbsp;&nbsp;Earth Pits must be sized per IS 732/CEA standards.<br>"
                    "- Grid Sync per CEA Regulations | Dedicated GI Earth Pits."
                )
                fig.add_annotation(xref="paper", yref="paper", x=0.22, y=0.22, text=gen_notes, align="left", showarrow=False, xanchor="left", yanchor="top", font=dict(size=11, color="black"))
                
                title_text = f"<b>ISSUED FOR<br>CONSTRUCTION</b><br><b>PROJECT:</b><br>{active_sector}"
                fig.add_annotation(xref="paper", yref="paper", x=0.75, y=0.98, text=title_text, align="left", showarrow=False, xanchor="left", yanchor="top", font=dict(size=16, color="black"))
                
                fig.update_layout(width=1200, height=1050, plot_bgcolor=p_bg, paper_bgcolor=p_bg, margin=dict(l=0, r=0, t=0, b=0), xaxis=dict(domain=[0.02, 0.72], range=[-2, roof_w+2], scaleanchor="y", scaleratio=1, showgrid=False, zeroline=False, visible=False), yaxis=dict(domain=[0.27, 0.98], range=[-2, roof_l+2], showgrid=False, zeroline=False, visible=False))
            else:
                fig.add_annotation(x=1.02, y=1.0, xref="paper", yref="paper", text=legend_text, align="left", showarrow=False, xanchor="left", yanchor="top", font=dict(size=11, color=plt_font), bgcolor=plt_card_bg, bordercolor=plt_border, borderwidth=2, borderpad=8)
                current_date = datetime.now().strftime("%Y-%m-%d")
                title_block = f"<b>PROJECT:</b> {active_sector}<br><b>PV CAP:</b> {actual_kw:.2f} kWp DC<br><b>THERMAL CAP:</b> {final_thermal_units*THERMAL_COLLECTORS[sel_mod_th]['capacity_lpd'] if th_active else 0} LPD<br><b>DATE:</b> {current_date}<br><b>SCALE:</b> 1:1 Metric"
                fig.add_annotation(x=1.02, y=0.0, xref="paper", yref="paper", text=title_block, align="left", showarrow=False, xanchor="left", yanchor="bottom", font=dict(size=11, color=plt_font), bgcolor=plt_card_bg, bordercolor=plt_border, borderwidth=2, borderpad=8)
                fig.update_layout(width=1200, height=800, plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", margin=dict(l=60, r=300, t=60, b=60), xaxis=dict(range=[-2, roof_w+2], scaleanchor="y", scaleratio=1, showgrid=True, gridcolor=plt_grid), yaxis=dict(range=[-2, roof_l+2], showgrid=True, gridcolor=plt_grid), title=dict(text=f"Issued for Construction (IFC) Blueprint - {active_sector}", font=dict(color=plt_font)))
            
            config_opts = {
                'toImageButtonOptions': {
                    'format': 'png', 
                    'filename': 'IFC_Blueprint', 
                    'width': 1200,
                    'height': 1050,
                    'scale': 2
                }
            } if enable_engineering_sheet else {
                'toImageButtonOptions': {
                    'format': 'png', 
                    'filename': 'IFC_Blueprint', 
                    'scale': 4
                }
            }
            # use_container_width=False forces the browser to render it precisely at the 1200x1000 size (same as the PNG export).
            # This completely solves the text overlapping issue inside Streamlit due to CSS resizing!
            st.plotly_chart(fig, use_container_width=(not enable_engineering_sheet), theme=None, config=config_opts)

            if pv_active:
                st.markdown("<div class='page-break'></div>", unsafe_allow_html=True)
                st.subheader("⚡ 7: Electrical System Architecture (Block Diagram)")
                
                fig_sld = go.Figure()
                bw, bh = 2.2, 0.8

                def draw_block(fig, x, y, text, color):
                    fig.add_shape(type="rect", x0=x-bw/2, y0=y-bh/2, x1=x+bw/2, y1=y+bh/2, fillcolor=color, line=dict(color="white", width=1), layer="above")
                    fig.add_annotation(x=x, y=y, text=text, showarrow=False, font=dict(color="white", size=9))

                draw_block(fig_sld, 2, 3, f"<b>PV ARRAY</b><br>{actual_kw:.2f} kWp<br>{num_parallel_strings} Strings", "#3b82f6")
                draw_block(fig_sld, 6, 3, f"<b>DC COMBINER</b><br>1000V DC SPD Type II<br>15A/20A String Fuses", "#7f8c8d")
                inv_text = f"<b>HYBRID INVERTER</b><br>{num_inverters}x {inv_data['max_ac_kw']} kW AC<br>Integrated MPPT<br>Charge Controller" if 'num_inverters' in locals() and num_inverters > 1 else f"<b>HYBRID INVERTER</b><br>{inv_ac_kw} kW AC<br>Integrated MPPT<br>Charge Controller"
                if grid_type == "On-Grid (Net-Metered)":
                    inv_text = inv_text.replace("HYBRID INVERTER", "STRING INVERTER").replace("Charge Controller", "Grid-Sync")
                elif grid_type == "Off-Grid (Standalone)":
                    inv_text = inv_text.replace("HYBRID INVERTER", "OFF-GRID INVERTER")
                draw_block(fig_sld, 10, 3, inv_text, "#2d3436")
                draw_block(fig_sld, 14, 3, "<b>AC DISCONNECT</b><br>AC SPD Type II<br>& MCCB<br>30mA ELCB", "#e74c3c")
                if grid_type != "Off-Grid (Standalone)":
                    draw_block(fig_sld, 18, 3, "<b>UTILITY METER</b><br>Bi-Directional", "#f39c12")
                    draw_block(fig_sld, 22, 3, "<b>THE GRID</b><br>Utility Supply", "#27ae60")
                else:
                    if use_generator:
                        draw_block(fig_sld, 18, 3, "<b>ATS SWITCH</b><br>Auto Transfer", "#f39c12")
                        draw_block(fig_sld, 18, 4.5, f"<b>BACKUP GEN</b><br>{gen_kw:.1f} kW", "#e67e22")
                        draw_block(fig_sld, 22, 3, "<b>CRITICAL LOADS</b><br>Sub-Panel", "#9b59b6")
                        fig_sld.add_trace(go.Scatter(x=[18, 18], y=[4.5-bh/2, 3+bh/2], mode='lines', line=dict(color='#e67e22', width=4), showlegend=False))
                    else:
                        draw_block(fig_sld, 18, 3, "<b>CRITICAL LOADS</b><br>Sub-Panel", "#9b59b6")

                # DC Positive and Negative
                fig_sld.add_trace(go.Scatter(x=[2+bw/2, 6-bw/2], y=[3.1, 3.1], mode='lines', line=dict(color='#e74c3c', width=4, shape='vh'), name="DC Positive (+)"))
                fig_sld.add_trace(go.Scatter(x=[2+bw/2, 6-bw/2], y=[2.9, 2.9], mode='lines', line=dict(color=sld_neg, width=4, shape='vh'), name="DC Negative (-)"))
                
                fig_sld.add_trace(go.Scatter(x=[6+bw/2, 10-bw/2], y=[3.1, 3.1], mode='lines', line=dict(color='#e74c3c', width=4, shape='vh'), showlegend=False))
                fig_sld.add_trace(go.Scatter(x=[6+bw/2, 10-bw/2], y=[2.9, 2.9], mode='lines', line=dict(color=sld_neg, width=4, shape='vh'), showlegend=False))

                # AC Output
                fig_sld.add_trace(go.Scatter(x=[10+bw/2, 14-bw/2], y=[3, 3], mode='lines', line=dict(color='#3b82f6', width=4, shape='vh'), name="AC Load Output"))
                fig_sld.add_trace(go.Scatter(x=[14+bw/2, 18-bw/2], y=[3, 3], mode='lines', line=dict(color='#3b82f6', width=4, shape='vh'), showlegend=False))
                if grid_type != "Off-Grid (Standalone)" or use_generator:
                    fig_sld.add_trace(go.Scatter(x=[18+bw/2, 22-bw/2], y=[3, 3], mode='lines', line=dict(color='#3b82f6', width=4, shape='vh'), showlegend=False))

                # Grounding
                fig_sld.add_trace(go.Scatter(x=[2, 2, 10, 10], y=[3-bh/2, 2, 2, 3-bh/2], mode='lines', line=dict(color='#27ae60', width=2, dash='dot', shape='vh'), name="Earth Grounding"))
                # Add Earth Pits visually
                fig_sld.add_trace(go.Scatter(x=[2, 10], y=[1.8, 1.8], mode='markers', marker=dict(color='#27ae60', symbol='triangle-down', size=15), name="Earth Pits (< 1 Ohm)"))
                fig_sld.add_annotation(x=6, y=1.8, text="3x Dedicated GI Earth Pits (16mm² Cu/GI strip)", showarrow=False, font=dict(size=10, color="#27ae60"))

                if 'batt_cost' in locals() and batt_cost > 0:
                    batt_charge_rating = inv_data.get("max_dc_i", 30) * 1.5  # Typical charge/discharge buffer
                    draw_block(fig_sld, 10, 1, f"<b>BATTERY BANK</b><br>{usable_batt_kwh:.1f} kWh Usable<br>125A DC Fuse /<br>Battery Isolator", "#8e44ad")
                    fig_sld.add_trace(go.Scatter(x=[10, 10], y=[1+bh/2, 3-bh/2], mode='lines', line=dict(color='#f39c12', width=4, dash='dash'), name=f"DC Charge/Discharge Link<br>(BMS Comm & {batt_charge_rating:.0f}A Rated)"))

                fig_sld.add_annotation(x=4, y=3.3, text=f"DC Wire: {selected_awg}", showarrow=False, font=dict(size=10, color=cad_lines))

                fig_sld.update_layout(height=400, xaxis=dict(visible=False, range=[0, 24]), yaxis=dict(visible=False, range=[0, 4.5]), plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", margin=dict(l=10, r=10, t=10, b=10), showlegend=True, legend=dict(orientation="h", y=0, x=0.2, font=dict(color=plt_font)))
                st.plotly_chart(fig_sld, use_container_width=True)

                st.markdown("<div class='page-break'></div>", unsafe_allow_html=True)
                st.subheader("⚡ 7b: Technical Single-Line Diagram (ANSI/IEC Standard)")
                
                fig_true_sld = go.Figure()
                
                def draw_rect(fig, x, y, w, h, text, is_dashed=False):
                    dash_style = "dash" if is_dashed else "solid"
                    fig.add_shape(type="rect", x0=x-w/2, y0=y-h/2, x1=x+w/2, y1=y+h/2, line=dict(color=plt_font, width=1.5, dash=dash_style), fillcolor="rgba(0,0,0,0)")
                    fig.add_annotation(x=x, y=y-h/2-0.5, text=text, showarrow=False, font=dict(color=plt_font, size=10))

                def draw_switch(fig, x, y):
                    fig.add_trace(go.Scatter(x=[x-0.4, x-0.2], y=[y, y], mode='lines', line=dict(color=plt_font, width=1.5), showlegend=False))
                    fig.add_trace(go.Scatter(x=[x-0.2], y=[y], mode='markers', marker=dict(color=plt_font, size=4), showlegend=False))
                    fig.add_trace(go.Scatter(x=[x-0.2, x+0.15], y=[y, y+0.3], mode='lines', line=dict(color=plt_font, width=1.5), showlegend=False))
                    fig.add_trace(go.Scatter(x=[x+0.2], y=[y], mode='markers', marker=dict(color=plt_font, size=4), showlegend=False))
                    fig.add_trace(go.Scatter(x=[x+0.2, x+0.4], y=[y, y], mode='lines', line=dict(color=plt_font, width=1.5), showlegend=False))
                
                draw_rect(fig_true_sld, 2, 4, 3, 2, "", is_dashed=False)
                fig_true_sld.add_annotation(x=2, y=4, text=f"PV<br>Array ({len(pv_panels) if 'pv_panels' in locals() else 0}<br>Module)", showarrow=False, font=dict(color=plt_font, size=11))
                
                draw_rect(fig_true_sld, 6, 4, 1.5, 1.5, "PV Array<br>Junction Box", is_dashed=True)
                draw_switch(fig_true_sld, 6, 4)
                
                draw_rect(fig_true_sld, 9, 4, 1.5, 1.5, "DC<br>Disconnect<br>Switch", is_dashed=True)
                draw_switch(fig_true_sld, 9, 4)
                
                draw_rect(fig_true_sld, 13, 4, 3, 2, "", is_dashed=False)
                inv_display = f"{inv_ac_kw}kW Inverter" if 'num_inverters' not in locals() or num_inverters == 1 else f"{num_inverters}x {inv_data['max_ac_kw']}kW Inverters"
                fig_true_sld.add_annotation(x=13, y=4, text=inv_display, showarrow=False, font=dict(color=plt_font, size=11))
                
                draw_rect(fig_true_sld, 17, 4, 1.5, 1.5, "AC<br>Disconnect<br>Switch", is_dashed=True)
                draw_switch(fig_true_sld, 17, 4)
                
                if grid_type != "Off-Grid (Standalone)":
                    draw_rect(fig_true_sld, 21, 4, 2, 1.5, "Grid Connection<br>Cabinet", is_dashed=True)
                    draw_switch(fig_true_sld, 21, 4)
                    fig_true_sld.add_annotation(x=21, y=4+1, text="PCC", showarrow=False, font=dict(color=plt_font, size=11))
                    fig_true_sld.add_trace(go.Scatter(x=[25, 25], y=[3, 5], mode='lines', line=dict(color=plt_font, width=3), showlegend=False))
                    fig_true_sld.add_trace(go.Scatter(x=[25.5, 26.5], y=[3.5, 4.5], mode='lines', line=dict(color=plt_font, width=1), showlegend=False))
                    fig_true_sld.add_trace(go.Scatter(x=[25.5, 26.5], y=[4.5, 3.5], mode='lines', line=dict(color=plt_font, width=1), showlegend=False))
                    fig_true_sld.add_annotation(x=26, y=2.5, text="Low Voltage<br>Network", showarrow=False, font=dict(color=plt_font, size=10))
                else:
                    draw_rect(fig_true_sld, 21, 4, 2, 2, "Critical Loads<br>Panel", is_dashed=False)

                fig_true_sld.add_trace(go.Scatter(x=[3.5, 5.25], y=[4, 4], mode='lines', line=dict(color=plt_font, width=1.5), showlegend=False))
                fig_true_sld.add_trace(go.Scatter(x=[6.75, 8.25], y=[4, 4], mode='lines', line=dict(color=plt_font, width=1.5), showlegend=False))
                fig_true_sld.add_trace(go.Scatter(x=[9.75, 11.5], y=[4, 4], mode='lines', line=dict(color=plt_font, width=1.5), showlegend=False))
                fig_true_sld.add_trace(go.Scatter(x=[14.5, 16.25], y=[4, 4], mode='lines', line=dict(color=plt_font, width=1.5), showlegend=False))
                fig_true_sld.add_trace(go.Scatter(x=[17.75, 20.0], y=[4, 4], mode='lines', line=dict(color=plt_font, width=1.5), showlegend=False))
                if grid_type != "Off-Grid (Standalone)":
                    fig_true_sld.add_trace(go.Scatter(x=[22.0, 25], y=[4, 4], mode='lines', line=dict(color=plt_font, width=1.5), showlegend=False))

                fig_true_sld.add_annotation(x=10.5, y=4.5, text="I_pv", showarrow=False, font=dict(color=plt_font, size=12, family="Times New Roman", style="italic"))
                fig_true_sld.add_annotation(x=10.5, y=3.5, text="V_dc", showarrow=False, font=dict(color=plt_font, size=12, family="Times New Roman", style="italic"))
                fig_true_sld.add_annotation(x=15.5, y=4.5, text="P_ac", showarrow=False, font=dict(color=plt_font, size=12, family="Times New Roman", style="italic"))
                if grid_type != "Off-Grid (Standalone)":
                    fig_true_sld.add_annotation(x=23.5, y=4.5, text="P_f, Q_f", showarrow=False, font=dict(color=plt_font, size=12, family="Times New Roman", style="italic"))
                    fig_true_sld.add_annotation(x=19.0, y=4.5, text="P_i, Q_i", showarrow=False, font=dict(color=plt_font, size=12, family="Times New Roman", style="italic"))
                
                draw_rect(fig_true_sld, 13, 1, 3, 1, "", is_dashed=False)
                fig_true_sld.add_annotation(x=13, y=1, text="Solar Log 300 PM+", showarrow=False, font=dict(color=plt_font, size=10))
                
                fig_true_sld.add_trace(go.Scatter(x=[13, 13], y=[3, 1.5], mode='lines', line=dict(color=plt_font, width=1.5), showlegend=False))
                fig_true_sld.add_annotation(x=13, y=3, ax=13, ay=2.8, xref='x', yref='y', axref='x', ayref='y', showarrow=True, arrowhead=2, arrowsize=1, arrowcolor=plt_font)
                fig_true_sld.add_annotation(x=13, y=1.5, ax=13, ay=1.7, xref='x', yref='y', axref='x', ayref='y', showarrow=True, arrowhead=2, arrowsize=1, arrowcolor=plt_font)
                fig_true_sld.add_annotation(x=14, y=2.25, text="RJ45 - RS485<br>connection", showarrow=False, font=dict(color=plt_font, size=9), align="left")

                draw_rect(fig_true_sld, 13, -1, 2.5, 0.8, "", is_dashed=False)
                fig_true_sld.add_annotation(x=13, y=-1, text="💻 Computer", showarrow=False, font=dict(color=plt_font, size=10))
                
                fig_true_sld.add_trace(go.Scatter(x=[13, 13], y=[0.5, -0.6], mode='lines', line=dict(color=plt_font, width=1.5), showlegend=False))
                fig_true_sld.add_annotation(x=13, y=0.5, ax=13, ay=0.3, xref='x', yref='y', axref='x', ayref='y', showarrow=True, arrowhead=2, arrowsize=1, arrowcolor=plt_font)
                fig_true_sld.add_annotation(x=13, y=-0.6, ax=13, ay=-0.4, xref='x', yref='y', axref='x', ayref='y', showarrow=True, arrowhead=2, arrowsize=1, arrowcolor=plt_font)
                fig_true_sld.add_annotation(x=11.5, y=-0.05, text="Web interface", showarrow=False, font=dict(color=plt_font, size=9))

                draw_rect(fig_true_sld, 18, -1, 2.5, 1.5, "", is_dashed=False)
                fig_true_sld.add_annotation(x=18, y=-1, text="CA8335 Power<br>Quality Analyzer", showarrow=False, font=dict(color=plt_font, size=10))
                fig_true_sld.add_trace(go.Scatter(x=[18, 18], y=[4, -0.25], mode='lines', line=dict(color=plt_font, width=1.5), showlegend=False))
                fig_true_sld.add_annotation(x=18, y=-0.25, ax=18, ay=0.5, xref='x', yref='y', axref='x', ayref='y', showarrow=True, arrowhead=2, arrowsize=1, arrowcolor=plt_font)
                
                fig_true_sld.add_trace(go.Scatter(x=[14.25, 16.75], y=[-1, -1], mode='lines', line=dict(color=plt_font, width=1.5), showlegend=False))
                fig_true_sld.add_annotation(x=14.25, y=-1, ax=14.45, ay=-1, xref='x', yref='y', axref='x', ayref='y', showarrow=True, arrowhead=2, arrowsize=1, arrowcolor=plt_font)
                fig_true_sld.add_annotation(x=16.75, y=-1, ax=16.55, ay=-1, xref='x', yref='y', axref='x', ayref='y', showarrow=True, arrowhead=2, arrowsize=1, arrowcolor=plt_font)

                fig_true_sld.add_annotation(x=2.25, y=1.2, text="G", showarrow=False, font=dict(color=plt_font, size=12, family="Times New Roman", style="italic"))
                fig_true_sld.add_shape(type="rect", x0=2.5, y0=0.5, x1=2.8, y1=0.8, line=dict(color="blue", width=2), fillcolor="rgba(0,0,0,0)")
                
                fig_true_sld.add_annotation(x=1.2, y=0.5, text="T_a", showarrow=False, font=dict(color=plt_font, size=12, family="Times New Roman", style="italic"))
                fig_true_sld.add_annotation(x=3.2, y=0.5, text="T_c", showarrow=False, font=dict(color=plt_font, size=12, family="Times New Roman", style="italic"))
                
                fig_true_sld.add_trace(go.Scatter(x=[1.5, 11.5], y=[0, 0], mode='lines', line=dict(color=plt_font, width=1.5), showlegend=False))
                fig_true_sld.add_trace(go.Scatter(x=[11.5, 11.5], y=[0, 1], mode='lines', line=dict(color=plt_font, width=1.5), showlegend=False))
                fig_true_sld.add_annotation(x=6, y=0.2, text="RS485 connection", showarrow=False, font=dict(color=plt_font, size=10))
                fig_true_sld.add_annotation(x=11.5, y=1, ax=11.5, ay=0.8, xref='x', yref='y', axref='x', ayref='y', showarrow=True, arrowhead=2, arrowsize=1, arrowcolor=plt_font)

                fig_true_sld.update_layout(height=400, xaxis=dict(visible=False, range=[0, 28]), yaxis=dict(visible=False, range=[-2, 6]), plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", margin=dict(l=10, r=10, t=10, b=10))
                st.plotly_chart(fig_true_sld, use_container_width=True)


        # ==========================================
        # LAYER 6: NASA METEOROLOGY & 3D SUN-PATH TAB
        # ==========================================
        with tab_nasa:
            st.header("🛰️ 8: NASA Meteorological Data")
            st.write(f"**Data Source:** NASA POWER Satellite API | **Coordinates:** {st.session_state.lat:.4f}, {st.session_state.lon:.4f}")
            
            w1, w2, w3 = st.columns(3)
            w1.metric("Average Wind Speed", f"{avg_wind_speed:.2f} m/s")
            base_t = max(10, abs(st.session_state.lat))
            aero_msg = "Safe" if avg_wind_speed <= 4.5 else ("High Wind Risk" if avg_wind_speed <= 6.0 else "Extreme Wind Risk")
            w2.metric("Aerodynamic Profile", aero_msg)
            w3.metric("Wind-Adjusted Array Tilt", f"{tilt_angle:.1f}°", f"{- (base_t - tilt_angle):.1f}° Reduction" if tilt_angle < base_t else "No Reduction", delta_color="normal")
            
            if nasa_ghi_data and nasa_diff_data:
                months_labels = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
                nasa_keys = ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN', 'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC']
                ghi_values = [nasa_ghi_data.get(k, 0) for k in nasa_keys]
                diff_values = [nasa_diff_data.get(k, 0) for k in nasa_keys]

                fig_nasa = go.Figure()
                fig_nasa.add_trace(go.Bar(x=months_labels, y=ghi_values, name='Total Irradiance (GHI)', marker_color='#f1c40f'))
                fig_nasa.add_trace(go.Bar(x=months_labels, y=diff_values, name='Diffuse Irradiance (Scattered)', marker_color='#95a5a6'))
                fig_nasa.update_layout(title="Monthly Average Solar Irradiance", yaxis_title="kWh/m²/day", barmode='group', height=400, plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", font=dict(color=plt_font))
                st.plotly_chart(fig_nasa, use_container_width=True)

            st.divider()
            st.subheader("🌐 9: 3D Sun-Path & Shadow Trajectory")
            
            s_col1, s_col2 = st.columns(2)
            s_col1.metric("Winter Solstice Profile Angle (9AM/3PM)", f"{profile_angle_deg:.2f}°", "Used for Shade-Free Inter-Row Spacing", delta_color="off")
            s_col2.metric("Winter Solstice Altitude (Noon)", f"{winter_elevation:.2f}°", delta_color="off")
            
            lat_rad = math.radians(st.session_state.lat)
            dec_summer = math.radians(23.45)
            dec_winter = math.radians(-23.45)
            dec_equinox = 0.0

            def calc_sun_path(declination):
                azimuths = []
                elevations = []
                for hour in np.linspace(-6, 6, 50): 
                    omega = math.radians(hour * 15)
                    val = math.sin(lat_rad)*math.sin(declination) + math.cos(lat_rad)*math.cos(declination)*math.cos(omega)
                    el_rad = math.asin(max(-1.0, min(1.0, val)))
                    
                    cos_az = (math.sin(declination) - math.sin(lat_rad)*math.sin(el_rad)) / (math.cos(lat_rad)*math.cos(el_rad))
                    az_rad = math.acos(max(-1.0, min(1.0, cos_az)))
                    
                    el_deg = math.degrees(el_rad)
                    az_deg = math.degrees(az_rad)
                    if hour > 0: az_deg = 360 - az_deg 
                    
                    if el_deg > 0:
                        azimuths.append(az_deg)
                        elevations.append(90 - el_deg) 
                return azimuths, elevations

            az_sum, el_sum = calc_sun_path(dec_summer)
            az_win, el_win = calc_sun_path(dec_winter)
            az_eq, el_eq = calc_sun_path(dec_equinox)

            fig_polar = go.Figure()
            fig_polar.add_trace(go.Scatterpolar(r=el_sum, theta=az_sum, mode='lines', name='Summer Solstice (Jun 21)', line=dict(color='orange', width=3)))
            fig_polar.add_trace(go.Scatterpolar(r=el_eq, theta=az_eq, mode='lines', name='Equinox (Mar/Sep)', line=dict(color='green', width=2)))
            fig_polar.add_trace(go.Scatterpolar(r=el_win, theta=az_win, mode='lines', name='Winter Solstice (Dec 21)', line=dict(color='blue', width=3)))

            fig_polar.update_layout(
                polar=dict(
                    bgcolor="rgba(0,0,0,0)",
                    radialaxis=dict(visible=True, range=[90, 0], tickvals=[0, 30, 60, 90], ticktext=['90°', '60°', '30°', 'Horizon'], gridcolor=plt_grid),
                    angularaxis=dict(direction="clockwise", rotation=90, gridcolor=plt_grid)
                ),
                showlegend=True, height=500, paper_bgcolor="rgba(0,0,0,0)", font=dict(color=plt_font)
            )
            st.plotly_chart(fig_polar, use_container_width=True)

        with tab_sop:
            st.header("Structural Engineering Standard Operating Procedures")
            st.markdown("""
            The solar structural engineer profession is developing rapidly as demand for clean and sustainable energy skyrockets. Solar structural engineer reports play an essential part in the development of solar projects, they evaluate the project's design, materials, and construction for solar development. They provide essential insights to the feasibility and longevity of solar projects across locations and climates.
            
            **(Click here for additional information on our solar structural engineering services.)**
            
            One of the key considerations of a solar structural engineer report is the evaluation of the solar facilities. It involves analysis of the solar panels, supporting structures, and connections to the electrical grid. The solar structural report ensures the project adheres to local building code and safety standards, while evaluating other environmental aspects such as wind loads, snow loads, and seismic activity.
            
            As the solar field growth is rapid, the solar structural engineer reports are invaluable. The structural report helps avoid potential hazards and risks, and enable advancement and optimization in this rapidly emerging field. The reports leverage solar project infrastructure knowledge and expertise, which create value while advancing solar energy and its related systems nationally and globally.
            
            ### Responsibilities and Roles
            
            **Solar Structural Engineers**
            Solar structural engineers are an essential part of the design and implementation of solar energy systems. Their job is to evaluate the structural integrity of buildings, and that solar installations can be safely and successfully mounted on various types of structures, from houses and residential buildings to commercial buildings. Structural engineers analyze the materials of the building, construction techniques, and overall structural safety to determine if solar installations are achievable.
            
            Structural engineers coordinate with other professional designers, such as architects, to produce calculations of loads and design systems to support the solar installation on the building. Their involvement is imperative for the safe, and operational capacity of the solar system. Structural engineers keep abreast of the developments in the industry and follow regulations and policies, including confirm ownership of or establishing building codes impact on the support for solar panels.
            
            **Contractors and Owners**
            Solar structural engineering plays a role towing the technical aspects of the solar installation, and responsibility lies with the contractor and owner. Owners manage the overall experience of working with the design engineer to develop and select the right solution for solar for their situation based on the information obtained about their performance and budget. They consider the energy being used in the facility, and if the solar supply will meet that facility energy load.
            
            Owners consider the appropriate state and local building codes for the building and permit issue needed for the installation, as well as whether to allocate funds to regularly inspect and maintain the solar system and support hierarchy.
            
            The contractor has the responsibility of implementation of the solar system system, and follows the documents from the structural engineer so their field implementation of the design is respecting the structural engineers designs. This could mean coordination with other construction trades, such as with an electrician and roofer, to ensure installation would go problem-free. It is also important to understand and meet contractor liability requirements, which depend on where the project is located.
            
            ### Structural Review and Design
            
            **Weight Assessment**
            When reviewing a solar structural engineer report, the loaded weight is assessed as dead load and live load on the structure by a photovoltaic (PV) system. The dead load is the weight of the solar panel mounts and rackings. The live load is the supplemental weight to the structure like snow, ice, and maintenance activities. These two weights define the allowable weight or load on the structure without compromising structural integrity.
            
            **Load Calculations**
            Loading calculations are conducted by solar structural engineers to establish the overall strength and stability of a PV system. The loading calculations are made up of the dead load from the solar panel array, live load from the environmental conditions including wind loads and snow loads, and additional loading provided by fasteners.
            
            **Wind Loads and Snow Loads**
            Wind loads and snow loads are critical considerations in PV system design as they are considered live loads. In order to evaluate the wind loads and snow loads of a proposed PV system, solar structural engineers will simulate and utilize mathematical models that account for local climate as well as historical meteorological events.
            
            **Ballasting and Racking Systems**
            A central aspect to solar structural engineering is the selection of a ballast and racking system. Ballast systems are non-penetrating keeping the integrity of the roof intact; racking systems are penetrating and fastened directly to the structure to enhance load capacity. When the structural engineering team performs structural analysis and design of a PV system, they will evaluate the two systems based upon roof design, load capacity and overall stability adjustments.
            
            ### Building Code Compliance
            
            **Compliance with International Codes**
            There are two primary codes, the International Building Code (IBC) and the International Residential Code (IRC) that are utilized for solar installations. These guides help ensure solar systems are designed and installed safely and effectively in the structural, mechanical, electrical, and plumbing systems of the building. Publications, such as the American Society of Civil Engineers (ASCE), are used in collaboration with these codes.
            
            **Wind and Seismic Design Standards**
            Aspects of environmental exposure are an important consideration during the design of solar installations. A solar structural engineer should follow the wind design and seismic design standards developed by the ASCE 7 and indicated in the IBC and IRC. Some of the important design considerations for wind and seismic standards include:
            - Wind speed and exposure
            - Structural materials and connections
            - Geometry and slope of the roof
            - Seismic site classifications and hazard levels
            - Foundation design and soil conditions
            
            ### Project Planning and Execution
            
            **Surveys and Capacity Assessment**
            Before the start of a solar structural engineering project, field assessments and existing structure capacity evaluation must be conducted. The discussions revolve around parameters such as existing roof area, existing roof load capacity, and any reinforcement that has to take place for the installation of the PV Panels on the roof.
            
            **Rooftop Solar Installation Specifics**
            - **Panel Orientation:** Optimal angle for maximum solar energy capture
            - **Mounting System:** The style and materials used to install and secure the panels onto the roof
            - **Wiring Layout:** Proper routing of electrical cables to minimize potential hazards
            
            **Strengthening and Reinforcement**
            If the existing roof condition was not design to accommodate extra weight and mechanical loads of solar, such reinforcement would have to occur. This may include structural support of beams, columns, and/or braced support.
            
            ### Risk Management
            
            **Design Errors – Identify and Correct**
            In the area of solar structural engineering, this work is essential to be able to have a process to identify and correct design errors. Establishing a formal review process at key points within the structural report design, assembly experienced professionals, and using more technical modeling and analysis software can significantly improve the design.
            
            **Construction Defects and Liability**
            Some construction defect risk management techniques include:
            - Contractor selection with construction experience related to solar installations
            - Adequate training and monitoring for construction crews
            - Routine inspections and progress evaluations
            - Identifying and correcting defects at the earliest opportunity.
            
            ### Innovations in Solar Engineering
            
            **Material Technology Advancements**
            The development of new less costly and efficient materials in photovoltaic (PV) panel manufacturing has advanced the absorption of solar energy. For example, the advent of perovskite solar cells has led to higher efficient and less expensive solar panels than traditionally manufactured silicon solar panels.
            
            **Integration of New Design Strategies**
            Furthermore, solar energy engineering has integrated new design strategies to optimize solar energy systems. For example, building-integrated photovoltaics (BIPVs) design integrates solar panels into the building structuring components where in many cases the solar panels are invisible.
            """)

        st.divider()
        st.subheader("📄 10: Generate Comprehensive PDF Report")
        st.markdown("Compile all financial logic, engineering schematics, and interactive data above into a high-resolution, multi-page PDF document suitable for printing or sharing.")
        
        if st.button("Generate Professional PDF Report", type="primary", use_container_width=True):
            with st.spinner("Compiling Engineering & Financial Data..."):
                try:
                    import tempfile
                    import kaleido
                    import importlib
                    import pdf_generator
                    importlib.reload(pdf_generator)
                    from pdf_generator import generate_pdf_report
                    
                    cf_path = tempfile.NamedTemporaryFile(suffix=".png", delete=False).name
                    power_path = tempfile.NamedTemporaryFile(suffix=".png", delete=False).name
                    nasa_path = tempfile.NamedTemporaryFile(suffix=".png", delete=False).name
                    cad_path = tempfile.NamedTemporaryFile(suffix=".png", delete=False).name
                    bom_path = tempfile.NamedTemporaryFile(suffix=".png", delete=False).name
                    sld_path = tempfile.NamedTemporaryFile(suffix=".png", delete=False).name
                    
                    fig_cf.write_image(cf_path, engine="kaleido", width=800, height=400)
                    if 'fig_power' in locals() and fig_power:
                        fig_power.write_image(power_path, engine="kaleido", width=800, height=300)
                    elif 'fig_arch' in locals() and fig_arch:
                        fig_arch.write_image(power_path, engine="kaleido", width=800, height=300)
                    else:
                        power_path = None
                    if 'fig_nasa' in locals() and fig_nasa:
                        fig_nasa.write_image(nasa_path, engine="kaleido", width=800, height=400)
                    else:
                        nasa_path = None
                    fig.write_image(cad_path, engine="kaleido")
                    
                    if 'fig_bom' in locals() and fig_bom:
                        fig_bom.write_image(bom_path, engine="kaleido", width=600, height=400)
                    else:
                        bom_path = None
                    
                    if 'fig_sld' in locals() and fig_sld:
                        fig_sld.write_image(sld_path, engine="kaleido", width=1000, height=600)
                    else:
                        sld_path = None
                        
                    true_sld_path = tempfile.NamedTemporaryFile(suffix=".png", delete=False).name
                    if 'fig_true_sld' in locals() and fig_true_sld:
                        fig_true_sld.write_image(true_sld_path, engine="kaleido", width=1200, height=500)
                    else:
                        true_sld_path = None

                    report_data = {
                        "location": address,
                        "lat": st.session_state.lat,
                        "lon": st.session_state.lon,
                        "gross_cost": gross_cost,
                        "net_cost": net_cost,
                        "pv_savings": pv_savings if 'pv_savings' in locals() else 0,
                        "payback_yr": payback_yr if 'payback_yr' in locals() else None,
                        "lcoe": lcoe if 'lcoe' in locals() else 0,
                        "cumulative_profit": cumulative_cf[-1] if 'cumulative_cf' in locals() else 0,
                        "total_kw": actual_kw if 'actual_kw' in locals() else 0,
                        "inv_ac_kw": inv_ac_kw if 'inv_ac_kw' in locals() else 0,
                        "dc_ac_ratio": dc_ac_ratio if 'dc_ac_ratio' in locals() else 0,
                        "total_roof_area": total_roof_area if 'total_roof_area' in locals() else 0,
                        "usable_roof_area": (total_placed*(grid_mod_w*grid_mod_l)) if 'total_placed' in locals() else 0,
                        "target_gen_kwh": target_gen_kwh if 'target_gen_kwh' in locals() else 0,
                        "panel_model": sel_mod if 'sel_mod' in locals() else "N/A",
                        "panel_count": len(pv_panels) if 'pv_panels' in locals() else 0,
                        "modules_in_series": modules_in_series if 'modules_in_series' in locals() else 0,
                        "num_parallel_strings": num_parallel_strings if 'num_parallel_strings' in locals() else 0,
                        "num_inverters": num_inverters if 'num_inverters' in locals() else 1,
                        "inverter_model": sel_inv if 'sel_inv' in locals() else "N/A",
                        "grid_type": grid_type if 'grid_type' in locals() else "N/A",
                        "batt_cap": usable_batt_kwh if 'usable_batt_kwh' in locals() else 0,
                        "batt_model": sel_batt if 'sel_batt' in locals() else "N/A",
                        "mount_type": mount_type if 'mount_type' in locals() else "N/A",
                        "azimuth": blueprint_top_az if 'blueprint_top_az' in locals() else 0,
                        "tilt": tilt_angle if 'tilt_angle' in locals() else 0,
                        "row_gap": final_gap_y if 'final_gap_y' in locals() else 0.6,
                        "wind_uplift": wind_uplift_kg_m2 if 'wind_uplift_kg_m2' in locals() else 0,
                        "snow_load": snow_load_kg_m2 if 'snow_load_kg_m2' in locals() else 0,
                        "dead_load": distributed_load if 'distributed_load' in locals() else 0,
                        "total_combined_load": total_combined_load if 'total_combined_load' in locals() else 0,
                        "roof_capacity": roof_capacity if 'roof_capacity' in locals() else 0,
                        "annual_rad": annual_rad if 'annual_rad' in locals() else 0,
                        "thermal_derate_pct": thermal_derate_pct if 'thermal_derate_pct' in locals() else 0,
                        "soiling_loss": soiling_loss if 'soiling_loss' in locals() else 0,
                        "lid_loss": lid_loss if 'lid_loss' in locals() else 0,
                        "cf_image": cf_path,
                        "power_image": power_path,
                        "nasa_image": nasa_path,
                        "cad_image": cad_path,
                        "bom_image": bom_path,
                        "sld_image": sld_path,
                        "true_sld_image": true_sld_path,
                        "monthly_gen": monthly_gen.tolist() if 'monthly_gen' in locals() else [],
                        "monthly_load": monthly_load.tolist() if 'monthly_load' in locals() else [],
                        "monthly_cf": monthly_cf if 'monthly_cf' in locals() else [],
                        "pv_active": pv_active if 'pv_active' in locals() else False,
                        "th_active": th_active if 'th_active' in locals() else False,
                        "thermal_panels": len(thermal_panels) if 'thermal_panels' in locals() else 0,
                        "heater_rating": heater_rating if 'heater_rating' in locals() else "",
                        "target_lpd": target_lpd if 'target_lpd' in locals() else 0,
                        "delta_t": delta_t if 'delta_t' in locals() else 0,
                        "t_in": t_in if 't_in' in locals() else 0,
                        "t_out": t_out if 't_out' in locals() else 0,
                        "daily_thermal_energy_kwh": daily_thermal_energy_kwh if 'daily_thermal_energy_kwh' in locals() else 0,
                        "generator_kw": generator_kw if 'generator_kw' in locals() else 0,
                        "fuel_run_hours": fuel_run_hours if 'fuel_run_hours' in locals() else 0
                    }
                    
                    pdf_bytes = generate_pdf_report(report_data)
                    st.session_state.pdf_ready = pdf_bytes
                except Exception as e:
                    st.error(f"Error generating PDF: {e}")
        
        if st.session_state.get('pdf_ready'):
            st.success("✅ Report compiled successfully!")
            st.download_button(
                label="⬇️ Download PDF Report",
                data=bytes(st.session_state.pdf_ready),
                file_name="Daisy_Solar_Feasibility_Report.pdf",
                mime="application/pdf",
                use_container_width=True
            )

