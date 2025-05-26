"""
Auto-subtitle 모듈
faster-whisper를 사용한 고성능 구현
"""
from faster_whisper import WhisperModel
import ffmpeg
import os
import tempfile
from pathlib import Path
from typing import Optional, Dict, List
import subprocess
import json

class AutoSubtitle:
    def __init__(self):
        self.models = {}
    
    def load_model(self, model_name: str = "small"):
        """Faster-Whisper 모델 로드"""
        if model_name not in self.models:
            print(f"Loading Faster-Whisper model: {model_name}")
            # CPU에서 실행하도록 설정
            self.models[model_name] = WhisperModel(model_name, device="cpu", compute_type="int8")
        return self.models[model_name]
    
    def transcribe_audio(
        self, 
        audio_path: str, 
        model_name: str = "small",
        language: Optional[str] = None,
        task: str = "transcribe"
    ) -> Dict:
        """오디오 파일을 텍스트로 변환"""
        try:
            model = self.load_model(model_name)
            
            print(f"Transcribing audio: {audio_path}")
            segments, info = model.transcribe(
                audio_path, 
                language=language if language else None,
                task=task,
                word_timestamps=True
            )
            
            # 결과 수집
            segments_list = []
            full_text = ""
            
            for segment in segments:
                segment_dict = {
                    "start": segment.start,
                    "end": segment.end,
                    "text": segment.text
                }
                segments_list.append(segment_dict)
                full_text += segment.text
            
            result = {
                "text": full_text,
                "segments": segments_list,
                "language": info.language
            }
            
            return result
        
        except Exception as e:
            raise Exception(f"Audio transcription failed: {str(e)}")
    
    def generate_srt(self, result: Dict) -> str:
        """Whisper 결과를 SRT 형식으로 변환"""
        srt_content = ""
        
        for i, segment in enumerate(result["segments"], 1):
            start_time = self.seconds_to_srt_time(segment["start"])
            end_time = self.seconds_to_srt_time(segment["end"])
            text = segment["text"].strip()
            
            srt_content += f"{i}\n"
            srt_content += f"{start_time} --> {end_time}\n"
            srt_content += f"{text}\n\n"
        
        return srt_content
    
    def seconds_to_srt_time(self, seconds: float) -> str:
        """초를 SRT 시간 형식으로 변환"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millisecs = int((seconds % 1) * 1000)
        
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millisecs:03d}"
    
    def get_audio_duration(self, audio_path: str) -> float:
        """오디오 파일의 길이를 구함"""
        try:
            probe = ffmpeg.probe(audio_path)
            duration = float(probe['streams'][0]['duration'])
            return duration
        except:
            return 60.0  # 기본값
    
    def create_video_with_subtitles(
        self, 
        audio_path: str, 
        srt_content: str, 
        output_path: str,
        background_color: str = "black"
    ):
        """오디오와 자막으로 비디오 생성"""
        try:
            # 오디오 길이 구하기
            duration = self.get_audio_duration(audio_path)
            
            with tempfile.NamedTemporaryFile(mode='w', suffix='.srt', delete=False, encoding='utf-8') as srt_file:
                srt_file.write(srt_content)
                srt_path = srt_file.name
            
            # FFmpeg를 사용하여 비디오 생성
            cmd = [
                'ffmpeg',
                '-f', 'lavfi',
                '-i', f'color=c={background_color}:s=1280x720:d={duration}',
                '-i', audio_path,
                '-vf', f'subtitles={srt_path}:force_style=\'FontSize=24,PrimaryColour=&Hffffff,OutlineColour=&H000000,Outline=2\'',
                '-c:v', 'libx264',
                '-c:a', 'aac',
                '-shortest',
                '-y',  # 덮어쓰기
                output_path
            ]
            
            print(f"Creating video with subtitles: {output_path}")
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                raise Exception(f"FFmpeg error: {result.stderr}")
            
            # 임시 SRT 파일 삭제
            os.unlink(srt_path)
            
            print(f"Video created successfully: {output_path}")
            
        except Exception as e:
            # 임시 파일 정리
            if 'srt_path' in locals() and os.path.exists(srt_path):
                os.unlink(srt_path)
            raise Exception(f"Video creation failed: {str(e)}")
    
    def process_audio_to_video(
        self,
        audio_path: str,
        output_path: str,
        model_name: str = "small",
        language: Optional[str] = None,
        task: str = "transcribe",
        background_color: str = "black"
    ) -> Dict:
        """전체 프로세스: 오디오 → 자막 → 비디오"""
        try:
            # 1. 오디오 전사
            print("Step 1: Transcribing audio...")
            result = self.transcribe_audio(audio_path, model_name, language, task)
            
            # 2. SRT 생성
            print("Step 2: Generating SRT...")
            srt_content = self.generate_srt(result)
            
            # 3. 비디오 생성
            print("Step 3: Creating video with subtitles...")
            self.create_video_with_subtitles(audio_path, srt_content, output_path, background_color)
            
            return {
                "success": True,
                "output_path": output_path,
                "transcript": result["text"],
                "segments_count": len(result["segments"]),
                "language": result.get("language", "unknown")
            }
        
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

# 전역 인스턴스
auto_subtitle = AutoSubtitle()
