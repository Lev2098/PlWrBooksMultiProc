import json
import multiprocessing
import queue
import time
from playwright.sync_api import sync_playwright
from multiprocessing import Lock
import os


BASE_URL = "https://books.toscrape.com/"
DATA_FILE = "books.json"
lock = Lock()


class BookScraper:
    def __init__(self, use_cdp=False, cdp_port=9222):
        self.retry_count = 3
        self.retry_delay = 2
        self.use_cdp = use_cdp
        self.cdp_port = cdp_port

    def initialize_browser(self):
        """Optimized browser initialization"""
        playwright = sync_playwright().start()
        launch_args = {
            'headless': True,
            'args': [
                '--disable-gpu',
                '--disable-dev-shm-usage',
                '--disable-setuid-sandbox',
                '--no-sandbox',
                '--disable-extensions',
                '--disable-logging',
                '--disable-web-security',
            ]
        }
        
        if self.use_cdp:
            launch_args['args'].append(f'--remote-debugging-port={self.cdp_port}')
        
        browser = playwright.chromium.launch(**launch_args)
        context = browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            java_script_enabled=True,
            ignore_https_errors=True,
            bypass_csp=True
        )
        
        # Disable loading of images and other resources
        context.route("**/*.{png,jpg,jpeg,gif,svg,css,woff,woff2}", lambda route: route.abort())
        
        page = context.new_page()
        page.set_default_timeout(15000)
        
        return playwright, browser, page

    def scrape_book(self, page, book_url):
        for attempt in range(self.retry_count):
            try:
                page.goto(book_url, timeout=30000)
                page.wait_for_load_state("networkidle")

                if not page.locator(".product_main").is_visible():
                    raise Exception("Page did not load properly")

                title = page.locator(".product_main h1").inner_text()
                category = page.locator("ul.breadcrumb li:nth-child(3) a").inner_text()
                price = page.locator(".product_main .price_color").first.inner_text()
                rating = page.locator(".product_main .star-rating").first.get_attribute("class").split()[-1]
                stock_text = page.locator(".product_main .instock.availability").first.inner_text().strip()
                
                image_relative_url = page.locator("#product_gallery img").first.get_attribute("src")
                image_url = f"{BASE_URL}{image_relative_url.lstrip('/')}" if image_relative_url else None
                
                description = ""
                desc_locator = page.locator("#product_description ~ p")
                if desc_locator.count() > 0:
                    description = desc_locator.first.inner_text()

                product_info = {}
                info_table = page.locator("table.table-striped")
                if info_table.count() > 0:
                    rows = info_table.first.locator("tr").all()
                    for row in rows:
                        key = row.locator("th").inner_text().strip()
                        value = row.locator("td").inner_text().strip()
                        product_info[key] = value

                book_data = {
                    "title": title,
                    "category": category,
                    "price": price,
                    "rating": rating,
                    "stock": stock_text,
                    "image_url": image_url,
                    "description": description,
                    "product_info": product_info,
                    "url": book_url
                }
                
                print(f"Successfully scraped: {title}")
                return book_data

            except Exception as e:
                print(f"Error scraping {book_url}: {e}")
                if attempt < self.retry_count - 1:
                    time.sleep(self.retry_delay)
        
        return None

    def save_data(self, data):
        with lock:
            try:
                # Read existing data
                try:
                    with open(DATA_FILE, "r", encoding='utf-8') as f:
                        existing_data = json.load(f)
                except (FileNotFoundError, json.JSONDecodeError):
                    existing_data = []

                # Check if book already exists
                exists = False
                for book in existing_data:
                    if book.get('url') == data['url']:
                        exists = True
                        break

                if not exists:
                    # Create temporary file for safe writing
                    temp_file = f"{DATA_FILE}.temp"
                    
                    # Add new data
                    existing_data.append(data)
                    
                    try:
                        # First write to temporary file
                        with open(temp_file, "w", encoding='utf-8') as f:
                            json.dump(existing_data, f, indent=4, ensure_ascii=False)
                        
                        # If write successful, rename temporary file
                        if os.path.exists(DATA_FILE):
                            os.replace(temp_file, DATA_FILE)
                        else:
                            os.rename(temp_file, DATA_FILE)
                            
                        print(f"Saved book: {data['title']}")
                    except Exception as e:
                        print(f"Error writing to file: {e}")
                        # Delete temporary file in case of error
                        if os.path.exists(temp_file):
                            os.remove(temp_file)
                        raise
                else:
                    print(f"Book already exists: {data['title']}")

            except Exception as e:
                print(f"Error saving data: {e}")
                # Create backup on error
                try:
                    backup_file = f"backup_{int(time.time())}.json"
                    with open(backup_file, "w", encoding='utf-8') as f:
                        json.dump([data], f, indent=4, ensure_ascii=False)
                    print(f"Created backup file: {backup_file}")
                except Exception as backup_error:
                    print(f"Error creating backup: {backup_error}")

    # def validate_book_data(self, data):
    #     """Validates and cleans book data before saving"""
    #     required_fields = ['title', 'category', 'price', 'url']
    #
    #     # Check required fields
    #     for field in required_fields:
    #         if field not in data:
    #             raise ValueError(f"Missing required field: {field}")
    #
    #     # Validate URL
    #     if not data['url'].startswith(BASE_URL):
    #         raise ValueError(f"Invalid URL: {data['url']}")
    #
    #     return True


