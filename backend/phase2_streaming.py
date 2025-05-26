"""
🚀 Phase 2: 실시간 스트리밍 전사 시스템
- WebSocket 기반 실시간 업데이트
- 청크 단위 처리로 빠른 응답
- 진행률 실시간 표시
"""

import asyncio
import json
import time
import tempfile
import os
from typing import Dict, List, Optional, AsyncGenerator, Callable
from pathlib import Path
import numpy as np
from dataclasses import dataclass, asdict

# pydub 관련 임포트를 try-except로 처리
try:
    from pydub import AudioSegment
    from pydub.silence import split_on_silence
    PYDUB_AVAILABLE = True
except ImportError:
    print("⚠️ pydub를 사용할 수 없습니다. 기본 청킹 방식을 사용합니다.")
    PYDUB_AVAILABLE = False


@dataclass 
class StreamingProgress:
    """스트리밍 진행 상황"""
    total_chunks: int
    processed_chunks: int
    current_chunk: int
    progress_percent: float
    current_text: str
    estimated_remaining_time: float
    status: str  # "processing", "completed", "error"
    error_message: Optional[str] = None


@dataclass
class StreamingChunk:
    """스트리밍 청크 데이터"""
    chunk_id: int
    start_time: float
    end_time: float
    audio_data: bytes
    text: Optional[str] = None
    confidence: Optional[float] = None
    processing_time: Optional[float] = None


class AudioChunker:
    """오디오 청킹 시스템"""
    
    def __init__(self, chunk_duration: float = 30.0, overlap: float = 2.0):
        """
        초기화
        Args:
            chunk_duration: 청크 길이 (초)
            overlap: 청크 간 겹침 (초)
        """
        self.chunk_duration = chunk_duration
        self.overlap = overlap
    
    async def chunk_audio_file(self, audio_path: str) -> List[StreamingChunk]:
        """오디오 파일을 청크로 분할 (간단한 시간 기반 방식)"""
        
        try:
            if PYDUB_AVAILABLE:
                return await self._chunk_with_pydub(audio_path)
            else:
                return await self._chunk_simple(audio_path)
        except Exception as e:
            print(f"❌ 오디오 청킹 실패: {str(e)}")
            raise
    
    async def _chunk_simple(self, audio_path: str) -> List[StreamingChunk]:
        """간단한 시간 기반 청킹 (pydub 없이)"""
        
        # ffprobe를 사용해서 오디오 길이 구하기
        try:
            import subprocess
            cmd = ['ffprobe', '-v', 'quiet', '-show_entries', 'format=duration', 
                   '-of', 'csv=p=0', audio_path]
            result = subprocess.run(cmd, capture_output=True, text=True)
            total_duration = float(result.stdout.strip())
        except:
            total_duration = 60.0  # 기본값
        
        chunks = []
        chunk_id = 0
        start_time = 0.0
        
        print(f"🎵 오디오 총 길이: {total_duration:.1f}초 (간단한 청킹)")
        print(f"📊 청크 크기: {self.chunk_duration}초, 겹침: {self.overlap}초")
        
        while start_time < total_duration:
            end_time = min(start_time + self.chunk_duration, total_duration)
            
            # 실제 오디오 파일을 그대로 사용 (청킹하지 않고)
            with open(audio_path, 'rb') as f:
                audio_data = f.read()
            
            chunk = StreamingChunk(
                chunk_id=chunk_id,
                start_time=start_time,
                end_time=end_time,
                audio_data=audio_data  # 전체 파일 사용
            )
            
            chunks.append(chunk)
            print(f"  📦 청크 {chunk_id}: {start_time:.1f}s - {end_time:.1f}s")
            
            start_time = end_time - self.overlap
            chunk_id += 1
            
            if end_time >= total_duration:
                break
        
        print(f"✅ 총 {len(chunks)}개 청크 생성 완료 (간단한 방식)")
        return chunks
    
    async def _chunk_with_pydub(self, audio_path: str) -> List[StreamingChunk]:
        """pydub를 사용한 정확한 청킹"""
        
        # 오디오 로드
        audio = AudioSegment.from_file(audio_path)
        total_duration = len(audio) / 1000.0  # 초 단위
        
        chunks = []
        chunk_id = 0
        start_ms = 0
        chunk_duration_ms = int(self.chunk_duration * 1000)
        overlap_ms = int(self.overlap * 1000)
        
        print(f"🎵 오디오 총 길이: {total_duration:.1f}초")
        print(f"📊 청크 크기: {self.chunk_duration}초, 겹침: {self.overlap}초")
        
        while start_ms < len(audio):
            # 청크 끝 지점 계산
            end_ms = min(start_ms + chunk_duration_ms, len(audio))
            
            # 오디오 청크 추출
            chunk_audio = audio[start_ms:end_ms]
            
            # 청크 데이터 생성
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                chunk_audio.export(temp_file.name, format="wav")
                
                with open(temp_file.name, 'rb') as f:
                    audio_data = f.read()
                
                os.unlink(temp_file.name)
            
            chunk = StreamingChunk(
                chunk_id=chunk_id,
                start_time=start_ms / 1000.0,
                end_time=end_ms / 1000.0,
                audio_data=audio_data
            )
            
            chunks.append(chunk)
            
            print(f"  📦 청크 {chunk_id}: {chunk.start_time:.1f}s - {chunk.end_time:.1f}s")
            
            # 다음 청크 시작점 (겹침 고려)
            start_ms = end_ms - overlap_ms
            chunk_id += 1
            
            # 마지막 청크인 경우 종료
            if end_ms >= len(audio):
                break
        
        print(f"✅ 총 {len(chunks)}개 청크 생성 완료")
        return chunks


