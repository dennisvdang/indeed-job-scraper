#!/usr/bin/env python3
"""
Indeed Job Dashboard

Interactive dashboard for visualizing Indeed job scraper data using Streamlit.
This version is fully database‐backed: it applies filters in SQL, paginates,
and never falls back to CSV/DataFrame logic.
"""

import os
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime

import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import matplotlib.pyplot as plt
from wordcloud import WordCloud, STOPWORDS

from ..database.repository import JobListingRepository
from .repository import get_repository

# Suppress SQLAlchemy SQL statement logs in the dashboard
logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)

# Configure logging
logger = logging.getLogger(__name__)

# -----------------------------
# Database‐only Filter Helpers
# -----------------------------
PAGE_SIZE = 20

@st.cache_data(ttl=600)
def get_filter_options() -> Dict[str, List[Any]]:
    """Get unique filter options from the database (cached)."""
    return {
        "queried_job_title": JobListingRepository.get_unique_values("queried_job_title"),
        "state":             JobListingRepository.get_unique_values("state"),
        "work_setting":      JobListingRepository.get_unique_values("work_setting"),
        "job_type":          JobListingRepository.get_unique_values("job_type"),
    }

def sidebar_filters() -> Dict[str, Any]:
    """Render sidebar filter widgets and return selections."""
    opts = get_filter_options()
    f: Dict[str, Any] = {}
    f["queried_job_title"] = st.sidebar.multiselect("Job Title Queries", opts["queried_job_title"])
    f["state"]             = st.sidebar.multiselect("Location (State)",      opts["state"])
    f["work_setting"]      = st.sidebar.selectbox( "Work Setting",         [None] + opts["work_setting"])
    f["job_type"]          = st.sidebar.selectbox( "Job Type",             [None] + opts["job_type"])
    f["has_salary"]        = st.sidebar.checkbox(  "Show only jobs with salary data", value=False)
    return f

def filter_query_params(filters: Dict[str, Any]) -> Dict[str, Any]:
    """Convert sidebar selections into DB query parameters."""
    p: Dict[str, Any] = {}
    if filters.get("queried_job_title"): p["queried_job_title"] = filters["queried_job_title"]
    if filters.get("state"):             p["state"]             = filters["state"]
    if filters.get("work_setting"):      p["work_setting"]      = filters["work_setting"]
    if filters.get("job_type"):          p["job_type"]          = filters["job_type"]
    if filters.get("has_salary"):        p["has_salary"]        = True
    return p

# --------------------------------------
# UI / Chart / Display Helpers
# --------------------------------------

def format_currency(value: float) -> str:
    """Format a numeric value as currency."""
    return f"${value:,.0f}"

def get_safe_field(row: pd.Series, field: str, default: str = "Unknown") -> str:
    """Safely get a field value with fallback to default."""
    return str(row[field]) if field in row and pd.notna(row[field]) else default

def has_valid_columns(df: pd.DataFrame, required_cols: List[str]) -> bool:
    """Check if dataframe has required columns with valid data."""
    return all(col in df.columns and not df[col].isna().all() for col in required_cols)

def create_chart_factory(df: pd.DataFrame) -> Dict[str, Any]:
    return {
        "count":     lambda column, title, limit=20: create_bar_chart(df, column, title, limit),
        "histogram": lambda column='salary_midpoint_yearly', title=None: create_histogram(df, column, title),
        "pie":       lambda column, title: create_pie_chart(df, column, title),
        "box":       lambda x, y, title: create_box_plot(df, x, y, title),
        "map":       lambda: create_choropleth(df)
    }

def create_bar_chart(df: pd.DataFrame, column: str, title: str, limit: int = 20) -> Optional[go.Figure]:
    if not has_valid_columns(df, [column]):
        return None
    counts = df[column].value_counts().reset_index().head(limit)
    counts.columns = [column.title(), 'Count']
    fig = px.bar(counts, x='Count', y=column.title(),
                 orientation='h', title=title,
                 color='Count', color_continuous_scale='Viridis')
    fig.update_layout(yaxis={'categoryorder': 'total ascending'})
    return fig

