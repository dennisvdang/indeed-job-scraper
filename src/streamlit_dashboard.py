#!/usr/bin/env python3
"""
Indeed Job Dashboard

Interactive dashboard for visualizing Indeed job scraper data using Streamlit.
Run with: streamlit run src/streamlit_dashboard.py

Author: Dennis
"""

import os
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime
from functools import partial

import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import matplotlib.pyplot as plt
from wordcloud import WordCloud, STOPWORDS
import numpy as np


def find_csv_files(directory: str = "data/raw") -> List[Path]:
    """Find all CSV files in the specified directory."""
    return list(Path(directory).glob("**/*.csv"))


def load_data(file_path: Path) -> pd.DataFrame:
    """Load and prepare data from CSV file."""
    df = pd.read_csv(file_path)
    
    # Standardize column names
    df.columns = [col.lower().replace(' ', '_') for col in df.columns]
    
    # Convert date columns to datetime
    for date_col in ['date_scraped', 'date_posted']:
        if date_col in df.columns:
            df[date_col] = pd.to_datetime(df[date_col])
    
    # Create job_id if missing
    if 'job_id' not in df.columns:
        df['job_id'] = df.index.map(f"{file_path.stem}_{{}}".format)
    
    return df


@st.cache_data(ttl=60, show_spinner=True)
def load_multiple_datasets() -> pd.DataFrame:
    """Load and combine multiple CSV files with caching.
    
    The cache expires after 60 seconds (ttl=60) to ensure fresh data is loaded periodically.
    """
    files = find_csv_files()
    if not files:
        st.error("No CSV files found in the data/raw directory. Please add data files.")
        return pd.DataFrame()
    
    # Log number of files found to help with debugging
    st.session_state["num_files_found"] = len(files)
    st.session_state["last_refresh_time"] = datetime.now().strftime("%H:%M:%S")
    
    dfs = [load_data(file).assign(source_file=file.name) for file in files]
    combined_df = pd.concat(dfs, ignore_index=True)
    
    # Remove duplicate jobs
    if 'job_id' in combined_df.columns:
        combined_df.drop_duplicates(subset=['job_id'], keep='first', inplace=True)
    
    # Store job count in session state for reference
    st.session_state["total_job_count"] = len(combined_df)
    
    return combined_df


def check_required_columns(df: pd.DataFrame, required_cols: List[str]) -> bool:
    """Check if dataframe has required columns with valid data."""
    return all(col in df.columns and not df[col].isna().all() for col in required_cols)


def create_bar_chart(df: pd.DataFrame, column: str, title: str, limit: int = 20) -> Optional[go.Figure]:
    """Create a horizontal bar chart for counting values in a column."""
    if not check_required_columns(df, [column]):
        return None
    
    counts = df[column].value_counts().reset_index().head(limit)
    counts.columns = [column.title(), 'Count']
    
    fig = px.bar(
        counts, x='Count', y=column.title(),
        orientation='h', title=title,
        color='Count', color_continuous_scale='Viridis'
    )
    fig.update_layout(yaxis={'categoryorder': 'total ascending'})
    return fig


def create_histogram(
    df: pd.DataFrame, 
    column: str = 'salary_midpoint_yearly', 
    title: Optional[str] = None
) -> Optional[go.Figure]:
    """Create a histogram with median line for numerical data."""
    if not check_required_columns(df, [column]):
        return None
    
    # Use provided title or generate one
    title = title or f'{column.replace("_", " ").title()} Distribution'
    
    # Filter for valid data
    data = df[column].dropna()
    if len(data) < 5:
        return None
    
    # Remove outliers (5th to 95th percentile)
    quantiles = data.quantile([0.05, 0.95])
    filtered_df = df[(df[column] >= quantiles.iloc[0]) & (df[column] <= quantiles.iloc[1])]
    
    median_value = filtered_df[column].median()
    
    fig = px.histogram(
        filtered_df, x=column, title=title,
        labels={column: column.replace('_', ' ').title()},
        color_discrete_sequence=['#2E86C1'], nbins=20
    )
    
    # Add median line
    is_salary = 'salary' in column
    median_text = f"Median: ${median_value:,.0f}" if is_salary else f"Median: {median_value:.1f}"
    
    fig.add_vline(
        x=median_value, line_dash="dash", line_color="red",
        annotation_text=median_text,
        annotation_position="top right"
    )
    
    return fig


