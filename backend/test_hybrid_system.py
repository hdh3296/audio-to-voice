#!/usr/bin/env python3
"""
하이브리드 Whisper 시스템 통합 테스트
로컬 + OpenAI API 모드 모두 테스트
"""
import os
import sys
import asyncio
from pathlib import Path

# 현재 디렉토리를 Python 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from faster_whisper import WhisperModel
from auto_subtitle.openai_client_simple import openai_whisper_client

async def test_hybrid_system(audio_file_path: str):
    """하이브리드 시스템 전체 테스트"""
    
    print("🧪 하이브리드 Whisper 시스템 테스트 시작")
    print("="*60)
    
    # 파일 존재 확인
    if not os.path.exists(audio_file_path):
        print(f"❌ 오디오 파일을 찾을 수 없습니다: {audio_file_path}")
        return False
    
    file_size = os.path.getsize(audio_file_path)
    print(f"📁 파일 정보: {os.path.basename(audio_file_path)} ({file_size/1024:.1f}KB)")
    print()
    
    # 1단계: 로컬 모드 테스트
    print("🏠 1단계: 로컬 Faster-Whisper 테스트")
    print("-" * 40)
    
    local_success = await test_local_mode(audio_file_path)
    print()
    
    # 2단계: OpenAI API 모드 테스트  
    print("🌐 2단계: OpenAI API 모드 테스트")
    print("-" * 40)
    
    api_success = await test_api_mode(audio_file_path)
    print()
    
    # 3단계: 하이브리드 로직 테스트
    print("🔄 3단계: 하이브리드 로직 테스트")
    print("-" * 40)
    
    hybrid_success = await test_hybrid_logic(audio_file_path)
    print()
    
    # 결과 요약
    print("📊 테스트 결과 요약")
    print("=" * 60)
    print(f"🏠 로컬 모드:     {'✅ 성공' if local_success else '❌ 실패'}")
    print(f"🌐 OpenAI API:   {'✅ 성공' if api_success else '❌ 실패 (API 키 필요)'}")
    print(f"🔄 하이브리드:    {'✅ 성공' if hybrid_success else '❌ 실패'}")
    
    return local_success or api_success

async def test_local_mode(audio_path: str) -> bool:
    """로컬 모드 테스트"""
    try:
        print("📥 Faster-Whisper 모델 로드 중...")
        model = WhisperModel("large-v3", device="cpu", compute_type="int8")
        print("✅ 모델 로드 완료")
        
        print("🎯 로컬 음성 인식 중...")
        segments, info = model.transcribe(
            audio_path, 
            language="ko",
            task="transcribe"
        )
        
        segments_list = []
        full_text = ""
        for segment in segments:
            text = segment.text.strip()
            if text:
                segments_list.append(text)
                full_text += text + " "
        
        print(f"✅ 로컬 전사 완료!")
        print(f"   언어: {info.language} (확률: {info.language_probability:.2f})")
        print(f"   텍스트: {full_text.strip()}")
        print(f"   세그먼트: {len(segments_list)}개")
        
        return True
        
    except Exception as e:
        print(f"❌ 로컬 모드 실패: {e}")
        return False

async def test_api_mode(audio_path: str) -> bool:
    """OpenAI API 모드 테스트"""
    try:
        if not openai_whisper_client.is_available():
            print("⚠️ OpenAI API 키가 설정되지 않음")
            print("💡 .env 파일에 OPENAI_API_KEY 설정 필요")
            return False
        
        print("🌐 OpenAI API 전사 중...")
        result = await openai_whisper_client.transcribe_audio_api(audio_path, "ko")
        
        if result.get("success"):
            print(f"✅ API 전사 완료!")
            print(f"   언어: {result.get('language', 'unknown')}")
            print(f"   텍스트: {result.get('text', '')}")
            print(f"   세그먼트: {len(result.get('segments', []))}개")
            print(f"   파일 크기: {result.get('file_size_mb', 0):.1f}MB")
            return True
        else:
            print(f"❌ API 전사 실패: {result.get('error', 'Unknown error')}")
            return False
            
    except Exception as e:
        print(f"❌ API 모드 실패: {e}")
        return False

async def test_hybrid_logic(audio_path: str) -> bool:
    """하이브리드 로직 테스트 (API 우선, 실패시 로컬 대체)"""
    try:
        print("🔄 하이브리드 로직 실행...")
        
        # API 모드 우선 시도
        if openai_whisper_client.is_available():
            print("   → API 모드 시도...")
            api_result = await openai_whisper_client.transcribe_audio_api(audio_path, "ko")
            
            if api_result.get("success"):
                print("   ✅ API 모드 성공!")
                print(f"   텍스트: {api_result.get('text', '')}")
                return True
            else:
                print(f"   ⚠️ API 모드 실패: {api_result.get('error')}")
                print("   → 로컬 모드로 자동 대체...")
        else:
            print("   → API 사용 불가, 로컬 모드로 진행...")
        
        # 로컬 모드로 대체
        print("   → 로컬 모드 실행...")
        model = WhisperModel("large-v3", device="cpu", compute_type="int8")
        segments, info = model.transcribe(audio_path, language="ko")
        
        full_text = ""
        for segment in segments:
            text = segment.text.strip()
            if text:
                full_text += text + " "
        
        print("   ✅ 로컬 모드 성공!")
        print(f"   텍스트: {full_text.strip()}")
        return True
        
    except Exception as e:
        print(f"❌ 하이브리드 로직 실패: {e}")
        return False

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("사용법: python test_hybrid_system.py <audio_file_path>")
        sys.exit(1)
    
    audio_path = sys.argv[1]
    success = asyncio.run(test_hybrid_system(audio_path))
    
    if success:
        print("\n🎉 전체 테스트 성공!")
    else:
        print("\n💥 테스트 실패!")
