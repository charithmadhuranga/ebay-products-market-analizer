import requests
from bs4 import BeautifulSoup
import csv
import os
from dotenv import load_dotenv
from celery import Celery
from bokeh.plotting import figure, show, output_file, save
from bokeh.models import ColumnDataSource, HoverTool, Div, Span
from bokeh.layouts import column, row, gridplot
from bokeh.transform import cumsum
from bokeh.palettes import Category20c, Spectral6
import re
from typing import TypedDict, Annotated, List, Dict, Any
from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage, AIMessage
from langchain_google_genai import ChatGoogleGenerativeAI
import pandas as pd
import numpy as np
from math import pi

load_dotenv(verbose=True)

# Celery configuration
app = Celery('ebay_scraper', broker='redis://localhost:6379/0', backend='redis://localhost:6379/0')

# Proxy configuration (from ebay-scrape/ebayproductlist.py and ebay-scrape/main.py)
PROXY_HOST = "142.111.48.253"
PROXY_PORT = "7030"
def get_proxy_config(proxy_info):
    user = os.environ.get("BRD_USERNAME")
    password = os.environ.get("BRD_PASSWORD")
    if not user or not password:
        # Return None if credentials are missing, handled later
        return None

    proxy_url = f"http://{user}:{password}@{proxy_info['host']}:{proxy_info['port']}"
    return {"http": proxy_url, "https": proxy_url}

# Define a single proxy for this script, similar to ebayproductlist.py
PROXY_INFO = {"host": PROXY_HOST, "port": PROXY_PORT}

# Try to configure proxy, handle missing credentials gracefully
try:
    proxies = get_proxy_config(PROXY_INFO)
except ValueError as e:
    print(f"Warning: {e} Scraper will run without proxy.")
    proxies = None

# Headers to mimic a real browser (from ebay-scrape/ebayproductlist.py)
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.google.com/"
}

def clean_price(price_str):
    """Extracts numeric price from string."""
    try:
        # Remove currency symbols and commas, handle ranges by taking the first number
        # Example: "$1,234.56" -> 1234.56
        # Example: "$10.00 to $20.00" -> 10.00
        match = re.search(r"[\d,]+(\.\d{2})?", price_str)
        if match:
            return float(match.group(0).replace(',', ''))
    except Exception:
        pass
    return None

