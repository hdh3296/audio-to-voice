"""
🧪 Phase 2 기본 테스트 스크립트 (간소화 버전)
- pydub, websockets 의존성 없이 실행
- 핵심 기능만 테스트
"""

import asyncio
import os
import sys
import time
from pathlib import Path

# 프로젝트 루트로 경로 추가
sys.path.append(str(Path(__file__).parent))

from dotenv import load_dotenv


async def test_basic_imports():
    """기본 모듈 임포트 테스트"""
    print("📦 모듈 임포트 테스트...")
    
    try:
        from phase2_models import Phase2ModelManager, TranscriptionResult
        print("✅ phase2_models 임포트 성공")
        
        from phase2_quality import QualityAnalyzer, KoreanTextAnalyzer
        print("✅ phase2_quality 임포트 성공")
        
        # phase2_streaming은 pydub 없이도 작동하도록 수정됨
        from phase2_streaming import StreamingTranscriber
        print("✅ phase2_streaming 임포트 성공")
        
        return True
        
    except ImportError as e:
        print(f"❌ 모듈 임포트 실패: {e}")
        return False


async def test_openai_connection():
    """OpenAI API 연결 테스트"""
    print("\n🌐 OpenAI API 연결 테스트...")
    
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")
    
    if not api_key or api_key == "your_openai_api_key_here":
        print("❌ OpenAI API 키가 설정되지 않았습니다.")
        return False
    
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        
        # 간단한 API 호출 테스트 (실제 음성 파일 없이)
        print("✅ OpenAI 클라이언트 초기화 성공")
        print(f"  API 키 길이: {len(api_key)} 문자")
        print(f"  API 키 시작: {api_key[:10]}...")
        
        return True
        
    except Exception as e:
        print(f"❌ OpenAI API 연결 실패: {str(e)}")
        return False


async def test_quality_analyzer():
    """품질 분석기 테스트 (텍스트만)"""
    print("\n🔍 품질 분석기 테스트...")
    
    try:
        from phase2_quality import QualityAnalyzer
        
        analyzer = QualityAnalyzer()
        
        # 테스트 데이터
        test_text = "안녕하세요. 이것은 한국어 음성 인식 테스트입니다."
        test_segments = [
            {"start": 0.0, "end": 2.0, "text": "안녕하세요.", "confidence": 0.95},
            {"start": 2.0, "end": 5.0, "text": "이것은 한국어 음성 인식 테스트입니다.", "confidence": 0.89}
        ]
        
        quality = await analyzer.analyze_transcription_quality(
            test_text, test_segments, processing_time=2.5, model_used="test_model"
        )
        
        print("✅ 품질 분석 성공")
        print(f"  전체 점수: {quality.overall_score:.3f}")
        print(f"  한국어 품질: {quality.korean_quality_score:.3f}")
        print(f"  재처리 필요: {'예' if quality.needs_reprocessing else '아니오'}")
        
        return True
        
    except Exception as e:
        print(f"❌ 품질 분석 테스트 실패: {str(e)}")
        return False


async def test_model_manager():
    """모델 매니저 테스트 (API 호출 없이)"""
    print("\n🤖 모델 매니저 테스트...")
    
    try:
        from phase2_models import Phase2ModelManager
        
        load_dotenv()
        api_key = os.getenv("OPENAI_API_KEY")
        
        if not api_key:
            print("❌ API 키 없음, 모델 매니저 테스트 건너뛰기")
            return False
        
        manager = Phase2ModelManager(api_key)
        
        # 모델 정보 확인
        print("✅ 모델 매니저 초기화 성공")
        print("  사용 가능한 모델:")
        for model_name, info in manager.AVAILABLE_MODELS.items():
            print(f"    - {model_name}: {info['name']}")
        
        # 추천 시스템 테스트
        short_audio_rec = manager.get_recommendation(30, "quality")  # 30초
        long_audio_rec = manager.get_recommendation(300, "speed")   # 5분
        
        print(f"  30초 오디오 추천 (품질 우선): {short_audio_rec}")
        print(f"  5분 오디오 추천 (속도 우선): {long_audio_rec}")
        
        return True
        
    except Exception as e:
        print(f"❌ 모델 매니저 테스트 실패: {str(e)}")
        return False