def create_histogram(df: pd.DataFrame, column: str = 'salary_midpoint_yearly',
                     title: Optional[str] = None) -> Optional[go.Figure]:
    if not has_valid_columns(df, [column]):
        return None
    data = df[column].dropna()
    if len(data) < 5:
        return None
    title = title or f'{column.replace("_", " ").title()} Distribution'
    quantiles = data.quantile([0.05, 0.95])
    filtered_df = df[(df[column] >= quantiles.iloc[0]) & (df[column] <= quantiles.iloc[1])]
    median_value = filtered_df[column].median()
    median_text = f"Median: ${median_value:,.0f}"
    fig = px.histogram(filtered_df, x=column, title=title,
                       labels={column: column.replace('_', ' ').title()},
                       color_discrete_sequence=['#2E86C1'], nbins=20)
    fig.add_vline(x=median_value, line_dash="dash", line_color="red",
                  annotation_text=median_text, annotation_position="top right")
    return fig

def create_pie_chart(df: pd.DataFrame, column: str, title: str) -> Optional[go.Figure]:
    if not has_valid_columns(df, [column]):
        return None
    vc = df[column].value_counts().reset_index()
    vc.columns = [column.title(), 'Count']
    fig = px.pie(vc, values='Count', names=column.title(), 
                 title=title, color_discrete_sequence=px.colors.qualitative.Safe)
    fig.update_traces(textposition='inside', textinfo='percent+label')
    return fig

def create_box_plot(df: pd.DataFrame, x: str, y: str, title: str) -> Optional[go.Figure]:
    if not has_valid_columns(df, [x, y]):
        return None
    filtered = df.dropna(subset=[x, y])
    if len(filtered) < 5:
        return None
    fig = px.box(filtered, x=x, y=y, title=title,
                 labels={col: col.replace('_', ' ').title() for col in [x, y]},
                 color=x)
    return fig

def create_choropleth(df: pd.DataFrame) -> Optional[go.Figure]:
    """Create a US choropleth map of job counts by state."""
    if not has_valid_columns(df, ['state']):
        return None
    state_counts = df['state'].value_counts().reset_index()
    state_counts.columns = ['State', 'Job Count']
    fig = px.choropleth(
        state_counts, locations='State', locationmode='USA-states',
        color='Job Count', scope='usa', title='Job Distribution by State',
        color_continuous_scale='Viridis'
    )
    return fig

def create_wordcloud(df: pd.DataFrame, column: str = 'title') -> Optional[plt.Figure]:
    if not has_valid_columns(df, [column]):
        return None
    text = ' '.join(df[column].dropna().astype(str))
    wc = WordCloud(width=800, height=400, background_color='white',
                   colormap='viridis', max_words=100,
                   stopwords=STOPWORDS).generate(text)
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.imshow(wc, interpolation='bilinear')
    ax.axis('off')
    plt.tight_layout()
    return fig

def create_salary_by_location_chart(df: pd.DataFrame) -> Optional[go.Figure]:
    """Create chart of salaries grouped by location."""
    if not has_valid_columns(df, ['salary_midpoint_yearly']):
        return None
    
    location_fields = ['state', 'city', 'zip']
    loc_field = next((field for field in location_fields 
                     if field in df.columns and df[field].notna().sum() > 3), None)
    
    if not loc_field:
        return None
    
    valid_data = df.dropna(subset=[loc_field, 'salary_midpoint_yearly'])
    if len(valid_data) < 5:
        return None
    
    location_stats = valid_data.groupby(loc_field)['salary_midpoint_yearly'].agg(['mean', 'median', 'count'])
    location_stats = location_stats.sort_values('median', ascending=False)
    
    min_count = 2
    top_locations = location_stats[location_stats['count'] >= min_count].head(15)
    if len(top_locations) < 3:
        top_locations = location_stats.head(10)
    
    plot_data = df[df[loc_field].isin(top_locations.index)]
    
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