def create_pie_chart(df: pd.DataFrame, column: str, title: str) -> Optional[go.Figure]:
    """Create a pie chart for categorical data."""
    if not check_required_columns(df, [column]):
        return None
    
    value_counts = df[column].value_counts().reset_index()
    value_counts.columns = [column.title(), 'Count']
    
    fig = px.pie(
        value_counts, values='Count', names=column.title(),
        title=title, color_discrete_sequence=px.colors.qualitative.Safe
    )
    fig.update_traces(textposition='inside', textinfo='percent+label')
    return fig


def create_box_plot(df: pd.DataFrame, x: str, y: str, title: str) -> Optional[go.Figure]:
    """Create a box plot for comparing distributions across categories."""
    if not check_required_columns(df, [x, y]):
        return None
    
    filtered_df = df.dropna(subset=[x, y])
    if len(filtered_df) < 5:
        return None
    
    fig = px.box(
        filtered_df, x=x, y=y, title=title,
        labels={col: col.replace('_', ' ').title() for col in [x, y]},
        color=x
    )
    return fig


def create_choropleth(df: pd.DataFrame) -> Optional[go.Figure]:
    """Create a US choropleth map of job counts by state."""
    if not check_required_columns(df, ['state']):
        return None
    
    state_counts = df['state'].value_counts().reset_index()
    state_counts.columns = ['State', 'Job Count']
    
    fig = px.choropleth(
        state_counts, locations='State', locationmode='USA-states',
        color='Job Count', scope='usa', title='Job Distribution by State',
        color_continuous_scale='Viridis'
    )
    return fig


def create_chart(df: pd.DataFrame, chart_type: str, **kwargs) -> Optional[go.Figure]:
    """Create various chart types based on parameters."""
    chart_creators = {
        "count": partial(create_bar_chart, df=df, **kwargs),
        "histogram": partial(create_histogram, df=df, **kwargs),
        "pie": partial(create_pie_chart, df=df, **kwargs),
        "box": partial(create_box_plot, df=df, **kwargs),
        "map": partial(create_choropleth, df=df)
    }
    
    creator = chart_creators.get(chart_type)
    return creator() if creator else None


def create_wordcloud(df: pd.DataFrame, column: str = 'title') -> Optional[plt.Figure]:
    """Create a word cloud from text data in specified column."""
    if not check_required_columns(df, [column]):
        return None
    
    text = ' '.join(df[column].dropna().astype(str))
    
    wordcloud = WordCloud(
        width=800, height=400, 
        background_color='white',
        colormap='viridis', 
        max_words=100, 
        contour_width=1,
        stopwords=STOPWORDS
    ).generate(text)
    
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.imshow(wordcloud, interpolation='bilinear')
    ax.axis('off')
    plt.tight_layout()
    
    return fig


def create_salary_by_location_chart(df: pd.DataFrame) -> Optional[go.Figure]:
    """Create chart of salaries grouped by location."""
    if not check_required_columns(df, ['salary_midpoint_yearly']):
        return None
    
    # Find best location column (state, city, zip)
    location_fields = ['state', 'city', 'zip']
    loc_field = next((field for field in location_fields 
                     if field in df.columns and df[field].notna().sum() > 3), None)
    
    if not loc_field:
        return None
    
    valid_data = df.dropna(subset=[loc_field, 'salary_midpoint_yearly'])
    if len(valid_data) < 5:
        return None
    
    # Group by location and get statistics
    location_stats = valid_data.groupby(loc_field)['salary_midpoint_yearly'].agg(['mean', 'median', 'count'])
    location_stats = location_stats.sort_values('median', ascending=False)
    
    # Get top locations
    min_count = 2
    top_locations = location_stats[location_stats['count'] >= min_count].head(15)
    if len(top_locations) < 3:
        top_locations = location_stats.head(10)
    
    plot_data = df[df[loc_field].isin(top_locations.index)]
    
    # Create appropriate chart based on data amount
    if len(plot_data) >= 15:
        fig = px.box(
            plot_data, x=loc_field, y='salary_midpoint_yearly',
            title=f'Salary Distribution by {loc_field.title()}',
            labels={loc_field: loc_field.title(), 'salary_midpoint_yearly': 'Annual Salary ($)'},
            category_orders={loc_field: top_locations.index.tolist()}
        )
    else:
        bar_data = top_locations.reset_index()
        bar_data.columns = [loc_field.title(), 'Mean', 'Median', 'Count']
        
        fig = px.bar(
            bar_data, x=loc_field.title(), y='Median',
            title=f'Median Salary by {loc_field.title()}',
            text='Count', color='Median',
            labels={'Median': 'Median Annual Salary ($)'},
            color_continuous_scale='Viridis'
        )
        fig.update_traces(texttemplate='%{text} jobs', textposition='outside')
    
    fig.update_layout(
        xaxis_title=loc_field.title(),
        yaxis_title='Annual Salary ($)',
        xaxis={'categoryorder': 'array', 'categoryarray': top_locations.index.tolist()}
    )
    
    return fig


