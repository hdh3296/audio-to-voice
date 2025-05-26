#!/usr/bin/env python3
"""
독립적인 하이브리드 테스트 (pydub 의존성 없음)
"""
import os
import sys
import asyncio
from dotenv import load_dotenv
from openai import OpenAI
from faster_whisper import WhisperModel

async def test_openai_api_direct(audio_path: str):
    """OpenAI API 직접 테스트"""
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")
    
    if not api_key or api_key == "your_openai_api_key_here":
        print("⚠️ OpenAI API 키가 설정되지 않음")
        return None
    
    try:
        client = OpenAI(api_key=api_key)
        
        def call_api():
            with open(audio_path, "rb") as audio_file:
                return client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    language="ko",
                    response_format="verbose_json",
                    timestamp_granularities=["segment"]
                )
        
        result = await asyncio.to_thread(call_api)
        
        return {
            "method": "openai_api",
            "text": result.text,
            "language": getattr(result, 'language', 'ko'),
            "segments": len(result.segments) if result.segments else 0
        }
        
    except Exception as e:
        print(f"❌ API 호출 실패: {e}")
        return None

def test_local_whisper_direct(audio_path: str):
    """로컬 Whisper 직접 테스트"""
    try:
        model = WhisperModel("large-v3", device="cpu", compute_type="int8")
        segments, info = model.transcribe(audio_path, language="ko")
        
        full_text = ""
        segment_count = 0
        
        for segment in segments:
            text = segment.text.strip()
            if text:
                full_text += text + " "
                segment_count += 1
        
        return {
            "method": "local_whisper",
            "text": full_text.strip(),
            "language": info.language,
            "language_probability": info.language_probability,
            "segments": segment_count
        }
        
    except Exception as e:
        print(f"❌ 로컬 처리 실패: {e}")
        return None

async def main():
    if len(sys.argv) != 2:
        print("사용법: python simple_hybrid_test.py <audio_file>")
        sys.exit(1)
    
    audio_path = sys.argv[1]
    
    if not os.path.exists(audio_path):
        print(f"❌ 파일이 존재하지 않습니다: {audio_path}")
        sys.exit(1)
    
    file_size = os.path.getsize(audio_path) / 1024
    print(f"🧪 하이브리드 Whisper 테스트: {os.path.basename(audio_path)} ({file_size:.1f}KB)")
    print("=" * 60)
    
    # 1. 로컬 모드 테스트
    print("🏠 로컬 Faster-Whisper 테스트")
    print("-" * 30)
    
    local_result = test_local_whisper_direct(audio_path)
    if local_result:
        print("✅ 로컬 모드 성공!")
        print(f"   언어: {local_result['language']} (확률: {local_result.get('language_probability', 0):.2f})")
        print(f"   텍스트: {local_result['text']}")
        print(f"   세그먼트: {local_result['segments']}개")
    else:
        print("❌ 로컬 모드 실패")
    
    print()
    
    # 2. API 모드 테스트
    print("🌐 OpenAI API 테스트")  
    print("-" * 30)
    
    api_result = await test_openai_api_direct(audio_path)
    if api_result:
        print("✅ API 모드 성공!")
        print(f"   언어: {api_result['language']}")
        print(f"   텍스트: {api_result['text']}")
        print(f"   세그먼트: {api_result['segments']}개")
        
        # 비용 계산 (대략적)
        duration = 6  # 테스트 파일은 약 6초
        cost = (duration / 60) * 0.006
        print(f"   예상 비용: ${cost:.4f}")
    else:
        print("❌ API 모드 실패 (API 키 필요)")
    
    print()
    
    # 3. 하이브리드 로직 시뮬레이션
    print("🔄 하이브리드 로직 시뮬레이션")
    print("-" * 30)
    
    if api_result:
        print("✅ API 우선 → API 모드 사용됨")
        chosen_result = api_result
    elif local_result:
        print("✅ API 실패 → 로컬 모드로 자동 대체")
        chosen_result = local_result
    else:
        print("❌ 모든 모드 실패")
        chosen_result = None
    
    if chosen_result:
        print(f"최종 결과: {chosen_result['text']}")
    
    print("\n" + "=" * 60)
    
    if local_result or api_result:
        print("🎉 하이브리드 시스템 테스트 성공!")
        
        # 성능 비교
        if local_result and api_result:
            print("\n📊 성능 비교:")
            print(f"로컬:  {local_result['text']}")
            print(f"API:   {api_result['text']}")
            
            if local_result['text'] == api_result['text']:
                print("→ 결과 일치! ✅")
            else:
                print("→ 결과 차이 있음")
    else:
        print("💥 모든 테스트 실패")

if __name__ == "__main__":
    asyncio.run(main())
