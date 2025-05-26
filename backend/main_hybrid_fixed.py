from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import os
import sys
import shutil
import subprocess
import tempfile
from pathlib import Path
import uuid
from typing import Optional
import asyncio
from datetime import datetime
import hashlib
from dotenv import load_dotenv
from openai import OpenAI
from faster_whisper import WhisperModel

# 환경변수 로드
load_dotenv()

app = FastAPI(title="Audio to Voice API (Hybrid)", version="2.0.0")

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
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

# 전역 변수들
local_model = None
openai_client = None
api_available = False

def init_openai_client():
    """OpenAI 클라이언트 초기화"""
    global openai_client, api_available
    
    api_key = os.getenv("OPENAI_API_KEY")
    if api_key and api_key != "your_openai_api_key_here":
        openai_client = OpenAI(api_key=api_key)
        api_available = True
        print("✅ OpenAI API 클라이언트 초기화 완료")
    else:
        print("⚠️ OpenAI API 키가 설정되지 않음 - 로컬 모드만 사용 가능")

def load_local_model(model_name: str = "large-v3"):
    """로컬 Whisper 모델 로드"""
    global local_model
    
    if local_model is None:
        print(f"📥 로컬 Whisper 모델 로드 중: {model_name}")
        try:
            local_model = WhisperModel(model_name, device="cpu", compute_type="int8")
            print(f"✅ 로컬 모델 로드 완료: {model_name}")
        except Exception as e:
            print(f"❌ {model_name} 모델 로드 실패: {e}")
            if model_name == "large-v3":
                local_model = WhisperModel("medium", device="cpu", compute_type="int8")
                print("✅ medium 모델로 대체 완료")
            else:
                raise e
    
    return local_model

async def transcribe_with_stable_api(audio_path: str, language: str = "ko"):
    """안정화된 OpenAI API 전사"""
    if not api_available or not openai_client:
        return {"success": False, "error": "API 사용 불가능"}
    
    try:
        # 상세한 한국어 프롬프트
        prompt = """다음은 한국어 음성입니다. 정확한 한국어 표준어로 전사해주세요. 
문장 부호는 자연스럽게 사용하고, 띄어쓰기는 한국어 맞춤법에 맞게 해주세요. 
브랜드명이나 고유명사는 정확하게 표기해주세요."""
        
        def _api_call():
            with open(audio_path, "rb") as audio_file:
                return openai_client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    language=language,
                    response_format="verbose_json",
                    timestamp_granularities=["segment"],
                    prompt=prompt,
                    temperature=0.0  # 안정성을 위해 0
                )
        
        result = await asyncio.to_thread(_api_call)
        
        segments = []
        if result.segments:
            for segment in result.segments:
                segments.append({
                    "start": segment.start,
                    "end": segment.end,
                    "text": segment.text.strip()
                })
        
        return {
            "success": True,
            "text": result.text.strip(),
            "segments": segments,
            "language": getattr(result, 'language', language),
            "processing_method": "openai_api_stable"
        }
        
    except Exception as e:
        return {"success": False, "error": str(e), "processing_method": "openai_api_stable"}

async def transcribe_local(audio_path: str, language: str = "ko"):
    """로컬 Whisper 전사"""
    try:
        model = load_local_model()
        
        korean_prompt = "안녕하세요. 다음은 한국어 음성입니다. 정확한 문장 부호와 자연스러운 띄어쓰기를 포함해 주세요."
        
        def _transcribe():
            segments, info = model.transcribe(
                audio_path, 
                language=language,
                task="transcribe",
                initial_prompt=korean_prompt,
                beam_size=5,
                temperature=0.0
            )
            
            segments_list = []
            full_text = ""
            
            for segment in segments:
                text = segment.text.strip()
                if text:
                    segments_list.append({
                        "start": segment.start,
                        "end": segment.end,
                        "text": text
                    })
                    full_text += text + " "
            
            return {
                "success": True,
                "text": full_text.strip(),
                "segments": segments_list,
                "language": info.language,
                "processing_method": "local_whisper"
            }
        
        return await asyncio.to_thread(_transcribe)
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "processing_method": "local_whisper"
        }

def generate_srt(segments):
    """SRT 자막 생성"""
    srt_content = ""
    
    for i, segment in enumerate(segments, 1):
        start_time = seconds_to_srt_time(segment["start"])
        end_time = seconds_to_srt_time(segment["end"])
        text = segment["text"].strip()
        
        srt_content += f"{i}\n"
        srt_content += f"{start_time} --> {end_time}\n"
        srt_content += f"{text}\n\n"
    
    return srt_content

