#!/usr/bin/env python3
"""
안정화된 OpenAI API 테스트 스크립트
일관성 개선 방법들 검증
"""
import os
import sys
import asyncio
from dotenv import load_dotenv

# 현재 디렉토리를 Python 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from auto_subtitle.openai_stable_client import stable_openai_whisper_client

async def test_api_stability(audio_path: str, test_count: int = 5):
    """안정화된 API 일관성 테스트"""
    
    print("🧪 OpenAI API 안정화 테스트 시작")
    print("=" * 60)
    print(f"📁 파일: {os.path.basename(audio_path)}")
    print(f"🔄 테스트 횟수: {test_count}회")
    print()
    
    if not stable_openai_whisper_client.is_available():
        print("❌ OpenAI API 키가 설정되지 않음")
        return False
    
    results = []
    
    # 1. 기본 안정화 모드 테스트
    print("🎯 1단계: 안정화 모드 테스트 (temperature=0, 상세 프롬프트)")
    print("-" * 50)
    
    for i in range(test_count):
        print(f"📡 {i+1}번째 호출...")
        
        result = await stable_openai_whisper_client.transcribe_audio_stable(
            audio_path, 
            language="ko",
            use_deterministic=True
        )
        
        if result.get("success"):
            text = result["text"]
            results.append(text)
            print(f"   결과: {text}")
            print(f"   시드: {result.get('used_seed', 'N/A')}")
        else:
            print(f"   ❌ 실패: {result.get('error')}")
            results.append(f"ERROR: {result.get('error')}")
    
    print("\n📊 안정화 결과 분석:")
    print("-" * 30)
    
    # 고유 결과 수 계산
    unique_results = list(set([r for r in results if not r.startswith("ERROR")]))
    error_count = len([r for r in results if r.startswith("ERROR")])
    
    print(f"✅ 성공: {len(results) - error_count}/{len(results)}회")
    print(f"❌ 실패: {error_count}/{len(results)}회")
    print(f"🔀 고유 결과 수: {len(unique_results)}")
    
    for i, result in enumerate(unique_results):
        count = results.count(result)
        percentage = (count / len(results)) * 100
        print(f"   {i+1}. \"{result}\" ({count}회, {percentage:.1f}%)")
    
    # 일관성 평가
    if len(unique_results) == 1:
        print("→ 🎉 완벽한 일관성! (100% 동일한 결과)")
        consistency_score = 100
    elif len(unique_results) <= 2:
        print("→ ✅ 높은 일관성 (매우 유사한 결과)")
        consistency_score = 80
    elif len(unique_results) <= 3:
        print("→ ⚠️ 보통 일관성 (약간의 변동)")
        consistency_score = 60
    else:
        print("→ ❌ 낮은 일관성 (높은 변동성)")
        consistency_score = 40
    
    print(f"\n🏆 일관성 점수: {consistency_score}/100")
    
    # 2. 재시도 기반 안정화 테스트
    print(f"\n🔄 2단계: 재시도 기반 안정화 테스트")
    print("-" * 50)
    
    retry_result = await stable_openai_whisper_client.transcribe_with_retry(
        audio_path,
        language="ko",
        max_retries=3
    )
    
    if retry_result.get("success"):
        print(f"✅ 재시도 결과: {retry_result['text']}")
    else:
        print(f"❌ 재시도 실패: {retry_result.get('error')}")
    
    return consistency_score >= 80

async def test_comparison_with_baseline(audio_path: str):
    """기존 API vs 안정화 API 비교"""
    print("\n🆚 3단계: 기존 API vs 안정화 API 비교")
    print("-" * 50)
    
    # 기존 simple API 테스트 (비교용)
    from auto_subtitle.openai_client_simple import openai_whisper_client
    
    print("📊 기존 API (3회 테스트):")
    baseline_results = []
    for i in range(3):
        result = await openai_whisper_client.transcribe_audio_api(audio_path, "ko")
        if result.get("success"):
            baseline_results.append(result["text"])
            print(f"   {i+1}. {result['text']}")
    
    baseline_unique = len(set(baseline_results))
    
    print(f"\n📊 안정화 API (3회 테스트):")
    stable_results = []
    for i in range(3):
        result = await stable_openai_whisper_client.transcribe_audio_stable(audio_path, "ko")
        if result.get("success"):
            stable_results.append(result["text"])
            print(f"   {i+1}. {result['text']}")
    
    stable_unique = len(set(stable_results))
    
    print(f"\n📈 비교 결과:")
    print(f"   기존 API 고유 결과: {baseline_unique}개")
    print(f"   안정화 API 고유 결과: {stable_unique}개")
    
    if stable_unique < baseline_unique:
        print("   → ✅ 안정화 API가 더 일관된 결과 제공!")
    elif stable_unique == baseline_unique:
        print("   → ⚖️ 두 API 모두 유사한 일관성")
    else:
        print("   → ⚠️ 안정화 효과 미미")

async def main():
    if len(sys.argv) != 2:
        print("사용법: python test_api_stability.py <audio_file>")
        sys.exit(1)
    
    audio_path = sys.argv[1]
    
    if not os.path.exists(audio_path):
        print(f"❌ 파일이 존재하지 않습니다: {audio_path}")
        sys.exit(1)
    
    # 안정성 테스트
    is_stable = await test_api_stability(audio_path, 5)
    
    # 비교 테스트
    await test_comparison_with_baseline(audio_path)
    
    print("\n" + "=" * 60)
    if is_stable:
        print("🎉 API 안정화 성공! 일관된 결과 확보")
    else:
        print("⚠️ 완전한 안정화는 달성하지 못했지만 개선됨")
    
    print("\n💡 권장사항:")
    if is_stable:
        print("   → 안정화된 API 모드 사용 권장")
    else:
        print("   → 중요한 작업에는 로컬 모드 사용 권장")
        print("   → API 모드는 속도가 필요한 경우에만 사용")

if __name__ == "__main__":
    asyncio.run(main())
