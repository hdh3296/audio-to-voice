"""
OpenAI Whisper API 일관성 개선 클라이언트
temperature=0, seed, prompt 등을 활용한 결과 안정화
"""
import asyncio
import os
import tempfile
from typing import List, Dict, Optional, Tuple
from datetime import datetime
import aiofiles
from dotenv import load_dotenv
from openai import OpenAI
import logging
import hashlib

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class StableOpenAIWhisperClient:
    """일관된 결과를 위한 OpenAI Whisper API 클라이언트"""
    
    def __init__(self):
        self.client: Optional[OpenAI] = None
        self.api_key: Optional[str] = None
        self.max_audio_length: int = 10
        self._load_environment()
    
    def _load_environment(self):
        """환경변수 로드"""
        try:
            load_dotenv()
            self.api_key = os.getenv("OPENAI_API_KEY")
            self.max_audio_length = int(os.getenv("MAX_AUDIO_LENGTH_MINUTES", "10"))
            
            if self.api_key and self.api_key != "your_openai_api_key_here":
                self.client = OpenAI(api_key=self.api_key)
                logger.info("✅ OpenAI API 클라이언트 초기화 완료 (안정화 모드)")
            else:
                logger.warning("⚠️ OpenAI API 키가 설정되지 않음")
        except Exception as e:
            logger.error(f"❌ 환경변수 로드 실패: {e}")
    
    def is_available(self) -> bool:
        """API 사용 가능 여부 확인"""
        return self.client is not None
    
    def generate_file_seed(self, file_path: str) -> int:
        """파일 경로 기반 일관된 시드 생성"""
        # 파일 경로와 파일 크기를 기반으로 고유한 시드 생성
        file_size = os.path.getsize(file_path)
        seed_string = f"{file_path}_{file_size}"
        seed_hash = hashlib.md5(seed_string.encode()).hexdigest()
        # 해시를 정수로 변환 (OpenAI seed는 정수여야 함)
        return int(seed_hash[:8], 16) % (2**31 - 1)  # 32비트 정수 범위
    
    def create_consistent_prompt(self, language: str = "ko") -> str:
        """일관된 결과를 위한 상세한 프롬프트 생성"""
        if language == "ko":
            return """다음은 한국어 음성입니다. 정확한 한국어 표준어로 전사해주세요. 
문장 부호는 자연스럽게 사용하고, 띄어쓰기는 한국어 맞춤법에 맞게 해주세요. 
브랜드명이나 고유명사는 정확하게 표기해주세요."""
        else:
            return "Please transcribe this audio accurately with proper punctuation and spacing."
    
    async def transcribe_audio_stable(
        self, 
        audio_path: str, 
        language: str = "ko",
        use_deterministic: bool = True
    ) -> Dict:
        """안정화된 OpenAI API 전사 (일관된 결과)"""
        try:
            if not self.is_available():
                raise Exception("OpenAI API 클라이언트가 초기화되지 않음")
            
            logger.info(f"🎯 안정화 모드 OpenAI API 전사 시작: {audio_path}")
            
            # 파일 크기 확인
            file_size_mb = os.path.getsize(audio_path) / (1024 * 1024)
            if file_size_mb > 25:
                raise Exception(f"파일 크기 제한 초과: {file_size_mb:.1f}MB > 25MB")
            
            # 일관성을 위한 파라미터 설정
            consistent_prompt = self.create_consistent_prompt(language)
            file_seed = self.generate_file_seed(audio_path) if use_deterministic else None
            
            def _stable_api_call():
                with open(audio_path, "rb") as audio_file:
                    # 일관성 향상을 위한 파라미터 조합
                    params = {
                        "model": "whisper-1",
                        "file": audio_file,
                        "language": language,
                        "response_format": "verbose_json",
                        "timestamp_granularities": ["segment"],
                        "prompt": consistent_prompt,  # 상세한 프롬프트
                        "temperature": 0.0,  # 🔑 결정론적 결과를 위해 0
                    }
                    
                    # 시드 파라미터 추가 (지원되는 경우)
                    if file_seed is not None:
                        logger.info(f"🎲 파일 기반 시드 사용: {file_seed}")
                        # 참고: Whisper API는 현재 seed를 지원하지 않을 수 있음
                        # 하지만 향후 지원 가능성을 위해 조건부 추가
                        try:
                            params["seed"] = file_seed
                        except:
                            logger.warning("⚠️ Whisper API는 현재 seed 파라미터를 지원하지 않음")
                    
                    return self.client.audio.transcriptions.create(**params)
            
            # 비동기 API 호출
            result = await asyncio.to_thread(_stable_api_call)
            
            # 세그먼트 처리
            segments = []
            if result.segments:
                for segment in result.segments:
                    segments.append({
                        "start": segment.start,
                        "end": segment.end,
                        "text": segment.text.strip()
                    })
            
            logger.info(f"✅ 안정화 API 전사 완료: {len(segments)}개 세그먼트")
            
            return {
                "success": True,
                "text": result.text.strip(),
                "segments": segments,
                "language": getattr(result, 'language', language),
                "processing_method": "openai_api_stable",
                "file_size_mb": file_size_mb,
                "used_seed": file_seed,
                "temperature": 0.0,
                "prompt": consistent_prompt
            }
        
        except Exception as e:
            logger.error(f"❌ 안정화 API 전사 실패: {e}")
            return {
                "success": False,
                "error": str(e),
                "processing_method": "openai_api_stable"
            }
    
    async def transcribe_with_retry(
        self,
        audio_path: str,
        language: str = "ko",
        max_retries: int = 3
    ) -> Dict:
        """재시도를 통한 일관된 결과 확보"""
        results = []
        
        for attempt in range(max_retries):
            logger.info(f"🔄 시도 {attempt + 1}/{max_retries}")
            
            result = await self.transcribe_audio_stable(audio_path, language)
            
            if result.get("success"):
                results.append(result["text"])
                
                # 첫 번째 성공한 결과를 반환 (일관성을 위해)
                if attempt == 0:
                    logger.info("✅ 첫 번째 시도 성공, 결과 반환")
                    return result
                
                # 이전 결과와 비교
                if len(results) >= 2 and results[-1] == results[-2]:
                    logger.info("✅ 일관된 결과 확인됨")
                    return result
            
            # 실패시 잠시 대기
            await asyncio.sleep(1)
        
        # 모든 시도 실패시 마지막 결과 반환
        if results:
            logger.warning("⚠️ 완전 일관된 결과는 얻지 못했지만 마지막 결과 반환")
            return result
        else:
            return {
                "success": False,
                "error": "모든 재시도 실패",
                "processing_method": "openai_api_stable"
            }

# 전역 인스턴스
stable_openai_whisper_client = StableOpenAIWhisperClient()