class ProcessManager:
    def __init__(self, num_processes=3, use_cdp=False):
        self.num_processes = num_processes
        self.use_cdp = use_cdp
        self.manager = multiprocessing.Manager()
        self.url_queue = self.manager.Queue()
        self.save_queue = self.manager.Queue()  # New queue for data to save
        self.error_queue = self.manager.Queue()
        self.processed_urls = self.manager.dict()
        self.total_books = 0
        self.should_stop = self.manager.Event()
        self.load_tasks()

    def load_tasks(self):
        """Load all book URLs into the queue"""
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                page.goto(BASE_URL)

                categories = page.locator("ul.nav-list > li > ul > li > a").evaluate_all("elements => elements.map(e => e.href)")
                print(f"Found {len(categories)} categories")
                
                all_book_urls = set()  # Use set for unique URLs
                
                for i, category_url in enumerate(categories, 1):
                    print(f"Processing category {i}/{len(categories)}")
                    page.goto(category_url)
                    
                    category_books = 0
                    while True:
                        book_links = page.locator(".product_pod h3 a").evaluate_all("elements => elements.map(e => e.href)")
                        for link in book_links:
                            if link not in all_book_urls:
                                self.url_queue.put(link)
                                all_book_urls.add(link)
                                category_books += 1
                        
                        print(f"Found {category_books} books in current category")
                        
                        next_button = page.locator("li.next a")
                        if next_button.count() == 0:
                            break
                        
                        next_button.click()
                        page.wait_for_load_state("networkidle")

                self.total_books = len(all_book_urls)
                browser.close()
                print(f"Found {self.total_books} unique books to scrape")
                
        except Exception as e:
            print(f"Error loading tasks: {e}")
            raise

    @staticmethod
    def saver_process(save_queue, should_stop):
        """Separate process for saving data"""
        while not (should_stop.is_set() and save_queue.empty()):
            try:
                # Wait for data no more than 1 second
                data = save_queue.get(timeout=1)
                
                # Read existing data
                try:
                    with open(DATA_FILE, "r", encoding='utf-8') as f:
                        existing_data = json.load(f)
                except (FileNotFoundError, json.JSONDecodeError):
                    existing_data = []

                # Check if book already exists
                exists = False
                for book in existing_data:
                    if book.get('url') == data['url']:
                        exists = True
                        break

                if not exists:
                    # Add new data
                    existing_data.append(data)
                    
                    # Safe write using temporary file
                    temp_file = f"{DATA_FILE}.temp"
                    with open(temp_file, "w", encoding='utf-8') as f:
                        json.dump(existing_data, f, indent=4, ensure_ascii=False)
                    
                    os.replace(temp_file, DATA_FILE)
                    print(f"Saved book: {data['title']}")
                
            except queue.Empty:
                continue
            except Exception as e:
                print(f"Error in saver process: {e}")

    @staticmethod
    def worker_process(process_id, url_queue, save_queue, error_queue, processed_urls, use_cdp):
        """Worker process"""
        try:
            scraper = BookScraper(use_cdp=use_cdp, cdp_port=9222 + process_id)
            playwright, browser, page = scraper.initialize_browser()
            
            while True:
                try:
                    book_url = url_queue.get_nowait()
                except queue.Empty:
                    break

                if book_url in processed_urls:
                    continue

                try:
                    book_data = scraper.scrape_book(page, book_url)
                    if book_data:
                        processed_urls[book_url] = True
                        save_queue.put(book_data)  # Send data for saving
                except Exception as e:
                    print(f"Error in process {process_id} processing {book_url}: {e}")
                    error_queue.put((process_id, book_url, str(e)))

            browser.close()
            playwright.stop()
            
        except Exception as e:
            print(f"Critical error in process {process_id}: {e}")
            error_queue.put((process_id, None, str(e)))

    def start(self):
        """Start processes including saver process"""
        processes = []
        print(f"Starting {self.num_processes} processes...")
        
        # Start process for saving
        saver = multiprocessing.Process(
            target=self.saver_process,
            args=(self.save_queue, self.should_stop)
        )
        saver.start()
        
        # Start worker processes
        for i in range(self.num_processes):
            p = multiprocessing.Process(
                target=self.worker_process,
                args=(i, self.url_queue, self.save_queue, self.error_queue, 
                      self.processed_urls, self.use_cdp)
            )
            p.start()
            processes.append(p)

        start_time = time.time()
        last_log_time = start_time
        last_count = 0
        
        # Monitor processes
        while any(p.is_alive() for p in processes):
            # Handle errors
            while not self.error_queue.empty():
                process_id, book_url, error = self.error_queue.get()
                print(f"Process {process_id} encountered error: {error}")
                if book_url:
                    self.url_queue.put(book_url)

            # Show progress
            current_time = time.time()
            current_count = len(self.processed_urls)
            elapsed_time = current_time - start_time
            time_since_last_log = current_time - last_log_time
            
            # Log every 5 seconds
            if time_since_last_log >= 5:
                books_per_second = current_count / elapsed_time if elapsed_time > 0 else 0
                books_since_last_log = current_count - last_count
                current_speed = books_since_last_log / time_since_last_log if time_since_last_log > 0 else 0
                
                # Estimate time to completion
                remaining_books = self.total_books - current_count
                eta_seconds = remaining_books / current_speed if current_speed > 0 else 0
                eta_minutes = eta_seconds / 60
                
                print("\n=== Progress Update ===")
                print(f"Processed: {current_count}/{self.total_books} books ({(current_count/self.total_books)*100:.2f}%)")
                print(f"Overall speed: {books_per_second:.2f} books/second")
                print(f"Current speed: {current_speed:.2f} books/second")
                print(f"ETA: {eta_minutes:.1f} minutes")
                print(f"Active processes: {sum(1 for p in processes if p.is_alive())}/{self.num_processes}")
                print("=" * 20)
                
                last_log_time = current_time
                last_count = current_count
            
            time.sleep(1)

        print("\nAll books processed! Shutting down...")
        for p in processes:
            if p.is_alive():
                p.terminate()
            p.join()

        # Signal saver process to finish
        self.should_stop.set()
        saver.join()


