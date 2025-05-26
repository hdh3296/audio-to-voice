#!/usr/bin/env python3
"""
독립적인 안정화 API 테스트 (pydub 의존성 없음)
"""
import os
import sys
import asyncio
import hashlib
from dotenv import load_dotenv
from openai import OpenAI

class DirectStableAPITest:
    """직접 안정화 API 테스트"""
    
    def __init__(self):
        load_dotenv()
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.client = None
        
        if self.api_key and self.api_key != "your_openai_api_key_here":
            self.client = OpenAI(api_key=self.api_key)
    
    def is_available(self):
        return self.client is not None
    
    def generate_file_seed(self, file_path: str) -> int:
        """파일 기반 일관된 시드 생성"""
        file_size = os.path.getsize(file_path)
        seed_string = f"{file_path}_{file_size}"
        seed_hash = hashlib.md5(seed_string.encode()).hexdigest()
        return int(seed_hash[:8], 16) % (2**31 - 1)
    
    async def transcribe_stable(self, audio_path: str, use_enhanced_prompt: bool = True):
        """안정화된 전사"""
        if not self.is_available():
            return {"success": False, "error": "API 키 없음"}
        
        # 향상된 프롬프트
        if use_enhanced_prompt:
            prompt = """다음은 한국어 음성입니다. 정확한 한국어 표준어로 전사해주세요. 
문장 부호는 자연스럽게 사용하고, 띄어쓰기는 한국어 맞춤법에 맞게 해주세요. 
브랜드명이나 고유명사는 정확하게 표기해주세요."""
        else:
            prompt = ""
        
        def _api_call():
            with open(audio_path, "rb") as audio_file:
                return self.client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    language="ko",
                    response_format="verbose_json",
                    prompt=prompt,
                    temperature=0.0  # 🔑 안정성을 위해 0
                )
        
        try:
            result = await asyncio.to_thread(_api_call)
            return {
                "success": True,
                "text": result.text.strip(),
                "temperature": 0.0,
                "prompt_used": bool(prompt)
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def transcribe_baseline(self, audio_path: str):
        """기존 방식 (비교용)"""
        if not self.is_available():
            return {"success": False, "error": "API 키 없음"}
        
        def _api_call():
            with open(audio_path, "rb") as audio_file:
                return self.client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    language="ko",
                    response_format="verbose_json"
                    # temperature와 prompt 없음 (기본값 사용)
                )
        
        try:
            result = await asyncio.to_thread(_api_call)
            return {
                "success": True,
                "text": result.text.strip(),
                "method": "baseline"
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

async def main():
    if len(sys.argv) != 2:
        print("사용법: python direct_stability_test.py <audio_file>")
        sys.exit(1)
    
    audio_path = sys.argv[1]
    
    if not os.path.exists(audio_path):
        print(f"❌ 파일이 존재하지 않습니다: {audio_path}")
        sys.exit(1)
    
    tester = DirectStableAPITest()
    
    if not tester.is_available():
        print("❌ OpenAI API 키가 설정되지 않음")
        sys.exit(1)
    
    print("🧪 OpenAI API 안정화 효과 테스트")
    print("=" * 60)
    print(f"📁 파일: {os.path.basename(audio_path)}")
    print()
    
    # 1. 기존 방식 테스트 (5회)
    print("📊 1단계: 기존 방식 (temperature 기본값, 프롬프트 없음)")
    print("-" * 50)
    
    baseline_results = []
    for i in range(5):
        print(f"📡 {i+1}번째 호출...")
        result = await tester.transcribe_baseline(audio_path)
        
        if result.get("success"):
            text = result["text"]
            baseline_results.append(text)
            print(f"   결과: {text}")
        else:
            print(f"   ❌ 실패: {result.get('error')}")
            baseline_results.append(f"ERROR: {result.get('error')}")
    
    # 기존 방식 분석
    baseline_unique = list(set([r for r in baseline_results if not r.startswith("ERROR")]))
    baseline_errors = len([r for r in baseline_results if r.startswith("ERROR")])
    
    print(f"\n📈 기존 방식 결과:")
    print(f"   성공: {len(baseline_results) - baseline_errors}/5회")
    print(f"   고유 결과: {len(baseline_unique)}개")
    for i, result in enumerate(baseline_unique):
        count = baseline_results.count(result)
        print(f"      {i+1}. \"{result}\" ({count}회)")
    
    # 2. 안정화 방식 테스트 (5회)
    print(f"\n🎯 2단계: 안정화 방식 (temperature=0, 상세 프롬프트)")
    print("-" * 50)
    
    stable_results = []
    for i in range(5):
        print(f"📡 {i+1}번째 호출...")
        result = await tester.transcribe_stable(audio_path, use_enhanced_prompt=True)
        
        if result.get("success"):
            text = result["text"]
            stable_results.append(text)
            print(f"   결과: {text}")
        else:
            print(f"   ❌ 실패: {result.get('error')}")
            stable_results.append(f"ERROR: {result.get('error')}")
    
    # 안정화 방식 분석
    stable_unique = list(set([r for r in stable_results if not r.startswith("ERROR")]))
    stable_errors = len([r for r in stable_results if r.startswith("ERROR")])
    
    print(f"\n📈 안정화 방식 결과:")
    print(f"   성공: {len(stable_results) - stable_errors}/5회")
    print(f"   고유 결과: {len(stable_unique)}개")
    for i, result in enumerate(stable_unique):
        count = stable_results.count(result)
        print(f"      {i+1}. \"{result}\" ({count}회)")
    
    # 3. 비교 및 결론
    print(f"\n🆚 비교 결과:")
    print("=" * 60)
    print(f"기존 방식:")
    print(f"   고유 결과 수: {len(baseline_unique)}개")
    print(f"   변동성: {'높음' if len(baseline_unique) > 3 else '보통' if len(baseline_unique) > 1 else '낮음'}")
    
    print(f"안정화 방식:")
    print(f"   고유 결과 수: {len(stable_unique)}개")
    print(f"   변동성: {'높음' if len(stable_unique) > 3 else '보통' if len(stable_unique) > 1 else '낮음'}")
    
    # 개선 효과 계산
    improvement = len(baseline_unique) - len(stable_unique)
    
    print(f"\n🏆 개선 효과:")
    if improvement > 0:
        print(f"   ✅ {improvement}개 결과 감소 - 안정성 향상!")
        if len(stable_unique) == 1:
            print("   🎉 완벽한 일관성 달성!")
        else:
            print("   📈 일관성 크게 개선됨")
    elif improvement == 0:
        print("   ⚖️ 유사한 수준의 일관성")
    else:
        print("   ⚠️ 안정화 효과 미미")
    
    print(f"\n💡 결론:")
    if len(stable_unique) <= 1:
        print("   → ✅ 안정화된 API 모드 사용 권장")
        print("   → 자막 작업에 적합한 일관성 확보")
    elif len(stable_unique) < len(baseline_unique):
        print("   → ⚡ 안정화 모드가 기본 모드보다 개선됨")
        print("   → 중요한 작업에 안정화 모드 권장")
    else:
        print("   → 🏠 중요한 자막 작업에는 로컬 모드 사용 권장")
        print("   → API는 속도가 우선인 경우에만 사용")

if __name__ == "__main__":
    asyncio.run(main())
