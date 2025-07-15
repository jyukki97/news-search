# -*- coding: utf-8 -*-
#!/usr/bin/env python3
"""BBC 실제 검색 페이지 구조 분석"""

import requests
from bs4 import BeautifulSoup
import json
import re

def analyze_bbc_search_images():
    """Analyze image information from BBC search results"""
    url = "https://www.bbc.com/search"
    params = {'q': 'technology'}
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
    }
    
    try:
        response = requests.get(url, params=params, headers=headers, timeout=15)
        response.raise_for_status()
        
        print("=== BBC Search Results Image Analysis ===")
        
        # 1. Find image info in JSON data
        print("\n1. Looking for image info in JSON data:")
        json_patterns = [
            r'"results":\s*(\[.*?\])',
            r'"pageProps"[^{]*"results":\s*(\[.*?\])',
        ]
        
        for i, pattern in enumerate(json_patterns):
            matches = re.findall(pattern, response.text, re.DOTALL)
            for match in matches:
                try:
                    # Show first 1000 chars only
                    sample = match[:1000] + "..." if len(match) > 1000 else match
                    print(f"Pattern {i+1} match sample:")
                    print(sample)
                    print("-" * 50)
                    
                    # Try to parse JSON
                    # Simple cleanup
                    cleaned = match.strip()
                    if cleaned.endswith(','):
                        cleaned = cleaned[:-1]
                    
                    results = json.loads(cleaned)
                    if results and len(results) > 0:
                        first_item = results[0]
                        print(f"First result keys: {list(first_item.keys())}")
                        
                        # Look for image-related keys
                        for key, value in first_item.items():
                            if 'image' in key.lower() or 'img' in key.lower() or 'photo' in key.lower():
                                print(f"Image-related key '{key}': {value}")
                        
                        # Check if there are images in metadata
                        if 'metadata' in first_item:
                            metadata = first_item['metadata']
                            print(f"Metadata keys: {list(metadata.keys()) if isinstance(metadata, dict) else 'not a dict'}")
                            if isinstance(metadata, dict):
                                for key, value in metadata.items():
                                    if 'image' in key.lower() or 'img' in key.lower() or 'photo' in key.lower():
                                        print(f"Image-related key in metadata '{key}': {value}")
                        
                        break
                    
                except Exception as e:
                    print(f"JSON parsing failed: {e}")
                    continue
        
        # 2. Find images in HTML
        print("\n2. Looking for images in HTML:")
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Find all image tags
        images = soup.find_all('img')
        print(f"Total {len(images)} image tags found")
        
        # Find images related to search results
        search_containers = soup.find_all(['div', 'article'], class_=re.compile(r'search|result', re.I))
        print(f"Found {len(search_containers)} search result containers")
        
        for i, container in enumerate(search_containers[:3]):  # Check first 3 only
            images_in_container = container.find_all('img')
            if images_in_container:
                print(f"Container {i+1} has {len(images_in_container)} images:")
                for img in images_in_container:
                    src = img.get('src', '')
                    data_src = img.get('data-src', '')
                    alt = img.get('alt', '')
                    print(f"  - src: {src}")
                    print(f"  - data-src: {data_src}")
                    print(f"  - alt: {alt}")
                    print()
        
        # 3. Look for image info in script tags
        print("\n3. Looking for image info in script tags:")
        scripts = soup.find_all('script')
        for script in scripts:
            if script.string and 'image' in script.string.lower():
                # Output part of script content only
                content = script.string.strip()
                if len(content) > 500:
                    print(f"Image-related script found (length: {len(content)}):")
                    print(content[:500] + "...")
                else:
                    print(f"Image-related script:")
                    print(content)
                print("-" * 50)
        
    except Exception as e:
        print(f"Analysis failed: {e}")

if __name__ == "__main__":
    analyze_bbc_search_images() 