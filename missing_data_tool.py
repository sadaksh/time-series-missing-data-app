import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(page_title="Missing Data Checker", layout="wide")

st.title("⏳ Time Series Missing Data Checker with Timeline Plot")

# File upload
uploaded_file = st.file_uploader("Upload Time Series Data (CSV or Excel)", type=["csv", "xlsx"])

if uploaded_file:
    # Read data
    if uploaded_file.name.endswith(".csv"):
        df = pd.read_csv(uploaded_file)
    else:
        df = pd.read_excel(uploaded_file)

    st.write("### Preview of Data", df.head())

    # Select timestamp column
    timestamp_col = st.selectbox("Select Timestamp Column", df.columns)

    # Convert to datetime
    df[timestamp_col] = pd.to_datetime(df[timestamp_col], errors="coerce")
    df = df.dropna(subset=[timestamp_col])  # drop invalid datetimes
    df = df.sort_values(timestamp_col).reset_index(drop=True)

    # Check for duplicates
    duplicate_count = df.duplicated(subset=[timestamp_col]).sum()
    if duplicate_count > 0:
        st.warning(f"⚠️ Found {duplicate_count} duplicate rows with same timestamp")

        agg_option = st.selectbox(
            "How should duplicates be handled?",
            ["Keep First", "Keep Last", "Mean", "Median", "Min", "Max"],
            index=2  # Default to Mean
        )

        # Apply chosen aggregation
        if agg_option == "Keep First":
            df = df.groupby(timestamp_col).first().reset_index()
        elif agg_option == "Keep Last":
            df = df.groupby(timestamp_col).last().reset_index()
        elif agg_option == "Mean":
            df = df.groupby(timestamp_col).mean(numeric_only=True).reset_index()
        elif agg_option == "Median":
            df = df.groupby(timestamp_col).median(numeric_only=True).reset_index()
        elif agg_option == "Min":
            df = df.groupby(timestamp_col).min(numeric_only=True).reset_index()
        elif agg_option == "Max":
            df = df.groupby(timestamp_col).max(numeric_only=True).reset_index()

        st.success(f"✅ Duplicates handled using **{agg_option}**")
        st.write("### Data after handling duplicates", df.head())

    # User-defined interval
    interval = st.selectbox("Select Time Interval", ["5min", "10min", "30min", "1H", "1D"], index=0)

    # Full expected time range
    full_range = pd.date_range(start=df[timestamp_col].min(), end=df[timestamp_col].max(), freq=interval)

    # Identify missing timestamps
    missing = full_range.difference(df[timestamp_col])

    # ---- Summary Metrics ----
    actual_points = df[timestamp_col].nunique()
    expected_points = len(full_range)
    missing_points = expected_points - actual_points
    availability_pct = round((actual_points / expected_points) * 100, 2) if expected_points > 0 else 0

    st.write("### 📊 Data Availability Summary")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Actual Points", actual_points)
    col2.metric("Expected Points", expected_points)
    col3.metric("Missing Points", missing_points)
    col4.metric("Availability (%)", f"{availability_pct}%")

    # ---- Missing Data Info ----
    st.write(f"### Missing Data Info")
    if missing.empty:
        st.success("✅ No missing data found!")
    else:
        st.warning(f"⚠️ Found {len(missing)} missing timestamps")

        # Group consecutive missing timestamps into durations
        missing_df = pd.DataFrame(missing, columns=["Missing_Timestamp"])
        missing_df["Gap_Start"] = missing_df["Missing_Timestamp"].where(
            missing_df["Missing_Timestamp"].diff() != pd.Timedelta(interval)
        )
        missing_df["Gap_Start"].fillna(method="ffill", inplace=True)

        gaps = (
            missing_df.groupby("Gap_Start")
            .agg(Start=("Missing_Timestamp", "min"),
                 End=("Missing_Timestamp", "max"),
                 Count=("Missing_Timestamp", "count"))
            .reset_index(drop=True)
        )

        # Add user interval info
        gaps["Time_Interval"] = interval

        # Duration column
        gaps["Duration"] = gaps["Start"].astype(str) + " → " + gaps["End"].astype(str)

        # Final Output
        output = gaps[["Duration", "Time_Interval", "Count"]]

        st.write("### Missing Duration Table")
        st.dataframe(output)

        # Download option
        csv = output.to_csv(index=False).encode("utf-8")
        st.download_button("Download Missing Data Report", data=csv, file_name="missing_data_report.csv", mime="text/csv")

        # -------------------
        # Timeline Plot with Data
        # -------------------
        st.write("### 📉 Timeline of Data vs Missing Intervals")

        fig = go.Figure()

        # Add actual data points (if numeric columns exist)
        numeric_cols = df.select_dtypes(include="number").columns.tolist()
        if numeric_cols:
            y_col = st.selectbox("Select Value Column to Plot", numeric_cols, index=0)
            fig.add_trace(go.Scatter(
                x=df[timestamp_col],
                y=df[y_col],
                mode="markers+lines",
                name="Data",
                line=dict(color="blue"),
                marker=dict(size=5)
            ))

        # Add missing intervals as shaded regions
        for _, row in gaps.iterrows():
            fig.add_vrect(
                x0=row["Start"], x1=row["End"],
                fillcolor="red", opacity=0.3,
                layer="below", line_width=0,
                annotation_text="Missing", annotation_position="top left"
            )

        fig.update_layout(
            title="Data Points with Missing Intervals Highlighted",
            xaxis_title="Time",
            yaxis_title=y_col if numeric_cols else "Value",
            showlegend=True
        )

        st.plotly_chart(fig, use_container_width=True)
