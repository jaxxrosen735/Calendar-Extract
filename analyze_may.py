from bs4 import BeautifulSoup

with open('debug_tiff_final.html', 'r', encoding='utf-8') as f:
    html = f.read()

soup = BeautifulSoup(html, 'html.parser')

# Find all text containing "May"
elements_with_may = soup.find_all(string=lambda text: text and 'May' in text)
print(f"Found {len(elements_with_may)} elements with 'May'")

# Analyze the structure around first occurrence
if elements_with_may:
    elem = elements_with_may[0]
    
    # Walk up the tree to find the containing event card
    current = elem.parent
    depth = 0
    
    print(f"\n--- Walking up the tree from 'May' ---")
    while current and depth < 10:
        print(f"\nDepth {depth}: <{current.name}> (id={current.get('id', 'N/A')}, class={current.get('class', [])})")
        
        # Look for siblings that might contain event data
        if current.name in ['div', 'article', 'section']:
            # Print immediate children
            children = list(current.children)[:5]
            for child in children:
                if hasattr(child, 'name'):
                    text = child.get_text(strip=True)[:50] if child.get_text else ""
                    print(f"  - child: <{child.name}> {text}")
                    
        current = current.parent
        depth += 1

# Also search for common event container patterns
print("\n\n--- Looking for event grids/containers ---")
# Look for divs with specific patterns
for div in soup.find_all('div', class_=lambda x: x and any(kw in str(x).lower() for kw in ['grid', 'list', 'group', 'row'])):
    text_preview = div.get_text(strip=True)[:100]
    classes = div.get('class', [])
    print(f"Found div with classes {classes}: {text_preview}")
