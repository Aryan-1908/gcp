from dotenv import load_dotenv
import os
import json
import streamlit as st
import pydeck as pdk
import matplotlib.pyplot as plt
import graphviz
from google.oauth2 import service_account
from backend import ask_gemini
from datetime import datetime, timedelta
import random
import pandas as pd
 
# ==============================
# Load Environment and Credentials
# ==============================
load_dotenv()
key_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
credentials = service_account.Credentials.from_service_account_file(key_path)
 
# ==============================
# Allowed Users (Login System)
# ==============================

ALLOWED_USERS = {
    "shubham.kumar@cloudtechner.com": "shubham90",
    "aryan.kansal@cloudtechner.com": "shubham90",
    "namsani.vamshi@cloudtechner.com": "shubham90"
}
 
# ==============================
# Login Page
# ==============================
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
 
if not st.session_state.logged_in:
    st.title("🔒 CloudTechner Login")
 
    email = st.text_input("📧 Email")
    password = st.text_input("🔑 Password", type="password")
 
    if st.button("Login"):
        if email in ALLOWED_USERS and ALLOWED_USERS[email] == password:
            st.session_state.logged_in = True
            st.session_state.user = email
            st.success(f"✅ Welcome {email}!")
            st.rerun()
            # st.experimental_rerun()
        else:
            st.error("❌ Invalid email or password. Access denied.")
 
    st.stop()  # ⛔ Stop here until logged in
 
# ==============================
# Streamlit Page Config (After Login)
# ==============================
st.set_page_config(
    page_title="CloudTechner GCP Assistant",
    page_icon="☁",
    layout="wide",
    initial_sidebar_state="expanded"
)
 
# ==============================
# Custom CSS for Google-like UI
# ==============================
st.markdown(
    """
    <style>
        body {
            font-family: 'Google Sans', Arial, sans-serif;
            background-color: #f8f9fa;
        }
        .main-title {
            font-size: 42px;
            font-weight: bold;
            color: #4285F4;
            text-align: center;
            margin-bottom: 10px;
        }
        .subtitle {
            text-align: center;
            color: #5f6368;
            margin-bottom: 40px;
        }
        .stButton>button {
            background: #4285F4;
            color: white;
            border-radius: 8px;
            font-size: 16px;
            padding: 8px 16px;
        }
        .stTextArea textarea {
            border-radius: 8px;
            border: 1px solid #dadce0;
        }
    </style>
    """,
    unsafe_allow_html=True
)
 
# ==============================
# Header
# ==============================
st.markdown("<div class='main-title'>☁ CloudTechner GCP Assistant</div>", unsafe_allow_html=True)
st.markdown("<div class='subtitle'>Ask anything about your GCP resources</div>", unsafe_allow_html=True)
 
# ==============================
# Sidebar Navigation
# ==============================
st.sidebar.title("🔧 Tools")
st.sidebar.info(f"👤 Logged in as: {st.session_state.user}")
mode = st.sidebar.radio("Choose view:", ["Assistant", "Regions", "VMs", "Users", "Debug"])
 
# ==============================
# Query Box
# ==============================
query = st.text_area("💬 Enter your request:", placeholder="e.g., List all active VMs")
 
# ==============================
# Handle Queries
# ==============================
answer = None
raw_data = None
if st.button("Run Command"):
    if query.strip() == "":
        st.warning("Please enter a request.")
    else:
        with st.spinner("Processing your query with CloudTechner AI..."):
            try:
                # Call LLM connector 
                command, mcp_result, answer = ask_gemini(query)
                # Mock raw data for demo
                raw_data = {
                    "query": query,
                    "response": answer,
                    "timestamp": datetime.now().isoformat()
                }
                st.success("✅ Query processed successfully!")
            except Exception as e:
                st.error(f"❌ Error: {e}")
 
# ==============================
# Regions Visualization with Map
# ==============================
if mode == "Regions":
    st.header("🌍 GCP Regions Map")
 
    regions = [
        {"name": "us-central1", "lat": 41.2619, "lon": -95.8608},
        {"name": "us-east1", "lat": 33.1960, "lon": -80.0131},
        {"name": "europe-west1", "lat": 50.1109, "lon": 8.6821},
        {"name": "asia-south1", "lat": 19.0760, "lon": 72.8777},
    ]
 
    df = pd.DataFrame(regions)
 
    # Show map with markers
    st.map(df, latitude="lat", longitude="lon", size=100, color="#4285F4")
 
    # Also list regions
    st.subheader("📍 Region List")
    for r in regions:
        st.write(f"✅ {r['name']} ({r['lat']}, {r['lon']})")
 
# ==============================
# VM Visualization
# ==============================
if mode == "VMs":
    st.header("💻 Active VMs Visualization")
    vms = [
        {"name": "vm-1", "region": "us-central1"},
        {"name": "vm-2", "region": "us-east1"},
        {"name": "vm-3", "region": "europe-west1"},
    ]
    for vm in vms:
        st.markdown(f"🖥 **{vm['name']}** — Region: {vm['region']}")
    graph = graphviz.Digraph()
    graph.attr(rankdir='LR')
    for vm in vms:
        graph.node(vm["name"], f"{vm['name']}\n{vm['region']}")
    graph.edge("vm-1", "vm-2")
    graph.edge("vm-2", "vm-3")
    st.graphviz_chart(graph)
 
# ==============================
# User Activity Visualization
# ==============================
if mode == "Users":
    st.header("👤 Active Users Over Time")
    days = [datetime.now() - timedelta(days=i) for i in range(14)]
    users = [random.randint(1, 20) for _ in days]
    days.reverse()
    users.reverse()
    plt.figure(figsize=(10, 4))
    plt.plot(days, users, marker='o', linestyle='-', linewidth=2)
    plt.title("Active Users (Last 2 Weeks)")
    plt.xlabel("Date")
    plt.ylabel("Active Users")
    plt.grid(True)
    st.pyplot(plt)
 
# ==============================
# Debug Mode
# ==============================
if mode == "Debug":
    st.header("🛠 Debug Info")
    if raw_data:
        st.subheader("Raw JSON Response")
        st.json(raw_data)
    else:
        st.info("Run a query to see debug information.")
 
# ==============================
# Show Answer (Default Assistant Mode)
# ==============================
if mode == "Assistant" and answer:
    st.subheader("🤖 CloudTechner AI Answer")
    st.write(answer)
 
# ==============================
# Footer
# ==============================
st.markdown("---")
st.markdown("© 2025 CloudTechner — Powered by Google Cloud & Streamlit")

