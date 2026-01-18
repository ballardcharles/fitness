import streamlit as st
import pandas as pd
import sqlite3
from datetime import date
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# --- DATABASE SETUP ---
def init_db():
    conn = sqlite3.connect('fitness_data.db')
    c = conn.cursor()
    # Create table if it doesn't exist
    c.execute('''
        CREATE TABLE IF NOT EXISTS daily_stats (
            date TEXT PRIMARY KEY,
            weight REAL,
            active_calories INTEGER,
            exercise_mins INTEGER,
            workout_type TEXT
        )
    ''')
    conn.commit()
    return conn

conn = init_db()

# --- STREAMLIT UI ---
st.title("📈 Fitness Process Control")
st.markdown("Track signals, ignore noise, and improve capability.")

# Sidebar for Data Entry
with st.sidebar:
    st.header("Log Daily Stats")
    log_date = st.date_input("Date", date.today())
    weight = st.number_input("Weight (lbs/kg)", min_value=0.0, step=0.1)
    calories = st.number_input("Active Calories Burned", min_value=0, step=10)
    minutes = st.number_input("Exercise Minutes", min_value=0, step=1)
    workout_type = st.selectbox("Workout Type", ["Strength", "Cardio", "Yoga", "Rest"])
    
    if st.button("Save Entry"):
        try:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO daily_stats (date, weight, active_calories, exercise_mins, workout_type)
                VALUES (?, ?, ?, ?, ?)
            ''', (str(log_date), weight, calories, minutes, workout_type))
            conn.commit()
            st.success("Data saved successfully!")
        except Exception as e:
            st.error(f"Error: {e}")

# --- DATA ANALYSIS SECTION ---
st.header("Daily Logs")
df = pd.read_sql_query("SELECT * FROM daily_stats ORDER BY date DESC", conn)

if not df.empty:
    st.dataframe(df, use_container_width=True)
    
    # Simple Visual to get started
    st.subheader("Weight Trend")
    st.line_chart(data=df, x='date', y='weight')
else:
    st.info("No data logged yet. Use the sidebar to add your first entry!")

def calculate_imr_limits(df, column):
    if len(df) < 2:
        return df, None, None, None
    
    # 1. Calculate Moving Range (absolute difference between rows)
    df['MR'] = df[column].diff().abs()
    
    # 2. Calculate Averages
    x_bar = df[column].mean()
    mr_bar = df['MR'].mean()
    
    # 3. Calculate Limits (using the 2.66 constant for n=2)
    ucl = x_bar + (2.66 * mr_bar)
    lcl = x_bar - (2.66 * mr_bar)
    
    return df, x_bar, ucl, lcl

def plot_imr_combined(df, column):
    # 1. Calculate the data
    df = df.sort_values('date')
    df['MR'] = df[column].diff().abs()
    
    x_bar = df[column].mean()
    mr_bar = df['MR'].mean()
    
    # Constants for n=2
    ucl_i = x_bar + (2.66 * mr_bar)
    lcl_i = x_bar - (2.66 * mr_bar)
    ucl_mr = mr_bar * 3.267
    
    # 2. Create Subplots (2 rows, 1 column)
    fig = make_subplots(rows=2, cols=1, 
                        shared_xaxes=True,
                        vertical_spacing=0.1,
                        subplot_titles=(f'I-Chart: Individual {column}', 'MR-Chart: Moving Range'))

    # --- TOP CHART: INDIVIDUALS ---
    fig.add_trace(go.Scatter(x=df['date'], y=df[column], name='Value', mode='lines+markers'), row=1, col=1)
    fig.add_hline(y=x_bar, line_dash="dash", line_color="green", row=1, col=1)
    fig.add_hline(y=ucl_i, line_dash="dot", line_color="red", row=1, col=1)
    fig.add_hline(y=lcl_i, line_dash="dot", line_color="red", row=1, col=1)

    # --- BOTTOM CHART: MOVING RANGE ---
    fig.add_trace(go.Scatter(x=df['date'], y=df['MR'], name='Moving Range', mode='lines+markers', line_color='orange'), row=2, col=1)
    fig.add_hline(y=mr_bar, line_dash="dash", line_color="green", row=2, col=1)
    fig.add_hline(y=ucl_mr, line_dash="dot", line_color="red", row=2, col=1)

    fig.update_layout(height=700, showlegend=False)
    return fig

# In your main Streamlit app code:
if not df.empty:
    # 1. Sort data by date (Crucial for Moving Range!)
    df_sorted = df.sort_values('date')
    
    # 2. Call the NEW combined function
    # Note: Make sure you've pasted the 'plot_imr_combined' function above this
    combined_fig = plot_imr_combined(df_sorted, 'weight')
    
    # 3. Display the chart
    st.plotly_chart(combined_fig, use_container_width=True)
    
    # 4. Display the raw data table below
    with st.expander("View Raw Data Log"):
        st.dataframe(df_sorted.sort_index(ascending=False), use_container_width=True)
else:
    st.info("No data logged yet. Add your first entry in the sidebar!")