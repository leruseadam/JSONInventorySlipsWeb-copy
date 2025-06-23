#!/usr/bin/env python3
"""
Test script to verify session handling improvements
"""

import requests
import json
import time

def test_session_handling():
    """Test the session handling with a large dataset"""
    base_url = "http://localhost:5001"
    
    # Test data - simulate a large Bamboo dataset
    test_data = {
        "transfers": [
            {
                "id": f"transfer_{i}",
                "inventory_transfer_items": [
                    {
                        "Product Name*": f"Product {i}-{j}",
                        "Barcode*": f"BARCODE{i}{j:03d}",
                        "Quantity Received*": j,
                        "Vendor": f"Vendor {i}",
                        "Product Type*": "Flower",
                        "Accepted Date": "2025-06-22"
                    }
                    for j in range(1, 6)  # 5 items per transfer
                ]
            }
            for i in range(1, 21)  # 20 transfers = 100 items total
        ]
    }
    
    # Alternative: Use a simpler format that matches the parser
    simple_test_data = {
        "data": [
            {
                "Product Name*": f"Product {i}",
                "Barcode*": f"BARCODE{i:03d}",
                "Quantity Received*": i,
                "Vendor": f"Vendor {i}",
                "Product Type*": "Flower",
                "Accepted Date": "2025-06-22"
            }
            for i in range(1, 26)  # 25 items
        ]
    }
    
    print("Testing session handling with large dataset...")
    print(f"Dataset size: {len(json.dumps(simple_test_data))} characters")
    
    # Test the search_json_or_api endpoint
    try:
        response = requests.post(
            f"{base_url}/search_json_or_api",
            data={"search_input": json.dumps(simple_test_data)},
            allow_redirects=False
        )
        
        print(f"Response status: {response.status_code}")
        print(f"Response headers: {dict(response.headers)}")
        
        if response.status_code == 302:
            print("✅ Successfully processed large dataset")
            print(f"Redirect location: {response.headers.get('Location', 'None')}")
        else:
            print(f"❌ Unexpected response: {response.text[:200]}")
            
    except Exception as e:
        print(f"❌ Error testing session handling: {e}")

if __name__ == "__main__":
    test_session_handling() 