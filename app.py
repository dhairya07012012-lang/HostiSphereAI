import streamlit as st
import pandas as pd
import plotly.express as px
import bcrypt
import numpy as np
from sklearn.linear_model import LinearRegression
from supabase import create_client
from openai import OpenAI
import base64

# ========================= CONFIG =========================

st.set_page_config(page_title="HostiSphere AI Enterprise", layout="wide")

SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
DEFAULT_OPENAI_KEY = st.secrets["OPENAI_API_KEY"]

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ========================= PERFORMANCE =========================

@st.cache_data(ttl=60)
def fetch_all(table):
    return supabase.table(table).select("*").execute().data

@st.cache_data(ttl=60)
def fetch_filtered(table, column, value):
    return supabase.table(table).select("*").eq(column, value).execute().data

# ========================= PASSWORD =========================

def hash_password(p):
    return bcrypt.hashpw(p.encode(), bcrypt.gensalt()).decode()

def check_password(p, h):
    return bcrypt.checkpw(p.encode(), h.encode())

# ========================= THEME =========================

def apply_theme(theme, wallpaper):
    bg = "#0e1117" if theme == "Dark" else "#f5f7fa"
    text = "white" if theme == "Dark" else "black"

    wallpaper_style = ""
    if wallpaper:
        wallpaper_style = f"""
        background-image: url('{wallpaper}');
        background-size: cover;
        background-attachment: fixed;
        """

    st.markdown(f"""
    <style>
    .stApp {{
        background: {bg};
        color: {text};
        {wallpaper_style}
    }}
    .block-container {{
        backdrop-filter: blur(10px);
        background-color: rgba(0,0,0,0.2);
        padding: 2rem;
        border-radius: 15px;
    }}
    </style>
    """, unsafe_allow_html=True)

# ========================= AUTH =========================

if "user" not in st.session_state:
    st.session_state.user = None

def signup(email, password, role):
    supabase.table("users").insert({
        "email": email,
        "password": hash_password(password),
        "role": role
    }).execute()

def login(email, password):
    res = supabase.table("users").select("*").eq("email", email).execute()
    if res.data:
        user = res.data[0]
        if check_password(password, user["password"]):
            return user
    return None

if not st.session_state.user:

    st.title("🏨 HostiSphere AI Enterprise")

    tab1, tab2 = st.tabs(["Login","Sign Up"])

    with tab1:
        e = st.text_input("Email")
        p = st.text_input("Password", type="password")
        if st.button("Login"):
            user = login(e,p)
            if user:
                st.session_state.user = user
                st.rerun()
            else:
                st.error("Invalid credentials")

    with tab2:
        ne = st.text_input("New Email")
        npw = st.text_input("New Password", type="password")
        role = st.selectbox("Role",["Owner","Manager","Staff"])
        if st.button("Create Account"):
            signup(ne,npw,role)
            st.success("Account created")

    st.stop()

# ========================= SETTINGS LOAD =========================

settings = fetch_filtered("user_settings","user_id",st.session_state.user["id"])

if settings:
    settings = settings[0]
else:
    supabase.table("user_settings").insert({
        "user_id": st.session_state.user["id"],
        "theme": "Dark"
    }).execute()
    settings = {"theme":"Dark","wallpaper":None,"openai_key":None}

apply_theme(settings["theme"], settings.get("wallpaper"))

# ========================= NAVIGATION =========================

role = st.session_state.user["role"]

pages = []

if role == "Admin":
    pages = ["Admin","Dashboard","Hotels","Bookings","Reputation","Partners","Settings"]
elif role == "Owner":
    pages = ["Dashboard","Hotels","Bookings","Reputation","Partners","Settings"]
elif role == "Manager":
    pages = ["Dashboard","Bookings","Reputation","Settings"]
else:
    pages = ["Dashboard"]

page = st.sidebar.radio("Navigation",pages)

if st.sidebar.button("Logout"):
    st.session_state.user = None
    st.rerun()

# ========================= ADMIN =========================

if page == "Admin":

    st.title("Admin Super Dashboard")

    users = fetch_all("users")
    hotels = fetch_all("hotels")
    bookings = fetch_all("bookings")

    st.metric("Total Users",len(users))
    st.metric("Total Hotels",len(hotels))

    if bookings:
        df = pd.DataFrame(bookings)
        st.metric("Global Revenue",f"${round(df['revenue'].sum(),2)}")
        st.plotly_chart(px.line(df,x="date",y="revenue"))

    st.dataframe(pd.DataFrame(users))

# ========================= DASHBOARD =========================

elif page == "Dashboard":

    st.title("Operations Dashboard")

    bookings = fetch_all("bookings")

    if bookings:
        df = pd.DataFrame(bookings)
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date")

        st.metric("Revenue",f"${round(df['revenue'].sum(),2)}")
        st.metric("Avg Occupancy",f"{round(df['occupancy'].mean(),1)}%")

        st.plotly_chart(px.line(df,x="date",y="revenue"))

        df["index"]=np.arange(len(df))
        model=LinearRegression()
        model.fit(df[["index"]],df["occupancy"])
        future=np.arange(len(df),len(df)+90).reshape(-1,1)
        preds=model.predict(future)

        st.subheader("90 Day Forecast")
        st.line_chart(preds)

# ========================= SETTINGS =========================

elif page == "Settings":

    theme=st.selectbox("Theme",["Dark","Light"],
        index=0 if settings["theme"]=="Dark" else 1)

    wallpaper=st.file_uploader("Wallpaper",type=["jpg","png"])

    api_key=st.text_input("OpenAI API Key",
        value=settings.get("openai_key") or "",
        type="password")

    if st.button("Save"):
        wp=settings.get("wallpaper")
        if wallpaper:
            encoded=base64.b64encode(wallpaper.read()).decode()
            wp=f"data:image/png;base64,{encoded}"

        supabase.table("user_settings").update({
            "theme":theme,
            "wallpaper":wp,
            "openai_key":api_key
        }).eq("user_id",st.session_state.user["id"]).execute()

        st.success("Updated")
        st.rerun()