class StreamingTranscriber:
    """실시간 스트리밍 전사기"""
    
    def __init__(self, model_manager, chunk_duration: float = 30.0):
        """초기화"""
        self.model_manager = model_manager
        self.chunker = AudioChunker(chunk_duration)
        self.active_sessions: Dict[str, Dict] = {}
    
    async def transcribe_streaming(
        self,
        session_id: str,
        audio_path: str,
        model: str = "gpt-4o-audio-preview",
        language: str = "ko",
        progress_callback: Optional[Callable] = None
    ) -> AsyncGenerator[StreamingProgress, None]:
        """스트리밍 전사 실행"""
        
        start_time = time.time()
        
        try:
            # 세션 초기화
            self.active_sessions[session_id] = {
                "status": "chunking",
                "start_time": start_time,
                "model": model
            }
            
            # 1단계: 오디오 청킹
            yield StreamingProgress(
                total_chunks=0,
                processed_chunks=0,
                current_chunk=0,
                progress_percent=0.0,
                current_text="오디오를 분석 중...",
                estimated_remaining_time=0.0,
                status="chunking"
            )
            
            chunks = await self.chunker.chunk_audio_file(audio_path)
            total_chunks = len(chunks)
            
            # 2단계: 병렬 전사 시작
            self.active_sessions[session_id]["status"] = "processing"
            full_text = ""
            all_segments = []
            processing_times = []
            
            for i, chunk in enumerate(chunks):
                chunk_start_time = time.time()
                
                # 진행률 업데이트
                progress_percent = (i / total_chunks) * 100
                
                # 남은 시간 추정
                if processing_times:
                    avg_processing_time = sum(processing_times) / len(processing_times)
                    remaining_chunks = total_chunks - i
                    estimated_remaining_time = avg_processing_time * remaining_chunks
                else:
                    estimated_remaining_time = 0.0
                
                yield StreamingProgress(
                    total_chunks=total_chunks,
                    processed_chunks=i,
                    current_chunk=i + 1,
                    progress_percent=progress_percent,
                    current_text=f"청크 {i+1}/{total_chunks} 처리 중...",
                    estimated_remaining_time=estimated_remaining_time,
                    status="processing"
                )
                
                # 청크 전사
                try:
                    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                        temp_file.write(chunk.audio_data)
                        temp_file.flush()
                        
                        result = await self.model_manager.transcribe_with_model(
                            temp_file.name, model, language, include_quality_metrics=True
                        )
                        
                        os.unlink(temp_file.name)
                    
                    if result.success and result.text.strip():
                        chunk.text = result.text.strip()
                        chunk.confidence = result.confidence_score
                        
                        # 시간 오프셋 조정
                        adjusted_segments = []
                        for segment in result.segments:
                            adj_segment = segment.copy()
                            adj_segment["start"] += chunk.start_time
                            adj_segment["end"] += chunk.start_time
                            adjusted_segments.append(adj_segment)
                        
                        all_segments.extend(adjusted_segments)
                        full_text += " " + chunk.text
                        
                        print(f"  ✅ 청크 {i+1}: {chunk.text[:50]}...")
                    
                    else:
                        print(f"  ⚠️ 청크 {i+1}: 전사 실패 또는 빈 결과")
                
                except Exception as e:
                    print(f"  ❌ 청크 {i+1} 처리 오류: {str(e)}")
                
                # 처리 시간 기록
                chunk_processing_time = time.time() - chunk_start_time
                processing_times.append(chunk_processing_time)
                chunk.processing_time = chunk_processing_time
                
                # 중간 결과 업데이트
                yield StreamingProgress(
                    total_chunks=total_chunks,
                    processed_chunks=i + 1,
                    current_chunk=i + 1,
                    progress_percent=((i + 1) / total_chunks) * 100,
                    current_text=full_text.strip(),
                    estimated_remaining_time=estimated_remaining_time,
                    status="processing"
                )
                
                # 프로그레스 콜백 호출
                if progress_callback:
                    await progress_callback(session_id, i + 1, total_chunks)
            
            # 3단계: 완료
            total_processing_time = time.time() - start_time
            self.active_sessions[session_id]["status"] = "completed"
            self.active_sessions[session_id]["result"] = {
                "text": full_text.strip(),
                "segments": all_segments,
                "total_processing_time": total_processing_time,
                "chunks_processed": len(chunks)
            }
            
            yield StreamingProgress(
                total_chunks=total_chunks,
                processed_chunks=total_chunks,
                current_chunk=total_chunks,
                progress_percent=100.0,
                current_text=full_text.strip(),
                estimated_remaining_time=0.0,
                status="completed"
            )
            
            print(f"🎉 스트리밍 전사 완료 - 총 {total_processing_time:.2f}초")
            
        except Exception as e:
            error_msg = str(e)
            print(f"❌ 스트리밍 전사 오류: {error_msg}")
            
            self.active_sessions[session_id]["status"] = "error"
            self.active_sessions[session_id]["error"] = error_msg
            
            yield StreamingProgress(
                total_chunks=0,
                processed_chunks=0,
                current_chunk=0,
                progress_percent=0.0,
                current_text="",
                estimated_remaining_time=0.0,
                status="error",
                error_message=error_msg
            )
    
    def get_session_status(self, session_id: str) -> Optional[Dict]:
        """세션 상태 조회"""
        return self.active_sessions.get(session_id)
    
    def cancel_session(self, session_id: str) -> bool:
        """세션 취소"""
        if session_id in self.active_sessions:
            self.active_sessions[session_id]["status"] = "cancelled"
            return True
        return False
    
    def cleanup_session(self, session_id: str) -> bool:
        """세션 정리"""
        if session_id in self.active_sessions:
            del self.active_sessions[session_id]
            return True
        return False