def apply_date_filter(df: pd.DataFrame) -> Tuple[pd.DataFrame, bool]:
    """Apply date filter to the dataframe."""
    if 'date_posted' not in df.columns:
        return df, False
    
    min_date = df['date_posted'].min().date()
    max_date = df['date_posted'].max().date()
    
    # Set datetime format to mm/dd/yyyy
    st.sidebar.markdown(
        "<style>input[type=date] {min-height: 36px;}</style>", 
        unsafe_allow_html=True
    )
    
    date_range = st.sidebar.date_input(
        "Job Posted Date Range",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date,
        format="MM/DD/YYYY"
    )
    
    if len(date_range) == 2:
        start_date, end_date = date_range
        return df[
            (df['date_posted'].dt.date >= start_date) & 
            (df['date_posted'].dt.date <= end_date)
        ], True
    return df, False


def apply_filters(df: pd.DataFrame) -> pd.DataFrame:
    """Apply all dashboard filters to the dataframe."""
    filtered_df = df.copy()
    
    # Job title query filter
    if 'queried_job_title' in filtered_df.columns:
        job_title_queries = sorted(filtered_df['queried_job_title'].dropna().unique())
        selected_queries = st.sidebar.multiselect("Job Title Queries", job_title_queries)
        if selected_queries:
            filtered_df = filtered_df[filtered_df['queried_job_title'].isin(selected_queries)]
    
    # Date filter
    filtered_df, _ = apply_date_filter(filtered_df)
    
    # Location filter
    if 'state' in filtered_df.columns:
        states = sorted(filtered_df['state'].dropna().unique())
        selected_states = st.sidebar.multiselect("Location", states)
        if selected_states:
            filtered_df = filtered_df[filtered_df['state'].isin(selected_states)]
    
    # Generic categorical filters
    for column, label in [('work_setting', 'Work Setting'), ('job_type', 'Job Type')]:
        if column in filtered_df.columns:
            values = ['All'] + sorted(filtered_df[column].dropna().unique())
            selected = st.sidebar.selectbox(label, values)
            if selected != 'All':
                filtered_df = filtered_df[filtered_df[column] == selected]
    
    # Salary filter
    if 'salary_midpoint_yearly' in filtered_df.columns:
        show_only_with_salary = st.sidebar.checkbox("Show only jobs with salary data")
        if show_only_with_salary:
            filtered_df = filtered_df[filtered_df['salary_midpoint_yearly'].notna()]
    
    return filtered_df


def display_metrics(df: pd.DataFrame) -> None:
    """Display key metrics at the top of the dashboard."""
    # First row of metrics
    cols = st.columns(3)
    
    # Total jobs
    with cols[0]:
        st.metric("Total Jobs", len(df))
    
    # Company count
    with cols[1]:
        if 'company' in df.columns:
            st.metric("Companies", df['company'].nunique())
        else:
            st.metric("Companies", "N/A")
    
    # Median salary
    with cols[2]:
        if 'salary_midpoint_yearly' in df.columns and not df['salary_midpoint_yearly'].isna().all():
            median_salary = df['salary_midpoint_yearly'].median()
            st.metric("Median Salary", f"${median_salary:,.0f}")
        else:
            st.metric("Median Salary", "N/A")
    
    # Second row for min/max salary metrics
    if 'salary_min_yearly' in df.columns and 'salary_max_yearly' in df.columns:
        salary_cols = st.columns(3)
        
        with salary_cols[0]:
            min_salary = df['salary_min_yearly'].median()
            st.metric("Median Min Salary", f"${min_salary:,.0f}")
        
        with salary_cols[1]:
            mid_salary = df['salary_midpoint_yearly'].median()
            st.metric("Median Mid Salary", f"${mid_salary:,.0f}")
        
        with salary_cols[2]:
            max_salary = df['salary_max_yearly'].median()
            st.metric("Median Max Salary", f"${max_salary:,.0f}")