def create_salary_state_choropleth(df: pd.DataFrame) -> Optional[go.Figure]:
    """Create a US choropleth map of median salary by state."""
    if not has_valid_columns(df, ['state', 'salary_midpoint_yearly']):
        return None
    
    state_salary = df.groupby('state')['salary_midpoint_yearly'].agg(['median', 'count']).reset_index()
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
    
    fig.update_traces(
        hovertemplate='<b>%{location}</b><br>Median Salary: $%{z:,.0f}<br>Job Count: %{customdata}<extra></extra>',
        customdata=state_salary['count']
    )
    
    return fig

def create_salary_city_chart(df: pd.DataFrame) -> Optional[go.Figure]:
    """Create chart of median salary by top cities."""
    if not has_valid_columns(df, ['city', 'state', 'salary_midpoint_yearly']):
        return None
    
    df = df.copy()
    city_state_valid = pd.notna(df['city']) & pd.notna(df['state'])
    df.loc[city_state_valid, 'location'] = df.loc[city_state_valid, 'city'] + ', ' + df.loc[city_state_valid, 'state']
    
    location_salary = df.dropna(subset=['location', 'salary_midpoint_yearly'])
    location_salary = location_salary.groupby('location')['salary_midpoint_yearly'].agg(['median', 'count']).reset_index()
    location_salary = location_salary[location_salary['count'] >= 2]
    
    if len(location_salary) < 3:
        return None
    
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

def create_salary_trend_chart(df: pd.DataFrame) -> Optional[go.Figure]:
    """Create a moving average trend chart for salaries over time."""
    if not has_valid_columns(df, ['date_posted', 'salary_midpoint_yearly']):
        return None
        
    temp_df = df.dropna(subset=['date_posted', 'salary_midpoint_yearly']).copy()
    
    if len(temp_df) < 10:
        return None
    
    temp_df = temp_df.sort_values('date_posted')
    
    daily_salary = temp_df.groupby(temp_df['date_posted'].dt.date)['salary_midpoint_yearly'].mean().reset_index()
    daily_salary.columns = ['date', 'avg_salary']
    
    daily_salary['7d_moving_avg'] = daily_salary['avg_salary'].rolling(window=7, min_periods=1).mean()
    
    if len(daily_salary) >= 15:
        daily_salary['30d_moving_avg'] = daily_salary['avg_salary'].rolling(window=30, min_periods=7).mean()
    
    fig = go.Figure()
    
    fig.add_trace(go.Scatter(
        x=daily_salary['date'],
        y=daily_salary['avg_salary'],
        mode='markers',
        name='Daily Average',
        marker=dict(size=6, opacity=0.5),
        hovertemplate='Date: %{x|%b %d, %Y}<br>Avg Salary: $%{y:,.0f}<extra></extra>'
    ))
    
    fig.add_trace(go.Scatter(
        x=daily_salary['date'],
        y=daily_salary['7d_moving_avg'],
        mode='lines',
        name='7-day Moving Avg',
        line=dict(width=3, color='blue'),
        hovertemplate='Date: %{x|%b %d, %Y}<br>7-day Avg: $%{y:,.0f}<extra></extra>'
    ))
    
    if '30d_moving_avg' in daily_salary.columns:
        fig.add_trace(go.Scatter(
            x=daily_salary['date'],
            y=daily_salary['30d_moving_avg'],
            mode='lines',
            name='30-day Moving Avg',
            line=dict(width=3, color='red'),
            hovertemplate='Date: %{x|%b %d, %Y}<br>30-day Avg: $%{y:,.0f}<extra></extra>'
        ))
    
    fig.update_layout(
        title='Salary Trend Over Time (Moving Average)',
        xaxis_title='Date',
        yaxis_title='Salary ($)',
        hovermode='x unified',
        yaxis=dict(tickprefix='$', tickformat=','),
        height=500
    )
    
    return fig

