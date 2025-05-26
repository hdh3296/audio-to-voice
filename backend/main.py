from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
import uuid
from typing import Optional
import asyncio
from datetime import datetime
# pydub 문제로 auto_subtitle 임포트 제거

app = FastAPI(title="Audio to Voice API", version="1.0.0")

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],  # 프론트엔드 포트 2개 지원
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 디렉토리 설정
BASE_DIR = Path(__file__).parent.parent
UPLOADS_DIR = BASE_DIR / "uploads"
OUTPUTS_DIR = BASE_DIR / "outputs"

# 디렉토리 생성
UPLOADS_DIR.mkdir(exist_ok=True)
OUTPUTS_DIR.mkdir(exist_ok=True)

# 정적 파일 서빙
app.mount("/outputs", StaticFiles(directory=str(OUTPUTS_DIR)), name="outputs")

# 지원하는 오디오 형식
SUPPORTED_AUDIO_FORMATS = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg"}

@app.get("/")
async def root():
    return {"message": "Audio to Voice API", "status": "running"}

@app.get("/api-status")
async def api_status():
    """OpenAI API 및 GPT 후처리 상태 확인"""
    try:
        from dotenv import load_dotenv
        load_dotenv()
        
        api_key = os.getenv("OPENAI_API_KEY")
        api_available = api_key is not None and api_key != "your_openai_api_key_here"
        
        # GPT 후처리 상태 확인
        gpt_available = False
        try:
            # 간단한 GPT 후처리 모듈 사용
            from simple_gpt_postprocessor import simple_gpt_postprocessor
            gpt_available = simple_gpt_postprocessor.is_available()
        except ImportError as e:
            print(f"⚠️ GPT 후처리 모듈 임포트 실패: {e}")
            gpt_available = False 
        except Exception as e:
            print(f"⚠️ GPT 후처리 상태 확인 실패: {e}")
            gpt_available = False
        
        return {
            "openai_api_available": api_available,
            "gpt_postprocessing_available": gpt_available,
            "max_audio_length_minutes": 10 if api_available else None,
            "api_configured": api_available,
            "features": {
                "whisper_api": api_available,
                "gpt_correction": gpt_available,
                "local_whisper": True  # 항상 사용 가능
            }
        }
    except Exception as e:
        print(f"❌ API 상태 확인 중 오류: {e}")
        return {
            "openai_api_available": False,
            "gpt_postprocessing_available": False,
            "max_audio_length_minutes": None,
            "api_configured": False,
            "features": {
                "whisper_api": False,
                "gpt_correction": False,
                "local_whisper": True
            },
            "error": str(e)
        }

@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

@app.post("/upload-audio")
async def upload_audio(file: UploadFile = File(...)):
    """오디오 파일 업로드"""
    try:
        # 파일 확장자 검증
        file_extension = Path(file.filename).suffix.lower()
        if file_extension not in SUPPORTED_AUDIO_FORMATS:
            raise HTTPException(
                status_code=400, 
                detail=f"지원하지 않는 파일 형식입니다. 지원 형식: {', '.join(SUPPORTED_AUDIO_FORMATS)}"
            )
        
        # 고유 파일명 생성
        file_id = str(uuid.uuid4())
        filename = f"{file_id}{file_extension}"
        file_path = UPLOADS_DIR / filename
        
        # 파일 저장
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        return {
            "file_id": file_id,
            "filename": filename,
            "original_name": file.filename,
            "size": file_path.stat().st_size,
            "message": "파일이 성공적으로 업로드되었습니다."
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"파일 업로드 중 오류가 발생했습니다: {str(e)}")

