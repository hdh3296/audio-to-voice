#!/usr/bin/env python3
"""
최종 교차 검증 테스트
OpenAI API와 로컬 Whisper의 다양한 설정으로 교차 검증
"""
import os
import asyncio
from dotenv import load_dotenv
from openai import OpenAI
import sys
from collections import Counter

# 환경변수 로드
load_dotenv()

async def cross_validation_test(audio_file_path: str):
    """OpenAI API와 로컬 Whisper 교차 검증"""
    
    print("🎯 교차 검증 테스트 시작")
    print("="*60)
    
    results = []
    
    # 1. OpenAI API 테스트 (여러 설정)
    print("🌐 OpenAI API 테스트")
    print("-" * 30)
    
    api_key = os.getenv("OPENAI_API_KEY")
    if api_key and api_key != "your_openai_api_key_here":
        client = OpenAI(api_key=api_key)
        
        api_configs = [
            {"name": "API-기본", "params": {"language": "ko", "temperature": 0.0}},
            {"name": "API-언어자동", "params": {"temperature": 0.0}},
            {"name": "API-온도높임", "params": {"language": "ko", "temperature": 0.3}},
        ]
        
        for config in api_configs:
            try:
                def call_api():
                    with open(audio_file_path, "rb") as audio_file:
                        return client.audio.transcriptions.create(
                            model="whisper-1",
                            file=audio_file,
                            response_format="verbose_json",
                            timestamp_granularities=["segment"],
                            **config["params"]
                        )
                
                result = await asyncio.to_thread(call_api)
                text = result.text.strip()
                results.append({"method": config["name"], "text": text, "source": "OpenAI"})
                print(f"✅ {config['name']}: '{text}'")
                
            except Exception as e:
                print(f"❌ {config['name']}: {str(e)}")
                results.append({"method": config["name"], "text": f"오류: {str(e)}", "source": "OpenAI"})
    
    # 2. 로컬 Whisper 테스트 (여러 모델)
    print(f"\n🏠 로컬 Whisper 테스트")
    print("-" * 30)
    
    try:
        from faster_whisper import WhisperModel
        
        local_configs = [
            {"name": "로컬-large-v3", "model": "large-v3"},
            {"name": "로컬-medium", "model": "medium"},
        ]
        
        for config in local_configs:
            try:
                print(f"📥 {config['model']} 모델 로드 중...")
                model = WhisperModel(config["model"], device="cpu", compute_type="int8")
                
                segments, info = model.transcribe(
                    audio_file_path, 
                    language="ko",
                    task="transcribe"
                )
                
                text_parts = []
                for segment in segments:
                    if segment.text.strip():
                        text_parts.append(segment.text.strip())
                
                full_text = " ".join(text_parts).strip()
                results.append({"method": config["name"], "text": full_text, "source": "Local"})
                print(f"✅ {config['name']}: '{full_text}'")
                
            except Exception as e:
                print(f"❌ {config['name']}: {str(e)}")
                results.append({"method": config["name"], "text": f"오류: {str(e)}", "source": "Local"})
                
    except ImportError:
        print("⚠️ faster-whisper가 설치되지 않았습니다.")
    
    # 3. 결과 분석
    print(f"\n{'='*60}")
    print("📊 교차 검증 결과 분석")
    print("="*60)
    
    successful_results = [r for r in results if not r["text"].startswith("오류:")]
    
    if successful_results:
        print("📝 모든 결과:")
        for result in successful_results:
            print(f"  {result['method']} ({result['source']}): '{result['text']}'")
        
        # 텍스트 빈도 분석
        texts = [r["text"] for r in successful_results]
        text_counter = Counter(texts)
        
        print(f"\n🎯 결과 빈도 분석:")
        for text, count in text_counter.most_common():
            percentage = (count / len(successful_results)) * 100
            methods = [r["method"] for r in successful_results if r["text"] == text]
            print(f"  '{text}': {count}회 ({percentage:.1f}%)")
            print(f"    └ 방법: {', '.join(methods)}")
        
        # 소스별 분석
        openai_results = [r for r in successful_results if r["source"] == "OpenAI"]
        local_results = [r for r in successful_results if r["source"] == "Local"]
        
        print(f"\n🔍 소스별 일관성:")
        if openai_results:
            openai_texts = [r["text"] for r in openai_results]
            openai_counter = Counter(openai_texts)
            if len(openai_counter) == 1:
                print(f"  🌐 OpenAI API: 완전 일관됨 - '{list(openai_counter.keys())[0]}'")
            else:
                print(f"  🌐 OpenAI API: {len(openai_counter)}가지 결과")
                for text, count in openai_counter.items():
                    print(f"    - '{text}': {count}회")
        
        if local_results:
            local_texts = [r["text"] for r in local_results]
            local_counter = Counter(local_texts)
            if len(local_counter) == 1:
                print(f"  🏠 로컬 Whisper: 완전 일관됨 - '{list(local_counter.keys())[0]}'")
            else:
                print(f"  🏠 로컬 Whisper: {len(local_counter)}가지 결과")
                for text, count in local_counter.items():
                    print(f"    - '{text}': {count}회")
        
        # 최종 권장사항
        print(f"\n💡 최종 권장사항:")
        if len(text_counter) == 1:
            print("  ✅ 모든 방법이 동일한 결과를 제공합니다.")
            print(f"  🎯 신뢰할 수 있는 결과: '{list(text_counter.keys())[0]}'")
        else:
            most_common_text, most_common_count = text_counter.most_common(1)[0]
            print(f"  🎯 가장 빈번한 결과: '{most_common_text}' ({most_common_count}회)")
            
            if most_common_count >= len(successful_results) * 0.5:
                print("  ✅ 과반수 이상의 방법이 동일한 결과를 제공합니다.")
                print("  📋 권장: 이 결과를 사용하세요.")
            else:
                print("  ⚠️ 결과가 분산되어 있습니다.")
                print("  📋 권장: 오디오 품질을 확인하거나 수동 검토가 필요합니다.")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("사용법: python cross_validation_test.py <audio_file_path>")
        sys.exit(1)
    
    audio_path = sys.argv[1]
    
    # 파일 존재 확인
    if not os.path.exists(audio_path):
        print(f"❌ 오디오 파일을 찾을 수 없습니다: {audio_path}")
        sys.exit(1)
    
    file_size = os.path.getsize(audio_path)
    print(f"📁 파일 정보: {os.path.basename(audio_path)} ({file_size/1024:.1f}KB)")
    
    # 비동기 실행
    asyncio.run(cross_validation_test(audio_path))
    
    print("\n" + "="*60)
    print("🎉 교차 검증 완료!")
