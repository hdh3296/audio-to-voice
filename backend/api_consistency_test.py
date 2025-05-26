#!/usr/bin/env python3
"""
API 일관성 테스트 - 같은 파일을 여러 번 테스트
"""
import os
import sys
import asyncio
from dotenv import load_dotenv
from openai import OpenAI
from faster_whisper import WhisperModel

async def test_api_multiple_times(audio_path: str, num_tests: int = 3):
    """API를 여러 번 호출해서 일관성 확인"""
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")
    
    if not api_key or api_key == "your_openai_api_key_here":
        print("❌ API 키가 설정되지 않음")
        return
    
    client = OpenAI(api_key=api_key)
    
    print(f"🔄 OpenAI API {num_tests}회 반복 테스트")
    print("=" * 50)
    
    results = []
    
    for i in range(num_tests):
        try:
            print(f"📡 {i+1}번째 API 호출...")
            
            def call_api():
                with open(audio_path, "rb") as audio_file:
                    return client.audio.transcriptions.create(
                        model="whisper-1",
                        file=audio_file,
                        language="ko",
                        response_format="verbose_json"
                    )
            
            result = await asyncio.to_thread(call_api)
            results.append(result.text.strip())
            print(f"   결과: {result.text.strip()}")
            
        except Exception as e:
            print(f"   ❌ 실패: {e}")
            results.append(f"ERROR: {e}")
    
    print("\n📊 결과 분석:")
    print("-" * 30)
    
    unique_results = list(set(results))
    print(f"고유 결과 수: {len(unique_results)}")
    
    for i, result in enumerate(unique_results):
        count = results.count(result)
        print(f"{i+1}. \"{result}\" ({count}/{num_tests}회)")
    
    if len(unique_results) == 1:
        print("→ ✅ 완전히 일관된 결과!")
    else:
        print("→ ⚠️ 결과에 변동이 있음")

def test_local_whisper(audio_path: str):
    """로컬 Whisper 안정성 확인"""
    print("🏠 로컬 Faster-Whisper 테스트")
    print("=" * 50)
    
    try:
        model = WhisperModel("large-v3", device="cpu", compute_type="int8")
        segments, info = model.transcribe(audio_path, language="ko")
        
        full_text = ""
        for segment in segments:
            text = segment.text.strip()
            if text:
                full_text += text + " "
        
        print(f"✅ 로컬 결과: {full_text.strip()}")
        print(f"   언어: {info.language} (확률: {info.language_probability:.3f})")
        
    except Exception as e:
        print(f"❌ 로컬 테스트 실패: {e}")

async def main():
    if len(sys.argv) != 2:
        print("사용법: python api_consistency_test.py <audio_file>")
        sys.exit(1)
    
    audio_path = sys.argv[1]
    
    if not os.path.exists(audio_path):
        print(f"❌ 파일이 존재하지 않습니다: {audio_path}")
        sys.exit(1)
    
    print(f"🧪 API 일관성 테스트: {os.path.basename(audio_path)}")
    print()
    
    # 로컬 테스트 (기준점)
    test_local_whisper(audio_path)
    print()
    
    # API 여러 번 테스트
    await test_api_multiple_times(audio_path, 5)

if __name__ == "__main__":
    asyncio.run(main())