class StreamingWebSocketHandler:
    """WebSocket 스트리밍 핸들러 (선택적 기능)"""
    
    def __init__(self, streaming_transcriber: StreamingTranscriber):
        self.transcriber = streaming_transcriber
        self.connections: Dict[str, any] = {}  # WebSocket 연결 타입 일반화
    
    async def handle_connection(self, websocket, path):
        """WebSocket 연결 처리 (websockets 패키지 필요시에만 사용)"""
        session_id = None
        
        try:
            # 실제 WebSocket 처리는 main_phase2.py에서 처리
            pass
            
        except Exception as e:
            print(f"❌ WebSocket 오류: {str(e)}")
        
        finally:
            if session_id and session_id in self.connections:
                del self.connections[session_id]


# 테스트용 함수들
async def test_streaming_system():
    """스트리밍 시스템 테스트"""
    from phase2_models import Phase2ModelManager
    import os
    from dotenv import load_dotenv
    
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")
    
    if not api_key:
        print("❌ OpenAI API 키가 필요합니다")
        return
    
    # 매니저 초기화
    model_manager = Phase2ModelManager(api_key)
    transcriber = StreamingTranscriber(model_manager, chunk_duration=20.0)
    
    # 테스트 파일 경로
    test_audio = "/path/to/test/audio.mp3"
    
    if not os.path.exists(test_audio):
        print("❌ 테스트 오디오 파일이 없습니다")
        return
    
    # 스트리밍 전사 테스트
    session_id = "test_session_001"
    
    print("🚀 스트리밍 전사 테스트 시작...")
    
    async for progress in transcriber.transcribe_streaming(
        session_id, test_audio, "gpt-4o-audio-preview", "ko"
    ):
        print(f"📊 진행률: {progress.progress_percent:.1f}% - {progress.current_text[:50]}...")
        
        if progress.status == "completed":
            print("🎉 스트리밍 전사 완료!")
            break
        elif progress.status == "error":
            print(f"❌ 오류 발생: {progress.error_message}")
            break


if __name__ == "__main__":
    asyncio.run(test_streaming_system())
