"""
Test script for transcription service functionality.
Tests real-time transcription using AssemblyAI.
"""

import os
import sys
import time
from pathlib import Path

# Add app directory to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.transcription_service import start_transcription, stop_transcription

class TranscriptionTester:
    def __init__(self):
        self.results = []
        
    def run_transcription_test(self, duration=5, expected_text=None):
        """Run a single transcription test for the specified duration."""
        print(f"\n🎤 Starting transcription test (duration: {duration}s)")
        print("Please speak the following text clearly:")
        print(f"'{expected_text}'")
        
        try:
            # Start transcription
            result = start_transcription()
            if result["status"] != "started":
                print("❌ Failed to start transcription")
                return False
            
            # Wait for specified duration
            print(f"\n⏳ Recording for {duration} seconds...")
            time.sleep(duration)
            
            # Stop transcription and get result
            result = stop_transcription()
            transcript = result["transcript"]
            
            print("\n📝 Test Results:")
            print(f"Expected text: '{expected_text}'")
            print(f"Transcribed : '{transcript}'")
            
            # Calculate simple similarity if expected text was provided
            if expected_text:
                similarity = self._calculate_similarity(expected_text, transcript)
                print(f"\nSimilarity score: {similarity:.2%}")
                test_passed = similarity > 0.6  # Consider 60% match as passing
            else:
                print("\nNo expected text provided - check transcript manually")
                test_passed = len(transcript.strip()) > 0
            
            self.results.append(test_passed)
            return test_passed
            
        except Exception as e:
            print(f"❌ Error during test: {e}")
            self.results.append(False)
            return False
    
    def _calculate_similarity(self, expected, actual):
        """Calculate word-based similarity between expected and actual text."""
        expected_words = set(expected.lower().strip().split())
        actual_words = set(actual.lower().strip().split())
        common_words = expected_words.intersection(actual_words)
        return len(common_words) / max(len(expected_words), len(actual_words))
    
    def print_summary(self):
        """Print summary of all test results."""
        total = len(self.results)
        passed = sum(self.results)
        
        print("\n📊 Test Suite Summary:")
        print("-" * 50)
        print(f"Total tests  : {total}")
        print(f"Tests passed : {passed}")
        print(f"Tests failed : {total - passed}")
        if total > 0:
            print(f"Success rate : {(passed / total) * 100:.1f}%")
        
        if all(self.results):
            print("\n✅ All transcription tests passed!")
        else:
            print("\n⚠️ Some tests failed. Check logs above for details.")

def main():
    """Run the transcription service test suite."""
    print("\n🔍 Starting Transcription Service Test Suite")
    print("===========================================")
    print("\nThis test will use your microphone to check the transcription service.")
    print("You will be asked to speak several test phrases.")
    print("Make sure your microphone is connected and working.")
    print("\nPress Enter to begin, or Ctrl+C to cancel...")
    input()
    
    tester = TranscriptionTester()
    
    # Test cases
    test_cases = [
        {
            "text": "Hello, this is a test of the transcription service.",
            "duration": 5
        },
        {
            "text": "Testing microphone input and speech recognition.",
            "duration": 5
        },
        {
            "text": "The quick brown fox jumps over the lazy dog.",
            "duration": 5
        }
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n🔄 Running Test {i}/{len(test_cases)}")
        print("-" * 50)
        
        tester.run_transcription_test(
            duration=test_case["duration"],
            expected_text=test_case["text"]
        )
        
        # Short pause between tests
        if i < len(test_cases):
            print("\nPausing before next test...")
            time.sleep(2)
    
    tester.print_summary()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️ Test suite interrupted by user")
        print("Stopping any active transcription...")
        stop_transcription()
        sys.exit(1)