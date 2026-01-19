import streamlit as st
import pandas as pd
import numpy as np
import sqlite3
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import date

# --- 1. DATABASE LOGIC ---
def init_db():
    conn = sqlite3.connect('fitness_data.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS daily_stats (
            date TEXT PRIMARY KEY,
            weight REAL,
            active_calories INTEGER,
            exercise_mins INTEGER,
            workout_type TEXT
        )
    ''')
    c.execute('''
    CREATE TABLE IF NOT EXISTS nutrition (
        date TEXT PRIMARY KEY,
        calories_in INTEGER,
        protein INTEGER,
        carbs INTEGER,
        fat INTEGER
    )
    ''')
    conn.commit()
    return conn

conn = init_db()

# --- 2. STATISTICAL & PLOTTING LOGIC ---
def plot_imr_combined(df, column, title):
    # Ensure data is sorted by date for moving range calculation
    df = df.sort_values('date')
    
    # Calculate I-Chart Components
    x_bar = df[column].mean()
    # Calculate Moving Range (MR)
    df['MR'] = df[column].diff().abs()
    mr_bar = df['MR'].mean()
    
    # Constants for n=2 (Standard SPC values)
    ucl_i = x_bar + (2.66 * mr_bar)
    lcl_i = max(0, x_bar - (2.66 * mr_bar)) # Cannot be negative
    ucl_mr = mr_bar * 3.267
    
    # Create Subplots
    fig = make_subplots(
        rows=2, cols=1, 
        shared_xaxes=True,
        vertical_spacing=0.1,
        subplot_titles=(f'I-Chart (Individual {title})', f'MR-Chart (Moving Range {title})')
    )

    # --- TOP CHART: INDIVIDUALS ---
    fig.add_trace(go.Scatter(x=df['date'], y=df[column], name='Value', mode='lines+markers'), row=1, col=1)
    fig.add_hline(y=x_bar, line_dash="dash", line_color="green", row=1, col=1, annotation_text="Mean")
    fig.add_hline(y=ucl_i, line_dash="dot", line_color="red", row=1, col=1, annotation_text="UCL")
    fig.add_hline(y=lcl_i, line_dash="dot", line_color="red", row=1, col=1, annotation_text="LCL")

    # --- BOTTOM CHART: MOVING RANGE ---
    fig.add_trace(go.Scatter(x=df['date'], y=df['MR'], name='Moving Range', mode='lines+markers', line_color='orange'), row=2, col=1)
    fig.add_hline(y=mr_bar, line_dash="dash", line_color="green", row=2, col=1, annotation_text="Avg MR")
    fig.add_hline(y=ucl_mr, line_dash="dot", line_color="red", row=2, col=1, annotation_text="UCL")

    fig.update_layout(height=600, showlegend=False, margin=dict(l=20, r=20, t=40, b=20))
    return fig

def calculate_capability(df, column, lsl, usl):
    if len(df) < 5: # Need a few points for a valid standard deviation
        return None, None
    
    mean = df[column].mean()
    sigma = df[column].std()
    
    if sigma == 0: return 0, 0
    
    # Calculate Cp
    cp = (usl - lsl) / (6 * sigma)
    
    # Calculate Cpk
    cpu = (usl - mean) / (3 * sigma)
    cpl = (mean - lsl) / (3 * sigma)
    cpk = min(cpu, cpl)
    
    return round(cp, 2), round(cpk, 2)

# --- 3. STREAMLIT INTERFACE ---
st.set_page_config(page_title="Fitness & Nutrition SPC", layout="wide")
st.title("🥗 Fitness & Nutrition Process Control")

with st.sidebar:
    menu = st.radio("Select Input Mode", ["Physical Stats", "Nutrition"])
    
    if menu == "Physical Stats":
        with st.form("stats_form"):
            log_date = st.date_input("Date", date.today())
            weight = st.number_input("Weight", min_value=0.0, step=0.1)
            active_cal = st.number_input("Active Burned", min_value=0)
            mins = st.number_input("Minutes", min_value=0)
            w_type = st.selectbox("Type", ["Strength", "Cardio", "Yoga", "Rest"])
            if st.form_submit_button("Save Stats"):
                conn.execute("INSERT OR REPLACE INTO daily_stats VALUES (?,?,?,?,?)", 
                             (str(log_date), weight, active_cal, mins, w_type))
                conn.commit()
                st.success("Stats Saved!")
    else:
        with st.form("nutrition_form"):
            log_date = st.date_input("Date", date.today())
            cal_in = st.number_input("Calories Consumed", min_value=0)
            protein = st.number_input("Protein (g)", min_value=0)
            carbs = st.number_input("Carbs (g)", min_value=0)
            fat = st.number_input("Fat (g)", min_value=0)
            if st.form_submit_button("Save Nutrition"):
                conn.execute("INSERT OR REPLACE INTO nutrition VALUES (?,?,?,?,?)", 
                             (str(log_date), cal_in, protein, carbs, fat))
                conn.commit()
                st.success("Nutrition Saved!")

# --- 4. DATA ANALYSIS ---
df_stats = pd.read_sql_query("SELECT * FROM daily_stats", conn)
df_nutr = pd.read_sql_query("SELECT * FROM nutrition", conn)

if not df_stats.empty and len(df_stats) >= 2:
    df_sorted = df_stats.sort_values('date')
    
    # NEW: Merge datasets for correlation storytelling
    df_combined = pd.merge(df_sorted, df_nutr, on='date', how='inner')

    tab1, tab2, tab3, tab4 = st.tabs(["Weight", "Activity", "Nutrition", "Energy Balance"])

    with tab1:
        # (Your existing Weight Capability and I-MR code here)
        st.plotly_chart(plot_imr_combined(df_sorted, 'weight', 'Weight'), use_container_width=True)

    with tab3:
        if not df_nutr.empty:
            st.subheader("Daily Macro Distribution")
            # Simple bar chart for macros
            nutr_sorted = df_nutr.sort_values('date')
            fig_macro = px.bar(nutr_sorted, x='date', y=['protein', 'carbs', 'fat'], title="Macros Over Time")
            st.plotly_chart(fig_macro, use_container_width=True)
        else:
            st.info("Log nutrition data to see analysis.")

    with tab4:
        st.subheader("Net Energy Analysis")
        if not df_combined.empty:
            # Storytelling: Calculate Net Calories
            df_combined['net_calories'] = df_combined['calories_in'] - df_combined['active_calories'] - 2000 # Assuming 2000 BMR
            st.line_chart(df_combined, x='date', y='net_calories')
            st.caption("Net Calories = (In) - (Active Burn) - (Estimated 2000 BMR)")
        else:
            st.info("Log both stats and nutrition for the same dates to see the balance.")