@app.post("/generate-subtitles/{file_id}")
async def generate_subtitles(
    file_id: str,
    model: str = "large-v3",  # 한국어 정확도 향상을 위해 large-v3 기본값
    language: Optional[str] = "ko",  # 한국어 기본 설정
    task: str = "transcribe",
    background_color: str = "black",
    use_api: bool = False,  # 🆕 API 모드 선택 파라미터
    use_gpt_correction: bool = False  # 🆕 GPT 후처리 옵션
):
    """한국어 자막 생성 및 비디오 생성 (하이브리드 모드 + GPT 후처리 지원)"""
    try:
        # 업로드된 파일 찾기
        uploaded_files = list(UPLOADS_DIR.glob(f"{file_id}.*"))
        if not uploaded_files:
            raise HTTPException(status_code=404, detail="업로드된 파일을 찾을 수 없습니다.")
        
        input_file = uploaded_files[0]
        output_file = OUTPUTS_DIR / f"{file_id}_subtitled.mp4"
        
        gpt_status = " + GPT교정" if use_gpt_correction else ""
        mode_text = f"OpenAI API{gpt_status}" if use_api else f"로컬 Faster-Whisper{gpt_status}"
        print(f"🎯 {mode_text} 모드로 음성 처리 시작 - 모델: {model}")
        
        segments_list = []
        full_text = ""
        processing_method = ""
        language_detected = language
        language_probability = 1.0
        gpt_correction_applied = False
        total_corrections = 0
        
        if use_api:
            # OpenAI API 모드 - 자동 대체 없이 API만 사용
            print("🌐 OpenAI Whisper API 사용")
            try:
                from dotenv import load_dotenv
                import openai
                load_dotenv()
                
                # API 키 확인
                api_key = os.getenv("OPENAI_API_KEY")
                if not api_key or api_key == "your_openai_api_key_here":
                    raise HTTPException(
                        status_code=400, 
                        detail="OpenAI API 키가 설정되지 않았습니다. .env 파일을 확인해주세요."
                    )
                
                # OpenAI 클라이언트 초기화
                client = openai.OpenAI(api_key=api_key)
                
                # 파일 크기 확인 (25MB 제한)
                file_size = input_file.stat().st_size
                if file_size > 25 * 1024 * 1024:  # 25MB
                    raise HTTPException(
                        status_code=400,
                        detail=f"OpenAI API는 25MB 이하의 파일만 지원합니다. 현재 파일 크기: {file_size / (1024*1024):.1f}MB"
                    )
                
                # 한국어 최적화 프롬프트 설정
                korean_prompt = (
                    "다음은 한국어 음성입니다. "
                    "정확한 맞춤법과 자연스러운 띄어쓰기를 사용해 주세요. "
                    "문장 부호를 적절히 사용하고, 구어체 표현을 자연스럽게 변환해 주세요."
                ) if language == "ko" else ""
                
                # API 호출 - 한국어 정확도 향상을 위한 최적화 설정
                with open(input_file, "rb") as audio_file:
                    print(f"📤 OpenAI API로 파일 전송 중... ({file_size / (1024*1024):.1f}MB)")
                    
                    transcript = client.audio.transcriptions.create(
                        model="whisper-1",
                        file=audio_file,
                        language=language if language else None,
                        response_format="verbose_json",
                        timestamp_granularities=["segment"],
                        prompt=korean_prompt,  # 🆕 한국어 최적화 프롬프트
                        temperature=0.0  # 🆕 일관성을 위한 낮은 온도 설정
                    )
                    
                print(f"✅ OpenAI API 응답 받음 - 언어: {transcript.language}")
                
                # 결과 처리
                full_text = transcript.text
                language_detected = transcript.language
                processing_method = "openai_api"
                
                # 세그먼트 처리
                if hasattr(transcript, 'segments') and transcript.segments:
                    for segment in transcript.segments:
                        if hasattr(segment, 'text') and segment.text.strip():
                            segment_dict = {
                                "start": segment.start,
                                "end": segment.end,
                                "text": segment.text.strip()
                            }
                            segments_list.append(segment_dict)
                else:
                    # 세그먼트가 없는 경우 전체 텍스트를 하나의 세그먼트로 처리
                    segments_list.append({
                        "start": 0.0,
                        "end": 30.0,  # 기본값
                        "text": full_text
                    })
                
            except openai.AuthenticationError:
                raise HTTPException(status_code=401, detail="OpenAI API 키가 유효하지 않습니다.")
            except openai.RateLimitError:
                raise HTTPException(status_code=429, detail="OpenAI API 사용량 한도를 초과했습니다.")
            except openai.APIError as e:
                raise HTTPException(status_code=500, detail=f"OpenAI API 오류: {str(e)}")
            except Exception as e:
                # API 모드에서는 자동 대체하지 않고 오류 발생
                raise HTTPException(status_code=500, detail=f"OpenAI API 처리 중 오류: {str(e)}")
                
        else:
            # 로컬 Faster-Whisper 모드
            print("🏠 로컬 Faster-Whisper 사용")
            from faster_whisper import WhisperModel
            
            # 로컬 Whisper 모델 로드
            whisper_model = WhisperModel(model, device="cpu", compute_type="int8")
            
            # 한국어 최적화 전사
            segments, info = whisper_model.transcribe(
                str(input_file), 
                language=language,
                task=task
            )
            
            # 결과 수집
            for segment in segments:
                text = segment.text.strip()
                if text:
                    segment_dict = {
                        "start": segment.start,
                        "end": segment.end,
                        "text": text
                    }
                    segments_list.append(segment_dict)
                    full_text += text + " "
            
            language_detected = info.language
            language_probability = info.language_probability
            processing_method = "local_whisper"
        
        # GPT 후처리 적용 (모든 모드에서 사용 가능)
        if use_gpt_correction:
            try:
                print("🤖 GPT 후처리로 오타 교정 중...")
                
                # 간단한 GPT 후처리 모듈 사용
                from simple_gpt_postprocessor import simple_gpt_postprocessor
                
                if simple_gpt_postprocessor.is_available():
                    # 타임스탬프 보존 강화 버전 사용
                    correction_result = await simple_gpt_postprocessor.correct_segments_preserve_timing(
                        segments_list,
                        context="한국어 음성 인식 결과의 오타 및 맞춤법 교정"
                    )
                    
                    if correction_result.get("success"):
                        # 교정된 세그먼트로 업데이트
                        corrected_segments = correction_result.get("corrected_segments", [])
                        corrected_text = " ".join([seg.get("text", "") for seg in corrected_segments])
                        
                        segments_list = corrected_segments
                        full_text = corrected_text
                        gpt_correction_applied = correction_result.get("correction_applied", False)
                        total_corrections = correction_result.get("total_corrections", 0)
                        processing_method += " + GPT교정"
                        
                        print(f"✅ GPT 교정 완료: {total_corrections}개 수정")
                    else:
                        print(f"⚠️ GPT 교정 실패: {correction_result.get('error', 'Unknown error')}")
                else:
                    print("⚠️ GPT 후처리를 사용할 수 없습니다 (API 키 확인 필요)")
                    
            except Exception as e:
                print(f"⚠️ GPT 교정 중 오류 발생 (원본 유지): {str(e)}")
                # GPT 교정 실패해도 원본 결과는 유지
        
        # SRT 생성 (디버깅 정보 추가)
        srt_content = ""
        print(f"📄 SRT 생성: {len(segments_list)}개 세그먼트")
        
        for i, segment in enumerate(segments_list, 1):
            start_time = seconds_to_srt_time(segment["start"])
            end_time = seconds_to_srt_time(segment["end"])
            text = segment["text"].strip()
            
            print(f"  {i}: {start_time} → {end_time} | {text[:50]}...")
            
            srt_content += f"{i}\n"
            srt_content += f"{start_time} --> {end_time}\n"
            srt_content += f"{text}\n\n"
        
        # 비디오 생성
        create_video_with_srt(str(input_file), srt_content, str(output_file), background_color)
        
        return {
            "file_id": file_id,
            "output_file": f"{file_id}_subtitled.mp4",
            "download_url": f"/download/{file_id}_subtitled.mp4",
            "transcript": full_text.strip(),
            "segments_count": len(segments_list),
            "language": language_detected,
            "language_probability": language_probability,
            "model_used": model if not use_api else "whisper-1",
            "processing_method": processing_method,
            "use_api_mode": use_api,
            "gpt_correction_applied": gpt_correction_applied,
            "total_corrections": total_corrections,
            "message": f"{mode_text} 모드로 한국어 자막 비디오가 성공적으로 생성되었습니다."
        }
    
    except HTTPException:
        # HTTPException은 그대로 재발생
        raise
    except Exception as e:
        print(f"❌ 한국어 자막 생성 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=f"한국어 자막 생성 중 오류: {str(e)}")

def seconds_to_srt_time(seconds: float) -> str:
    """초를 SRT 시간 형식으로 변환"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millisecs = int((seconds % 1) * 1000)
    
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millisecs:03d}"

def get_audio_duration(audio_path: str) -> float:
    """FFprobe를 사용하여 정확한 오디오 길이 구하기"""
    try:
        cmd = [
            'ffprobe',
            '-v', 'quiet',
            '-show_entries', 'format=duration',
            '-of', 'csv=p=0',
            audio_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            duration = float(result.stdout.strip())
            print(f"📊 오디오 길이: {duration:.2f}초")
            return duration
        else:
            print(f"⚠️ FFprobe 오류: {result.stderr}")
            return 60.0  # 기본값
    except Exception as e:
        print(f"⚠️ 오디오 길이 계산 실패: {e}")
        return 60.0  # 기본값

def create_video_with_srt(audio_path: str, srt_content: str, output_path: str, background_color: str = "black"):
    """오디오와 자막으로 비디오 생성 (정확한 싱크)"""
    import subprocess
    import tempfile
    
    # 실제 오디오 길이 구하기
    duration = get_audio_duration(audio_path)
    print(f"🎬 비디오 생성: {duration:.2f}초 길이로 설정")
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.srt', delete=False, encoding='utf-8') as srt_file:
        srt_file.write(srt_content)
        srt_path = srt_file.name
    
    try:
        # 한국어 폰트 설정 (더 명확한 자막을 위해 개선)
        font_style = (
            'FontSize=24,'
            'PrimaryColour=&Hffffff,'  # 흰색 텍스트
            'OutlineColour=&H000000,'  # 검은색 외곽선
            'BackColour=&H80000000,'   # 반투명 배경
            'Outline=2,'               # 외곽선 두께
            'Shadow=2,'                # 그림자
            'Alignment=2,'             # 하단 중앙
            'MarginV=30,'              # 하단 여백
            'Bold=1'                   # 굵게
        )
        
        # FFmpeg 명령어 (더 정확한 싱크를 위해 개선)
        cmd = [
            'ffmpeg',
            '-f', 'lavfi',
            '-i', f'color=c={background_color}:s=1280x720:d={duration}',  # 정확한 길이 사용
            '-i', audio_path,
            '-vf', f'subtitles={srt_path}:force_style=\'{font_style}\'',
            '-c:v', 'libx264',
            '-preset', 'medium',
            '-crf', '23',
            '-c:a', 'aac',
            '-b:a', '128k',
            '-map', '0:v',      # 비디오 스트림 명시적 매핑
            '-map', '1:a',      # 오디오 스트림 명시적 매핑
            '-shortest',        # 가장 짧은 스트림에 맞춤
            '-avoid_negative_ts', 'make_zero',  # 타임스탬프 보정
            '-y',
            output_path
        ]
        
        print(f"🔧 FFmpeg 실행 중...")
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            print(f"❌ FFmpeg 상세 오류:\n{result.stderr}")
            raise Exception(f"FFmpeg 오류: {result.stderr}")
        
        print(f"✅ 비디오 생성 완료: {output_path}")
        
    except Exception as e:
        print(f"❌ 비디오 생성 실패: {e}")
        raise e
    finally:
        # 임시 SRT 파일 삭제
        if os.path.exists(srt_path):
            os.unlink(srt_path)

@app.get("/download/{filename}")
async def download_file(filename: str):
    """생성된 파일 다운로드"""
    file_path = OUTPUTS_DIR / filename
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="파일을 찾을 수 없습니다.")
    
    return FileResponse(
        path=str(file_path),
        filename=filename,
        media_type="application/octet-stream"
    )

@app.get("/status/{file_id}")
async def get_status(file_id: str):
    """처리 상태 확인"""
    input_files = list(UPLOADS_DIR.glob(f"{file_id}.*"))
    output_file = OUTPUTS_DIR / f"{file_id}_subtitled.mp4"
    
    status = "unknown"
    if not input_files:
        status = "not_found"
    elif output_file.exists():
        status = "completed"
    else:
        status = "processing"
    
    return {
        "file_id": file_id,
        "status": status,
        "has_input": bool(input_files),
        "has_output": output_file.exists()
    }

@app.delete("/cleanup/{file_id}")
async def cleanup_files(file_id: str):
    """임시 파일 정리"""
    try:
        # 입력 파일 삭제
        for file_path in UPLOADS_DIR.glob(f"{file_id}.*"):
            file_path.unlink()
        
        # 출력 파일 삭제
        for file_path in OUTPUTS_DIR.glob(f"{file_id}*"):
            file_path.unlink()
        
        return {"message": "파일이 성공적으로 정리되었습니다."}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"파일 정리 중 오류: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
