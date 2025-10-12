#!/usr/bin/env python3
"""
Comprehensive Chatbot Test Suite
Tests various query types to optimize chatbot routing and responses
"""

import requests
import json
import time
from typing import Dict, Any

class ChatbotTester:
    def __init__(self, base_url: str = "http://localhost:8001"):
        self.base_url = base_url
        self.auth_token = None
        self.test_results = []
        
    def authenticate(self, username: str = "chatbotuser", password: str = "testpass123"):
        """Authenticate and get token"""
        try:
            response = requests.post(
                f"{self.base_url}/api/auth/login",
                data={"username": username, "password": password},
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            if response.status_code == 200:
                self.auth_token = response.json()["access_token"]
                print("✅ Authentication successful")
                return True
            else:
                print(f"❌ Authentication failed: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Authentication error: {e}")
            return False
    
    def test_query(self, query: str, expected_agent: str = None, description: str = "") -> Dict[str, Any]:
        """Test a single query"""
        if not self.auth_token:
            return {"error": "Not authenticated"}
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.auth_token}"
        }
        
        payload = {"query": query}
        
        try:
            start_time = time.time()
            response = requests.post(
                f"{self.base_url}/api/chatbot/chat",
                json=payload,
                headers=headers
            )
            end_time = time.time()
            
            response_time = end_time - start_time
            
            if response.status_code == 200:
                result = response.json()
                test_result = {
                    "query": query,
                    "description": description,
                    "success": result.get("success", False),
                    "agent_used": result.get("agent_used", "unknown"),
                    "expected_agent": expected_agent,
                    "response_time": response_time,
                    "response": result.get("response", {}),
                    "error": result.get("error"),
                    "correct_agent": expected_agent == result.get("agent_used") if expected_agent else None
                }
                
                # Print result
                status = "✅" if result.get("success") else "❌"
                agent_match = "🎯" if test_result["correct_agent"] else "⚠️" if expected_agent else ""
                print(f"{status} {agent_match} {description}: {result.get('agent_used', 'unknown')} ({response_time:.2f}s)")
                
                return test_result
            else:
                print(f"❌ HTTP Error {response.status_code}: {response.text}")
                return {"query": query, "error": f"HTTP {response.status_code}", "response_time": response_time}
                
        except Exception as e:
            print(f"❌ Request error: {e}")
            return {"query": query, "error": str(e)}
    
    def run_comprehensive_tests(self):
        """Run comprehensive test suite"""
        print("🧪 Starting Comprehensive Chatbot Test Suite")
        print("=" * 60)
        
        # Test cases organized by category
        test_cases = [
            # Meal Requests
            {
                "category": "Meal Requests",
                "tests": [
                    ("what can i eat for lunch today", "chefgenius", "Basic lunch request"),
                    ("what should i have for a chicken dinner tonight", "chefgenius", "Chicken dinner request"),
                    ("I want to cook chicken breast for dinner", "chefgenius", "Specific protein request"),
                    ("suggest me a healthy lunch recipe with vegetables and protein", "chefgenius", "Healthy meal request"),
                    ("what's a good breakfast idea", "chefgenius", "Breakfast request"),
                    ("I need a quick snack", "chefgenius", "Snack request"),
                ]
            },
            
            # Recipe Requests
            {
                "category": "Recipe Requests", 
                "tests": [
                    ("give me a recipe for masala dosa", "culinaryexplorer", "Specific dish recipe"),
                    ("how to make chicken curry", "culinaryexplorer", "Cooking instruction"),
                    ("recipe for biryani", "culinaryexplorer", "Traditional dish"),
                    ("how to cook pasta", "culinaryexplorer", "Basic cooking"),
                    ("kerala beef fry recipe", "culinaryexplorer", "Regional cuisine"),
                ]
            },
            
            # Fitness Requests
            {
                "category": "Fitness Requests",
                "tests": [
                    ("how much do i have to workout to burn 5 kg weight in a week", "fitmentor", "Weight loss workout"),
                    ("give me a workout plan for building muscle", "fitmentor", "Muscle building"),
                    ("I am highly active", "fitmentor", "Activity level"),
                    ("cardio exercises for beginners", "fitmentor", "Cardio request"),
                    ("strength training routine", "fitmentor", "Strength training"),
                ]
            },
            
            # Meal Planning
            {
                "category": "Meal Planning",
                "tests": [
                    ("create a weekly meal plan", "advanced_meal_planner", "Weekly planning"),
                    ("7-day diet plan for weight loss", "advanced_meal_planner", "Diet planning"),
                    ("meal planning for the week", "advanced_meal_planner", "General meal planning"),
                ]
            },
            
            # Budget Requests
            {
                "category": "Budget Requests",
                "tests": [
                    ("cheap meal ideas under 100 rupees", "budgetchef", "Budget constraint"),
                    ("affordable dinner recipes", "budgetchef", "Affordable cooking"),
                    ("budget meal plan", "budgetchef", "Budget meal planning"),
                ]
            },
            
            # Nutrition Analysis
            {
                "category": "Nutrition Analysis",
                "tests": [
                    ("analyze the nutrition of this meal", "nutrient_analyzer", "Nutrition analysis"),
                    ("how many calories in chicken breast", "nutrient_analyzer", "Calorie query"),
                    ("protein content of eggs", "nutrient_analyzer", "Macro query"),
                ]
            },
            
            # Edge Cases
            {
                "category": "Edge Cases",
                "tests": [
                    ("hello", "chefgenius", "Greeting"),
                    ("help", "chefgenius", "Help request"),
                    ("what can you do", "chefgenius", "Capability query"),
                    ("", "chefgenius", "Empty query"),
                    ("random text without keywords", "chefgenius", "No keywords"),
                ]
            },
            
            # Context Following
            {
                "category": "Context Following",
                "tests": [
                    ("I want chicken for dinner", "chefgenius", "Context 1: Chicken dinner"),
                    ("make it spicy", "chefgenius", "Context 2: Follow-up request"),
                    ("what about lunch tomorrow", "chefgenius", "Context 3: Next meal"),
                ]
            }
        ]
        
        all_results = []
        
        for category in test_cases:
            print(f"\n📋 {category['category']}")
            print("-" * 40)
            
            for query, expected_agent, description in category["tests"]:
                result = self.test_query(query, expected_agent, description)
                all_results.append(result)
                time.sleep(0.5)  # Rate limiting
        
        # Generate summary
        self.generate_summary(all_results)
        
        return all_results
    
    def generate_summary(self, results: list):
        """Generate test summary"""
        print("\n" + "=" * 60)
        print("📊 TEST SUMMARY")
        print("=" * 60)
        
        total_tests = len(results)
        successful_tests = len([r for r in results if r.get("success")])
        failed_tests = total_tests - successful_tests
        
        # Agent accuracy
        agent_tests = [r for r in results if r.get("expected_agent")]
        correct_agent = len([r for r in agent_tests if r.get("correct_agent")])
        agent_accuracy = (correct_agent / len(agent_tests) * 100) if agent_tests else 0
        
        # Response times
        response_times = [r.get("response_time", 0) for r in results if r.get("response_time")]
        avg_response_time = sum(response_times) / len(response_times) if response_times else 0
        max_response_time = max(response_times) if response_times else 0
        
        print(f"Total Tests: {total_tests}")
        print(f"Successful: {successful_tests} ({successful_tests/total_tests*100:.1f}%)")
        print(f"Failed: {failed_tests} ({failed_tests/total_tests*100:.1f}%)")
        print(f"Agent Accuracy: {correct_agent}/{len(agent_tests)} ({agent_accuracy:.1f}%)")
        print(f"Avg Response Time: {avg_response_time:.2f}s")
        print(f"Max Response Time: {max_response_time:.2f}s")
        
        # Agent distribution
        agent_counts = {}
        for result in results:
            agent = result.get("agent_used", "unknown")
            agent_counts[agent] = agent_counts.get(agent, 0) + 1
        
        print(f"\nAgent Distribution:")
        for agent, count in sorted(agent_counts.items()):
            print(f"  {agent}: {count} queries")
        
        # Failed tests
        failed_results = [r for r in results if not r.get("success")]
        if failed_results:
            print(f"\n❌ Failed Tests:")
            for result in failed_results:
                print(f"  - {result.get('description', result.get('query', 'Unknown'))}: {result.get('error', 'Unknown error')}")
        
        # Save results
        with open("chatbot_test_results.json", "w") as f:
            json.dump(results, f, indent=2)
        
        print(f"\n💾 Results saved to chatbot_test_results.json")

def main():
    """Main function to run tests"""
    tester = ChatbotTester()
    
    if not tester.authenticate():
        print("❌ Cannot proceed without authentication")
        return
    
    print("🚀 Running comprehensive chatbot tests...")
    results = tester.run_comprehensive_tests()
    
    print("\n✅ Test suite completed!")

if __name__ == "__main__":
    main()
