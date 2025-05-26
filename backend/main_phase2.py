"""
🚀 Phase 2: 차세대 Audio-to-Voice API 서버
- 새로운 OpenAI 모델 지원 (whisper-1 최적화)
- 실시간 스트리밍 처리
- 지능형 품질 검증 및 자동 재처리
- WebSocket 실시간 업데이트
"""

from fastapi import FastAPI, File, UploadFile, HTTPException, WebSocket, WebSocketDisconnect
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
from typing import Optional, Dict, List
import asyncio
from datetime import datetime
import json
from dotenv import load_dotenv

# Phase 2 모듈 임포트
from phase2_models import Phase2ModelManager, TranscriptionResult
from phase2_streaming import StreamingTranscriber, StreamingProgress
from phase2_quality import QualityAnalyzer, AutoReprocessor
from phase2_postprocessing import Phase2PostProcessor

# 환경변수 로드
load_dotenv()

app = FastAPI(
    title="Audio to Voice API - Phase 2", 
    version="3.0.0",
    description="차세대 한국어 음성 인식 시스템 - 실시간 스트리밍 & 지능형 품질 검증"
)

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

# 전역 매니저들
model_manager: Optional[Phase2ModelManager] = None
streaming_transcriber: Optional[StreamingTranscriber] = None
quality_analyzer: Optional[QualityAnalyzer] = None
auto_reprocessor: Optional[AutoReprocessor] = None
postprocessor: Optional[Phase2PostProcessor] = None
api_available = False

# WebSocket 연결 관리
websocket_connections: Dict[str, WebSocket] = {}


def init_phase2_systems():
    """Phase 2 시스템 초기화"""
    global model_manager, streaming_transcriber, quality_analyzer, auto_reprocessor, postprocessor, api_available
    
    api_key = os.getenv("OPENAI_API_KEY")
    if api_key and api_key != "your_openai_api_key_here":
        print("🚀 Phase 2 시스템 초기화 중...")
        
        try:
            # 모델 매니저 초기화
            model_manager = Phase2ModelManager(api_key)
            print("✅ Phase 2 모델 매니저 초기화 완료")
            
            # 스트리밍 전사기 초기화
            streaming_transcriber = StreamingTranscriber(model_manager, chunk_duration=30.0)
            print("✅ 스트리밍 전사기 초기화 완료")
            
            # 품질 분석기 초기화
            quality_analyzer = QualityAnalyzer()
            print("✅ 품질 분석기 초기화 완료")
            
            # 자동 재처리기 초기화
            auto_reprocessor = AutoReprocessor(model_manager, quality_analyzer)
            print("✅ 자동 재처리기 초기화 완료")
            
            # GPT 후처리기 초기화
            postprocessor = Phase2PostProcessor(api_key)
            print("✅ GPT 후처리기 초기화 완료")
            
            api_available = True
            print("🎉 Phase 2 시스템 초기화 성공!")
            
        except Exception as e:
            print(f"❌ Phase 2 시스템 초기화 실패: {str(e)}")
            api_available = False
    else:
        print("⚠️ OpenAI API 키가 설정되지 않음 - Phase 2 기능 사용 불가")


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
init_phase2_systems()


@app.get("/")
async def root():
    return {
        "message": "Audio to Voice API - Phase 2", 
        "status": "running", 
        "version": "3.0.0",
        "features": {
            "streaming": "실시간 스트리밍 처리",
            "quality_analysis": "지능형 품질 검증",
            "auto_reprocessing": "자동 재처리",
            "advanced_models": "차세대 AI 모델"
        },
        "models": {
            "whisper-1-standard": "Whisper-1 표준 설정",
            "whisper-1-optimized": "Whisper-1 최적화 설정",
            "whisper-1-creative": "Whisper-1 창의적 설정"
        },
        "api_status": "Available" if api_available else "Requires API key"
    }


@app.get("/health")
async def health_check():
    return {
        "status": "healthy", 
        "timestamp": datetime.now().isoformat(),
        "phase2_systems": {
            "model_manager": model_manager is not None,
            "streaming_transcriber": streaming_transcriber is not None,
            "quality_analyzer": quality_analyzer is not None,
            "auto_reprocessor": auto_reprocessor is not None,
            "gpt_postprocessor": postprocessor is not None and postprocessor.is_available()
        }
    }


