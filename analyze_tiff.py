import json
from bs4 import BeautifulSoup

with open('debug_tiff_page1.html', 'r', encoding='utf-8') as f:
    html = f.read()

soup = BeautifulSoup(html, 'html.parser')

# Find JSON-LD scripts
json_scripts = soup.find_all('script', {'type': 'application/ld+json'})
print(f"Total JSON-LD scripts: {len(json_scripts)}")

# Parse and check what type of data is in them
for i, script in enumerate(json_scripts[:3]):  # First 3 scripts
    try:
        data = json.loads(script.string)
        if isinstance(data, dict):
            print(f"\nScript {i+1}: {data.get('@type', data.get('type', 'unknown'))}")
            if data.get('@type') == 'Event':
                print(f"  - Event name: {data.get('name', 'N/A')[:50]}")
        elif isinstance(data, list) and len(data) > 0:
            print(f"\nScript {i+1}: Array with {len(data)} items")
            if isinstance(data[0], dict) and data[0].get('@type') == 'Event':
                print(f"  - First event: {data[0].get('name', 'N/A')[:50]}")
    except Exception as e:
        print(f"Script {i+1}: Error parsing - {e}")

# Check for buttons
print("\n\nSearching for buttons and links...")
all_buttons = soup.find_all('button')
print(f"Total buttons: {len(all_buttons)}")
for btn in all_buttons[:5]:
    aria_label = btn.get('aria-label', '')
    text = btn.get_text(strip=True)[:30]
    print(f"  - {aria_label or text}")

# Check for navigation elements
nav = soup.find('nav')
if nav:
    print("\nFound <nav> element")
    nav_buttons = nav.find_all(['button', 'a'])
    for b in nav_buttons[:5]:
        print(f"  - {b}")

# Look for event containers
print("\n\nSearching for event containers...")
event_containers = soup.find_all(['div', 'article'], class_=lambda x: x and 'event' in str(x).lower())
print(f"Event containers found: {len(event_containers)}")

# Look for specific TIFF structures
print("\nLooking for TIFF-specific data structures...")
# Search for elements with data attributes
elements_with_data = soup.find_all(lambda tag: tag.has_attr('data-event-id') or tag.has_attr('data-eventid'))
print(f"Elements with event IDs: {len(elements_with_data)}")