def display_metrics(df: pd.DataFrame) -> None:
    """Display key metrics at the top of the dashboard."""
    st.markdown("""
    <style>
    div[data-testid="metric-container"] {
        padding: 10px 15px;
        margin-bottom: 0px;
    }
    div[data-testid="metric-container"] > div[data-testid="stVerticalBlock"] > div {
        font-size: 0.9rem;
    }
    div[data-testid="metric-container"] > div[data-testid="stVerticalBlock"] > div:nth-child(2) {
        font-size: 1.8rem;
    }
    </style>
    """, unsafe_allow_html=True)
    
    metrics = []
    
    metrics.append(("Total Jobs", len(df)))
    if 'company' in df.columns:
        metrics.append(("Companies", df['company'].nunique()))
    
    salary_cols = ['salary_min_yearly', 'salary_midpoint_yearly', 'salary_max_yearly']
    if all(col in df.columns for col in salary_cols):
        median_salary = df['salary_midpoint_yearly'].median()
        metrics.append(("Median Salary", f"${median_salary:,.0f}"))
        
        min_salary = df['salary_min_yearly'].median()
        max_salary = df['salary_max_yearly'].median()
        salary_range = f"${min_salary:,.0f} - ${max_salary:,.0f}"
        metrics.append(("Median Salary Range", salary_range))
    
    cols = st.columns(len(metrics))
    for i, (label, value) in enumerate(metrics):
        with cols[i]:
            st.metric(label, value)

def display_overview_tab(df: pd.DataFrame) -> None:
    """Display content for the Overview tab."""
    col1, col2 = st.columns(2)
    
    with col1:
        if wordcloud_fig := create_wordcloud(df):
            st.subheader("Popular Job Titles")
            st.pyplot(wordcloud_fig)
        
        if company_chart := create_chart(df, "count", column='company', title='Top 20 Companies by Job Count'):
            st.plotly_chart(company_chart, use_container_width=True)
    
    with col2:
        if location_map := create_chart(df, "map"):
            st.plotly_chart(location_map, use_container_width=True)
        
        if 'work_setting' in df.columns:
            if work_setting_fig := create_chart(df, "pie", column='work_setting', title='Job Distribution by Work Setting'):
                st.plotly_chart(work_setting_fig, use_container_width=True)

def display_salary_statistics(df: pd.DataFrame) -> None:
    """Display detailed salary statistics table."""
    st.subheader("Salary Statistics")
    
    percentiles = [0.1, 0.25, 0.5, 0.75, 0.9]
    percentile_names = ['10th', '25th', '50th (Median)', '75th', '90th']
    
    stats = df['salary_midpoint_yearly'].describe()
    percentile_stats = df['salary_midpoint_yearly'].quantile(percentiles)
    
    all_stats = pd.DataFrame({
        'Statistic': ['Count', 'Mean', 'Standard Deviation', 'Minimum'] + percentile_names + ['Maximum'],
        'Value': [
            stats['count'],
            stats['mean'],
            stats['std'],
            stats['min'],
            *percentile_stats.values,
            stats['max']
        ]
    })
    
    all_stats['Value'] = all_stats.apply(
        lambda row: f"${row['Value']:,.2f}" if row['Statistic'] != 'Count' 
                   else f"{row['Value']:,.0f}",
        axis=1
    )
    
    st.dataframe(all_stats, hide_index=True)

def display_salary_tab(df: pd.DataFrame) -> None:
    """Display content for the Salary Analysis tab."""
    if 'salary_midpoint_yearly' not in df.columns:
        st.write("No salary data available.")
        return
    
    display_salary_statistics(df)
    
    col1, col2 = st.columns(2)
    
    with col1:
        salary_fig = create_chart(df, "histogram", column='salary_midpoint_yearly', 
                               title='Annual Salary Distribution (Midpoint)')
        if salary_fig:
            st.plotly_chart(salary_fig, use_container_width=True)
    
    with col2:
        if 'work_setting' in df.columns:
            salary_by_setting_fig = create_chart(df, "box", x='work_setting', y='salary_midpoint_yearly', 
                                              title='Salary Distribution by Work Setting')
            if salary_by_setting_fig:
                st.plotly_chart(salary_by_setting_fig, use_container_width=True)
    
    salary_trend_fig = create_salary_trend_chart(df)
    if salary_trend_fig:
        st.plotly_chart(salary_trend_fig, use_container_width=True)
    else:
        st.info("Not enough time-series data to create salary trend chart. Ensure job posting dates and salary data are available.")

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

