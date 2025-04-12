#!/usr/bin/env python3
"""
Indeed Job Dashboard

Interactive dashboard for visualizing Indeed job scraper data using Streamlit.
Run with: streamlit run src/streamlit_dashboard.py

Author: Dennis
"""

import os
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime

import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import matplotlib.pyplot as plt
from wordcloud import WordCloud, STOPWORDS


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
        df['job_id'] = df.index.map(lambda i: f"{file_path.stem}_{i}")
    
    return df


@st.cache_data
def load_multiple_datasets() -> pd.DataFrame:
    """Load and combine multiple CSV files with caching."""
    files = find_csv_files()
    if not files:
        return pd.DataFrame()
    
    dfs = [load_data(file).assign(source_file=file.name) for file in files]
    combined_df = pd.concat(dfs, ignore_index=True)
    
    # Remove duplicate jobs
    if 'job_id' in combined_df.columns:
        combined_df.drop_duplicates(subset=['job_id'], keep='first', inplace=True)
    
    return combined_df


def create_chart(df: pd.DataFrame, chart_type: str, **kwargs) -> Optional[go.Figure]:
    """Create various chart types based on parameters."""
    if chart_type == "count":
        column = kwargs.get('column')
        title = kwargs.get('title')
        limit = kwargs.get('limit', 20)
        
        if column not in df.columns or df[column].isna().all():
            return None
        
        counts = df[column].value_counts().reset_index().head(limit)
        counts.columns = [column.title(), 'Count']
        
        fig = px.bar(
            counts, x='Count', y=column.title(),
            orientation='h', title=title,
            color='Count', color_continuous_scale='Viridis'
        )
        fig.update_layout(yaxis={'categoryorder': 'total ascending'})
        
    elif chart_type == "histogram":
        column = kwargs.get('column', 'salary_midpoint_yearly')
        title = kwargs.get('title', f'{column.replace("_", " ").title()} Distribution')
        
        if column not in df.columns:
            return None
        
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
        fig.add_vline(
            x=median_value, line_dash="dash", line_color="red",
            annotation_text=f"Median: ${median_value:,.0f}" if 'salary' in column else f"Median: {median_value:.1f}",
            annotation_position="top right"
        )
        
    elif chart_type == "pie":
        column = kwargs.get('column')
        title = kwargs.get('title')
        
        if column not in df.columns or df[column].isna().all():
            return None
        
        value_counts = df[column].value_counts().reset_index()
        value_counts.columns = [column.title(), 'Count']
        
        fig = px.pie(
            value_counts, values='Count', names=column.title(),
            title=title, color_discrete_sequence=px.colors.qualitative.Safe
        )
        fig.update_traces(textposition='inside', textinfo='percent+label')
        
    elif chart_type == "box":
        x, y = kwargs.get('x'), kwargs.get('y')
        title = kwargs.get('title')
        
        if not all(col in df.columns for col in [x, y]) or df[y].isna().all():
            return None
        
        filtered_df = df.dropna(subset=[x, y])
        if len(filtered_df) < 5:
            return None
        
        fig = px.box(
            filtered_df, x=x, y=y, title=title,
            labels={col: col.replace('_', ' ').title() for col in [x, y]},
            color=x
        )
        
    elif chart_type == "map":
        if 'state' not in df.columns or df['state'].isna().all():
            return None
        
        state_counts = df['state'].value_counts().reset_index()
        state_counts.columns = ['State', 'Job Count']
        
        fig = px.choropleth(
            state_counts, locations='State', locationmode='USA-states',
            color='Job Count', scope='usa', title='Job Distribution by State',
            color_continuous_scale='Viridis'
        )
        
    else:
        return None
    
    return fig


