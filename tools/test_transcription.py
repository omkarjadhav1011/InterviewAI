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

from app.services.transcription_service import tts_synthesize, stt_transcribe

def create_test_audio(text, output_path="test_audio.wav"):
    """Create a test audio file using TTS."""
    try:
        print(f"\n🎤 Testing TTS with text: '{text}'")
        audio_data = tts_synthesize(text)
        
        if isinstance(audio_data, str) and audio_data.startswith(('http://', 'https://')):
            print("✅ TTS returned a URL, downloading audio...")
            response = requests.get(audio_data)
            audio_data = response.content
        
        if audio_data:
            # Save audio to WAV file
            with wave.open(output_path, 'wb') as wav_file:
                wav_file.setnchannels(1)  # Mono
                wav_file.setsampwidth(2)  # 2 bytes per sample
                wav_file.setframerate(16000)  # 16kHz sample rate
                wav_file.writeframes(audio_data)
            print(f"✅ Audio file created: {output_path}")
            return output_path
        else:
            print("❌ No audio data received from TTS")
            return None
    except Exception as e:
        print(f"❌ Error creating test audio: {e}")
        return None

def test_transcription(audio_path):
    """Test STT by transcribing the audio file."""
    try:
        print("\n🎧 Testing STT with generated audio...")
        with open(audio_path, 'rb') as audio_file:
            transcript = stt_transcribe(audio_file)
        
        if transcript:
            print(f"✅ Transcription received: '{transcript}'")
            return transcript
        else:
            print("❌ No transcription received")
            return None
    except Exception as e:
        print(f"❌ Error during transcription: {e}")
        return None

def compare_results(original_text, transcribed_text):
    """Compare original text with transcription."""
    if not transcribed_text:
        print("\n❌ Cannot compare - no transcription available")
        return False
        
    original = original_text.lower().strip()
    transcribed = transcribed_text.lower().strip()
    
    print("\n📊 Comparison Results:")
    print(f"Original text: '{original}'")
    print(f"Transcribed : '{transcribed}'")
    
    # Calculate simple similarity score
    words_original = set(original.split())
    words_transcribed = set(transcribed.split())
    common_words = words_original.intersection(words_transcribed)
    similarity = len(common_words) / max(len(words_original), len(words_transcribed))
    
    print(f"\nSimilarity score: {similarity:.2%}")
    return similarity > 0.7  # Consider successful if 70% or more words match

def cleanup(audio_path):
    """Clean up test files."""
    try:
        if os.path.exists(audio_path):
            os.remove(audio_path)
            print(f"\n🧹 Cleaned up test file: {audio_path}")
    except Exception as e:
        print(f"\n⚠️ Error during cleanup: {e}")

def main():
    """Run the transcription service test suite."""
    print("\n🔍 Starting Transcription Service Test Suite...")
    
    # Test cases with varying complexity
    test_cases = [
        "Hello, this is a test of the transcription service.",
        "Python programming is fun and rewarding.",
        "The quick brown fox jumps over the lazy dog."
    ]
    
    results = []
    for i, test_text in enumerate(test_cases, 1):
        print(f"\n📝 Test Case {i}/{len(test_cases)}")
        print("-" * 50)
        
        # Create test audio
        audio_path = f"test_audio_{i}.wav"
        created_audio = create_test_audio(test_text, audio_path)
        
        if created_audio:
            # Test transcription
            transcribed_text = test_transcription(audio_path)
            
            # Compare results
            success = compare_results(test_text, transcribed_text)
            results.append(success)
            
            # Cleanup
            cleanup(audio_path)
            
            # Short pause between tests
            time.sleep(1)
    
    # Final summary
    print("\n📊 Test Suite Summary:")
    print("-" * 50)
    print(f"Total tests: {len(test_cases)}")
    print(f"Successful: {sum(results)}")
    print(f"Failed: {len(results) - sum(results)}")
    print(f"Success rate: {(sum(results) / len(results)) * 100:.1f}%")
    
    if all(results):
        print("\n✅ All transcription tests passed!")
    else:
        print("\n⚠️ Some tests failed. Check logs above for details.")

if __name__ == "__main__":
    main()