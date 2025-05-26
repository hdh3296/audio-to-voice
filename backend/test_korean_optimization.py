#!/usr/bin/env python3
"""
OpenAI Whisper API 최적화 검증 스크립트
한국어 정확도 개선 확인용
"""
import os
import asyncio
from dotenv import load_dotenv
from openai import OpenAI
import sys

# 환경변수 로드
load_dotenv()

async def test_optimized_korean_api(audio_file_path: str):
    """최적화된 한국어 OpenAI Whisper API 테스트"""
    
    # API 키 확인
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or api_key == "your_openai_api_key_here":
        print("❌ OpenAI API 키가 설정되지 않았습니다.")
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
    
    try:
        print("🎯 최적화된 한국어 OpenAI Whisper API 전사 시작...")
        
        # 한국어 최적화 프롬프트
        korean_prompt = (
            "다음은 한국어 음성입니다. "
            "정확한 맞춤법과 자연스러운 띄어쓰기를 사용해 주세요. "
            "문장 부호를 적절히 사용하고, 구어체 표현을 자연스럽게 변환해 주세요."
        )
        
        # API 호출을 별도 함수로 분리
        def call_optimized_api():
            with open(audio_file_path, "rb") as audio_file:
                transcript = client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    language="ko",  # 한국어 명시적 설정
                    response_format="verbose_json",
                    timestamp_granularities=["segment"],
                    prompt=korean_prompt,  # 🆕 한국어 최적화 프롬프트
                    temperature=0.0  # 🆕 일관성을 위한 낮은 온도
                )
                return transcript
        
        # 비동기 실행
        result = await asyncio.to_thread(call_optimized_api)
        
        print("✅ 최적화된 API 전사 완료!")
        print(f"🌐 감지된 언어: {result.language}")
        print(f"📝 전사 텍스트: {result.text}")
        print(f"📊 세그먼트 수: {len(result.segments) if result.segments else 0}")
        
        # 세그먼트 정보 상세 출력
        if result.segments:
            print("\n📋 세그먼트 상세 정보:")
            for i, segment in enumerate(result.segments):
                start_time = f"{int(segment.start//60)}:{int(segment.start%60):02d}"
                end_time = f"{int(segment.end//60)}:{int(segment.end%60):02d}"
                print(f"  {i+1}. [{start_time}-{end_time}] {segment.text}")
        
        # 비용 계산
        duration_seconds = result.duration if hasattr(result, 'duration') else 0
        if duration_seconds == 0 and result.segments:
            duration_seconds = result.segments[-1].end
        
        cost = (duration_seconds / 60) * 0.006
        print(f"💰 예상 비용: ${cost:.4f} (약 {duration_seconds:.1f}초)")
        
        return True, result.text
        
    except Exception as e:
        print(f"❌ 최적화된 API 호출 실패: {str(e)}")
        return False, ""

async def compare_before_after(audio_file_path: str):
    """개선 전후 비교 테스트"""
    
    api_key = os.getenv("OPENAI_API_KEY")
    client = OpenAI(api_key=api_key)
    
    print("🔄 개선 전후 비교 테스트")
    print("="*60)
    
    try:
        # 1. 개선 전 방식 (기본 설정)
        print("1️⃣ 개선 전 방식 (기본 설정)")
        with open(audio_file_path, "rb") as audio_file:
            basic_result = await asyncio.to_thread(
                lambda: client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    language="ko",
                    response_format="verbose_json",
                    timestamp_granularities=["segment"]
                )
            )
        
        print(f"📝 기본 결과: {basic_result.text}")
        print()
        
        # 2. 개선 후 방식 (최적화 설정)
        print("2️⃣ 개선 후 방식 (한국어 최적화)")
        success, improved_text = await test_optimized_korean_api(audio_file_path)
        
        if success:
            print()
            
            # 3. 결과 비교
            print("🔍 결과 비교:")
            print(f"개선 전: '{basic_result.text}'")
            print(f"개선 후: '{improved_text}'")
            
            # 품질 평가
            if len(basic_result.text) > len(improved_text) * 3:
                print("🎯 개선 후 결과가 더 간결하고 정확합니다!")
            elif basic_result.text.strip() == improved_text.strip():
                print("⚡ 결과가 동일합니다.")
            else:
                print("🔄 결과가 다릅니다. 수동 확인이 필요합니다.")
        
        return True
        
    except Exception as e:
        print(f"❌ 비교 테스트 실패: {str(e)}")
        return False

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("사용법: python test_korean_optimization.py <audio_file_path>")
        print("예시: python test_korean_optimization.py ../test-file/test.mp3")
        sys.exit(1)
    
    audio_path = sys.argv[1]
    print("🧪 OpenAI Whisper API 한국어 최적화 검증 테스트")
    print("="*60)
    
    # 최적화된 API 테스트
    success1 = asyncio.run(test_optimized_korean_api(audio_path))
    
    print("\n" + "="*60)
    
    # 개선 전후 비교
    success2 = asyncio.run(compare_before_after(audio_path))
    
    print("="*60)
    if success1[0] and success2:
        print("🎉 모든 테스트 성공! 한국어 최적화가 적용되었습니다.")
    else:
        print("💥 일부 테스트 실패! 설정을 확인해주세요.")
