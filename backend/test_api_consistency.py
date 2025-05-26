#!/usr/bin/env python3
"""
OpenAI Whisper API 안정성 테스트
동일한 파일을 여러 번 호출하여 일관성 확인
"""
import os
import asyncio
from dotenv import load_dotenv
from openai import OpenAI
import sys
from collections import Counter

# 환경변수 로드
load_dotenv()

async def test_api_consistency(audio_file_path: str, num_tests: int = 5):
    """동일한 파일을 여러 번 API 호출하여 일관성 테스트"""
    
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
    print(f"🔄 {num_tests}회 반복 테스트 시작")
    
    results = []
    
    try:
        for i in range(num_tests):
            print(f"\n{'='*30}")
            print(f"테스트 {i+1}/{num_tests}")
            print(f"{'='*30}")
            
            try:
                # API 호출 함수 (프롬프트 없이 순수 인식)
                def call_api():
                    with open(audio_file_path, "rb") as audio_file:
                        return client.audio.transcriptions.create(
                            model="whisper-1",
                            file=audio_file,
                            language="ko",  # 한국어 고정
                            response_format="verbose_json",
                            timestamp_granularities=["segment"],
                            temperature=0.0  # 일관성을 위해 0으로 고정
                            # prompt 사용하지 않음 - 실제 오디오만 인식
                        )
                
                # 비동기 실행
                result = await asyncio.to_thread(call_api)
                
                transcript_text = result.text.strip()
                print(f"✅ 결과: '{transcript_text}'")
                print(f"🌐 언어: {result.language}")
                print(f"📊 세그먼트: {len(result.segments) if result.segments else 0}개")
                
                # 세그먼트 상세 정보
                if result.segments:
                    for j, segment in enumerate(result.segments):
                        print(f"  └ 세그먼트 {j+1}: [{segment.start:.1f}s-{segment.end:.1f}s] '{segment.text.strip()}'")
                
                results.append({
                    'test_num': i+1,
                    'text': transcript_text,
                    'language': result.language,
                    'segments': len(result.segments) if result.segments else 0,
                    'success': True
                })
                
                # API 호출 간격 (속도 제한 방지)
                if i < num_tests - 1:
                    print("⏳ 1초 대기...")
                    await asyncio.sleep(1)
                
            except Exception as e:
                print(f"❌ 테스트 {i+1} 실패: {str(e)}")
                results.append({
                    'test_num': i+1,
                    'text': f"오류: {str(e)}",
                    'success': False
                })
        
        # 결과 분석
        print(f"\n{'='*50}")
        print("📊 일관성 분석 결과")
        print(f"{'='*50}")
        
        successful_results = [r for r in results if r['success']]
        
        if successful_results:
            # 모든 결과 표시
            print("📝 모든 전사 결과:")
            for result in successful_results:
                print(f"  {result['test_num']}. '{result['text']}'")
            
            # 결과 빈도 분석
            texts = [r['text'] for r in successful_results]
            text_counter = Counter(texts)
            
            print(f"\n🎯 결과 빈도 분석:")
            for text, count in text_counter.most_common():
                percentage = (count / len(successful_results)) * 100
                print(f"  '{text}': {count}회 ({percentage:.1f}%)")
            
            # 일관성 평가
            if len(text_counter) == 1:
                print(f"\n🏆 완벽한 일관성! 모든 결과가 동일합니다.")
                most_common_text = list(text_counter.keys())[0]
            else:
                most_common_text, most_common_count = text_counter.most_common(1)[0]
                consistency_rate = (most_common_count / len(successful_results)) * 100
                
                if consistency_rate >= 80:
                    print(f"\n✅ 높은 일관성: {consistency_rate:.1f}%")
                elif consistency_rate >= 60:
                    print(f"\n⚠️ 보통 일관성: {consistency_rate:.1f}%")
                else:
                    print(f"\n❌ 낮은 일관성: {consistency_rate:.1f}%")
                
                print(f"🎯 가장 신뢰할 만한 결과: '{most_common_text}' ({most_common_count}회)")
            
            print(f"\n💡 권장사항:")
            if len(text_counter) == 1:
                print("  - OpenAI API가 이 파일에 대해 일관된 결과를 제공합니다.")
                print("  - 프로덕션에서 안전하게 사용할 수 있습니다.")
            elif len(text_counter) <= 2:
                print("  - 대부분 일관되지만 가끔 다른 결과가 나올 수 있습니다.")
                print("  - 중요한 경우 여러 번 호출 후 가장 빈번한 결과를 사용하세요.")
            else:
                print("  - 결과가 불안정합니다. 오디오 품질이나 설정을 점검해보세요.")
                print("  - 로컬 Whisper 사용을 고려해보세요.")
        
        return True
        
    except Exception as e:
        print(f"❌ 전체 테스트 실패: {str(e)}")
        return False

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("사용법: python test_api_consistency.py <audio_file_path> [횟수]")
        sys.exit(1)
    
    audio_path = sys.argv[1]
    num_tests = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    
    print("🧪 OpenAI Whisper API 일관성 테스트")
    print("="*50)
    
    # 비동기 실행
    success = asyncio.run(test_api_consistency(audio_path, num_tests))
    
    print("="*50)
    if success:
        print("🎉 테스트 완료!")
    else:
        print("💥 테스트 실패!")
