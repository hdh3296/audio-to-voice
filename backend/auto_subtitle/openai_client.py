"""
OpenAI Whisper API 클라이언트 모듈
LexGlu/whisper-audio-transcriber 방식을 참조하여 구현
"""
import asyncio
import os
import tempfile
from typing import List, Dict, Optional, Tuple
from datetime import datetime
import aiofiles
from dotenv import load_dotenv
from openai import OpenAI
from pydub import AudioSegment
import logging

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 10분 청크 설정 (25MB 제한 준수)
CHUNK_DURATION_MS = 10 * 60 * 1000

class OpenAIWhisperClient:
    """OpenAI Whisper API 클라이언트"""
    
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
    
    async def read_audio_file(self, audio_path: str) -> AudioSegment:
        """비동기로 오디오 파일 읽기"""
        return await asyncio.to_thread(AudioSegment.from_file, audio_path)
    
    def split_audio_chunks(self, audio: AudioSegment) -> List[AudioSegment]:
        """오디오를 청크로 분할 (10분 단위)"""
        chunks = []
        total_duration = len(audio)
        
        for start in range(0, total_duration, CHUNK_DURATION_MS):
            end = min(start + CHUNK_DURATION_MS, total_duration)
            chunk = audio[start:end]
            chunks.append(chunk)
        
        logger.info(f"📊 오디오 분할 완료: {len(chunks)}개 청크 ({total_duration/1000/60:.1f}분)")
        return chunks
    
    async def export_chunk_temp(self, chunk: AudioSegment, index: int) -> str:
        """청크를 임시 파일로 내보내기"""
        temp_file = tempfile.NamedTemporaryFile(
            suffix=f"_chunk_{index}.mp3", 
            delete=False
        )
        temp_path = temp_file.name
        temp_file.close()
        
        # 비동기로 청크 내보내기
        await asyncio.to_thread(chunk.export, temp_path, format="mp3")
        return temp_path
    
    async def transcribe_chunk_api(
        self, 
        chunk_path: str, 
        language: str = "ko"
    ) -> Dict:
        """OpenAI API로 청크 전사"""
        def _api_call():
            with open(chunk_path, "rb") as audio_file:
                transcript = self.client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    language=language,
                    response_format="verbose_json",
                    timestamp_granularities=["segment"]
                )
                return transcript
        
        try:
            result = await asyncio.to_thread(_api_call)
            return {
                "text": result.text,
                "segments": [
                    {
                        "start": seg.start,
                        "end": seg.end,
                        "text": seg.text.strip()
                    }
                    for seg in result.segments
                ],
                "language": getattr(result, 'language', language)
            }
        except Exception as e:
            logger.error(f"❌ API 전사 실패: {e}")
            raise e
    
    async def process_chunk(
        self, 
        chunk: AudioSegment, 
        index: int, 
        language: str = "ko"
    ) -> Dict:
        """청크 처리 (내보내기 + 전사)"""
        chunk_path = None
        try:
            # 청크를 임시 파일로 내보내기
            chunk_path = await self.export_chunk_temp(chunk, index)
            logger.info(f"🎵 청크 {index} 처리 중... ({chunk.duration_seconds:.1f}초)")
            
            # API로 전사
            result = await self.transcribe_chunk_api(chunk_path, language)
            
            return {
                "success": True,
                "chunk_index": index,
                "duration": chunk.duration_seconds,
                **result
            }
        
        except Exception as e:
            logger.error(f"❌ 청크 {index} 처리 실패: {e}")
            return {
                "success": False,
                "chunk_index": index,
                "error": str(e)
            }
        
        finally:
            # 임시 파일 정리
            if chunk_path and os.path.exists(chunk_path):
                try:
                    os.unlink(chunk_path)
                except:
                    pass
    
    def format_timestamp(self, seconds: float) -> str:
        """초를 타임스탬프 형식으로 변환"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    
    def merge_segments(self, chunk_results: List[Dict]) -> List[Dict]:
        """청크별 세그먼트를 시간 순서로 병합"""
        all_segments = []
        cumulative_time = 0.0
        
        for chunk_result in chunk_results:
            if not chunk_result.get("success"):
                continue
                
            chunk_duration = chunk_result.get("duration", 0)
            segments = chunk_result.get("segments", [])
            
            # 세그먼트 시간 조정
            for segment in segments:
                adjusted_segment = {
                    "start": segment["start"] + cumulative_time,
                    "end": segment["end"] + cumulative_time,
                    "text": segment["text"]
                }
                all_segments.append(adjusted_segment)
            
            cumulative_time += chunk_duration
        
        return all_segments
    
    async def transcribe_audio_api(
        self, 
        audio_path: str, 
        language: str = "ko"
    ) -> Dict:
        """전체 API 전사 프로세스 (청크 처리)"""
        try:
            if not self.is_available():
                raise Exception("OpenAI API 클라이언트가 초기화되지 않음")
            
            logger.info(f"🎯 OpenAI API 전사 시작: {audio_path}")
            
            # 오디오 파일 읽기
            audio = await self.read_audio_file(audio_path)
            duration_minutes = audio.duration_seconds / 60
            
            # 길이 제한 확인
            if duration_minutes > self.max_audio_length:
                raise Exception(f"오디오 길이 제한 초과: {duration_minutes:.1f}분 > {self.max_audio_length}분")
            
            # 청크 분할
            chunks = self.split_audio_chunks(audio)
            
            # 병렬 청크 처리
            logger.info(f"⚡ {len(chunks)}개 청크 병렬 처리 시작...")
            tasks = [
                self.process_chunk(chunk, i+1, language)
                for i, chunk in enumerate(chunks)
            ]
            chunk_results = await asyncio.gather(*tasks)
            
            # 성공한 청크만 필터링
            successful_chunks = [r for r in chunk_results if r.get("success")]
            if not successful_chunks:
                raise Exception("모든 청크 처리 실패")
            
            # 결과 병합
            all_text = " ".join([r["text"] for r in successful_chunks])
            all_segments = self.merge_segments(successful_chunks)
            
            logger.info(f"✅ API 전사 완료: {len(all_segments)}개 세그먼트")
            
            return {
                "success": True,
                "text": all_text.strip(),
                "segments": all_segments,
                "language": language,
                "processing_method": "openai_api",
                "chunks_processed": len(successful_chunks),
                "total_duration": audio.duration_seconds
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
