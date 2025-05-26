"""
GPT 후처리 기능 테스트 스크립트
"""
import asyncio
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from auto_subtitle.gpt_postprocessor import gpt_postprocessor

async def test_gpt_correction():
    """GPT 후처리 기능 테스트"""
    
    # 테스트 텍스트 (일반적인 한국어 음성 인식 오타들)
    test_texts = [
        "안녕하세요 저는 AI 개발자 입니다. 오늘은 웹개발에 대해서 이야기해보겠습니다.",
        "이거 정말되나요? 안되는것같은데 뭔가이상해요.",
        "계시는분들은 다들 잘들리시나요? 소리가잘안나와서 걱정이되네요.",
        "그런데 이런문제는 어떻게 해결하면되요? 방법을알려주세요.",
        "웬지 이상한 느낌이 들어서 한번더 확인해보려고 해요."
    ]
    
    print("🤖 GPT 후처리 테스트 시작...\n")
    
    if not gpt_postprocessor.is_available():
        print("❌ GPT 후처리를 사용할 수 없습니다. OpenAI API 키를 확인해주세요.")
        return
    
    for i, text in enumerate(test_texts, 1):
        print(f"📝 테스트 {i}/5")
        print(f"원본: {text}")
        
        result = await gpt_postprocessor.correct_text(text)
        
        if result["success"]:
            print(f"교정: {result['corrected_text']}")
            print(f"변경: {'✅ 교정됨' if result['correction_applied'] else '❌ 변경 없음'}")
        else:
            print(f"오류: {result['error']}")
        
        print("-" * 50)
    
    print("✅ 테스트 완료!")

if __name__ == "__main__":
    asyncio.run(test_gpt_correction())
