"""
GPT 후처리 단독 테스트 (의존성 최소화)
"""
import asyncio
import os
from typing import Dict
from openai import AsyncOpenAI
from dotenv import load_dotenv

async def test_gpt_correction_simple():
    """간단한 GPT 후처리 테스트"""
    
    load_dotenv()
    api_key = os.getenv('OPENAI_API_KEY')
    
    if not api_key:
        print("❌ OPENAI_API_KEY가 설정되지 않았습니다.")
        return
    
    client = AsyncOpenAI(api_key=api_key)
    
    # 테스트 텍스트
    test_text = "안녕하세요 저는 AI 개발자 입니다. 이거 정말되나요? 웬지 이상한 느낌이 들어요."
    
    system_prompt = """당신은 한국어 전문 교정자입니다. 음성 인식 결과의 오타와 맞춤법을 교정해주세요.

**교정 원칙:**
1. 음성학적 오료 수정: "되요" → "돼요", "웬지" → "왠지"
2. 띄어쓰기 정규화: 자연스러운 한국어 띄어쓰기
3. 맞춤법 준수: 표준 한국어 맞춤법
4. 원본 의미 보존: 절대 의미 변경 금지

교정된 텍스트만 출력하세요."""
    
    print("🤖 GPT 후처리 단독 테스트")
    print(f"원본: {test_text}")
    print("\n처리 중...")
    
    try:
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"다음 텍스트를 교정해주세요:\n\n{test_text}"}
            ],
            temperature=0.1,
            max_tokens=500
        )
        
        corrected_text = response.choices[0].message.content.strip()
        
        print(f"교정: {corrected_text}")
        print(f"변경: {'✅ 교정됨' if corrected_text != test_text else '❌ 변경 없음'}")
        print("✅ 테스트 성공!")
        
    except Exception as e:
        print(f"❌ 테스트 실패: {e}")

if __name__ == "__main__":
    asyncio.run(test_gpt_correction_simple())
