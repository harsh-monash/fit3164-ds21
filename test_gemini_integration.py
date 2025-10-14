#!/usr/bin/env python3
"""
Test script for Gemini AI Integration
Run this script to verify the Gemini integration is working correctly.
"""

import os
import sys
import asyncio
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Try to load .env file if python-dotenv is available
try:
    from dotenv import load_dotenv
    env_file = project_root / '.env'
    if env_file.exists():
        load_dotenv(env_file)
        print(f"Loaded environment from: {env_file}")
    else:
        # Try config/.env
        env_file = project_root / 'config' / '.env'
        if env_file.exists():
            load_dotenv(env_file)
            print(f"Loaded environment from: {env_file}")
except ImportError:
    print("Note: python-dotenv not installed. Using system environment variables only.")
    print("To use .env files, run: pip install python-dotenv")


def check_environment():
    """Check if environment is properly configured"""
    print("=" * 60)
    print("GEMINI INTEGRATION TEST")
    print("=" * 60)
    print()
    
    print("1. Checking Environment Variables...")
    api_key = os.getenv('GEMINI_API_KEY')
    
    if api_key:
        masked_key = api_key[:10] + "..." + api_key[-4:] if len(api_key) > 14 else "***"
        print(f"   ✓ GEMINI_API_KEY is set: {masked_key}")
        return True
    else:
        print("   ✗ GEMINI_API_KEY is NOT set")
        print("   → Set it with: export GEMINI_API_KEY='your_key_here'")
        return False


def check_dependencies():
    """Check if required packages are installed"""
    print("\n2. Checking Dependencies...")
    
    try:
        import google.generativeai as genai
        print("   ✓ google-generativeai is installed")
        return True
    except ImportError:
        print("   ✗ google-generativeai is NOT installed")
        print("   → Install with: pip install google-generativeai==0.3.2")
        return False


async def test_service():
    """Test the Gemini service"""
    print("\n3. Testing Gemini Service...")
    
    try:
        from app.services.gemini_analysis_service import gemini_service
        
        if not gemini_service.is_configured():
            print("   ✗ Service is not configured (API key missing)")
            return False
        
        print("   ✓ Service initialized successfully")
        
        # Test temperature analysis
        print("\n4. Testing Temperature Analysis...")
        test_data = {
            'max_data': [
                {'date': '2025-01-01', 'value': 28.5},
                {'date': '2025-01-02', 'value': 30.2},
                {'date': '2025-01-03', 'value': 29.8},
                {'date': '2025-01-04', 'value': 27.3},
                {'date': '2025-01-05', 'value': 28.9},
            ],
            'min_data': [
                {'date': '2025-01-01', 'value': 18.3},
                {'date': '2025-01-02', 'value': 19.1},
                {'date': '2025-01-03', 'value': 18.7},
                {'date': '2025-01-04', 'value': 17.5},
                {'date': '2025-01-05', 'value': 18.0},
            ]
        }
        
        analysis = await gemini_service.generate_temperature_analysis(
            data=test_data,
            station_name="Test Station",
            date_range="Jan 1-5"
        )
        
        print("   ✓ Temperature analysis generated")
        print("\n   Analysis Preview:")
        print("   " + "-" * 56)
        print(f"   {analysis[:200]}...")
        print("   " + "-" * 56)
        
        # Test wind analysis
        print("\n5. Testing Wind Analysis...")
        wind_data = {
            'data': [
                {'date': '2025-01-01', 'value': 5.2},
                {'date': '2025-01-02', 'value': 6.8},
                {'date': '2025-01-03', 'value': 4.5},
                {'date': '2025-01-04', 'value': 7.1},
                {'date': '2025-01-05', 'value': 5.9},
            ]
        }
        
        analysis = await gemini_service.generate_wind_analysis(
            data=wind_data,
            station_name="Test Station",
            date_range="Jan 1-5"
        )
        
        print("   ✓ Wind analysis generated")
        print("\n   Analysis Preview:")
        print("   " + "-" * 56)
        print(f"   {analysis[:200]}...")
        print("   " + "-" * 56)
        
        # Test humidity analysis
        print("\n6. Testing Humidity Analysis...")
        humidity_data = {
            'data': [
                {'date': '2025-01-01', 'value': 65.3},
                {'date': '2025-01-02', 'value': 72.1},
                {'date': '2025-01-03', 'value': 68.7},
                {'date': '2025-01-04', 'value': 70.5},
                {'date': '2025-01-05', 'value': 66.0},
            ]
        }
        
        analysis = await gemini_service.generate_humidity_analysis(
            data=humidity_data,
            station_name="Test Station",
            date_range="Jan 1-5"
        )
        
        print("   ✓ Humidity analysis generated")
        print("\n   Analysis Preview:")
        print("   " + "-" * 56)
        print(f"   {analysis[:200]}...")
        print("   " + "-" * 56)
        
        return True
        
    except Exception as e:
        print(f"   ✗ Error testing service: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_fallback():
    """Test fallback analysis when API is not configured"""
    print("\n7. Testing Fallback Mode...")
    
    try:
        # Temporarily unset API key
        original_key = os.getenv('GEMINI_API_KEY')
        if 'GEMINI_API_KEY' in os.environ:
            del os.environ['GEMINI_API_KEY']
        
        from importlib import reload
        from app.services import gemini_analysis_service
        reload(gemini_analysis_service)
        
        fallback_service = gemini_analysis_service.GeminiAnalysisService()
        
        if not fallback_service.is_configured():
            print("   ✓ Fallback mode detected correctly")
            
            test_data = {
                'max_data': [{'date': '2025-01-01', 'value': 28.5}],
                'min_data': [{'date': '2025-01-01', 'value': 18.3}]
            }
            
            fallback_analysis = fallback_service._fallback_temperature_analysis(test_data)
            print("   ✓ Fallback analysis generated")
            print(f"\n   Fallback Text: {fallback_analysis}")
        
        # Restore API key
        if original_key:
            os.environ['GEMINI_API_KEY'] = original_key
        
        return True
        
    except Exception as e:
        print(f"   ✗ Error testing fallback: {str(e)}")
        return False


def print_summary(results):
    """Print test summary"""
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    all_passed = all(results.values())
    
    for test_name, passed in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status}: {test_name}")
    
    print()
    if all_passed:
        print("🎉 All tests passed! Gemini integration is working correctly.")
        print("\nNext Steps:")
        print("1. Start the server: python start_server.py")
        print("2. Navigate to the weather visualization page")
        print("3. Select a weather station to see AI-generated analysis")
    else:
        print("❌ Some tests failed. Please check the errors above.")
        print("\nTroubleshooting:")
        print("1. Ensure GEMINI_API_KEY is set correctly")
        print("2. Install dependencies: pip install -r requirements.txt")
        print("3. Check the documentation: docs/GEMINI_QUICK_SETUP.md")
    
    print("=" * 60)


async def main():
    """Main test function"""
    results = {}
    
    # Run tests
    results['Environment Check'] = check_environment()
    results['Dependencies Check'] = check_dependencies()
    
    # Only run service tests if environment and dependencies are OK
    if results['Environment Check'] and results['Dependencies Check']:
        results['Service Test'] = await test_service()
        results['Fallback Test'] = test_fallback()
    else:
        results['Service Test'] = False
        results['Fallback Test'] = False
        print("\n⚠️  Skipping service tests due to environment/dependency issues")
    
    # Print summary
    print_summary(results)
    
    # Exit with appropriate code
    sys.exit(0 if all(results.values()) else 1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nUnexpected error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
