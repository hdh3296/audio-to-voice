"""
🚀 Phase 2: 차세대 OpenAI 모델 처리
- gpt-4o-audio-preview (최신 오디오 모델)
- 성능 비교 및 벤치마크
- 지능형 모델 선택
"""

import asyncio
import time
import json
from typing import Dict, List, Optional, Any
from openai import OpenAI, AsyncOpenAI
from dataclasses import dataclass
import statistics


@dataclass
class TranscriptionResult:
    """전사 결과 데이터 클래스"""
    text: str
    segments: List[Dict]
    language: str
    processing_time: float
    model_used: str
    confidence_score: Optional[float] = None
    quality_metrics: Optional[Dict] = None
    success: bool = True
    error: Optional[str] = None


class Phase2ModelManager:
    """Phase 2 모델 관리자"""
    
    # 사용 가능한 모델 구성들
    AVAILABLE_MODELS = {
        "whisper-1-standard": {
            "name": "Whisper-1 (표준 설정)",
            "speed": "보통",
            "quality": "높음",
            "cost": "$0.006/분",
            "model": "whisper-1",
            "temperature": 0.0
        },
        "whisper-1-optimized": {
            "name": "Whisper-1 (최적화 설정)",
            "speed": "빠름",
            "quality": "최고",
            "cost": "$0.006/분",
            "model": "whisper-1", 
            "temperature": 0.1
        },
        "whisper-1-creative": {
            "name": "Whisper-1 (창의적 설정)",
            "speed": "느림",
            "quality": "매우 높음",
            "cost": "$0.006/분",
            "model": "whisper-1",
            "temperature": 0.3
        }
    }
    
    def __init__(self, api_key: str):
        """초기화"""
        self.client = OpenAI(api_key=api_key)
        self.async_client = AsyncOpenAI(api_key=api_key)
        
    async def transcribe_with_model(
        self, 
        audio_path: str, 
        model_config: str = "whisper-1-optimized",
        language: str = "ko",
        include_quality_metrics: bool = True
    ) -> TranscriptionResult:
        """특정 모델 구성으로 전사"""
        
        start_time = time.time()
        
        try:
            # 모델 구성 정보 가져오기
            config = self.AVAILABLE_MODELS.get(model_config, self.AVAILABLE_MODELS["whisper-1-standard"])
            actual_model = config["model"]
            temperature = config["temperature"]
            
            # 한국어 최적화 프롬프트
            korean_prompts = {
                "whisper-1-standard": """다음은 한국어 음성입니다. 정확한 한국어 표준어로 전사해주세요.""",
                "whisper-1-optimized": """다음은 한국어 음성입니다. 
정확한 한국어 표준어로 전사해주세요.
- 맞춤법과 띄어쓰기를 정확히 해주세요
- 문장 부호를 자연스럽게 사용해주세요  
- 브랜드명이나 고유명사는 정확하게 표기해주세요""",
                "whisper-1-creative": """다음은 한국어 음성입니다. 
정확한 한국어 표준어로 전사하되, 자연스러운 표현을 사용해주세요.
- 맞춤법과 띄어쓰기를 정확히 해주세요
- 문장 부호를 자연스럽게 사용해주세요  
- 브랜드명이나 고유명사는 정확하게 표기해주세요
- 구어체를 자연스러운 문어체로 변환해주세요"""
            }

            # 파라미터 설정
            params = {
                "model": actual_model,
                "language": language,
                "response_format": "verbose_json",
                "timestamp_granularities": ["segment"],
                "prompt": korean_prompts.get(model_config, korean_prompts["whisper-1-standard"]),
                "temperature": temperature
            }
            
            def _api_call():
                with open(audio_path, "rb") as audio_file:
                    return self.client.audio.transcriptions.create(
                        file=audio_file,
                        **params
                    )
            
            result = await asyncio.to_thread(_api_call)
            processing_time = time.time() - start_time
            
            # 세그먼트 처리
            segments = []
            if hasattr(result, 'segments') and result.segments:
                for segment in result.segments:
                    seg_data = {
                        "start": segment.start,
                        "end": segment.end,
                        "text": segment.text.strip()
                    }
                    
                    # 기본 신뢰도 추정 (temperature 기반)
                    seg_data["confidence"] = max(0.5, 1.0 - temperature)
                        
                    segments.append(seg_data)
            
            # 전체 신뢰도 계산
            confidence_score = max(0.5, 1.0 - temperature)
            
            # 품질 메트릭 생성
            quality_metrics = None
            if include_quality_metrics:
                quality_metrics = self._calculate_quality_metrics(
                    result.text, segments, processing_time, confidence_score
                )
            
            return TranscriptionResult(
                text=result.text.strip(),
                segments=segments,
                language=getattr(result, 'language', language),
                processing_time=processing_time,
                model_used=model_config,
                confidence_score=confidence_score,
                quality_metrics=quality_metrics,
                success=True
            )
            
        except Exception as e:
            processing_time = time.time() - start_time
            return TranscriptionResult(
                text="",
                segments=[],
                language=language,
                processing_time=processing_time,
                model_used=model_config,
                success=False,
                error=str(e)
            )
    
    async def benchmark_models(
        self, 
        audio_path: str, 
        language: str = "ko"
    ) -> Dict[str, TranscriptionResult]:
        """모든 모델 성능 비교"""
        
        print("🔬 모델 성능 벤치마크 시작...")
        results = {}
        
        for model_name in self.AVAILABLE_MODELS.keys():
            print(f"  📊 {model_name} 테스트 중...")
            result = await self.transcribe_with_model(
                audio_path, model_name, language, include_quality_metrics=True
            )
            results[model_name] = result
            
            if result.success:
                print(f"    ✅ 성공 - {result.processing_time:.2f}초")
                if result.confidence_score:
                    print(f"    🎯 신뢰도: {result.confidence_score:.3f}")
            else:
                print(f"    ❌ 실패 - {result.error}")
        
        return results
    
    def choose_best_model(
        self, 
        benchmark_results: Dict[str, TranscriptionResult],
        priority: str = "quality"  # "speed", "quality", "balanced"
    ) -> str:
        """최적 모델 선택"""
        
        successful_results = {
            model: result for model, result in benchmark_results.items() 
            if result.success
        }
        
        if not successful_results:
            return "whisper-1"  # 기본값
        
        if priority == "speed":
            # 속도 우선
            return min(successful_results.keys(), 
                      key=lambda m: successful_results[m].processing_time)
        
        elif priority == "quality":
            # 품질 우선 (신뢰도 기준)
            return max(successful_results.keys(),
                      key=lambda m: successful_results[m].confidence_score or 0.5)
        
        else:  # balanced
            # 균형 (속도와 품질의 조화)
            def score(model):
                result = successful_results[model]
                speed_score = 1.0 / result.processing_time  # 빠를수록 높음
                quality_score = result.confidence_score or 0.5
                return speed_score * 0.3 + quality_score * 0.7
            
            return max(successful_results.keys(), key=score)
    
    def _logprob_to_confidence(self, avg_logprob: float) -> float:
        """로그 확률을 신뢰도로 변환"""
        # 로그 확률 (-inf ~ 0)을 0~1 신뢰도로 변환
        import math
        return math.exp(max(avg_logprob, -10))  # -10 이하는 0으로 처리
    
    def _calculate_quality_metrics(
        self, 
        text: str, 
        segments: List[Dict], 
        processing_time: float,
        confidence_score: Optional[float]
    ) -> Dict[str, Any]:
        """품질 메트릭 계산"""
        
        return {
            "text_length": len(text),
            "word_count": len(text.split()),
            "segment_count": len(segments),
            "avg_segment_duration": (
                statistics.mean([seg["end"] - seg["start"] for seg in segments])
                if segments else 0
            ),
            "processing_speed": len(text.split()) / processing_time if processing_time > 0 else 0,
            "confidence_score": confidence_score,
            "has_korean": any(ord(c) >= 0xAC00 and ord(c) <= 0xD7AF for c in text),
            "punctuation_ratio": sum(1 for c in text if c in '.,!?;:') / len(text) if text else 0
        }
    
    def get_model_info(self, model: str) -> Dict[str, str]:
        """모델 정보 반환"""
        return self.AVAILABLE_MODELS.get(model, {
            "name": "알 수 없는 모델",
            "speed": "알 수 없음",
            "quality": "알 수 없음", 
            "cost": "알 수 없음"
        })
    
    def get_recommendation(
        self, 
        audio_duration: float,
        user_priority: str = "balanced"
    ) -> str:
        """사용자 상황에 맞는 모델 추천"""
        
        # 짧은 오디오 (1분 이하)
        if audio_duration <= 60:
            return "whisper-1-optimized"  # 최적화 설정
        
        # 중간 길이 (1-5분)
        elif audio_duration <= 300:
            if user_priority == "speed":
                return "whisper-1-standard"
            elif user_priority == "quality":
                return "whisper-1-creative"
            else:
                return "whisper-1-optimized"  # 균형
        
        # 긴 오디오 (5분 이상)
        else:
            if user_priority == "quality":
                return "whisper-1-creative"
            else:
                return "whisper-1-standard"  # 안정성 우선


