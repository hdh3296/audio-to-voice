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
    
    def load_model(self, model_name: str = "large-v3"):
        """Faster-Whisper 모델 로드 (한국어 최적화, 안정성 우선)"""
        if model_name not in self.models:
            print(f"📥 Faster-Whisper 모델 로드 중: {model_name}")
            try:
                # 안정성을 위해 CPU 사용, 필요시 GPU는 사용자가 수동 설정
                self.models[model_name] = WhisperModel(
                    model_name, 
                    device="cpu", 
                    compute_type="int8",
                    download_root=None,  # 기본 캐시 디렉토리 사용
                    local_files_only=False  # 온라인 다운로드 허용
                )
                print(f"✅ 모델 로드 완료: {model_name}")
            except Exception as e:
                print(f"❌ {model_name} 모델 로드 실패: {e}")
                # large-v3 실패시 medium으로 자동 대체
                if model_name == "large-v3":
                    print("🔄 medium 모델로 자동 대체 중...")
                    fallback_model = "medium"
                    self.models[model_name] = WhisperModel(
                        fallback_model, 
                        device="cpu", 
                        compute_type="int8"
                    )
                    print(f"✅ 대체 모델 로드 완료: {fallback_model}")
                else:
                    raise e
        return self.models[model_name]
    
    def transcribe_audio(
        self, 
        audio_path: str, 
        model_name: str = "large-v3",
        language: Optional[str] = "ko",
        task: str = "transcribe"
    ) -> Dict:
        """오디오 파일을 텍스트로 변환 (한국어 최적화)"""
        try:
            model = self.load_model(model_name)
            
            # 한국어 최적화 프롬프트
            korean_prompt = "안녕하세요. 다음은 한국어 음성입니다. 정확한 문장 부호와 자연스러운 띄어쓰기를 포함해 주세요."
            
            print(f"🎯 한국어 음성 인식 시작: {audio_path}")
            print(f"📊 모델: {model_name}, 언어: {language}")
            
            segments, info = model.transcribe(
                audio_path, 
                language=language,
                task=task,
                word_timestamps=True,
                initial_prompt=korean_prompt,
                # 한국어 최적화 설정 (수정된 파라미터명)
                beam_size=5,
                best_of=5,
                temperature=0.0,  # 일관된 결과를 위해
                condition_on_previous_text=True,
                compression_ratio_threshold=2.4,
                log_prob_threshold=-1.0,  # 수정: logprob_threshold -> log_prob_threshold
                no_speech_threshold=0.6
            )
            
            # 결과 수집
            segments_list = []
            full_text = ""
            
            for segment in segments:
                # 한국어 텍스트 정리
                cleaned_text = segment.text.strip()
                if cleaned_text:  # 빈 텍스트 제외
                    segment_dict = {
                        "start": segment.start,
                        "end": segment.end,
                        "text": cleaned_text
                    }
                    segments_list.append(segment_dict)
                    full_text += cleaned_text + " "
            
            result = {
                "text": full_text.strip(),
                "segments": segments_list,
                "language": info.language,
                "language_probability": info.language_probability
            }
            
            print(f"✅ 한국어 음성 인식 완료: {len(segments_list)}개 구간")
            return result
        
        except Exception as e:
            raise Exception(f"한국어 음성 인식 실패: {str(e)}")
    
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
        """오디오와 자막으로 비디오 생성 (한국어 최적화)"""
        try:
            # 오디오 길이 구하기
            duration = self.get_audio_duration(audio_path)
            
            with tempfile.NamedTemporaryFile(mode='w', suffix='.srt', delete=False, encoding='utf-8') as srt_file:
                srt_file.write(srt_content)
                srt_path = srt_file.name
            
            # 한국어 폰트 설정 (시스템에 따라 자동 선택)
            font_style = (
                'FontSize=28,'
                'PrimaryColour=&Hffffff,'
                'OutlineColour=&H000000,'
                'Outline=3,'
                'Shadow=1,'
                'Alignment=2,'  # 중앙 하단
                'MarginV=50'    # 하단 여백
            )
            
            # FFmpeg를 사용하여 비디오 생성 (한국어 최적화)
            cmd = [
                'ffmpeg',
                '-f', 'lavfi',
                '-i', f'color=c={background_color}:s=1280x720:d={duration}',
                '-i', audio_path,
                '-vf', f'subtitles={srt_path}:force_style=\'{font_style}\'',
                '-c:v', 'libx264',
                '-preset', 'medium',  # 품질과 속도 균형
                '-crf', '23',         # 고품질 설정
                '-c:a', 'aac',
                '-b:a', '128k',       # 오디오 품질
                '-shortest',
                '-y',  # 덮어쓰기
                output_path
            ]
            
            print(f"🎬 한국어 자막 비디오 생성 중: {output_path}")
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                raise Exception(f"FFmpeg 오류: {result.stderr}")
            
            # 임시 SRT 파일 삭제
            os.unlink(srt_path)
            
            print(f"✅ 한국어 자막 비디오 생성 완료: {output_path}")
            
        except Exception as e:
            # 임시 파일 정리
            if 'srt_path' in locals() and os.path.exists(srt_path):
                os.unlink(srt_path)
            raise Exception(f"비디오 생성 실패: {str(e)}")
    
    def process_audio_to_video(
        self,
        audio_path: str,
        output_path: str,
        model_name: str = "large-v3",
        language: Optional[str] = "ko",
        task: str = "transcribe",
        background_color: str = "black"
    ) -> Dict:
        """전체 프로세스: 오디오 → 자막 → 비디오 (한국어 최적화)"""
        try:
            print(f"🚀 한국어 음성 처리 시작 - 모델: {model_name}")
            
            # 1. 한국어 오디오 전사
            print("📝 1단계: 한국어 음성 인식 중...")
            result = self.transcribe_audio(audio_path, model_name, language, task)
            
            # 2. SRT 생성
            print("📄 2단계: 한국어 자막 생성 중...")
            srt_content = self.generate_srt(result)
            
            # 3. 한국어 자막 비디오 생성
            print("🎬 3단계: 한국어 자막 비디오 생성 중...")
            self.create_video_with_subtitles(audio_path, srt_content, output_path, background_color)
            
            return {
                "success": True,
                "output_path": output_path,
                "transcript": result["text"],
                "segments_count": len(result["segments"]),
                "language": result.get("language", "ko"),
                "language_probability": result.get("language_probability", 0.0),
                "model_used": model_name
            }
        
        except Exception as e:
            print(f"❌ 오류 발생: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

# 전역 인스턴스
auto_subtitle = AutoSubtitle()
