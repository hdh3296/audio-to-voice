"""
Auto-subtitle 모듈 (하이브리드 버전)
faster-whisper + OpenAI API 통합
"""
from faster_whisper import WhisperModel
import ffmpeg
import os
import tempfile
from pathlib import Path
from typing import Optional, Dict, List
import subprocess
import json
import asyncio
from dotenv import load_dotenv

# OpenAI 클라이언트 임포트
from .openai_client import openai_whisper_client

# GPT 후처리 모듈 임포트 (지연 임포트로 의존성 문제 해결)
try:
    from .gpt_postprocessor import gpt_postprocessor
    GPT_POSTPROCESSOR_AVAILABLE = True
    print("✅ GPT 후처리 모듈 로드 성공")
except Exception as e:
    print(f"⚠️ GPT 후처리 모듈 로드 실패: {e}")
    gpt_postprocessor = None
    GPT_POSTPROCESSOR_AVAILABLE = False

class AutoSubtitle:
    def __init__(self):
        self.models = {}
        load_dotenv()  # 환경변수 로드
    
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
    
    def transcribe_audio_local(
        self, 
        audio_path: str, 
        model_name: str = "large-v3",
        language: Optional[str] = "ko",
        task: str = "transcribe"
    ) -> Dict:
        """로컬 Faster-Whisper로 오디오 전사"""
        try:
            model = self.load_model(model_name)
            
            # 한국어 최적화 프롬프트
            korean_prompt = "안녕하세요. 다음은 한국어 음성입니다. 정확한 문장 부호와 자연스러운 띄어쓰기를 포함해 주세요."
            
            print(f"🎯 로컬 한국어 음성 인식 시작: {audio_path}")
            print(f"📊 모델: {model_name}, 언어: {language}")
            
            segments, info = model.transcribe(
                audio_path, 
                language=language,
                task=task,
                word_timestamps=True,
                initial_prompt=korean_prompt,
                # 한국어 최적화 설정
                beam_size=5,
                best_of=5,
                temperature=0.0,
                condition_on_previous_text=True,
                compression_ratio_threshold=2.4,
                log_prob_threshold=-1.0,
                no_speech_threshold=0.6
            )
            
            # 결과 수집
            segments_list = []
            full_text = ""
            
            for segment in segments:
                cleaned_text = segment.text.strip()
                if cleaned_text:
                    segment_dict = {
                        "start": segment.start,
                        "end": segment.end,
                        "text": cleaned_text
                    }
                    segments_list.append(segment_dict)
                    full_text += cleaned_text + " "
            
            result = {
                "success": True,
                "text": full_text.strip(),
                "segments": segments_list,
                "language": info.language,
                "language_probability": info.language_probability,
                "processing_method": "local_faster_whisper"
            }
            
            print(f"✅ 로컬 음성 인식 완료: {len(segments_list)}개 구간")
            return result
        
        except Exception as e:
            print(f"❌ 로컬 음성 인식 실패: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "processing_method": "local_faster_whisper"
            }
    
    async def transcribe_audio_hybrid(
        self, 
        audio_path: str, 
        model_name: str = "large-v3",
        language: Optional[str] = "ko",
        task: str = "transcribe",
        use_api: bool = False,
        use_gpt_correction: bool = False
    ) -> Dict:
        """하이브리드 전사 (API 우선, 실패시 로컬 대체)"""
        
        # API 모드 시도
        if use_api and openai_whisper_client.is_available():
            print("🌐 OpenAI API 모드로 전사 시도...")
            api_result = await openai_whisper_client.transcribe_audio_api(audio_path, language)
            
            if api_result.get("success"):
                print("✅ API 전사 성공!")
                return api_result
            else:
                print(f"⚠️ API 전사 실패, 로컬 모드로 대체: {api_result.get('error')}")
        
        # 로컬 모드로 대체
        print("🏠 로컬 모드로 전사...")
        local_result = self.transcribe_audio_local(audio_path, model_name, language, task)
        
        if not local_result.get("success"):
            print("❌ 로컬 전사도 실패!")
            return local_result
        
        # GPT 후처리 적용 (옵션)
        if use_gpt_correction and gpt_postprocessor and gpt_postprocessor.is_available():
            print("🤖 GPT 후처리로 오타 교정 중...")
            correction_result = await gpt_postprocessor.correct_segments(
                local_result.get("segments", []),
                context=f"한국어 음성 인식 결과 교정"
            )
            
            if correction_result.get("success"):
                # 교정된 세그먼트로 업데이트
                corrected_segments = correction_result.get("corrected_segments", [])
                corrected_text = " ".join([seg.get("text", "") for seg in corrected_segments])
                
                local_result.update({
                    "text": corrected_text,
                    "segments": corrected_segments,
                    "gpt_correction_applied": correction_result.get("correction_applied", False),
                    "total_corrections": correction_result.get("total_corrections", 0),
                    "processing_method": f"{local_result.get('processing_method', 'unknown')} + GPT교정"
                })
                
                print(f"✅ GPT 교정 완료: {correction_result.get('total_corrections', 0)}개 수정")
            else:
                print(f"⚠️ GPT 교정 실패: {correction_result.get('error', 'Unknown error')}")
                # 실패해도 원본 결과는 유지
        elif use_gpt_correction:
            print("⚠️ GPT 후처리를 사용할 수 없습니다 (API 키 확인 필요)")
        
        return local_result
    
    def generate_srt(self, result: Dict) -> str:
        """결과를 SRT 형식으로 변환"""
        srt_content = ""
        segments = result.get("segments", [])
        
        for i, segment in enumerate(segments, 1):
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
            
            # 한국어 폰트 설정
            font_style = (
                'FontSize=28,'
                'PrimaryColour=&Hffffff,'
                'OutlineColour=&H000000,'
                'Outline=3,'
                'Shadow=1,'
                'Alignment=2,'
                'MarginV=50'
            )
            
            # FFmpeg를 사용하여 비디오 생성
            cmd = [
                'ffmpeg',
                '-f', 'lavfi',
                '-i', f'color=c={background_color}:s=1280x720:d={duration}',
                '-i', audio_path,
                '-vf', f'subtitles={srt_path}:force_style=\'{font_style}\'',
                '-c:v', 'libx264',
                '-preset', 'medium',
                '-crf', '23',
                '-c:a', 'aac',
                '-b:a', '128k',
                '-shortest',
                '-y',
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
    
    async def process_audio_to_video(
        self,
        audio_path: str,
        output_path: str,
        model_name: str = "large-v3",
        language: Optional[str] = "ko",
        task: str = "transcribe",
        background_color: str = "black",
        use_api: bool = False,
        use_gpt_correction: bool = False
    ) -> Dict:
        """전체 프로세스: 오디오 → 자막 → 비디오 (하이브리드 모드)"""
        try:
            gpt_status = " + GPT교정" if use_gpt_correction else ""
            method = f"API + 로컬 하이브리드{gpt_status}" if use_api else f"로컬{gpt_status}"
            print(f"🚀 {method} 모드로 음성 처리 시작 - 모델: {model_name}")
            
            # 1. 하이브리드 오디오 전사 + GPT 후처리
            print("📝 1단계: 하이브리드 음성 인식 중...")
            result = await self.transcribe_audio_hybrid(
                audio_path, model_name, language, task, use_api, use_gpt_correction
            )
            
            if not result.get("success"):
                return result
            
            # 2. SRT 생성
            print("📄 2단계: 자막 생성 중...")
            srt_content = self.generate_srt(result)
            
            # 3. 비디오 생성
            print("🎬 3단계: 자막 비디오 생성 중...")
            self.create_video_with_subtitles(
                audio_path, srt_content, output_path, background_color
            )
            
            return {
                "success": True,
                "output_path": output_path,
                "transcript": result["text"],
                "segments_count": len(result.get("segments", [])),
                "language": result.get("language", "ko"),
                "language_probability": result.get("language_probability", 0.0),
                "model_used": model_name,
                "processing_method": result.get("processing_method", "unknown"),
                "gpt_correction_applied": result.get("gpt_correction_applied", False),
                "total_corrections": result.get("total_corrections", 0)
            }
        
        except Exception as e:
            print(f"❌ 오류 발생: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

# 전역 인스턴스
auto_subtitle = AutoSubtitle()