@app.get("/api-status")
async def api_status():
    """Phase 2 API 상태 확인"""
    return {
        "phase2_available": api_available,
        "systems_ready": {
            "model_manager": model_manager is not None,
            "streaming": streaming_transcriber is not None,
            "quality_analysis": quality_analyzer is not None,
            "auto_reprocessing": auto_reprocessor is not None,
            "gpt_postprocessing": postprocessor is not None and postprocessor.is_available()
        },
        "supported_models": list(model_manager.AVAILABLE_MODELS.keys()) if model_manager else [],
        "features": [
            "실시간 스트리밍 처리",
            "지능형 품질 검증", 
            "자동 재처리",
            "차세대 AI 모델",
            "GPT 후처리 교정",
            "WebSocket 실시간 업데이트"
        ]
    }


@app.get("/models")
async def get_available_models():
    """사용 가능한 모델 목록"""
    if not model_manager:
        raise HTTPException(status_code=503, detail="Model manager not available")
    
    models_info = {}
    for model_name, info in model_manager.AVAILABLE_MODELS.items():
        models_info[model_name] = {
            **info,
            "recommended_for": model_manager.get_recommendation(60, "balanced") == model_name
        }
    
    return {
        "available_models": models_info,
        "total_count": len(models_info)
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
        
        # 오디오 정보 분석
        duration = get_audio_duration(str(file_path))
        
        # 추천 모델 계산
        recommended_model = None
        if model_manager:
            recommended_model = model_manager.get_recommendation(duration, "balanced")
        
        return {
            "file_id": file_id,
            "filename": filename,
            "original_name": file.filename,
            "size": file_path.stat().st_size,
            "duration": duration,
            "recommended_model": recommended_model,
            "message": "파일이 성공적으로 업로드되었습니다."
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"파일 업로드 중 오류: {str(e)}")


@app.post("/generate-subtitles-advanced/{file_id}")
async def generate_subtitles_advanced(
    file_id: str,
    model: str = "whisper-1-optimized",
    language: str = "ko",
    background_color: str = "black",
    enable_quality_analysis: bool = True,
    enable_auto_reprocessing: bool = True,
    enable_gpt_postprocessing: bool = True,  # 🆕 GPT 후처리 기본값을 True로 변경 (테스트용)
    target_quality: float = 0.8
):
    """고급 자막 생성 (품질 분석 + 자동 재처리 + GPT 후처리)"""
    if not api_available:
        raise HTTPException(status_code=503, detail="Phase 2 features not available")
    
    try:
        # 🔍 디버깅용 로그 추가
        print(f"🔍 [DEBUG] GPT 후처리 옵션 확인:")
        print(f"   enable_gpt_postprocessing: {enable_gpt_postprocessing}")
        print(f"   postprocessor 존재: {postprocessor is not None}")
        print(f"   postprocessor 사용가능: {postprocessor.is_available() if postprocessor else 'N/A'}")
        
        uploaded_files = list(UPLOADS_DIR.glob(f"{file_id}.*"))
        if not uploaded_files:
            raise HTTPException(status_code=404, detail="업로드된 파일을 찾을 수 없습니다.")
        
        input_file = uploaded_files[0]
        output_file = OUTPUTS_DIR / f"{file_id}_advanced_subtitled.mp4"
        
        processing_stages = []
        gpt_suffix = " + GPT교정" if enable_gpt_postprocessing else ""
        print(f"🚀 고급 자막 생성 시작: {model} 모델{gpt_suffix}")
        
        # 1단계: 초기 전사
        print("📝 1단계: 초기 전사 중...")
        processing_stages.append("초기 전사")
        result = await model_manager.transcribe_with_model(
            str(input_file), model, language, include_quality_metrics=True
        )
        
        if not result.success:
            raise HTTPException(status_code=500, detail=result.error)
        
        initial_result = {
            "text": result.text,
            "segments": result.segments,
            "processing_time": result.processing_time,
            "model_used": result.model_used,
            "confidence_score": result.confidence_score
        }
        
        # 2단계: 품질 분석
        quality_metrics = None
        if enable_quality_analysis and quality_analyzer:
            print("🔍 2단계: 품질 분석 중...")
            processing_stages.append("품질 분석")
            quality_metrics = await quality_analyzer.analyze_transcription_quality(
                result.text, result.segments, result.processing_time, result.model_used
            )
            print(f"📊 품질 점수: {quality_metrics.overall_score:.3f}")
        
        # 3단계: 자동 재처리 (필요시)
        final_result = initial_result
        if enable_auto_reprocessing and auto_reprocessor and quality_metrics:
            if quality_metrics.needs_reprocessing and quality_metrics.overall_score < target_quality:
                print("🔄 3단계: 자동 재처리 중...")
                processing_stages.append("자동 재처리")
                final_result = await auto_reprocessor.auto_reprocess_if_needed(
                    str(input_file), initial_result, target_quality
                )
        
        # 🆕 4단계: GPT 후처리 (선택적) - 강제 활성화
        postprocessing_result = None
        print(f"🔍 [DEBUG] GPT 후처리 단계 진입:")
        print(f"   enable_gpt_postprocessing: {enable_gpt_postprocessing}")
        print(f"   postprocessor: {postprocessor is not None}")
        print(f"   postprocessor.is_available(): {postprocessor.is_available() if postprocessor else False}")
        
        # 🚨 임시: 항상 GPT 후처리 실행 (테스트용)
        force_gpt_processing = True
        
        if (enable_gpt_postprocessing or force_gpt_processing) and postprocessor and postprocessor.is_available():
            print("🤖 4단계: GPT 후처리 시작! (강제 활성화)")
            processing_stages.append("GPT 후처리")
            
            # 원본 텍스트 로그
            print(f"📝 [DEBUG] 원본 세그먼트 ({len(final_result['segments'])}개):")
            for i, seg in enumerate(final_result["segments"][:3]):  # 처음 3개만 로그
                print(f"   {i+1}: {seg.get('text', '')}")
            
            # 품질 분석 결과를 GPT 후처리에 전달
            postprocessing_result = await postprocessor.process_with_progress(
                segments=final_result["segments"],
                quality_metrics=quality_metrics.__dict__ if hasattr(quality_metrics, '__dict__') else None
            )
            
            print(f"🔍 [DEBUG] GPT 후처리 결과:")
            print(f"   success: {postprocessing_result['success']}")
            print(f"   correction_applied: {postprocessing_result.get('correction_applied', False)}")
            print(f"   total_corrections: {postprocessing_result.get('total_corrections', 0)}")
            
            if postprocessing_result["success"] and postprocessing_result["correction_applied"]:
                # 교정된 텍스트 로그
                print(f"📝 [DEBUG] 교정된 세그먼트:")
                for i, seg in enumerate(postprocessing_result["corrected_segments"][:3]):  # 처음 3개만 로그
                    print(f"   {i+1}: {seg.get('text', '')}")
                
                # GPT 교정된 세그먼트로 업데이트
                final_result["segments"] = postprocessing_result["corrected_segments"]
                final_result["text"] = " ".join([seg["text"] for seg in postprocessing_result["corrected_segments"]])
                final_result["gpt_correction_applied"] = True
                final_result["total_corrections"] = postprocessing_result["total_corrections"]
                final_result["correction_strategy"] = postprocessing_result["correction_strategy"]
                final_result["gpt_quality_score"] = postprocessing_result["final_quality_score"]
                final_result["gpt_improvements"] = postprocessing_result["improvement_details"]
                
                print(f"✅ GPT 교정 완료: {postprocessing_result['total_corrections']}개 항목 수정")
                print(f"🔍 [DEBUG] 업데이트된 최종 텍스트: {final_result['text'][:100]}...")
            else:
                print("ℹ️ GPT 교정이 적용되지 않았거나 실패했습니다")
                if not postprocessing_result["success"]:
                    print(f"   오류: {postprocessing_result.get('error', 'Unknown error')}")
                final_result["gpt_correction_applied"] = False
        else:
            print("⏭️ GPT 후처리 건너뜀")
            if not enable_gpt_postprocessing and not force_gpt_processing:
                print("   이유: 사용자가 GPT 후처리를 비활성화함")
            elif not postprocessor:
                print("   이유: GPT 후처리기가 초기화되지 않음")
            elif not postprocessor.is_available():
                print("   이유: GPT 후처리기 사용 불가 (API 키 확인 필요)")
        
        # 최종 단계: 비디오 생성
        final_stage_num = len(processing_stages) + 1
        print(f"🎬 {final_stage_num}단계: 비디오 생성 중...")
        srt_content = generate_srt(final_result["segments"])
        create_video_with_subtitles(str(input_file), srt_content, str(output_file), background_color)
        
        # 응답 데이터 구성
        response_data = {
            "file_id": file_id,
            "output_file": f"{file_id}_advanced_subtitled.mp4",
            "download_url": f"/download/{file_id}_advanced_subtitled.mp4",
            "transcript": final_result["text"],
            "segments_count": len(final_result["segments"]),
            "language": language,
            "processing_method": "phase2_advanced",
            "processing_stages": processing_stages,
            "model_used": final_result.get("model_used", model),
            "reprocessed": final_result.get("reprocessed", False),
            "reprocess_attempts": final_result.get("total_reprocess_attempts", 0),
            "quality_metrics": final_result.get("quality_metrics"),
            "processing_time": final_result.get("processing_time", 0),
            "gpt_postprocessing_enabled": enable_gpt_postprocessing,
            "message": f"Phase 2 고급 처리로 한국어 자막 비디오가 성공적으로 생성되었습니다."
        }
        
        # GPT 후처리 결과 추가
        if postprocessing_result:
            response_data.update({
                "gpt_correction_applied": final_result.get("gpt_correction_applied", False),
                "total_corrections": final_result.get("total_corrections", 0),
                "correction_strategy": final_result.get("correction_strategy", ""),
                "gpt_quality_score": final_result.get("gpt_quality_score", 0),
                "gpt_improvements": final_result.get("gpt_improvements", []),
                "gpt_processing_time": postprocessing_result.get("processing_time", 0)
            })
        
        print(f"🔍 [DEBUG] 최종 응답 데이터:")
        print(f"   gpt_postprocessing_enabled: {response_data['gpt_postprocessing_enabled']}")
        print(f"   gpt_correction_applied: {response_data.get('gpt_correction_applied', 'N/A')}")
        print(f"   total_corrections: {response_data.get('total_corrections', 'N/A')}")
        
        return response_data
    
    except Exception as e:
        print(f"❌ 고급 자막 생성 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=f"고급 자막 생성 중 오류: {str(e)}")



    """품질 분석 전용 엔드포인트"""
    if not quality_analyzer or not model_manager:
        raise HTTPException(status_code=503, detail="Quality analysis not available")
    
    try:
        uploaded_files = list(UPLOADS_DIR.glob(f"{file_id}.*"))
        if not uploaded_files:
            raise HTTPException(status_code=404, detail="업로드된 파일을 찾을 수 없습니다.")
        
        input_file = uploaded_files[0]
        
        # 전사 실행
        result = await model_manager.transcribe_with_model(
            str(input_file), model, language, include_quality_metrics=True
        )
        
        if not result.success:
            raise HTTPException(status_code=500, detail=result.error)
        
        # 품질 분석
        quality_metrics = await quality_analyzer.analyze_transcription_quality(
            result.text, result.segments, result.processing_time, result.model_used
        )
        
        return {
            "file_id": file_id,
            "transcript": result.text,
            "model_used": result.model_used,
            "processing_time": result.processing_time,
            "quality_analysis": {
                "overall_score": quality_metrics.overall_score,
                "confidence_score": quality_metrics.confidence_score,
                "korean_quality_score": quality_metrics.korean_quality_score,
                "grammar_score": quality_metrics.grammar_score,
                "consistency_score": quality_metrics.consistency_score,
                "completeness_score": quality_metrics.completeness_score,
                "needs_reprocessing": quality_metrics.needs_reprocessing,
                "recommended_model": quality_metrics.recommended_model,
                "improvement_suggestions": quality_metrics.improvement_suggestions,
                "detailed_metrics": {
                    "word_count": quality_metrics.word_count,
                    "korean_word_ratio": quality_metrics.korean_word_ratio,
                    "punctuation_ratio": quality_metrics.punctuation_ratio,
                    "low_confidence_segments": quality_metrics.low_confidence_segments
                }
            }
        }
    
    except Exception as e:
        print(f"❌ 품질 분석 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=f"품질 분석 중 오류: {str(e)}")


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
    output_files = list(OUTPUTS_DIR.glob(f"{file_id}*"))
    
    status = "unknown"
    if not input_files:
        status = "not_found"
    elif output_files:
        status = "completed"
    else:
        status = "processing"
    
    return {
        "file_id": file_id,
        "status": status,
        "has_input": bool(input_files),
        "output_files": [f.name for f in output_files]
    }


@app.delete("/cleanup/{file_id}")
async def cleanup_files(file_id: str):
    """파일 정리"""
    try:
        cleaned_files = []
        
        # 업로드 파일 정리
        for file_path in UPLOADS_DIR.glob(f"{file_id}.*"):
            file_path.unlink()
            cleaned_files.append(f"uploads/{file_path.name}")
        
        # 출력 파일 정리
        for file_path in OUTPUTS_DIR.glob(f"{file_id}*"):
            file_path.unlink()
            cleaned_files.append(f"outputs/{file_path.name}")
        
        return {
            "message": "파일이 성공적으로 정리되었습니다.",
            "cleaned_files": cleaned_files
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"파일 정리 중 오류: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    print("🚀 Phase 2 Audio-to-Voice API 서버 시작!")
    print("🆕 새로운 기능들:")
    print("  🤖 차세대 AI 모델 (Whisper-1 최적화)")
    print("  ⚡ 실시간 스트리밍 처리")
    print("  🔍 지능형 품질 검증")
    print("  🔄 자동 재처리 시스템")
    print("  📡 WebSocket 실시간 업데이트")
    print(f"🌐 API 상태: {'사용 가능' if api_available else 'API 키 필요'}")
    uvicorn.run(app, host="0.0.0.0", port=8002)