def add_job_listing_css() -> None:
    """Add custom CSS for job listings display."""
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

def display_job_listing_row(df: pd.DataFrame, index: int) -> None:
    """Display a single job listing row in the job descriptions tab."""
    row = df.iloc[index]
    job_id = row['job_id']
    
    title = get_field_display_value(row, 'title', "Unknown Job")
    company = get_field_display_value(row, 'company', "Unknown Company")
    location = get_location_display(row)
    salary = get_field_display_value(row, 'salary_midpoint_yearly', "Not listed")
    date_posted = get_field_display_value(row, 'date_posted', "Unknown")
    
    is_selected = job_id == st.session_state.selected_job_id
    
    cols = st.columns([3, 1.5, 1.2, 1.2, 1.2, 1.1, 1.1])
    cols[0].write(f"**{title}**")
    cols[1].write(company)
    cols[2].write(location)
    cols[3].write(salary)
    cols[4].write(date_posted)
    
    button_type = "secondary" if is_selected else "primary"
    button_label = "Selected" if is_selected else "Job Description"
    if cols[5].button(button_label, key=f"btn_{index}", use_container_width=True, 
                    type=button_type, disabled=is_selected):
        st.session_state.selected_job_id = job_id
        st.rerun()
    
    job_url = get_job_url(row)
    if job_url:
        cols[6].markdown(f"<a href='{job_url}' target='_blank'><button style='width:100%'>Visit Link</button></a>", 
                        unsafe_allow_html=True)
    else:
        cols[6].write("No URL")
    
    if index < len(df) - 1:
        st.markdown("<div class='row-divider'></div>", unsafe_allow_html=True)

def display_job_details(job: pd.Series) -> None:
    """Display detailed job information in the right panel."""
    st.markdown("### Quick Info")
    
    details = []
    
    for field, label in [('company', 'Company'), ('job_type', 'Job Type'), ('work_setting', 'Work Setting')]:
        if field in job and pd.notna(job[field]):
            details.append(f"**{label}:** {job[field]}")
    
    location = get_location_display(job)
    if location != "Unknown":
        details.append(f"**Location:** {location}")
    
    if 'salary_midpoint_yearly' in job and pd.notna(job['salary_midpoint_yearly']):
        details.append(f"**Annual Salary:** ${job['salary_midpoint_yearly']:,.0f}")
    
    job_url = get_job_url(job)
    if job_url:
        details.append(f"**[View Job Post Link]({job_url})**")
    
    st.markdown("\n\n".join(details))

def display_job_description_content(job: pd.Series) -> None:
    """Display the job description content."""
    desc_cols = ['description', 'job_description']
    desc_col = next((col for col in desc_cols 
                if col in job and pd.notna(job[col])), None)
            
    if desc_col:
        st.markdown(job[desc_col])
    else:
        try:
            if 'job_id' in job and pd.notna(job['job_id']):
                from ..database.repository import JobListingRepository
                
                description = JobListingRepository.get_description_for_job(job['job_id'])
                if description:
                    st.markdown(description)
                    return
        except Exception as e:
            logger.error(f"Error fetching job description: {e}")
        
        st.info("No job description available for this listing.")

def get_job_with_description(job_id: str) -> Optional[pd.Series]:
    """Get a job with its description loaded on demand."""
    try:
        from ..database.repository import JobListingRepository
        
        job_data = JobListingRepository.get_job_details(job_id)
        if job_data:
            return pd.Series(job_data)
        return None
    except Exception as e:
        logger.error(f"Error fetching job with description: {e}")
        return None