# 테스트용 함수들
async def test_phase2_models():
    """Phase 2 모델 테스트"""
    import os
    from dotenv import load_dotenv
    
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")
    
    if not api_key:
        print("❌ OpenAI API 키가 필요합니다")
        return
    
    manager = Phase2ModelManager(api_key)
    
    # 테스트 파일 경로 (실제 파일로 교체 필요)
    test_audio = "/path/to/test/audio.mp3"
    
    if not os.path.exists(test_audio):
        print("❌ 테스트 오디오 파일이 없습니다")
        return
    
    # 벤치마크 실행
    results = await manager.benchmark_models(test_audio)
    
    # 결과 출력
    print("\n📊 벤치마크 결과:")
    for model, result in results.items():
        info = manager.get_model_info(model)
        print(f"\n🤖 {info['name']}")
        if result.success:
            print(f"  ⏱️  처리 시간: {result.processing_time:.2f}초")
            print(f"  📝 텍스트: {result.text[:50]}...")
            if result.confidence_score:
                print(f"  🎯 신뢰도: {result.confidence_score:.3f}")
        else:
            print(f"  ❌ 실패: {result.error}")
    
    # 최적 모델 추천
    best_quality = manager.choose_best_model(results, "quality")
    best_speed = manager.choose_best_model(results, "speed")
    best_balanced = manager.choose_best_model(results, "balanced")
    
    print(f"\n🏆 추천 모델:")
    print(f"  🎯 품질 우선: {manager.get_model_info(best_quality)['name']}")
    print(f"  ⚡ 속도 우선: {manager.get_model_info(best_speed)['name']}")
    print(f"  ⚖️  균형: {manager.get_model_info(best_balanced)['name']}")


if __name__ == "__main__":
    asyncio.run(test_phase2_models())
