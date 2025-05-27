#!/usr/bin/env python3
"""
GPT 스마트 줄바꿈 기능 테스트 스크립트
"""

import asyncio
import os

async def gpt_smart_line_breaks(text: str, max_line_length: int, max_lines: int = 2) -> str:
    """
    🤖 GPT 기반 의미 단위 스마트 분할
    """
    try:
        from openai import AsyncOpenAI
        
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            print("❌ OpenAI API 키가 없습니다")
            return text
            
        client = AsyncOpenAI(api_key=api_key)
        
        prompt = f"""다음 한국어 텍스트를 자연스럽고 의미있는 단위로 {max_lines}줄로 나누어 주세요.

🎯 분할 조건:
- 각 줄은 최대 {max_line_length}자 이하
- 의미가 완결되는 지점에서 분할
- 너무 짧은 줄(3글자 이하) 방지
- 조사나 어미가 혼자 남지 않도록 주의
- "~을", "~를", "~에 대한", "~을 위하여" 등은 분할하지 말 것
- 균형잡힌 줄 길이로 조정

📝 텍스트: "{text}"

✅ 결과: 줄바꿈으로 구분된 텍스트만 반환 (설명 없이)"""

        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=1000
        )
        
        result = response.choices[0].message.content.strip()
        
        # 결과 검증
        lines = result.split('\n')
        if len(lines) <= max_lines and all(len(line) <= max_line_length + 5 for line in lines):
            print(f"🤖 GPT 스마트 분할 성공: {len(lines)}줄")
            for i, line in enumerate(lines, 1):
                print(f"   {i}줄: '{line}' (길이: {len(line)}자)")
            return result
        else:
            print(f"⚠️ GPT 결과 검증 실패 - 원본 사용")
            return text
            
    except Exception as e:
        print(f"❌ GPT 스마트 분할 오류: {str(e)}")
        return text


def apply_word_based_line_breaks(text: str, max_line_length: int) -> str:
    """A방식: 단어 단위 줄바꿈 (기존)"""
    if not text or len(text) <= max_line_length:
        return text
    
    words = text.split()
    if not words:
        return text
    
    if len(words) == 1:
        return words[0]
    
    total_length = len(text)
    target_line_length = min(max_line_length, total_length // 2 + 5)
    
    lines = []
    current_line = ""
    
    for i, word in enumerate(words):
        test_line = current_line + (" " if current_line else "") + word
        
        if len(lines) == 0:
            if len(test_line) <= target_line_length or len(test_line) <= max_line_length:
                current_line = test_line
            else:
                if current_line:
                    lines.append(current_line)
                    current_line = word
                else:
                    current_line = word
        elif len(lines) == 1:
            current_line = test_line
        else:
            break
    
    if current_line:
        lines.append(current_line)
    
    result = "\n".join(lines)
    print(f"✅ A방식 결과: {len(lines)}줄")
    for i, line in enumerate(lines, 1):
        print(f"   {i}줄: '{line}' (길이: {len(line)}자)")
    
    return result


def needs_smart_improvement(text: str, formatted_result: str, max_line_length: int) -> bool:
    """개선 필요성 판단"""
    lines = formatted_result.split('\n')
    
    # 너무 짧은 줄 검사
    for line in lines:
        if len(line.strip()) <= 3 and len(line.strip()) > 0:
            print(f"🔍 개선 필요: 너무 짧은 줄 감지 - '{line.strip()}'")
            return True
    
    # 불균형 검사
    if len(lines) == 2:
        line1_len = len(lines[0])
        line2_len = len(lines[1])
        if line1_len > 0 and line2_len > 0:
            length_ratio = abs(line1_len - line2_len) / max(line1_len, line2_len)
            if length_ratio > 0.7:
                print(f"🔍 개선 필요: 불균형한 줄 길이 - {line1_len}자 vs {line2_len}자")
                return True
    
    # 부자연스러운 분할점 검사
    problem_patterns = ["내용을\n", "것을\n", "을\n", "를\n", "에\n"]
    for pattern in problem_patterns:
        if pattern in formatted_result:
            print(f"🔍 개선 필요: 부자연스러운 분할점 감지 - '{pattern.strip()}'")
            return True
    
    return False


async def test_smart_line_breaks():
    """테스트 실행"""
    
    test_cases = [
        {
            "name": "🎯 핵심 문제: 내용을이 혼자 남는 경우 (강제)",
            "text": "성경을 잘 알지 못하는 분들이나 예수 그리스도에 대한 믿음의 주요 내용을 더 잘 알고 싶은 분들을 위하여 성경의 줄거리와 내용을 읽기 쉽게 정리하였습니다",
            "max_length": 25  # 더 작게 해서 문제 강제 발생
        },
        {
            "name": "조사 분리 강제 유발",  
            "text": "컨사이스 바이블은 성경 공부에 관심이 있는 분들을 위해 준비된 것을 알려드립니다",
            "max_length": 20  # 매우 작게 해서 조사 분리 유발
        },
        {
            "name": "극단적 불균형 케이스",
            "text": "아주 긴 첫 번째 문장으로 시작해서 둘째 줄은 을",
            "max_length": 25
        }
    ]
    
    print("🧪 GPT 스마트 줄바꿈 테스트 시작\n")
    print("="*80)
    
    for i, case in enumerate(test_cases, 1):
        print(f"\n{i}. {case['name']}")
        print(f"📝 원본: {case['text']}")
        print(f"📏 최대 길이: {case['max_length']}자 (원본 길이: {len(case['text'])}자)")
        
        # A방식 적용
        print(f"\n🔤 A방식 (기존) 결과:")
        basic_result = apply_word_based_line_breaks(case['text'], case['max_length'])
        
        # 개선 필요성 판단
        needs_improvement = needs_smart_improvement(case['text'], basic_result, case['max_length'])
        
        if needs_improvement:
            print(f"\n🤖 GPT 스마트 분할 적용:")
            smart_result = await gpt_smart_line_breaks(case['text'], case['max_length'])
            
            if smart_result != basic_result:
                print(f"✅ GPT 개선 성공!")
                print(f"📝 개선된 결과:")
                for j, line in enumerate(smart_result.split('\n'), 1):
                    print(f"   {j}줄: '{line}' (길이: {len(line)}자)")
            else:
                print(f"ℹ️ GPT 결과가 기존과 동일")
        else:
            print(f"ℹ️ 개선 불필요 - A방식 결과 사용")
        
        print("-" * 80)

if __name__ == "__main__":
    asyncio.run(test_smart_line_breaks())