def create_wordcloud(df: pd.DataFrame, column: str = 'title') -> Optional[plt.Figure]:
    """Create a word cloud from text data in specified column."""
    if column not in df.columns or df[column].isna().all():
        return None
    
    text = ' '.join(df[column].dropna().astype(str))
    
    wordcloud = WordCloud(
        width=800, height=400, background_color='white',
        colormap='viridis', max_words=100, contour_width=1,
        stopwords=STOPWORDS
    ).generate(text)
    
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.imshow(wordcloud, interpolation='bilinear')
    ax.axis('off')
    plt.tight_layout()
    
    return fig


def create_salary_by_location_chart(df: pd.DataFrame) -> Optional[go.Figure]:
    """Create chart of salaries grouped by location."""
    if 'salary_midpoint_yearly' not in df.columns:
        return None
    
    # Find best location column (state, city, zip)
    loc_field = next((field for field in ['state', 'city', 'zip'] 
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
    if 'date_posted' in filtered_df.columns:
        min_date = filtered_df['date_posted'].min().date()
        max_date = filtered_df['date_posted'].max().date()
        
        # Set datetime format to mm/dd/yyyy
        st.sidebar.markdown("""
        <style>input[type=date] {min-height: 36px;}</style>
        """, unsafe_allow_html=True)
        
        date_range = st.sidebar.date_input(
            "Job Posted Date Range",
            value=(min_date, max_date),
            min_value=min_date,
            max_value=max_date,
            format="MM/DD/YYYY"
        )
        
        if len(date_range) == 2:
            start_date, end_date = date_range
            filtered_df = filtered_df[
                (filtered_df['date_posted'].dt.date >= start_date) & 
                (filtered_df['date_posted'].dt.date <= end_date)
            ]
    
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


def display_salary_tab(df: pd.DataFrame) -> None:
    """Display content for the Salary Analysis tab."""
    if 'salary_midpoint_yearly' not in df.columns:
        st.write("No salary data available.")
        return
    
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
    
    # Salary by location analysis
    st.subheader("Salary by Location")
    if salary_by_location_fig := create_salary_by_location_chart(df):
        st.plotly_chart(salary_by_location_fig, use_container_width=True)
    else:
        st.info("Not enough location data available for salary analysis.")
    
    # Salary statistics table
    st.subheader("Salary Statistics")
    salary_stats = (
        df['salary_midpoint_yearly']
        .describe()
        .reset_index()
        .rename(columns={'index': 'Statistic', 'salary_midpoint_yearly': 'Value'})
    )
    
    # Format values as currency except for count
    salary_stats['Value'] = salary_stats.apply(
        lambda row: f"${row['Value']:,.2f}" 
                   if row['Statistic'] != 'count' and isinstance(row['Value'], (int, float)) 
                   else row['Value'], 
        axis=1
    )
    
    st.dataframe(salary_stats, hide_index=True)


def get_field_display_value(row: pd.Series, field: str, default: str = "Unknown") -> str:
    """Get display value for a field with appropriate formatting."""
    if field not in row or pd.isna(row[field]):
        return default
        
    if field == 'salary_midpoint_yearly':
        return f"${row[field]:,.0f}"
    
    if field == 'date_posted' and hasattr(row[field], 'strftime'):
        return row[field].strftime('%m/%d/%y')
    
    return str(row[field])
    

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
    
    # Add custom CSS for compact table-like display
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
    /* Row divider styles */
    .row-divider {
        border-bottom: 1px solid #e0e0e0;
        margin: 4px 0;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Display header row
    header_cols = st.columns([3, 1.5, 1.2, 1.2, 1.2, 1.1, 1.1])
    headers = ["Job Title", "Company", "Location", "Salary", "Date Posted", "View Job Description", "Visit Job Post"]
    for i, header in enumerate(headers):
        header_cols[i].write(f"**{header}**")
    
    # Separator after header
    st.markdown("<hr style='margin: 0; padding: 0; margin-bottom: 10px'>", unsafe_allow_html=True)
    
    # Create scrollable container for jobs
    with st.container(height=280, border=False):
        for i in range(len(df)):
            row = df.iloc[i]
            job_id = row['job_id']
            
            # Get field values with appropriate defaults and formatting
            title = get_field_display_value(row, 'title', "Unknown Job")
            company = get_field_display_value(row, 'company', "Unknown Company")
            
            # Get location info
            location = "Unknown"
            if 'city' in row and 'state' in row and pd.notna(row['city']) and pd.notna(row['state']):
                location = f"{row['city']}, {row['state']}"
            elif 'state' in row and pd.notna(row['state']):
                location = row['state']
            elif 'city' in row and pd.notna(row['city']):
                location = row['city']
            
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
            if cols[5].button(button_label, key=f"btn_{i}", use_container_width=True, type=button_type, disabled=is_selected):
                st.session_state.selected_job_id = job_id
                st.rerun()
            
            # Job URL button
            job_url = next((row[url_field] for url_field in ['url', 'job_url', 'apply_url']
                          if url_field in row and pd.notna(row[url_field])), None)
            
            if job_url:
                cols[6].markdown(f"<a href='{job_url}' target='_blank'><button style='width:100%'>Visit Link</button></a>", unsafe_allow_html=True)
            else:
                cols[6].write("No URL")
            
            # Add divider line between rows (except after the last row)
            if i < len(df) - 1:
                st.markdown("<div class='row-divider'></div>", unsafe_allow_html=True)
    
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
        job_title = get_field_display_value(selected_job.iloc[0], 'title', 'Unknown Position')
        company_name = get_field_display_value(selected_job.iloc[0], 'company', 'Unknown Company')
        st.subheader(f"{job_title} @ {company_name}")
        
        col1, col2 = st.columns([3, 1])
        
        # Job description (left column)
        with col1:
            # Find description content
            desc_col = next((col for col in ['job_description', 'description'] 
                        if col in selected_job.iloc[0] and pd.notna(selected_job.iloc[0][col])), None)
                    
            if desc_col:
                st.markdown(selected_job.iloc[0][desc_col])
            else:
                st.info("No job description available for this listing.")
        
        # Job details (right column)
        with col2:
            st.markdown("### Quick Info")
            
            # Collect available details
            fields = [
                ('company', 'Company'),
                ('job_type', 'Job Type'),
                ('work_setting', 'Work Setting'),
            ]
            
            details_md = []
            job = selected_job.iloc[0]
            
            # Add standard fields
            for field, label in fields:
                if field in job and pd.notna(job[field]):
                    details_md.append(f"**{label}:** {job[field]}")
            
            # Add location
            if 'city' in job and 'state' in job and pd.notna(job['city']) and pd.notna(job['state']):
                details_md.append(f"**Location:** {job['city']}, {job['state']}")
            elif 'state' in job and pd.notna(job['state']):
                details_md.append(f"**Location:** {job['state']}")
            
            # Add salary
            if 'salary_midpoint_yearly' in job and pd.notna(job['salary_midpoint_yearly']):
                details_md.append(f"**Annual Salary:** ${job['salary_midpoint_yearly']:,.0f}")
            
            # Add job URL
            job_url = next((job[url_field] for url_field in ['url', 'job_url', 'apply_url']
                          if url_field in job and pd.notna(job[url_field])), None)
            if job_url:
                details_md.append(f"**[View Job Post Link]({job_url})**")
            
            st.markdown("\n\n".join(details_md))
    else:
        st.info("No job data available to display.")


def display_sidebar_info(df: pd.DataFrame) -> None:
    """Display dataset information in the sidebar."""
    st.sidebar.header("Dataset Info")
    
    # Display basic info
    st.sidebar.write(f"Total jobs: {len(df)}")
    if 'company' in df.columns:
        st.sidebar.write(f"Unique companies: {df['company'].nunique()}")
    
    # Add date range if available
    if 'date_posted' in df.columns and not df['date_posted'].empty:
        date_format = '%m/%d/%y'
        st.sidebar.write(
            f"Job postings from: {df['date_posted'].min().strftime(date_format)} "
            f"to {df['date_posted'].max().strftime(date_format)}"
        )
    
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