"""
OpenAI Whisper API 클라이언트 모듈 (pydub 없는 버전)
간단한 파일 기반 처리로 pydub 의존성 제거
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

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class OpenAIWhisperClient:
    """OpenAI Whisper API 클라이언트 (간소화 버전)"""
    
    def __init__(self):
        self.client: Optional[OpenAI] = None
        self.api_key: Optional[str] = None
        self.max_audio_length: int = 10  # 기본 10분
        self._load_environment()
    
    def _load_environment(self):
        """환경변수 로드"""
        try:
            load_dotenv()
            self.api_key = os.getenv("OPENAI_API_KEY")
            self.max_audio_length = int(os.getenv("MAX_AUDIO_LENGTH_MINUTES", "10"))
            
            if self.api_key and self.api_key != "your_openai_api_key_here":
                self.client = OpenAI(api_key=self.api_key)
                logger.info("✅ OpenAI API 클라이언트 초기화 완료")
            else:
                logger.warning("⚠️ OpenAI API 키가 설정되지 않음 - 로컬 모드만 사용 가능")
        except Exception as e:
            logger.error(f"❌ 환경변수 로드 실패: {e}")
    
    def is_available(self) -> bool:
        """API 사용 가능 여부 확인"""
        return self.client is not None
    
    def get_file_size_mb(self, file_path: str) -> float:
        """파일 크기를 MB로 반환"""
        return os.path.getsize(file_path) / (1024 * 1024)
    
    async def transcribe_audio_api(
        self, 
        audio_path: str, 
        language: str = "ko"
    ) -> Dict:
        """OpenAI API로 오디오 전사 (단일 파일 처리)"""
        try:
            if not self.is_available():
                raise Exception("OpenAI API 클라이언트가 초기화되지 않음")
            
            logger.info(f"🎯 OpenAI API 전사 시작: {audio_path}")
            
            # 파일 크기 확인 (25MB 제한)
            file_size_mb = self.get_file_size_mb(audio_path)
            if file_size_mb > 25:
                raise Exception(f"파일 크기 제한 초과: {file_size_mb:.1f}MB > 25MB")
            
            # API 호출 함수
            def _api_call():
                with open(audio_path, "rb") as audio_file:
                    transcript = self.client.audio.transcriptions.create(
                        model="whisper-1",
                        file=audio_file,
                        language=language,
                        response_format="verbose_json",
                        timestamp_granularities=["segment"]
                    )
                    return transcript
            
            # 비동기 API 호출
            result = await asyncio.to_thread(_api_call)
            
            # 세그먼트 처리
            segments = []
            if result.segments:
                for segment in result.segments:
                    segments.append({
                        "start": segment.start,
                        "end": segment.end,
                        "text": segment.text.strip()
                    })
            
            logger.info(f"✅ API 전사 완료: {len(segments)}개 세그먼트")
            
            return {
                "success": True,
                "text": result.text.strip(),
                "segments": segments,
                "language": getattr(result, 'language', language),
                "processing_method": "openai_api",
                "file_size_mb": file_size_mb
            }
        
        except Exception as e:
            logger.error(f"❌ API 전사 실패: {e}")
            return {
                "success": False,
                "error": str(e),
                "processing_method": "openai_api"
            }

# 전역 인스턴스
openai_whisper_client = OpenAIWhisperClient()
