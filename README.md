# eBay Market Analyzer with AI & Visualization

This project is a sophisticated eBay scraper and market analysis tool. It scrapes product data from eBay, analyzes the market trends using Google's Gemini AI, and generates an interactive dashboard with visualizations using Bokeh.

## Features

*   **Web Scraping**: Scrapes eBay search results for product names and prices.
*   **Proxy Support**: Configurable proxy support (Bright Data) with automatic fallback to direct connection.
*   **AI Market Analysis**: Uses **Google Gemini 1.5 Flash** via **LangChain** and **LangGraph** to provide a professional market summary (price ranges, trends, buying advice).
*   **Interactive Dashboard**: Generates a rich HTML dashboard using **Bokeh** containing:
    *   Price Distribution Scatter Plot
    *   Price Frequency Histogram
    *   Top 5 Cheapest Options Bar Chart
    *   Quick Statistics (Average, Median, Min, Max)
    *   Embedded AI Analysis Report
*   **Task Queue**: Built on **Celery** for asynchronous task execution (can also run in eager mode for local testing).

## Prerequisites

*   Python 3.13+
*   Redis (for Celery broker)
*   Google Cloud API Key (for Gemini)

## Installation

1.  **Clone the repository**:
    ```bash
    git clone <repository-url>
    cd ebay-products-market-analizer
    ```

2.  **Install dependencies**:
    It is recommended to use a virtual environment.
    ```bash
    pip install -r requirements.txt
    # Or if using uv/poetry based on pyproject.toml
    pip install .
    ```
    *Key dependencies*: `requests`, `beautifulsoup4`, `celery`, `bokeh`, `pandas`, `langchain`, `langgraph`, `langchain-google-genai`, `python-dotenv`.

3.  **Configure Environment Variables**:
    Create a `.env` file in the `ebay-products-market-analizer` directory (or root) with the following keys:

    ```ini
    # Google Gemini API Key (Required for AI Analysis)
    GOOGLE_API_KEY=your_google_api_key_here

    # Bright Data Proxy Credentials (Optional)
    BRD_USERNAME=your_username
    BRD_PASSWORD=your_password
    ```

4.  **Start Redis**:
    Ensure a Redis server is running locally on port 6379.
    ```bash
    redis-server
    ```

## Usage

### Running Locally (Debug Mode)

The script is configured to run in "eager mode" by default, meaning it doesn't require a separate Celery worker process to be running. It will execute the scraping and analysis immediately.

1.  Navigate to the project directory:
    ```bash
    cd ebay-products-market-analizer
    ```

2.  Run the main script:
    ```bash
    python main.py
    ```

3.  **Output**:
    *   The script will print the scraping progress and the AI analysis to the console.
    *   It will save a CSV file: `ebay_product_list_<search_term>.csv`.
    *   It will generate and automatically open an HTML dashboard: `ebay_dashboard_<search_term>.html`.

### Running with Celery Worker (Production Mode)

To use the actual asynchronous task queue:

1.  Modify `ebay-products-market-analizer/main.py`:
    Set `app.conf.task_always_eager = False` in the `if __name__ == "__main__":` block.

2.  Start the Celery worker:
    ```bash
    celery -A main worker --loglevel=info
    ```

3.  Run the script to dispatch the task:
    ```bash
    python main.py
    ```

## Project Structure

*   `ebay-products-market-analizer/main.py`: The core script containing the scraper, LangGraph workflow, Gemini integration, and Bokeh visualization logic.
*   `pyproject.toml`: Project dependencies and configuration.

## Troubleshooting

*   **Proxy Errors**: If the proxy fails, the script automatically falls back to a direct connection. Check your `BRD_USERNAME` and `BRD_PASSWORD` if you intend to use proxies.
*   **Gemini Errors**: Ensure your `GOOGLE_API_KEY` is valid and has access to the `gemini-1.5-flash` model.
*   **Bokeh Errors**: If the browser doesn't open automatically, look for the generated `.html` file in the directory and open it manually.