def main(num_processes=3, use_cdp=False):
    print("\n=== Starting Book Scraper ===")
    start_time = time.time()
    
    # Check existing scraped books
    try:
        with open(DATA_FILE, "r", encoding='utf-8') as f:
            existing_books = json.load(f)
            print(f"Found {len(existing_books)} books already scraped in {DATA_FILE}")
    except (FileNotFoundError, json.JSONDecodeError):
        existing_books = []
        print(f"No existing books found in {DATA_FILE}")

    manager = ProcessManager(num_processes=num_processes, use_cdp=use_cdp)
    manager.start()

    end_time = time.time()
    total_time = end_time - start_time
    hours = int(total_time // 3600)
    minutes = int((total_time % 3600) // 60)
    seconds = int(total_time % 60)

    # Calculate final statistics
    try:
        with open(DATA_FILE, "r", encoding='utf-8') as f:
            final_books = json.load(f)
            new_books = len(final_books) - len(existing_books)
            
        print("\n=== Scraping Complete ===")
        print(f"Total time: {hours:02d}:{minutes:02d}:{seconds:02d}")
        print(f"Books at start: {len(existing_books)}")
        print(f"New books scraped: {new_books}")
        print(f"Total books in database: {len(final_books)}")
        if total_time > 0:
            print(f"Average speed: {new_books / total_time:.2f} books/second")
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error reading final results: {e}")


if __name__ == "__main__":
    main()
 