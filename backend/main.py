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
from auto_subtitle import auto_subtitle

app = FastAPI(title="Audio to Voice API", version="1.0.0")

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Next.js 개발 서버
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
    model: str = "small",
    language: Optional[str] = None,
    task: str = "transcribe",
    background_color: str = "black"
):
    """자막 생성 및 비디오 생성 (업데이트된 버전)"""
    try:
        # 업로드된 파일 찾기
        uploaded_files = list(UPLOADS_DIR.glob(f"{file_id}.*"))
        if not uploaded_files:
            raise HTTPException(status_code=404, detail="업로드된 파일을 찾을 수 없습니다.")
        
        input_file = uploaded_files[0]
        output_file = OUTPUTS_DIR / f"{file_id}_subtitled.mp4"
        
        # auto_subtitle를 사용하여 비디오 생성
        result = auto_subtitle.process_audio_to_video(
            audio_path=str(input_file),
            output_path=str(output_file),
            model_name=model,
            language=language,
            task=task,
            background_color=background_color
        )
        
        if not result["success"]:
            raise HTTPException(status_code=500, detail=result["error"])
        
        return {
            "file_id": file_id,
            "output_file": f"{file_id}_subtitled.mp4",
            "download_url": f"/download/{file_id}_subtitled.mp4",
            "transcript": result["transcript"],
            "segments_count": result["segments_count"],
            "language": result["language"],
            "message": "자막 비디오가 성공적으로 생성되었습니다."
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"자막 생성 중 오류: {str(e)}")

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
