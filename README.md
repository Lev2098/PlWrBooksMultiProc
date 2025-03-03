# PlWrBooksMultiProc
# Books to Scrape - Multi-Process Scraper

A high-performance web scraper built with Playwright and Python's multiprocessing to extract book data from [Books to Scrape](https://books.toscrape.com/).

## Features

- **Multi-Process Architecture**: Utilizes Python's multiprocessing for parallel scraping
- **Safe Data Handling**: Implements atomic file operations to prevent data corruption
- **Robust Error Handling**: Includes retry mechanisms and error logging
- **Progress Monitoring**: Real-time statistics and ETA calculations
- **Data Validation**: Built-in duplicate detection and data integrity checks

## Project Structure

## Requirements

- Python 3.13
- Playwright
- Required packages: `pip install -r requirements.txt`

## Usage

1. Install dependencies:

```bash
pip install -r requirements.txt
playwright install
```

2. Run the scraper:
```bash
python plwr_scraper.py
```

3. Check for duplicates (optional):
```bash
python check_duplicates.py
```

## Output

The scraper saves book data in JSON format with the following structure:
```json
{
    "title": "Book Title",
    "category": "Category",
    "price": "£00.00",
    "rating": "Rating",
    "stock": "Stock status",
    "image_url": "Image URL",
    "description": "Book description",
    "product_info": {
        "UPC": "Unique code",
        "Product Type": "Books",
        ...
    },
    "url": "Product URL"
}
```

## Implementation Details

### plwr_scraper.py
- Multi-process implementation
- Safe file handling with atomic writes
- Real-time progress monitoring
- Automatic retry mechanism
- Memory-efficient processing

### check_duplicates.py
- Validates scraped data
- Checks for URL duplicates
- Checks for title duplicates
- Provides detailed reports

## Performance

- Processes multiple books simultaneously
- Handles network issues gracefully
- Maintains data integrity with atomic writes
- Provides real-time progress updates
- Typical processing speed: 2-5 books per second

## Error Handling

- Automatic retry for failed requests
- Backup creation on write errors
- Detailed error logging
- Process monitoring and recovery

## Acknowledgments

- [Books to Scrape](https://books.toscrape.com/) for providing the test website
