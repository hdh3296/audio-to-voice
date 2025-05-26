#!/usr/bin/env python3
"""
OpenAI Whisper API 테스트 스크립트
pydub 없이 직접 API 테스트
"""
import os
import asyncio
from dotenv import load_dotenv
from openai import OpenAI
import sys

# 환경변수 로드
load_dotenv()

async def test_openai_whisper_api(audio_file_path: str):
    """OpenAI Whisper API 직접 테스트"""
    
    # API 키 확인
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or api_key == "your_openai_api_key_here":
        print("❌ OpenAI API 키가 설정되지 않았습니다.")
        print("💡 .env 파일에 OPENAI_API_KEY를 설정해주세요.")
        return False
    
    # OpenAI 클라이언트 초기화
    client = OpenAI(api_key=api_key)
    print(f"✅ OpenAI 클라이언트 초기화 완료")
    
    # 파일 존재 확인
    if not os.path.exists(audio_file_path):
        print(f"❌ 오디오 파일을 찾을 수 없습니다: {audio_file_path}")
        return False
    
    file_size = os.path.getsize(audio_file_path)
    print(f"📁 파일 정보: {os.path.basename(audio_file_path)} ({file_size/1024:.1f}KB)")
    
    # 파일 크기 제한 확인 (25MB)
    max_size = 25 * 1024 * 1024  # 25MB
    if file_size > max_size:
        print(f"❌ 파일 크기가 너무 큽니다: {file_size/1024/1024:.1f}MB > 25MB")
        return False
    
    try:
        print("🎯 OpenAI Whisper API 전사 시작...")
        
        # API 호출을 별도 함수로 분리 (asyncio 호환)
        def call_api():
            with open(audio_file_path, "rb") as audio_file:
                transcript = client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    language="ko",  # 한국어 설정
                    response_format="verbose_json",
                    timestamp_granularities=["segment"]
                )
                return transcript
        
        # 비동기 실행
        result = await asyncio.to_thread(call_api)
        
        print("✅ API 전사 완료!")
        print(f"🌐 감지된 언어: {result.language}")
        print(f"📝 전사 텍스트: {result.text}")
        print(f"📊 세그먼트 수: {len(result.segments) if result.segments else 0}")
        
        # 세그먼트 정보 출력 (처음 3개만)
        if result.segments:
            print("\n📋 세그먼트 미리보기 (처음 3개):")
            for i, segment in enumerate(result.segments[:3]):
                start_time = f"{int(segment.start//60)}:{int(segment.start%60):02d}"
                end_time = f"{int(segment.end//60)}:{int(segment.end%60):02d}"
                print(f"  {i+1}. [{start_time}-{end_time}] {segment.text}")
        
        # 비용 계산 (대략적)
        duration_seconds = result.duration if hasattr(result, 'duration') else 0
        if duration_seconds == 0 and result.segments:
            duration_seconds = result.segments[-1].end
        
        cost = (duration_seconds / 60) * 0.006  # $0.006 per minute
        print(f"💰 예상 비용: ${cost:.4f} (약 {duration_seconds:.1f}초)")
        
        return True
        
    except Exception as e:
        print(f"❌ API 호출 실패: {str(e)}")
        return False

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("사용법: python test_openai_api.py <audio_file_path>")
        sys.exit(1)
    
    audio_path = sys.argv[1]
    print("🧪 OpenAI Whisper API 테스트 시작")
    print("="*50)
    
    # 비동기 실행
    success = asyncio.run(test_openai_whisper_api(audio_path))
    
    print("="*50)
    if success:
        print("🎉 테스트 성공!")
    else:
        print("💥 테스트 실패!")
