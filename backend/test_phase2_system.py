"""
🧪 Phase 2 테스트 스크립트
- 구현된 모든 기능 테스트
- 오류 검증 및 디버깅
"""

import asyncio
import os
import sys
import tempfile
from pathlib import Path

# 프로젝트 루트로 경로 추가
sys.path.append(str(Path(__file__).parent))

try:
    from phase2_models import Phase2ModelManager
    from phase2_quality import QualityAnalyzer
    from phase2_streaming import StreamingTranscriber
except ImportError as e:
    print(f"❌ 모듈 임포트 실패: {e}")
    print("가상환경이 활성화되었는지 확인해주세요.")
    sys.exit(1)

from dotenv import load_dotenv


def create_test_audio():
    """테스트용 오디오 파일 생성 (TTS 시뮬레이션을 위한 더미 파일)"""
    
    test_dir = Path(__file__).parent.parent.parent / "test-file"
    test_dir.mkdir(exist_ok=True)
    
    # 실제 프로젝트에서 사용할 수 있는 기존 테스트 파일 찾기
    test_audio_path = test_dir / "test.mp3"
    
    if test_audio_path.exists():
        print(f"✅ 기존 테스트 파일 사용: {test_audio_path}")
        return str(test_audio_path)
    
    # 더미 오디오 파일 생성 (실제 테스트를 위해서는 실제 오디오 파일 필요)
    print("⚠️ 실제 테스트를 위해서는 test-file/test.mp3 파일이 필요합니다.")
    print("   간단한 한국어 음성 파일을 업로드해주세요.")
    
    return None


async def test_phase2_models():
    """Phase 2 모델 시스템 테스트"""
    print("🔬 Phase 2 모델 시스템 테스트 시작")
    
    # API 키 확인
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")
    
    if not api_key or api_key == "your_openai_api_key_here":
        print("❌ OpenAI API 키가 설정되지 않았습니다.")
        print("   .env 파일에 실제 API 키를 설정해주세요.")
        return False
    
    # 테스트 오디오 파일 확인
    test_audio = create_test_audio()
    if not test_audio:
        print("❌ 테스트 오디오 파일이 없습니다.")
        return False
    
    try:
        # 모델 매니저 테스트
        print("\n📊 모델 매니저 초기화...")
        manager = Phase2ModelManager(api_key)
        
        # 사용 가능한 모델 확인
        print("🤖 사용 가능한 모델들:")
        for model_name, info in manager.AVAILABLE_MODELS.items():
            print(f"  - {model_name}: {info['name']}")
        
        # 단일 모델 테스트
        print(f"\n🎯 단일 모델 테스트 (whisper-1-optimized)...")
        result = await manager.transcribe_with_model(
            test_audio, "whisper-1-optimized", "ko", True
        )
        
        if result.success:
            print(f"✅ 성공!")
            print(f"  📝 텍스트: {result.text[:50]}...")
            print(f"  ⏱️  처리 시간: {result.processing_time:.2f}초")
            print(f"  🎯 신뢰도: {result.confidence_score:.3f}")
            print(f"  📊 세그먼트: {len(result.segments)}개")
        else:
            print(f"❌ 실패: {result.error}")
            return False
        
        print("\n🏆 모델 시스템 테스트 완료!")
        return True
        
    except Exception as e:
        print(f"❌ 모델 테스트 중 오류: {str(e)}")
        return False


async def test_quality_analyzer():
    """품질 분석 시스템 테스트"""
    print("\n🔍 품질 분석 시스템 테스트 시작")
    
    try:
        analyzer = QualityAnalyzer()
        
        # 테스트 데이터
        test_cases = [
            {
                "name": "한국어 고품질",
                "text": "안녕하세요. 이것은 한국어 음성 인식 테스트입니다. 품질이 매우 좋습니다.",
                "segments": [
                    {"start": 0.0, "end": 2.0, "text": "안녕하세요.", "confidence": 0.95},
                    {"start": 2.0, "end": 5.0, "text": "이것은 한국어 음성 인식 테스트입니다.", "confidence": 0.89},
                    {"start": 5.0, "end": 7.0, "text": "품질이 매우 좋습니다.", "confidence": 0.92}
                ]
            },
            {
                "name": "영어 저품질",
                "text": "hello world this is english test",
                "segments": [
                    {"start": 0.0, "end": 3.0, "text": "hello world this is english test", "confidence": 0.45}
                ]
            }
        ]
        
        for test_case in test_cases:
            print(f"\n🧪 테스트: {test_case['name']}")
            print(f"📝 텍스트: {test_case['text']}")
            
            quality = await analyzer.analyze_transcription_quality(
                test_case["text"],
                test_case["segments"],
                processing_time=2.5,
                model_used="test_model"
            )
            
            print(f"📊 품질 분석 결과:")
            print(f"  🎯 전체 점수: {quality.overall_score:.3f}")
            print(f"  🤖 신뢰도: {quality.confidence_score:.3f}")
            print(f"  🇰🇷 한국어 품질: {quality.korean_quality_score:.3f}")
            print(f"  📝 문법 점수: {quality.grammar_score:.3f}")
            print(f"  🔄 재처리 필요: {'예' if quality.needs_reprocessing else '아니오'}")
            
            if quality.improvement_suggestions:
                print(f"  💡 개선 제안:")
                for suggestion in quality.improvement_suggestions[:2]:  # 최대 2개만 표시
                    print(f"    - {suggestion}")
        
        print("\n🏆 품질 분석 시스템 테스트 완료!")
        return True
        
    except Exception as e:
        print(f"❌ 품질 분석 테스트 중 오류: {str(e)}")
        return False