def create_bokeh_graph(product_list, search_query, analysis_text=""):
    """Creates a professional dashboard with multiple Bokeh graphs and analysis."""
    if not product_list:
        print("No data to plot.")
        return

    # Prepare DataFrame
    data = []
    for item in product_list:
        price = clean_price(item['Price'])
        if price is not None:
            data.append({
                'name': item['Product Name'],
                'price': price,
                'short_name': item['Product Name'][:30] + "..." if len(item['Product Name']) > 30 else item['Product Name']
            })
    
    if not data:
        print("No valid price data found.")
        return

    df = pd.DataFrame(data)
    # Add index as a column so it can be referenced by Bokeh
    df['index'] = df.index
    
    # --- 1. Scatter Plot (Price Distribution) ---
    source = ColumnDataSource(df)
    p_scatter = figure(title=f"Price Distribution for '{search_query}'", 
                       x_axis_label='Item Index', 
                       y_axis_label='Price ($)',
                       tooltips=[("Name", "@name"), ("Price", "$@price{0.2f}")],
                       width=700, height=400)
    
    # Fixed: x='index' refers to the column in the source, not the raw array
    p_scatter.scatter(x='index', y='price', size=8, source=source, legend_label="Price", color="navy", alpha=0.6)
    
    # Add average price line
    avg_price = df['price'].mean()
    avg_line = Span(location=avg_price, dimension='width', line_color='red', line_dash='dashed', line_width=2)
    p_scatter.add_layout(avg_line)
    p_scatter.legend.location = "top_left"

    # --- 2. Histogram (Price Frequency) ---
    hist, edges = np.histogram(df['price'], bins=10)
    hist_df = pd.DataFrame({'top': hist, 'left': edges[:-1], 'right': edges[1:]})
    hist_source = ColumnDataSource(hist_df)
    
    p_hist = figure(title="Price Frequency Histogram", 
                    x_axis_label='Price ($)', 
                    y_axis_label='Count',
                    width=700, height=400)
    p_hist.quad(top='top', bottom=0, left='left', right='right', source=hist_source,
                fill_color="skyblue", line_color="white", alpha=0.7)

    # --- 3. Price Statistics Box (Text) ---
    stats_text = f"""
    <div style="font-family: Arial; padding: 10px; border: 1px solid #ddd; border-radius: 5px;">
        <h3 style="margin-top: 0;">Quick Stats</h3>
        <p><b>Count:</b> {len(df)} items</p>
        <p><b>Average Price:</b> ${df['price'].mean():.2f}</p>
        <p><b>Median Price:</b> ${df['price'].median():.2f}</p>
        <p><b>Min Price:</b> ${df['price'].min():.2f}</p>
        <p><b>Max Price:</b> ${df['price'].max():.2f}</p>
    </div>
    """
    stats_div = Div(text=stats_text, width=300)

    # --- 4. Top 5 Cheapest Items (Bar Chart) ---
    df_sorted = df.sort_values('price').head(5)
    
    # Ensure unique factors for y_range to avoid DUPLICATE_FACTORS error
    # We append the index to the name to make it unique if names are identical
    df_sorted['unique_name'] = df_sorted['short_name'] + " (" + df_sorted.index.astype(str) + ")"
    
    source_bar = ColumnDataSource(df_sorted)
    
    p_bar = figure(y_range=df_sorted['unique_name'], title="Top 5 Cheapest Options",
                   x_axis_label='Price ($)', height=300, width=700,
                   tooltips=[("Name", "@name"), ("Price", "$@price{0.2f}")])
    p_bar.hbar(y='unique_name', right='price', height=0.5, source=source_bar, color="green", alpha=0.6)

    # --- Layout Construction ---
    
    # Handle analysis text formatting
    formatted_analysis = str(analysis_text)
    if not ("<p>" in formatted_analysis or "<ul>" in formatted_analysis or "<h3>" in formatted_analysis):
        formatted_analysis = formatted_analysis.replace("\n", "<br>")

    analysis_div = Div(text=f"""
        <div style="font-family: Arial, sans-serif; padding: 20px; background-color: #f4f4f4; border-radius: 5px; margin-top: 20px;">
            <h2 style="color: #333;">AI Market Analysis</h2>
            <div style="font-size: 14px; line-height: 1.6; color: #555;">
                {formatted_analysis}
            </div>
        </div>
    """, width=1000)

    # Organize layout
    # Row 1: Scatter Plot + Stats
    row1 = row(p_scatter, stats_div)
    # Row 2: Histogram
    row2 = row(p_hist)
    # Row 3: Bar Chart
    row3 = row(p_bar)
    
    # Full Dashboard
    dashboard = column(
        Div(text=f"<h1 style='font-family: Arial; text-align: center;'>eBay Market Dashboard: {search_query}</h1>"),
        row1,
        row2,
        row3,
        analysis_div
    )

    output_filename = f"ebay_dashboard_{search_query.replace(' ', '_')}.html"
    output_file(output_filename)
    
    print(f"Dashboard created: {output_filename}")
    try:
        save(dashboard)
        import webbrowser
        webbrowser.open(f"file://{os.path.abspath(output_filename)}")
    except Exception as e:
        print(f"Could not open browser automatically: {e}")

# --- LangGraph & Gemini Integration ---

class AgentState(TypedDict):
    search_query: str
    scraped_data: List[Dict[str, Any]]
    analysis: str

def scrape_node(state: AgentState):
    """Node to perform the scraping."""
    query = state['search_query']
    print(f"--- LangGraph: Scraping for '{query}' ---")
    
    # We can reuse the logic from the Celery task here directly or call it.
    # Calling the function directly to avoid async complexity within the graph for now.
    # In a production system, you might want to await the Celery result.
    
    url = f"https://www.ebay.com/sch/i.html?_nkw={query.replace(' ', '+')}&_sop=12"
    
    response = None
    # Attempt with proxy if configured
    if proxies:
        try:
            response = requests.get(url, headers=headers, proxies=proxies, timeout=20)
            if response.status_code != 200:
                response = None
        except Exception:
            response = None
    
    # Fallback
    if response is None:
        try:
            response = requests.get(url, headers=headers, timeout=20)
        except Exception:
            return {"scraped_data": []}

    if not response or response.status_code != 200:
        return {"scraped_data": []}

    soup = BeautifulSoup(response.text, 'html.parser')
    items = soup.select('.s-item__info, .s-card, .s-item__wrapper')
    product_list = []

    for item in items:
        title_elem = item.select_one('.s-item__title, .s-card__title, [role="heading"]')
        price_elem = item.select_one('.s-item__price, .s-card__price')

        if title_elem and price_elem:
            name = title_elem.get_text(strip=True)
            name = name.replace("New Listing", "").replace("Opens in a new window or tab", "").strip()
            price = price_elem.get_text(strip=True)

            if not name or "Shop on eBay" in name:
                continue

            product_list.append({"Product Name": name, "Price": price})

    if product_list and "results for" in product_list[0]["Product Name"].lower():
        product_list.pop(0)
        
    return {"scraped_data": product_list}

