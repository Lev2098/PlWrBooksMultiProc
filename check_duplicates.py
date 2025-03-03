import json
from collections import defaultdict

def check_duplicates():
    with open('books.json', 'r', encoding='utf-8') as f:
        books = json.load(f)
    
    # Check by URL
    url_count = defaultdict(int)
    url_books = defaultdict(list)
    
    # Check by title
    title_count = defaultdict(int)
    title_books = defaultdict(list)
    
    for book in books:
        url = book.get('url', '')
        title = book.get('title', '')
        
        url_count[url] += 1
        url_books[url].append(book)
        
        title_count[title] += 1
        title_books[title].append(book)
    
    print(f"Total books in file: {len(books)}")
    
    # Outputting duplicates by URL
    url_duplicates = {url: count for url, count in url_count.items() if count > 1}
    if url_duplicates:
        print("<---------------------->"
              "\n⚠️ Duplicate URLs found:")
        for url, count in url_duplicates.items():
            print(f"\nURL: {url}")
            print(f"Count: {count}")
            for book in url_books[url]:
                print(f"Title: {book['title']}")
            print("<---------------------->")
    else:
        print("\n✅ No duplicate URLs found")
    
    # Outputting duplicates by title
    title_duplicates = {title: count for title, count in title_count.items() if count > 1}
    if title_duplicates:
        print("<---------------------->"
              "\n⚠️ Duplicate titles found ⚠️")
        for title, count in title_duplicates.items():
            print(f"\n Title: {title}"
                  f"\n Count: {count}")
            for book in title_books[title]:
                print(f" URL: {book['url']}")
            print("<---------------------->")
    else:
        print("\n✅ No duplicate titles found")

if __name__ == "__main__":
    check_duplicates() 