async def test_api_server():
    """API 서버 접속 테스트"""
    print("\n🌐 API 서버 접속 테스트 시작")
    
    try:
        import httpx
        
        # API 서버 상태 확인
        async with httpx.AsyncClient() as client:
            # 기본 엔드포인트 테스트
            response = await client.get("http://localhost:8002/")
            if response.status_code == 200:
                print("✅ 메인 엔드포인트 접속 성공")
            else:
                print(f"❌ 메인 엔드포인트 접속 실패: {response.status_code}")
                return False
            
            # API 상태 확인
            response = await client.get("http://localhost:8002/api-status")
            if response.status_code == 200:
                data = response.json()
                print("✅ API 상태 확인 성공")
                print(f"  Phase 2 사용 가능: {data.get('phase2_available', False)}")
            else:
                print(f"❌ API 상태 확인 실패: {response.status_code}")
                return False
            
            # 모델 정보 확인
            response = await client.get("http://localhost:8002/models")
            if response.status_code == 200:
                data = response.json()
                print("✅ 모델 정보 확인 성공")
                print(f"  사용 가능한 모델: {data.get('total_count', 0)}개")
            else:
                print(f"❌ 모델 정보 확인 실패: {response.status_code}")
        
        print("\n🏆 API 서버 테스트 완료!")
        return True
        
    except Exception as e:
        print(f"❌ API 서버 테스트 중 오류: {str(e)}")
        print("  서버가 실행 중인지 확인해주세요: python main_phase2.py")
        return False


async def run_all_tests():
    """모든 테스트 실행"""
    print("🚀 Phase 2 통합 테스트 시작")
    print("=" * 50)
    
    results = []
    
    # 1. 모델 시스템 테스트
    results.append(await test_phase2_models())
    
    # 2. 품질 분석 시스템 테스트 
    results.append(await test_quality_analyzer())
    
    # 3. API 서버 테스트 (별도 실행 필요)
    print("\n⚠️ API 서버 테스트는 서버가 실행 중일 때만 가능합니다.")
    print("  다른 터미널에서 다음 명령어를 실행해주세요:")
    print("  cd backend && source venv_phase2/bin/activate && python main_phase2.py")
    
    # 결과 요약
    print("\n📊 테스트 결과 요약")
    print("=" * 50)
    
    test_names = ["모델 시스템", "품질 분석"]
    for i, (name, result) in enumerate(zip(test_names, results)):
        status = "✅ 성공" if result else "❌ 실패"
        print(f"{i+1}. {name}: {status}")
    
    success_rate = sum(results) / len(results) * 100
    print(f"\n🎯 전체 성공률: {success_rate:.1f}%")
    
    if all(results):
        print("🎉 모든 테스트 통과! Phase 2 시스템이 정상 작동합니다.")
    else:
        print("⚠️ 일부 테스트 실패. 위의 오류 메시지를 확인해주세요.")


if __name__ == "__main__":
    print("🧪 Phase 2 시스템 테스트 도구")
    print("시작하기 전에 다음을 확인해주세요:")
    print("1. .env 파일에 OpenAI API 키가 설정되어 있는지")
    print("2. test-file/test.mp3 파일이 존재하는지") 
    print("3. 가상환경이 활성화되어 있는지")
    print("")
    
    try:
        asyncio.run(run_all_tests())
    except KeyboardInterrupt:
        print("\n\n🛑 테스트가 중단되었습니다.")
    except Exception as e:
        print(f"\n❌ 예상치 못한 오류: {str(e)}")
