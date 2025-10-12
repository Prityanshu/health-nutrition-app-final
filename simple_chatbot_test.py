#!/usr/bin/env python3
"""
Simple Chatbot Test
Tests the chatbot with minimal queries to isolate issues
"""

import requests
import json

def test_simple_chatbot():
    base_url = "http://localhost:8001"
    
    # Authenticate
    auth_response = requests.post(
        f"{base_url}/api/auth/login",
        data={"username": "chatbotuser", "password": "testpass123"},
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    
    if auth_response.status_code != 200:
        print(f"❌ Authentication failed: {auth_response.status_code}")
        return
    
    token = auth_response.json()["access_token"]
    print("✅ Authentication successful")
    
    # Test simple queries
    test_queries = [
        "hello",
        "what can i eat for lunch",
        "chicken recipe",
        "workout plan"
    ]
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }
    
    for query in test_queries:
        print(f"\n🧪 Testing: '{query}'")
        
        try:
            response = requests.post(
                f"{base_url}/api/chatbot/chat",
                json={"query": query},
                headers=headers
            )
            
            if response.status_code == 200:
                result = response.json()
                print(f"✅ Success: {result.get('success')}")
                print(f"🎯 Agent: {result.get('agent_used')}")
                print(f"📝 Response length: {len(str(result.get('response', '')))}")
                if result.get('error'):
                    print(f"⚠️ Error: {result['error']}")
            else:
                print(f"❌ HTTP Error: {response.status_code}")
                print(f"Response: {response.text}")
                
        except Exception as e:
            print(f"❌ Request error: {e}")

if __name__ == "__main__":
    test_simple_chatbot()