def seconds_to_srt_time(seconds: float) -> str:
    """초를 SRT 시간 형식으로 변환"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millisecs = int((seconds % 1) * 1000)
    
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millisecs:03d}"

def get_audio_duration(audio_path: str) -> float:
    """오디오 길이 구하기"""
    try:
        import ffmpeg
        probe = ffmpeg.probe(audio_path)
        duration = float(probe['streams'][0]['duration'])
        return duration
    except:
        return 60.0

def create_video_with_subtitles(audio_path: str, srt_content: str, output_path: str, background_color: str = "black"):
    """비디오 생성"""
    try:
        duration = get_audio_duration(audio_path)
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.srt', delete=False, encoding='utf-8') as srt_file:
            srt_file.write(srt_content)
            srt_path = srt_file.name
        
        font_style = (
            'FontSize=28,'
            'PrimaryColour=&Hffffff,'
            'OutlineColour=&H000000,'
            'Outline=3,'
            'Shadow=1,'
            'Alignment=2,'
            'MarginV=50'
        )
        
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
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            raise Exception(f"FFmpeg 오류: {result.stderr}")
        
        os.unlink(srt_path)
        
    except Exception as e:
        if 'srt_path' in locals() and os.path.exists(srt_path):
            os.unlink(srt_path)
        raise Exception(f"비디오 생성 실패: {str(e)}")

# 서버 시작시 초기화
init_openai_client()

@app.get("/")
async def root():
    return {
        "message": "Audio to Voice API (Hybrid)", 
        "status": "running", 
        "version": "2.0.0",
        "modes": {
            "local": "Always available",
            "api": "Available" if api_available else "Requires API key"
        }
    }

@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

@app.get("/api-status")
async def api_status():
    """OpenAI API 상태 확인"""
    return {
        "openai_api_available": api_available,
        "max_audio_length_minutes": 10,
        "api_configured": api_available
    }

@app.post("/upload-audio")
async def upload_audio(file: UploadFile = File(...)):
    """오디오 파일 업로드"""
    try:
        file_extension = Path(file.filename).suffix.lower()
        if file_extension not in SUPPORTED_AUDIO_FORMATS:
            raise HTTPException(
                status_code=400, 
                detail=f"지원하지 않는 파일 형식입니다. 지원 형식: {', '.join(SUPPORTED_AUDIO_FORMATS)}"
            )
        
        file_id = str(uuid.uuid4())
        filename = f"{file_id}{file_extension}"
        file_path = UPLOADS_DIR / filename
        
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
        raise HTTPException(status_code=500, detail=f"파일 업로드 중 오류: {str(e)}")

@app.post("/generate-subtitles/{file_id}")
async def generate_subtitles(
    file_id: str,
    model: str = "large-v3",
    language: Optional[str] = "ko",
    task: str = "transcribe",
    background_color: str = "black",
    use_api: bool = False
):
    """하이브리드 자막 생성"""
    try:
        uploaded_files = list(UPLOADS_DIR.glob(f"{file_id}.*"))
        if not uploaded_files:
            raise HTTPException(status_code=404, detail="업로드된 파일을 찾을 수 없습니다.")
        
        input_file = uploaded_files[0]
        output_file = OUTPUTS_DIR / f"{file_id}_subtitled.mp4"
        
        mode_text = "안정화 API" if use_api else "로컬"
        print(f"🎯 {mode_text} 모드로 음성 처리 시작")
        
        # 하이브리드 처리
        if use_api and api_available:
            print("🌐 안정화 API 모드 시도...")
            result = await transcribe_with_stable_api(str(input_file), language)
            
            if not result.get("success"):
                print(f"⚠️ API 모드 실패, 로컬 모드로 대체: {result.get('error')}")
                result = await transcribe_local(str(input_file), language)
        else:
            print("🏠 로컬 모드로 처리...")
            result = await transcribe_local(str(input_file), language)
        
        if not result.get("success"):
            raise HTTPException(status_code=500, detail=result.get("error"))
        
        # SRT 생성 및 비디오 생성
        srt_content = generate_srt(result["segments"])
        create_video_with_subtitles(str(input_file), srt_content, str(output_file), background_color)
        
        return {
            "file_id": file_id,
            "output_file": f"{file_id}_subtitled.mp4",
            "download_url": f"/download/{file_id}_subtitled.mp4",
            "transcript": result["text"],
            "segments_count": len(result["segments"]),
            "language": result.get("language", language),
            "processing_method": result.get("processing_method", "unknown"),
            "use_api_mode": use_api,
            "message": f"{mode_text} 모드로 한국어 자막 비디오가 성공적으로 생성되었습니다."
        }
    
    except Exception as e:
        print(f"❌ 자막 생성 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=f"자막 생성 중 오류: {str(e)}")

@app.get("/download/{filename}")
async def download_file(filename: str):
    """파일 다운로드"""
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
    """파일 정리"""
    try:
        for file_path in UPLOADS_DIR.glob(f"{file_id}.*"):
            file_path.unlink()
        
        for file_path in OUTPUTS_DIR.glob(f"{file_id}*"):
            file_path.unlink()
        
        return {"message": "파일이 성공적으로 정리되었습니다."}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"파일 정리 중 오류: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    print("🚀 하이브리드 Audio-to-Voice API 서버 시작!")
    print("🏠 로컬 모드: Faster-Whisper (항상 사용 가능)")
    print(f"🌐 API 모드: 안정화된 OpenAI Whisper API ({'사용 가능' if api_available else 'API 키 필요'})")
    uvicorn.run(app, host="0.0.0.0", port=8000)