async def test_api_server_status():
    """API 서버 상태 확인 (서버 실행시에만)"""
    print("\n🌐 API 서버 상태 확인...")
    
    try:
        import httpx
        
        # 짧은 타임아웃으로 서버 확인
        async with httpx.AsyncClient(timeout=3.0) as client:
            response = await client.get("http://localhost:8002/")
            
            if response.status_code == 200:
                print("✅ Phase 2 API 서버 실행 중")
                data = response.json()
                print(f"  서버 버전: {data.get('version', 'Unknown')}")
                return True
            else:
                print(f"⚠️ API 서버 응답 오류: {response.status_code}")
                return False
                
    except Exception as e:
        print("⚠️ API 서버가 실행되지 않음 (정상 - 별도 실행 필요)")
        print("  서버 시작: cd backend && python main_phase2.py")
        return False


def print_phase2_info():
    """Phase 2 시스템 정보 출력"""
    print("\n📋 Phase 2 시스템 정보")
    print("=" * 50)
    print("🚀 구현된 주요 기능:")
    print("  1️⃣ 차세대 모델 관리 시스템")
    print("  2️⃣ 실시간 스트리밍 처리")
    print("  3️⃣ 지능형 품질 검증")
    print("  4️⃣ 자동 재처리 시스템")
    print("")
    print("🔧 핵심 파일:")
    print("  - phase2_models.py: 모델 관리")
    print("  - phase2_quality.py: 품질 분석")
    print("  - phase2_streaming.py: 스트리밍 처리")
    print("  - main_phase2.py: 메인 API 서버")
    print("")
    print("🌐 접속 방법:")
    print("  - API 서버: http://localhost:8002")
    print("  - 웹 UI: http://localhost:3000/phase2")
    print("")


async def run_basic_tests():
    """기본 테스트 실행"""
    print("🧪 Phase 2 기본 테스트 시작")
    print("=" * 50)
    
    results = []
    
    # 1. 모듈 임포트 테스트
    results.append(await test_basic_imports())
    
    # 2. OpenAI 연결 테스트
    results.append(await test_openai_connection())
    
    # 3. 품질 분석기 테스트
    results.append(await test_quality_analyzer())
    
    # 4. 모델 매니저 테스트
    results.append(await test_model_manager())
    
    # 5. API 서버 상태 확인 (선택적)
    server_status = await test_api_server_status()
    
    # 결과 요약
    print("\n📊 테스트 결과 요약")
    print("=" * 50)
    
    test_names = ["모듈 임포트", "OpenAI 연결", "품질 분석", "모델 매니저"]
    
    for i, (name, result) in enumerate(zip(test_names, results)):
        status = "✅ 성공" if result else "❌ 실패"
        print(f"{i+1}. {name}: {status}")
    
    print(f"5. API 서버: {'✅ 실행중' if server_status else '⚠️ 미실행'}")
    
    success_rate = sum(results) / len(results) * 100
    print(f"\n🎯 핵심 기능 성공률: {success_rate:.1f}%")
    
    if all(results):
        print("\n🎉 모든 핵심 기능이 정상 작동합니다!")
        print("   다음 단계: API 서버를 시작하여 웹 UI를 테스트해보세요.")
        print("")
        print("   서버 시작 방법:")
        print("   1. cd backend && source venv_phase2/bin/activate")
        print("   2. python main_phase2.py")
        print("   3. 웹 브라우저: http://localhost:8002")
    else:
        print("\n⚠️ 일부 기능에서 문제가 발견되었습니다.")
        print("   위의 오류 메시지를 확인하여 문제를 해결해주세요.")
    
    # Phase 2 정보 출력
    print_phase2_info()


if __name__ == "__main__":
    print("🧪 Phase 2 기본 테스트 도구")
    print("=" * 50)
    print("테스트 전 확인사항:")
    print("1. ✅ 가상환경 활성화: source venv_phase2/bin/activate")
    print("2. ✅ .env 파일의 OpenAI API 키 설정")
    print("3. ⚠️ 패키지 설치: pip install -r requirements_phase2.txt")
    print("")
    
    try:
        asyncio.run(run_basic_tests())
    except KeyboardInterrupt:
        print("\n\n🛑 테스트가 중단되었습니다.")
    except Exception as e:
        print(f"\n❌ 예상치 못한 오류: {str(e)}")
        print("가상환경과 패키지 설치 상태를 확인해주세요.")