def analyze_node(state: AgentState):
    """Node to analyze the data using Gemini."""
    print("--- LangGraph: Analyzing Data with Gemini ---")
    data = state['scraped_data']
    query = state['search_query']
    
    if not data:
        return {"analysis": "No data found to analyze."}

    # Prepare a summary of the data for the LLM (limit to first 20 items to save tokens)
    data_summary = "\n".join([f"- {item['Product Name']}: {item['Price']}" for item in data[:20]])
    
    prompt = f"""
    You are an expert market analyst. I have scraped eBay for "{query}".
    Here are the top results:
    {data_summary}
    
    Please provide a detailed market analysis formatted in HTML. 
    Use <h3> for section headers, <ul>/<li> for lists, and <p> for paragraphs.
    Do not include <html>, <head>, or <body> tags.
    
    Sections to cover:
    1. Price Range
    2. Trends (brands, specs)
    3. Buying Recommendation
    """
    
    try:
        llm = ChatGoogleGenerativeAI(model="gemini-3-flash-preview", google_api_key=os.environ.get("GOOGLE_API_KEY"))
        response = llm.invoke(prompt)
        content = response.content
        
        # Robust content extraction
        final_text = ""
        if isinstance(content, str):
            final_text = content
        elif isinstance(content, list):
            # Handle list of blocks (e.g. [{'type': 'text', 'text': '...'}])
            for part in content:
                if isinstance(part, dict):
                    final_text += part.get('text', '')
                elif hasattr(part, 'text'):
                    final_text += part.text
                else:
                    final_text += str(part)
        else:
            final_text = str(content)
            
        return {"analysis": final_text}
    except Exception as e:
        return {"analysis": f"Failed to analyze with Gemini: {e}"}

def build_graph():
    workflow = StateGraph(AgentState)
    
    workflow.add_node("scraper", scrape_node)
    workflow.add_node("analyst", analyze_node)
    
    workflow.set_entry_point("scraper")
    workflow.add_edge("scraper", "analyst")
    workflow.add_edge("analyst", END)
    
    return workflow.compile()

@app.task
def scrape_ebay_product_list(search_query):
    """
    Scrapes eBay for product listings based on a search query and saves them to a CSV.
    This task is designed to be run by Celery.
    """
    # This function is kept for backward compatibility with the Celery task interface
    # But we will now use the LangGraph workflow inside it if we want the analysis.
    
    # For the purpose of this task, let's run the graph.
    print(f"Starting LangGraph workflow for: {search_query}")
    app_graph = build_graph()
    result = app_graph.invoke({"search_query": search_query, "scraped_data": [], "analysis": ""})
    
    scraped_data = result.get("scraped_data", [])
    analysis = result.get("analysis", "")
    
    print("\n=== Gemini Analysis ===\n")
    print(analysis)
    print("\n=======================\n")
    
    # Save to CSV (Legacy logic)
    if scraped_data:
        filename = f"ebay_product_list_{search_query.replace(' ', '_')}.csv"
        with open(filename, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=["Product Name", "Price"])
            writer.writeheader()
            writer.writerows(scraped_data)
        print(f"Saved {len(scraped_data)} products to '{filename}'")
        
    # Return both data and analysis so the caller can use them
    return {"data": scraped_data, "analysis": analysis}

if __name__ == "__main__":
    # Enable eager execution to run tasks locally without a worker for debugging
    app.conf.task_always_eager = True

    search_term = "gaming laptop"
    
    # Check for Google API Key
    if not os.environ.get("GOOGLE_API_KEY"):
        print("ERROR: GOOGLE_API_KEY not found in environment variables. Gemini analysis will fail.")
        # You might want to set it here for testing if not in .env
        # os.environ["GOOGLE_API_KEY"] = "YOUR_KEY_HERE"

    print("Starting eBay product list scraping task with LangGraph & Gemini...")
    
    result = scrape_ebay_product_list.delay(search_term)
    
    # Get the scraped results
    try:
        task_result = result.get(timeout=120) 
        
        # Handle the new return format (dict with data and analysis)
        if isinstance(task_result, dict) and "data" in task_result:
            scraped_data = task_result["data"]
            analysis_text = task_result.get("analysis", "")
            
            if scraped_data:
                create_bokeh_graph(scraped_data, search_term, analysis_text)
            else:
                print("No scraped data received.")
        # Fallback for legacy return format (list)
        elif isinstance(task_result, list):
             if task_result:
                create_bokeh_graph(task_result, search_term)
             else:
                print("No scraped data received.")

    except Exception as e:
        print(f"Error retrieving task result: {e}")