def display_overview_tab(df: pd.DataFrame) -> None:
    """Display content for the Overview tab."""
    col1, col2 = st.columns(2)
    
    with col1:
        # Word cloud of job titles
        if wordcloud_fig := create_wordcloud(df):
            st.subheader("Popular Job Titles")
            st.pyplot(wordcloud_fig)
        
        # Company counts
        if company_chart := create_chart(df, "count", column='company', title='Top 20 Companies by Job Count'):
            st.plotly_chart(company_chart, use_container_width=True)
    
    with col2:
        # Location map
        if location_map := create_chart(df, "map"):
            st.plotly_chart(location_map, use_container_width=True)
        
        # Work setting chart
        if 'work_setting' in df.columns:
            if work_setting_fig := create_chart(df, "pie", column='work_setting', title='Job Distribution by Work Setting'):
                st.plotly_chart(work_setting_fig, use_container_width=True)


def create_salary_location_boxplot(df: pd.DataFrame) -> Optional[go.Figure]:
    """Create a boxplot with scatter points of salary by state and city."""
    if not check_required_columns(df, ['salary_midpoint_yearly']):
        return None
    
    # Check if we have state data
    has_state = 'state' in df.columns and not df['state'].isna().all()
    has_city = 'city' in df.columns and not df['city'].isna().all()
    
    if not has_state:
        st.warning("State information is required for this visualization but was not found in the data.")
        return None
    
    # Filter for rows with salary and state data
    filtered_df = df.dropna(subset=['salary_midpoint_yearly', 'state']).copy()
    if len(filtered_df) < 5:
        return None
    
    # Remove salary outliers
    # Calculate the Q1, Q3 and IQR
    Q1 = filtered_df['salary_midpoint_yearly'].quantile(0.10)
    Q3 = filtered_df['salary_midpoint_yearly'].quantile(0.90)
    IQR = Q3 - Q1
    
    # Define bounds for outliers (using 1.5 * IQR)
    lower_bound = Q1 - 1.5 * IQR
    upper_bound = Q3 + 1.5 * IQR
    
    # Filter out the outliers
    filtered_df = filtered_df[
        (filtered_df['salary_midpoint_yearly'] >= lower_bound) & 
        (filtered_df['salary_midpoint_yearly'] <= upper_bound)
    ]
    
    # Create location field for hover info
    if has_city:
        filtered_df['location'] = filtered_df.apply(
            lambda x: f"{x['city']}, {x['state']}" if pd.notna(x['city']) else x['state'], 
            axis=1
        )
        
        # Create a city category for coloring
        # Get top cities for better visualization
        top_cities = filtered_df['city'].value_counts().nlargest(15).index.tolist()
        filtered_df['city_category'] = filtered_df['city'].apply(
            lambda x: x if pd.notna(x) and x in top_cities else "Other Cities"
        )
    else:
        filtered_df['location'] = filtered_df['state']
        filtered_df['city_category'] = "Unknown"
    
    # Only include states with sufficient data
    state_counts = filtered_df['state'].value_counts()
    valid_states = state_counts[state_counts >= 3].index.tolist()
    filtered_df = filtered_df[filtered_df['state'].isin(valid_states)]
    
    if len(filtered_df) < 5:
        st.warning("Not enough data points for each state after filtering.")
        return None
    
    # Create the figure with both box plot and scatter points
    fig = go.Figure()
    
    # First, add box plots for each state
    for state in sorted(filtered_df['state'].unique()):
        state_data = filtered_df[filtered_df['state'] == state]
        fig.add_trace(go.Box(
            x=[state] * len(state_data),
            y=state_data['salary_midpoint_yearly'],
            name=state,
            boxpoints=False,  # Don't show points with the box plot as we'll add scatter points separately
            marker_color='rgba(200,200,200,0.5)',  # Light grey boxes
            line_color='rgba(100,100,100,0.8)',
            showlegend=False,
            hoverinfo='skip'  # Skip hover for box plots
        ))
    
    # Then, add scatter points colored by city
    for city_cat in sorted(filtered_df['city_category'].unique()):
        city_data = filtered_df[filtered_df['city_category'] == city_cat]
        
        # Add jitter to x-coordinates to spread points horizontally within each state
        jitter = np.random.normal(0, 0.1, size=len(city_data))
        x_with_jitter = [f"{state}{j}" for state, j in zip(city_data['state'], jitter)]
        
        fig.add_trace(go.Scatter(
            x=city_data['state'],
            y=city_data['salary_midpoint_yearly'],
            mode='markers',
            marker=dict(
                size=6,
                opacity=0.7,
                line=dict(width=1, color='DarkSlateGrey')
            ),
            name=city_cat,
            customdata=np.stack((
                city_data['title'].values,
                city_data['company'].values if 'company' in city_data.columns else np.array(['Unknown'] * len(city_data)),
                city_data['location'].values
            ), axis=-1),
            hovertemplate='<b>%{customdata[0]}</b><br>Salary: $%{y:,.0f}<br>Company: %{customdata[1]}<br>Location: %{customdata[2]}<extra></extra>'
        ))
    
    # Update layout
    fig.update_layout(
        title='Salary Distribution by State and City',
        xaxis_title='State',
        yaxis_title='Annual Salary ($)',
        boxmode='group',
        height=700,
        showlegend=True,
        legend_title_text='City',
        xaxis={'categoryorder': 'array', 'categoryarray': sorted(filtered_df['state'].unique())},
        yaxis=dict(tickprefix='$', tickformat=',')
    )
    
    return fig


