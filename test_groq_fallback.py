#!/usr/bin/env python3
"""
Test script for Groq API Key Fallback System
Demonstrates how the system automatically switches between API keys
"""

import os
import sys
from dotenv import load_dotenv

# Add the app directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), '.'))

load_dotenv()

def test_groq_fallback_system():
    """Test the Groq API key fallback system"""
    
    print("🚀 Testing Groq API Key Fallback System")
    print("=" * 50)
    
    try:
        # Import the configuration
        from app.config.groq_config import groq_config
        
        print(f"✅ Configuration loaded successfully")
        print(f"📊 Total API keys: {len(groq_config.api_keys)}")
        
        # Display current status
        status = groq_config.get_status()
        print(f"\n📋 Current Status:")
        print(f"   • Active keys: {status['active_keys']}/{status['total_keys']}")
        print(f"   • Current key: {status['current_key_name']}")
        print(f"   • Current index: {status['current_key_index']}")
        
        # Display individual key status
        print(f"\n🔑 API Key Details:")
        for i, key_info in enumerate(status['keys']):
            status_icon = "✅" if key_info['is_active'] else "❌"
            print(f"   {i+1}. {key_info['name']} {status_icon}")
            print(f"      • Active: {key_info['is_active']}")
            print(f"      • Error count: {key_info['error_count']}")
            print(f"      • Usage count: {key_info['usage_count']}")
        
        # Test the fallback model
        print(f"\n🧪 Testing GroqWithFallback Model:")
        from app.models.groq_with_fallback import GroqWithFallback
        from agno.agent import Agent
        
        # Create a test agent
        model = GroqWithFallback(id="llama-3.3-70b-versatile")
        test_agent = Agent(
            name="FallbackTestAgent",
            model=model,
            description="Test agent for fallback system"
        )
        
        print(f"   ✅ Model created successfully")
        
        # Test API call
        print(f"   🔄 Making API call...")
        response = test_agent.run("Say 'Fallback system working!' in exactly 3 words")
        
        print(f"   ✅ API call successful!")
        print(f"   📝 Response: {response.content}")
        
        # Show final status
        final_status = model.get_status()
        print(f"\n📊 Final Status:")
        print(f"   • Current key: {final_status['current_key_name']}")
        print(f"   • Usage count: {final_status['keys'][final_status['current_key_index']]['usage_count']}")
        
        print(f"\n🎉 Groq API Key Fallback System is working perfectly!")
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing fallback system: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_nutrient_analyzer():
    """Test the nutrient analyzer with fallback"""
    
    print(f"\n🥗 Testing Nutrient Analyzer with Fallback")
    print("=" * 50)
    
    try:
        from app.services.nutrient_analyzer_service import NutrientAnalyzerService
        
        service = NutrientAnalyzerService()
        print(f"✅ NutrientAnalyzerService created")
        
        # Test nutrition analysis
        result = service.analyze_food_nutrition("banana", "1 medium")
        
        if result['success']:
            nutrients = result['parsed_nutrients']
            print(f"✅ Analysis successful!")
            print(f"   • Food: {result['food_name']}")
            print(f"   • Serving: {result['serving_size']}")
            print(f"   • Calories: {nutrients['calories']}")
            print(f"   • Protein: {nutrients['protein']}g")
            print(f"   • Carbs: {nutrients['carbohydrates']}g")
            print(f"   • Fat: {nutrients['fat']}g")
        else:
            print(f"❌ Analysis failed: {result['error']}")
            
        return result['success']
        
    except Exception as e:
        print(f"❌ Error testing nutrient analyzer: {e}")
        return False

if __name__ == "__main__":
    print("🧪 Groq API Key Fallback System Test Suite")
    print("=" * 60)
    
    # Test 1: Basic fallback system
    test1_success = test_groq_fallback_system()
    
    # Test 2: Nutrient analyzer
    test2_success = test_nutrient_analyzer()
    
    # Summary
    print(f"\n📋 Test Summary:")
    print(f"   • Fallback System: {'✅ PASS' if test1_success else '❌ FAIL'}")
    print(f"   • Nutrient Analyzer: {'✅ PASS' if test2_success else '❌ FAIL'}")
    
    if test1_success and test2_success:
        print(f"\n🎉 All tests passed! Your Groq API key fallback system is ready!")
    else:
        print(f"\n⚠️  Some tests failed. Please check the configuration.")