def display_descriptions_tab(df: pd.DataFrame, total_pages: int) -> None:
    """Display paginated job descriptions for the current page."""
    add_job_listing_css()
    
    if 'job_list_page' not in st.session_state:
        st.session_state.job_list_page = 0
    
    items_per_page = PAGE_SIZE
    
    display_df = df
    
    if 'job_id' not in display_df.columns and not display_df.empty:
        display_df['job_id'] = display_df.index.astype(str)
    
    for col in ['title', 'company']:
        if col not in display_df.columns and not display_df.empty:
            display_df[col] = "Unknown"
    
    if ('selected_job_id' not in st.session_state or 
        st.session_state.selected_job_id not in display_df['job_id'].values):
        st.session_state.selected_job_id = display_df['job_id'].iloc[0] if not display_df.empty else ""
    
    st.subheader("Select a job to view its description")
    
    headers = ["Job Title", "Company", "Location", "Salary", "Date Posted", "View Job Description", "Visit Job Post"]
    header_cols = st.columns([3, 1.5, 1.2, 1.2, 1.2, 1.1, 1.1])
    for i, header in enumerate(headers):
        header_cols[i].write(f"**{header}**")
    
    st.markdown("<hr style='margin: 0; padding: 0; margin-bottom: 10px'>", unsafe_allow_html=True)
    
    with st.container(height=280, border=False):
        if display_df.empty:
            st.info("No job listings found with the current filters.")
        else:
            for i in range(len(display_df)):
                display_job_listing_row(display_df, i)
    
    col1, col2, col3, col4, col5 = st.columns([1, 3, 2, 3, 1])
    
    with col2:
        if st.button("← Previous Page", disabled=(st.session_state.job_list_page <= 0)):
            st.session_state.job_list_page = max(0, st.session_state.job_list_page - 1)
            st.experimental_rerun()
    
    with col3:
        st.write(f"Page {st.session_state.job_list_page + 1} of {max(1, total_pages)}")
    
    with col4:
        if st.button("Next Page →", disabled=(st.session_state.job_list_page >= total_pages - 1)):
            st.session_state.job_list_page = min(total_pages - 1, st.session_state.job_list_page + 1)
            st.experimental_rerun()
    
    st.write("---")
    
    # Get the selected job description
    selected_job_id = st.session_state.selected_job_id
    job_with_description: Optional[pd.Series] = None
    
    selected_job_row = display_df[display_df['job_id'] == selected_job_id]
    
    if not selected_job_row.empty:
        # We have the job metadata, now fetch the description on demand
        job_with_description = get_job_with_description(selected_job_id)
        
        if job_with_description is None:
            job_with_description = selected_job_row.iloc[0]
    
    if job_with_description is not None:
        job_title = get_safe_field(job_with_description, 'title', 'Unknown Position')
        company_name = get_safe_field(job_with_description, 'company', 'Unknown Company')
        st.subheader(f"{job_title} @ {company_name}")
        
        col1, col2 = st.columns([3, 1])
        with col1:
            display_job_description_content(job_with_description)
        with col2:
            display_job_details(job_with_description)
    else:
        st.info("No job data available to display.")

def display_sidebar_info(df: pd.DataFrame) -> None:
    """Display dataset information in the sidebar."""
    st.sidebar.header("Dataset Info")
    
    st.sidebar.write(f"Total jobs: {len(df)}")
    if 'company' in df.columns:
        st.sidebar.write(f"Unique companies: {df['company'].nunique()}")
    
    if 'date_posted' in df.columns and not df['date_posted'].empty:
        date_format = '%m/%d/%y'
        min_date = df['date_posted'].min().strftime(date_format)
        max_date = df['date_posted'].max().strftime(date_format)
        st.sidebar.write(f"Job postings from: {min_date} to {max_date}")
    
    st.sidebar.markdown("---")
    os.makedirs("data/processed", exist_ok=True)
    filename = f"indeed_jobs_{datetime.now().strftime('%m%d%y')}.csv"
    
    st.sidebar.download_button(
        label="Download Data as CSV",
        data=df.to_csv(index=False).encode('utf-8'),
        file_name=filename,
        mime="text/csv"
    )