def create_salary_state_choropleth(df: pd.DataFrame) -> Optional[go.Figure]:
    """Create a US choropleth map of median salary by state."""
    if not check_required_columns(df, ['state', 'salary_midpoint_yearly']):
        return None
    
    # Group by state and get median salary
    state_salary = df.groupby('state')['salary_midpoint_yearly'].agg(['median', 'count']).reset_index()
    
    # Filter states with at least 2 data points
    state_salary = state_salary[state_salary['count'] >= 2]
    
    if len(state_salary) < 3:
        return None
    
    fig = px.choropleth(
        state_salary,
        locations='state',
        locationmode='USA-states',
        color='median',
        scope='usa',
        title='Median Salary by State',
        color_continuous_scale='Viridis',
        labels={'median': 'Median Salary ($)'}
    )
    
    # Add count as hover data
    fig.update_traces(
        hovertemplate='<b>%{location}</b><br>Median Salary: $%{z:,.0f}<br>Job Count: %{customdata}<extra></extra>',
        customdata=state_salary['count']
    )
    
    return fig


def create_salary_city_chart(df: pd.DataFrame) -> Optional[go.Figure]:
    """Create chart of median salary by top cities."""
    if not check_required_columns(df, ['city', 'state', 'salary_midpoint_yearly']):
        return None
    
    # Create location column combining city and state
    df = df.copy()
    df['location'] = df.apply(lambda row: f"{row['city']}, {row['state']}" 
                             if pd.notna(row['city']) and pd.notna(row['state']) 
                             else None, axis=1)
    
    # Group by location and calculate median salary
    location_salary = df.groupby('location')['salary_midpoint_yearly'].agg(['median', 'count']).reset_index()
    
    # Filter locations with enough data points
    location_salary = location_salary[location_salary['count'] >= 2]
    
    if len(location_salary) < 3:
        return None
    
    # Sort by median salary and get top 15 cities
    top_cities = location_salary.sort_values('median', ascending=False).head(15)
    
    fig = px.bar(
        top_cities,
        x='location',
        y='median',
        title='Median Salary in Top 15 Cities',
        labels={'location': 'City', 'median': 'Median Salary ($)', 'count': 'Job Count'},
        text='count',
        color='median',
        color_continuous_scale='Viridis'
    )
    
    fig.update_traces(
        texttemplate='%{text} jobs',
        textposition='outside'
    )
    
    fig.update_layout(
        xaxis={'categoryorder': 'total descending', 'tickangle': 45},
        xaxis_title='City',
        yaxis_title='Median Annual Salary ($)'
    )
    
    return fig


