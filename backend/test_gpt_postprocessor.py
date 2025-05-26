"""
GPT 후처리 모듈 테스트
한국어 오타 교정 기능을 테스트합니다.
"""
import asyncio
import sys
import os

# 현재 디렉토리를 Python 경로에 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

async def test_gpt_postprocessor():
    try:
        print("🧪 GPT 후처리 모듈 테스트 시작")
        
        # GPT 후처리 모듈 임포트
        from auto_subtitle.gpt_postprocessor import gpt_postprocessor
        
        # 사용 가능 여부 확인
        print(f"📋 GPT 후처리 사용 가능: {gpt_postprocessor.is_available()}")
        
        if not gpt_postprocessor.is_available():
            print("❌ OpenAI API 키가 설정되지 않았습니다.")
            print("💡 .env 파일에 OPENAI_API_KEY를 설정해주세요.")
            return
        
        # 테스트용 한국어 텍스트 (일반적인 음성 인식 오타들)
        test_segments = [
            {
                "start": 0.0,
                "end": 3.0,
                "text": "안녕하세요 오늘은 계시가 좋은 날씨 입니다"
            },
            {
                "start": 3.0,
                "end": 6.0,
                "text": "이것은 되요 안되요 라는 말을 자주 쓰는데"
            },
            {
                "start": 6.0,
                "end": 9.0,
                "text": "띄어쓰기가 제대로안되어있거나 맞춤법이 틀릴수있어요"
            }
        ]
        
        print("📝 원본 텍스트:")
        for i, seg in enumerate(test_segments, 1):
            print(f"  {i}. {seg['text']}")
        
        print("\n🤖 GPT 후처리 중...")
        
        # GPT 후처리 실행
        result = await gpt_postprocessor.correct_segments(
            test_segments,
            context="한국어 음성 인식 결과의 오타 및 맞춤법 교정 테스트"
        )
        
        if result.get("success"):
            corrected_segments = result.get("corrected_segments", [])
            total_corrections = result.get("total_corrections", 0)
            
            print("✅ GPT 후처리 완료!")
            print(f"📊 총 {total_corrections}개 수정됨")
            print("\n📝 교정된 텍스트:")
            
            for i, seg in enumerate(corrected_segments, 1):
                original = test_segments[i-1]["text"] if i-1 < len(test_segments) else ""
                corrected = seg.get("text", "")
                
                print(f"  {i}. {corrected}")
                
                # 변경사항 표시
                if original != corrected:
                    print(f"     🔄 변경: '{original}' → '{corrected}'")
            
            print(f"\n🎯 교정 적용 여부: {result.get('correction_applied', False)}")
            
        else:
            print(f"❌ GPT 후처리 실패: {result.get('error', 'Unknown error')}")
            
    except Exception as e:
        print(f"❌ 테스트 중 오류 발생: {str(e)}")

if __name__ == "__main__":
    print("🧪 GPT 후처리 테스트 프로그램")
    print("=" * 50)
    
    # 비동기 실행
    asyncio.run(test_gpt_postprocessor())
    
    print("=" * 50)
    print("✅ 테스트 완료")
