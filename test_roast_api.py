#!/usr/bin/env python3
"""
Test script for LinkedIn Profile Roasting API
This script tests the new roasting endpoints
"""

import requests
import json
import time

# Configuration
BASE_URL = "http://localhost:5000"
TEST_LINKEDIN_URL = "https://www.linkedin.com/in/nithin-jambula-59b3a4233/"

def test_roast_profile():
    """Test the roast profile endpoint"""
    print("🔥 Testing Profile Roast Endpoint")
    print("=" * 50)
    
    url = f"{BASE_URL}/api/roast-profile"
    payload = {
        "profile_url": TEST_LINKEDIN_URL,
        "user_interests": ["software development", "AI", "technology"],
        "tone": "witty",
        "company": "google"  # Test company-specific roasting
    }
    
    print(f"📤 Sending POST to: {url}")
    print(f"📋 Payload: {json.dumps(payload, indent=2)}")
    
    try:
        response = requests.post(url, json=payload, timeout=120)  # Increased timeout to 2 minutes
        print(f"📊 Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print("✅ SUCCESS! Roast generated:")
            print("-" * 30)
            
            if data.get('success'):
                roast = data.get('roast', {})
                print(f"🎯 Roast Level: {roast.get('roast_level', 'unknown')}")
                print(f"💡 Comedy Gold: {roast.get('comedy_gold_quote', 'N/A')}")
                print(f"📝 Summary: {roast.get('complete_roast_summary', 'N/A')[:200]}...")
                print(f"🔗 Profile URL: {data.get('profile_url')}")
                print(f"🏢 Company: {data.get('metadata', {}).get('company', 'N/A')}")
                
                highlights = roast.get('roast_highlights', [])
                print(f"\n🎪 Roast Highlights ({len(highlights)} items):")
                for i, highlight in enumerate(highlights[:3], 1):
                    print(f"  {i}. {highlight}")
                
                return True
            else:
                print(f"❌ Roast failed: {data.get('error')}")
                return False
        else:
            print(f"❌ HTTP Error: {response.status_code}")
            try:
                error_data = response.json()
                print(f"Error details: {error_data}")
            except:
                print(f"Response text: {response.text}")
            return False
            
    except requests.RequestException as e:
        print(f"❌ Request failed: {e}")
        return False

def test_cached_roast():
    """Test the cached roast endpoint"""
    print("\n📱 Testing Cached Roast Endpoint")
    print("=" * 50)
    
    url = f"{BASE_URL}/api/get-cached-roast"
    params = {"profile_url": TEST_LINKEDIN_URL}
    
    print(f"📤 Sending GET to: {url}")
    print(f"📋 Params: {params}")
    
    try:
        response = requests.get(url, params=params)
        print(f"📊 Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            if data.get('cached'):
                print("✅ SUCCESS! Found cached roast:")
                cached_data = data.get('data', {})
                print(f"🕒 From cache: {cached_data.get('from_cache', False)}")
                print(f"📅 Cached at: {cached_data.get('cached_at', 'unknown')}")
                return True
            else:
                print("ℹ️ No cached roast found (this is normal for first-time)")
                return True
        else:
            print(f"❌ HTTP Error: {response.status_code}")
            return False
            
    except requests.RequestException as e:
        print(f"❌ Request failed: {e}")
        return False

def test_roast_stats():
    """Test the roast statistics endpoint"""
    print("\n📊 Testing Roast Stats Endpoint")
    print("=" * 50)
    
    url = f"{BASE_URL}/api/roast-stats"
    
    print(f"📤 Sending GET to: {url}")
    
    try:
        response = requests.get(url)
        print(f"📊 Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                stats = data.get('stats', {})
                print("✅ SUCCESS! Stats retrieved:")
                print(f"📈 Total roasts: {stats.get('total_roasts', 0)}")
                print(f"🕐 Recent roasts (24h): {stats.get('recent_roasts_24h', 0)}")
                print(f"🗄️ Database status: {stats.get('database_status', 'unknown')}")
                print(f"🎭 Available tones: {', '.join(stats.get('available_tones', []))}")
                
                platforms = stats.get('platform_distribution', [])
                if platforms:
                    print("🏢 Platform distribution:")
                    for platform in platforms:
                        print(f"  - {platform.get('_id', 'unknown')}: {platform.get('count', 0)} roasts")
                
                return True
            else:
                print(f"❌ Stats failed: {data.get('error')}")
                return False
        else:
            print(f"❌ HTTP Error: {response.status_code}")
            return False
            
    except requests.RequestException as e:
        print(f"❌ Request failed: {e}")
        return False

def test_health_check():
    """Test if the server is running"""
    print("🏥 Testing Server Health")
    print("=" * 50)
    
    url = f"{BASE_URL}/health"
    
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            print("✅ Server is healthy and running!")
            return True
        else:
            print(f"⚠️ Server responded with status: {response.status_code}")
            return False
    except requests.RequestException as e:
        print(f"❌ Server is not responding: {e}")
        print("💡 Make sure the Flask app is running on port 5000")
        return False

def main():
    """Run all tests"""
    print("🚀 SYNTEXA LinkedIn Profile Roasting API Tests")
    print("=" * 60)
    
    # Test server health first
    if not test_health_check():
        print("\n❌ Server is not running. Please start the Flask app first.")
        return
    
    # Wait a bit for server to be fully ready
    time.sleep(1)
    
    # Run all tests
    results = []
    
    print(f"\n🎯 Testing with LinkedIn URL: {TEST_LINKEDIN_URL}")
    print("⚠️ Note: This may take 30-60 seconds for first-time scraping")
    
    results.append(("Health Check", test_health_check()))
    results.append(("Roast Stats", test_roast_stats()))
    results.append(("Cached Roast Check", test_cached_roast()))
    results.append(("Profile Roast", test_roast_profile()))
    results.append(("Cached Roast Verify", test_cached_roast()))
    
    # Summary
    print("\n" + "=" * 60)
    print("📋 TEST SUMMARY")
    print("=" * 60)
    
    passed = 0
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {test_name}")
        if result:
            passed += 1
    
    print(f"\n🎯 Results: {passed}/{len(results)} tests passed")
    
    if passed == len(results):
        print("🎉 All tests passed! The roasting API is working perfectly.")
        print("\n🔗 You can now integrate this into your frontend:")
        print(f"   POST {BASE_URL}/api/roast-profile")
        print(f"   GET  {BASE_URL}/api/get-cached-roast")
        print(f"   GET  {BASE_URL}/api/roast-stats")
    else:
        print("⚠️ Some tests failed. Check the logs above for details.")

if __name__ == "__main__":
    main()