def display_salary_tab(df: pd.DataFrame) -> None:
    """Display content for the Salary Analysis tab."""
    if 'salary_midpoint_yearly' not in df.columns:
        st.write("No salary data available.")
        return
    
    # Row 1: Salary distribution histogram and Box plot by work setting
    col1, col2 = st.columns(2)
    
    # Salary distribution histogram
    with col1:
        if salary_fig := create_chart(df, "histogram", column='salary_midpoint_yearly', title='Annual Salary Distribution (Midpoint)'):
            st.plotly_chart(salary_fig, use_container_width=True)
    
    # Salary by work setting
    with col2:
        if 'work_setting' in df.columns:
            if salary_by_setting_fig := create_chart(
                df, "box", x='work_setting', y='salary_midpoint_yearly', 
                title='Salary Distribution by Work Setting'
            ):
                st.plotly_chart(salary_by_setting_fig, use_container_width=True)
    
    # Row 2: Salary by state and city - full width
    st.subheader("Salary by State and City")
    
    if salary_location_fig := create_salary_location_boxplot(df):
        st.plotly_chart(salary_location_fig, use_container_width=True)
    else:
        st.info("Not enough data to create the salary visualization. Ensure states and salary data are available.")
    
    # Row 3: Location-based salary intelligence
    st.subheader("Location-Based Salary Intelligence")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if salary_state_map := create_salary_state_choropleth(df):
            st.plotly_chart(salary_state_map, use_container_width=True)
    
    with col2:
        if salary_city_chart := create_salary_city_chart(df):
            st.plotly_chart(salary_city_chart, use_container_width=True)
    
    # Row 4: Salary statistics table
    st.subheader("Detailed Salary Statistics")
    
    percentiles = [0.1, 0.25, 0.5, 0.75, 0.9]
    percentile_names = ['10th', '25th', '50th (Median)', '75th', '90th']
    
    basic_stats = df['salary_midpoint_yearly'].describe()
    percentile_stats = df['salary_midpoint_yearly'].quantile(percentiles)
    
    # Combine stats into a dataframe
    all_stats = pd.DataFrame({
        'Statistic': ['Count', 'Mean', 'Standard Deviation', 'Minimum'] + percentile_names + ['Maximum'],
        'Value': [
            basic_stats['count'],
            basic_stats['mean'],
            basic_stats['std'],
            basic_stats['min'],
            *percentile_stats.values,
            basic_stats['max']
        ]
    })
    
    # Format values as currency except for count
    all_stats['Value'] = all_stats.apply(
        lambda row: f"${row['Value']:,.2f}" 
                   if row['Statistic'] != 'Count' and isinstance(row['Value'], (int, float)) 
                   else f"{row['Value']:,.0f}", 
        axis=1
    )
    
    st.dataframe(all_stats, hide_index=True)


def get_field_display_value(row: pd.Series, field: str, default: str = "Unknown") -> str:
    """Get display value for a field with appropriate formatting."""
    if field not in row or pd.isna(row[field]):
        return default
        
    if field == 'salary_midpoint_yearly':
        return f"${row[field]:,.0f}"
    
    if field == 'date_posted' and hasattr(row[field], 'strftime'):
        return row[field].strftime('%m/%d/%y')
    
    return str(row[field])


def get_location_display(row: pd.Series) -> str:
    """Extract formatted location from row data."""
    if 'city' in row and 'state' in row and pd.notna(row['city']) and pd.notna(row['state']):
        return f"{row['city']}, {row['state']}"
    if 'state' in row and pd.notna(row['state']):
        return row['state']
    if 'city' in row and pd.notna(row['city']):
        return row['city']
    return "Unknown"


def get_job_url(row: pd.Series) -> Optional[str]:
    """Extract job URL from row data."""
    url_fields = ['url', 'job_url', 'apply_url']
    return next((row[field] for field in url_fields 
               if field in row and pd.notna(row[field])), None)


