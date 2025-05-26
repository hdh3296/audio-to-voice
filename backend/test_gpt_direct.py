#!/usr/bin/env python3
"""
GPT 후처리 직접 테스트 스크립트
"""
import sys
import os
import asyncio
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv()

# backend 디렉토리를 Python 경로에 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from phase2_postprocessing import Phase2PostProcessor

async def test_gpt_correction():
    """직접 GPT 교정 테스트"""
    
    # API 키 확인
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key or api_key == 'your_openai_api_key_here':
        print("❌ OpenAI API 키가 설정되지 않았습니다.")
        return
    
    print(f"✅ API 키 설정됨: {api_key[:20]}...")
    
    # GPT 후처리기 초기화
    processor = Phase2PostProcessor(api_key)
    print(f"✅ GPT 후처리기 초기화 완료")
    print(f"✅ 사용 가능 여부: {processor.is_available()}")
    
    # 테스트할 세그먼트들
    test_segments = [
        {
            'start': 0, 
            'end': 5, 
            'text': '분들을 위하여 성경의 줄거래와 내용을 읽기 쉽게 정리하였습니다.'
        },
        {
            'start': 5, 
            'end': 10, 
            'text': '이것은 테스트 문장입니다.'
        }
    ]
    
    print(f"\\n🧪 테스트 세그먼트 ({len(test_segments)}개):")
    for i, seg in enumerate(test_segments, 1):
        print(f"  {i}: {seg['text']}")
    
    print(f"\\n🚀 GPT 후처리 실행 중...")
    
    try:
        # GPT 후처리 실행
        result = await processor.process_with_progress(test_segments)
        
        print(f"\\n📊 처리 결과:")
        print(f"  성공 여부: {result['success']}")
        
        if result['success']:
            print(f"  총 교정 수: {result['total_corrections']}")
            print(f"  처리 시간: {result.get('processing_time', 0):.2f}초")
            print(f"  교정 전략: {result.get('correction_strategy', 'N/A')}")
            
            print(f"\\n📝 교정 전후 비교:")
            for i, (original, corrected) in enumerate(zip(test_segments, result['corrected_segments'])):
                print(f"\\n  세그먼트 {i+1}:")
                print(f"    원본: {original['text']}")
                print(f"    교정: {corrected['text']}")
                
                # 변경 사항 체크
                if original['text'] != corrected['text']:
                    print(f"    변경: ✅ 예")
                    # 특정 단어 교정 확인
                    if '줄거래' in original['text'] and '줄거리' in corrected['text']:
                        print(f"    🎯 '줄거래' → '줄거리' 교정됨!")
                    if '읽기쉽게' in original['text'] and '읽기 쉽게' in corrected['text']:
                        print(f"    🎯 띄어쓰기 교정됨!")
                else:
                    print(f"    변경: ❌ 아니오")
        else:
            print(f"  오류: {result.get('error', 'Unknown error')}")
            
    except Exception as e:
        print(f"❌ 테스트 실패: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("🧪 GPT 후처리 직접 테스트 시작")
    print("=" * 50)
    
    asyncio.run(test_gpt_correction())
    
    print("\\n" + "=" * 50)
    print("🏁 테스트 완료")
