"""
Quick configuration test for AssemblyAI transcription service.
"""

import os
import sys
from pathlib import Path

# Add app directory to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.transcription_service import API_KEY

def test_configuration():
    """Test if the transcription service is properly configured."""
    print("\n🔍 Testing AssemblyAI Configuration")
    print("================================")
    
    # Check API key
    if not API_KEY:
        print("❌ API_KEY is not set")
        return False
    
    if len(API_KEY) < 32:  # AssemblyAI keys are typically longer
        print("⚠️ API_KEY looks invalid (too short)")
        return False
        
    print("✅ API_KEY is properly configured")
    
    # Check AssemblyAI package
    try:
        import assemblyai
        print(f"✅ assemblyai package installed (version {assemblyai.__version__})")
    except ImportError:
        print("❌ assemblyai package is not installed")
        print("Run: pip install assemblyai")
        return False
    
    return True

if __name__ == "__main__":
    success = test_configuration()
    if success:
        print("\n✅ Configuration test passed!")
        print("\nYou can now run the full transcription test:")
        print("python tools/test_transcription_service.py")
    else:
        print("\n❌ Configuration test failed")
        print("Please fix the issues above before running transcription tests")