def display_job_listing_row(df: pd.DataFrame, index: int) -> None:
    """Display a single job listing row in the job descriptions tab."""
    row = df.iloc[index]
    job_id = row['job_id']
    
    # Get field values with appropriate defaults and formatting
    title = get_field_display_value(row, 'title', "Unknown Job")
    company = get_field_display_value(row, 'company', "Unknown Company")
    location = get_location_display(row)
    salary = get_field_display_value(row, 'salary_midpoint_yearly', "Not listed")
    date_posted = get_field_display_value(row, 'date_posted', "Unknown")
    
    # Check if this is the selected job
    is_selected = job_id == st.session_state.selected_job_id
    
    # Create row with columns
    cols = st.columns([3, 1.5, 1.2, 1.2, 1.2, 1.1, 1.1])
    cols[0].write(f"**{title}**")
    cols[1].write(company)
    cols[2].write(location)
    cols[3].write(salary)
    cols[4].write(date_posted)
    
    # View button for job description
    button_type = "secondary" if is_selected else "primary"
    button_label = "Selected" if is_selected else "Job Description"
    if cols[5].button(button_label, key=f"btn_{index}", use_container_width=True, type=button_type, disabled=is_selected):
        st.session_state.selected_job_id = job_id
        st.rerun()
    
    # Job URL button
    job_url = get_job_url(row)
    
    if job_url:
        cols[6].markdown(f"<a href='{job_url}' target='_blank'><button style='width:100%'>Visit Link</button></a>", unsafe_allow_html=True)
    else:
        cols[6].write("No URL")
    
    # Add divider line between rows (except after the last row)
    if index < len(df) - 1:
        st.markdown("<div class='row-divider'></div>", unsafe_allow_html=True)


def display_job_details(job: pd.Series) -> None:
    """Display detailed job information in the right panel."""
    st.markdown("### Quick Info")
    
    # Collect available details
    fields = [
        ('company', 'Company'),
        ('job_type', 'Job Type'),
        ('work_setting', 'Work Setting'),
    ]
    
    details_md = []
    
    # Add standard fields
    for field, label in fields:
        if field in job and pd.notna(job[field]):
            details_md.append(f"**{label}:** {job[field]}")
    
    # Add location
    location = get_location_display(job)
    if location != "Unknown":
        details_md.append(f"**Location:** {location}")
    
    # Add salary
    if 'salary_midpoint_yearly' in job and pd.notna(job['salary_midpoint_yearly']):
        details_md.append(f"**Annual Salary:** ${job['salary_midpoint_yearly']:,.0f}")
    
    # Add job URL
    job_url = get_job_url(job)
    if job_url:
        details_md.append(f"**[View Job Post Link]({job_url})**")
    
    st.markdown("\n\n".join(details_md))


def display_job_description_content(job: pd.Series) -> None:
    """Display the job description content."""
    # Find description content
    desc_cols = ['job_description', 'description']
    desc_col = next((col for col in desc_cols 
                if col in job and pd.notna(job[col])), None)
            
    if desc_col:
        st.markdown(job[desc_col])
    else:
        st.info("No job description available for this listing.")