@st.cache_data(ttl=600)
def get_filter_options() -> Dict[str, List[Any]]:
    """Get unique filter options from the database (cached)."""
    return {
        "queried_job_title": JobListingRepository.get_unique_values("queried_job_title"),
        "state": JobListingRepository.get_unique_values("state"),
        "work_setting": JobListingRepository.get_unique_values("work_setting"),
        "job_type": JobListingRepository.get_unique_values("job_type"),
    }

def sidebar_filters() -> Dict[str, Any]:
    """Render sidebar filter widgets and return current selections."""
    opts = get_filter_options()
    filters: Dict[str, Any] = {}
    filters["queried_job_title"] = st.sidebar.multiselect("Job Title Queries", opts["queried_job_title"])
    filters["state"] = st.sidebar.multiselect("Location (State)", opts["state"])
    filters["work_setting"] = st.sidebar.selectbox("Work Setting", [None] + opts["work_setting"])
    filters["job_type"] = st.sidebar.selectbox("Job Type", [None] + opts["job_type"])
    filters["has_salary"] = st.sidebar.checkbox("Show only jobs with salary data", value=False)
    return filters

def filter_query_params(filters: Dict[str, Any]) -> Dict[str, Any]:
    """Convert sidebar selections into DB query parameters."""
    params: Dict[str, Any] = {}
    if filters.get("queried_job_title"): params["queried_job_title"] = filters["queried_job_title"]
    if filters.get("state"):              params["state"] = filters["state"]
    if filters.get("work_setting"):       params["work_setting"] = filters["work_setting"]
    if filters.get("job_type"):           params["job_type"] = filters["job_type"]
    if filters.get("has_salary"):         params["has_salary"] = True
    return params

def create_chart(df: pd.DataFrame, chart_type: str, **kwargs) -> Optional[go.Figure]:
    """Create various chart types based on parameters."""
    chart_creators = create_chart_factory(df)
    creator = chart_creators.get(chart_type)
    return creator(**kwargs) if creator else None

def render_dashboard() -> None:
    """Main function to render the dashboard with filter-driven, paginated DB queries."""
    st.set_page_config(page_title="Indeed Job Dashboard", page_icon="📊", layout="wide")
    st.title("Job Scraper Dashboard")

    # Sidebar filters
    st.sidebar.header("Filters")
    filters = sidebar_filters()

    # Initialize filter and pagination state
    if "apply_filter" not in st.session_state:
        st.session_state.apply_filter = False
    if "job_list_page" not in st.session_state:
        st.session_state.job_list_page = 0
    if st.sidebar.button("Apply Filter"):
        st.session_state.apply_filter = True
        st.session_state.job_list_page = 0

    # Wait for filters to be applied
    if not st.session_state.apply_filter:
        st.info("Select filters and click 'Apply Filter' to view jobs.")
        return

    # Run database query for metrics/charts
    params = filter_query_params(filters)
    df = JobListingRepository.get_job_listings_by_query(params)

    # Display sidebar info and metrics
    display_sidebar_info(df)
    display_metrics(df)

    # Tabs: Overview, Salary, Descriptions
    tab1, tab2, tab3 = st.tabs(["📊 Overview", "💰 Salary Analysis", "🔍 Job Descriptions"])
    with tab1:
        display_overview_tab(df)
    with tab2:
        display_salary_tab(df)
    with tab3:
        # Paginated descriptions
        page_df, total_count = JobListingRepository.get_paginated_job_listings(
            page=st.session_state.job_list_page,
            items_per_page=PAGE_SIZE,
            query_params=params
        )
        total_pages = (total_count + PAGE_SIZE - 1) // PAGE_SIZE
        display_descriptions_tab(page_df, total_pages)

if __name__ == "__main__":
    render_dashboard() 