def display_descriptions_tab(df: pd.DataFrame) -> None:
    """Display content for the Job Descriptions tab."""
    # Ensure job_id exists
    df = df.copy()
    if 'job_id' not in df.columns:
        df['job_id'] = df.index.astype(str)
    
    # Ensure we have title and company columns
    for col in ['title', 'company']:
        if col not in df.columns:
            df[col] = "Unknown"
    
    # Initialize selected job ID
    if 'selected_job_id' not in st.session_state or st.session_state.selected_job_id not in df['job_id'].values:
        st.session_state.selected_job_id = df['job_id'].iloc[0] if not df.empty else ""
    
    # Selection interface
    st.subheader("Select a job to view its description")
    
    # Add custom CSS
    st.markdown("""
    <style>
    .compact-item {padding: 6px 10px; border-bottom: 1px solid #eee; margin-bottom: 4px;}
    .compact-item:hover {background-color: #f5f5f5;}
    .job-number {color: #888; font-weight: bold; min-width: 30px; display: inline-block;}
    .job-title {font-weight: 500; color: #0068c9;}
    .job-company {color: #555;}
    .job-location {color: #777; font-size: 0.9em;}
    .selected-job {background-color: rgba(0, 104, 201, 0.1); border-left: 3px solid #0068c9;}
    [data-testid="stVerticalBlock"] > [style*="flex-direction: column;"] > [data-testid="stVerticalBlock"] {
        border: none !important; box-shadow: none !important;
    }
    .row-divider {
        border-bottom: 1px solid #e0e0e0;
        margin: 4px 0;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Display header row
    headers = ["Job Title", "Company", "Location", "Salary", "Date Posted", "View Job Description", "Visit Job Post"]
    header_cols = st.columns([3, 1.5, 1.2, 1.2, 1.2, 1.1, 1.1])
    for i, header in enumerate(headers):
        header_cols[i].write(f"**{header}**")
    
    # Separator after header
    st.markdown("<hr style='margin: 0; padding: 0; margin-bottom: 10px'>", unsafe_allow_html=True)
    
    # Create scrollable container for jobs
    with st.container(height=280, border=False):
        for i in range(len(df)):
            display_job_listing_row(df, i)
    
    # Add spacer
    st.write("---")
    
    # Get the selected job
    selected_job = df[df['job_id'] == st.session_state.selected_job_id]
    
    # If job not found, use the first available job
    if selected_job.empty and not df.empty:
        selected_job = df.iloc[[0]]
        st.session_state.selected_job_id = df['job_id'].iloc[0]
    
    # Display job description
    if not selected_job.empty:
        job = selected_job.iloc[0]
        job_title = get_field_display_value(job, 'title', 'Unknown Position')
        company_name = get_field_display_value(job, 'company', 'Unknown Company')
        st.subheader(f"{job_title} @ {company_name}")
        
        col1, col2 = st.columns([3, 1])
        
        # Job description (left column)
        with col1:
            display_job_description_content(job)
        
        # Job details (right column)
        with col2:
            display_job_details(job)
    else:
        st.info("No job data available to display.")


def display_sidebar_info(df: pd.DataFrame) -> None:
    """Display dataset information in the sidebar."""
    st.sidebar.header("Dataset Info")
    
    # Refresh data button
    if st.sidebar.button("🔄 Refresh Data"):
        # Clear caches to force data reload
        st.cache_data.clear()
        st.rerun()
    
    # Display when data was last refreshed
    last_refresh = st.session_state.get("last_refresh_time", "Never")
    st.sidebar.write(f"Last refreshed: {last_refresh}")
    
    # Display file count for debugging
    num_files = st.session_state.get("num_files_found", 0)
    st.sidebar.write(f"Data files loaded: {num_files}")
    
    # Display basic info
    st.sidebar.write(f"Total jobs: {len(df)}")
    if 'company' in df.columns:
        st.sidebar.write(f"Unique companies: {df['company'].nunique()}")
    
    # Add date range if available
    if 'date_posted' in df.columns and not df['date_posted'].empty:
        date_format = '%m/%d/%y'
        min_date = df['date_posted'].min().strftime(date_format)
        max_date = df['date_posted'].max().strftime(date_format)
        st.sidebar.write(f"Job postings from: {min_date} to {max_date}")
    
    # Download button
    st.sidebar.markdown("---")
    os.makedirs("data/processed", exist_ok=True)
    filename = f"indeed_jobs_{datetime.now().strftime('%m%d%y')}.csv"
    
    st.sidebar.download_button(
        label="Download Data as CSV",
        data=df.to_csv(index=False).encode('utf-8'),
        file_name=filename,
        mime="text/csv"
    )


def render_dashboard() -> None:
    """Main function to render the dashboard."""
    # Page configuration
    st.set_page_config(
        page_title="Indeed Job Dashboard",
        page_icon="📊",
        layout="wide"
    )
    
    st.title("Job Scraper Dashboard")
    
    # Load data
    try:
        df = load_multiple_datasets()
        if df.empty:
            st.error("No data available. Please run the job scraper first.")
            return
    except Exception as e:
        st.error(f"Error loading data: {e}")
        return
    
    # Apply filters from sidebar
    st.sidebar.header("Filters")
    filtered_df = apply_filters(df)
    display_sidebar_info(filtered_df)
    
    # Display metrics
    st.subheader("Key Metrics")
    display_metrics(filtered_df)
    
    # Display tabs with their content
    tabs = st.tabs(["Overview", "Salary Analysis", "Job Descriptions"])
    
    with tabs[0]:
        display_overview_tab(filtered_df)
    
    with tabs[1]:
        display_salary_tab(filtered_df)
        
    with tabs[2]:
        display_descriptions_tab(filtered_df)


if __name__ == "__main__":
    render_dashboard() 