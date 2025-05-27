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


def generate_srt(segments, video_resolution: str = "1080p"):
    """SRT 자막 생성 - 단어 단위 줄바꿈 지원"""
    
    # 해상도별 최적 줄 길이 설정 (A방식: 단어 단위 분할)
    line_length_configs = {
        "720p": 35,   # ~35자
        "1080p": 45,  # ~45자  
        "1440p": 55,  # ~55자
        "4k": 70      # ~70자
    }
    
    max_line_length = line_length_configs.get(video_resolution, 45)
    
    srt_content = ""
    
    for i, segment in enumerate(segments, 1):
        start_time = seconds_to_srt_time(segment["start"])
        end_time = seconds_to_srt_time(segment["end"])
        text = segment["text"].strip()
        
        # 🔤 A방식: 단어 단위 줄바꿈 적용
        formatted_text = apply_word_based_line_breaks(text, max_line_length)
        
        srt_content += f"{i}\n"
        srt_content += f"{start_time} --> {end_time}\n"
        srt_content += f"{formatted_text}\n\n"
    
    return srt_content


async def gpt_smart_line_breaks(text: str, max_line_length: int, max_lines: int = 2) -> str:
    """
    🤖 GPT 기반 의미 단위 스마트 분할
    - 자연스러운 의미 단위로 분할
    - 한국어 문법 고려 (조사, 어미 등)  
    - 균형잡힌 줄 길이
    """
    if not api_available:
        return text
    
    try:
        from openai import AsyncOpenAI
        
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return text
            
        client = AsyncOpenAI(api_key=api_key)
        
        prompt = f"""다음 한국어 텍스트를 자연스럽고 의미있는 단위로 {max_lines}줄로 나누어 주세요.

🎯 분할 조건:
- 각 줄은 최대 {max_line_length}자 이하
- 의미가 완결되는 지점에서 분할
- 너무 짧은 줄(3글자 이하) 방지
- 조사나 어미가 혼자 남지 않도록 주의
- "~을", "~를", "~에 대한", "~을 위하여" 등은 분할하지 말 것
- 균형잡힌 줄 길이로 조정

📝 텍스트: "{text}"

✅ 결과: 줄바꿈으로 구분된 텍스트만 반환 (설명 없이)"""

        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=1000
        )
        
        result = response.choices[0].message.content.strip()
        
        # 결과 검증: 줄 수 및 길이 체크
        lines = result.split('\n')
        if len(lines) <= max_lines and all(len(line) <= max_line_length + 5 for line in lines):
            print(f"🤖 GPT 스마트 분할 성공: {len(lines)}줄")
            for i, line in enumerate(lines, 1):
                print(f"   {i}줄: '{line}' (길이: {len(line)}자)")
            return result
        else:
            print(f"⚠️ GPT 결과 검증 실패 - 원본 사용")
            return text
            
    except Exception as e:
        print(f"❌ GPT 스마트 분할 오류: {str(e)} - 원본 사용")
        return text


def needs_smart_improvement(text: str, formatted_result: str, max_line_length: int) -> bool:
    """
    🔍 GPT 스마트 분할이 필요한지 판단
    - 너무 짧은 줄 (3글자 이하)
    - 불균형한 줄 길이 차이
    - 부자연스러운 분할점 ("내용을" 등)
    """
    lines = formatted_result.split('\n')
    
    # 1. 너무 짧은 줄 검사
    for line in lines:
        if len(line.strip()) <= 3 and len(line.strip()) > 0:
            print(f"🔍 개선 필요: 너무 짧은 줄 감지 - '{line.strip()}'")
            return True
    
    # 2. 줄 길이 불균형 검사 (2줄인 경우)
    if len(lines) == 2:
        line1_len = len(lines[0])
        line2_len = len(lines[1])
        if line1_len > 0 and line2_len > 0:
            length_ratio = abs(line1_len - line2_len) / max(line1_len, line2_len)
            if length_ratio > 0.7:  # 70% 이상 차이
                print(f"🔍 개선 필요: 불균형한 줄 길이 - {line1_len}자 vs {line2_len}자")
                return True
    
    # 3. 부자연스러운 분할점 검사
    problem_patterns = [
        "내용을\n", "것을\n", "을\n", "를\n", "에\n", "이\n", "가\n"
    ]
    
    for pattern in problem_patterns:
        if pattern in formatted_result:
            print(f"🔍 개선 필요: 부자연스러운 분할점 감지 - '{pattern.strip()}'")
            return True
    
    return False


def apply_word_based_line_breaks(text: str, max_line_length: int) -> str:
    """
    🔤 A방식: 단어 단위 줄바꿈 적용 (완전 개선 버전 v2.0)
    - 어절(공백) 기준으로만 분할 
    - 단어의 완전성 100% 보장
    - 최대 2줄 제한 (업계 표준)
    - 스마트한 줄 균형 맞추기
    - 단어 분할 절대 방지 시스템
    """
    if not text or len(text) <= max_line_length:
        return text
    
    # 어절(공백) 기준으로 분리
    words = text.split()
    
    if not words:
        return text
    
    # 단일 단어가 너무 긴 경우 처리
    if len(words) == 1:
        return words[0]  # 단일 단어는 절대 분할하지 않음
    
    # 🎯 스마트 2줄 분할 알고리즘
    total_length = len(text)
    target_line_length = min(max_line_length, total_length // 2 + 5)  # 균형잡힌 분할
    
    lines = []
    current_line = ""
    
    for i, word in enumerate(words):
        # 현재 줄에 단어를 추가했을 때의 길이 계산
        test_line = current_line + (" " if current_line else "") + word
        
        # 🔍 첫 번째 줄 최적화: 적절한 길이에서 자연스럽게 분할
        if len(lines) == 0:
            if len(test_line) <= target_line_length or len(test_line) <= max_line_length:
                current_line = test_line
            else:
                # 첫 번째 줄 완성 후 두 번째 줄 시작
                if current_line:
                    lines.append(current_line)
                    current_line = word
                else:
                    current_line = word  # 첫 단어 자체가 긴 경우
        
        # 🔍 두 번째 줄: 남은 모든 단어 수용 (단어 완전성 보장)
        elif len(lines) == 1:
            current_line = test_line
        
        # 🚨 2줄 제한 강제: 더 이상 줄 추가 금지
        else:
            break
    
    # 마지막 줄 추가
    if current_line:
        lines.append(current_line)
    
    # 🛡️ 단어 완전성 최종 검증
    result = "\n".join(lines)
    
    # 검증: 단어 분할 감지
    word_integrity_check = True
    split_violations = []
    
    for word in words:
        if len(word) > 2:  # 2글자 이상 단어만 검사
            # 단어가 줄 경계에서 분할되었는지 확인
            for i in range(1, len(word)):
                partial_word = word[:i]
                remaining_part = word[i:]
                if (partial_word + "\n") in result or ("\n" + remaining_part) in result:
                    word_integrity_check = False
                    split_violations.append(word)
                    break
    
    # 🎯 결과 로깅
    if len(lines) <= 2:
        print(f"✅ 단어 단위 줄바꿈 적용: {len(lines)}줄 (완전성: {'✓' if word_integrity_check else '✗'})")
        for i, line in enumerate(lines, 1):
            print(f"   {i}줄: '{line}' (길이: {len(line)}자)")
        if split_violations:
            print(f"   ⚠️ 분할 위험 단어: {split_violations}")
    else:
        print(f"⚠️ 2줄 초과: {len(lines)}줄")
    
    # 🔧 긴급 수정: 단어 분할 발생시 강제 결합
    if split_violations:
        print("🔧 단어 분할 감지 - 긴급 수정 적용")
        # 모든 텍스트를 첫 번째 줄에 결합
        result = text
    
    return result


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


def create_video_with_subtitles(audio_path: str, srt_content: str, output_path: str, background_color: str = "black", video_resolution: str = "1080p"):
    """비디오 생성 - 유튜브 최적화 다중 해상도 지원"""
    try:
        duration = get_audio_duration(audio_path)
        
        # 🎬 해상도별 설정 (자막 공간 최대 활용)
        resolution_configs = {
            "720p": {
                "size": "1280x720",
                "font_size": 18,        
                "outline": 2,           
                "margin": 30,           
                "margin_lr": 10,        # 30 → 10 (최소한의 여백)
                "description": "HD 720p"
            },
            "1080p": {
                "size": "1920x1080", 
                "font_size": 22,        
                "outline": 2,           
                "margin": 45,           
                "margin_lr": 15,        # 40 → 15 (최소한의 여백)
                "description": "Full HD 1080p (권장)"
            },
            "1440p": {
                "size": "2560x1440",
                "font_size": 28,        
                "outline": 2,           
                "margin": 60,           
                "margin_lr": 20,        # 60 → 20 (최소한의 여백)
                "description": "2K QHD"
            },
            "4k": {
                "size": "3840x2160",
                "font_size": 36,        
                "outline": 3,           
                "margin": 80,           
                "margin_lr": 30,        # 80 → 30 (최소한의 여백)
                "description": "4K UHD"
            }
        }
        
        # 선택된 해상도 설정 가져오기
        config = resolution_configs.get(video_resolution, resolution_configs["1080p"])
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.srt', delete=False, encoding='utf-8') as srt_file:
            srt_file.write(srt_content)
            srt_path = srt_file.name
        
        # 동적 자막 스타일 생성 (최대 폭 제한으로 자동 여백)
        font_style = (
            f'FontSize={config["font_size"]},'
            'PrimaryColour=&Hffffff,'   # 흰색 텍스트
            'OutlineColour=&H000000,'   # 검은색 아웃라인
            f'Outline={config["outline"]},'
            'Shadow=1,'                 # 그림자 효과
            'Alignment=2,'              # 하단 중앙 정렬
            f'MarginV={config["margin"]},'  # 하단 여백만 유지
            f'MarginL={config["margin_lr"]},'  # 좌우 여백으로 최대 폭 제한
            f'MarginR={config["margin_lr"]}'   # 자막이 이 안에서만 표시됨
        )
        
        print(f"🎬 비디오 생성: {config['description']} ({config['size']}) - 자막: {config['font_size']}px, 최대폭: {config['margin_lr']}px 여백")
        
        cmd = [
            'ffmpeg',
            '-f', 'lavfi',
            '-i', f'color=c={background_color}:s={config["size"]}:d={duration}',
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


@app.get("/video-resolutions")
async def get_video_resolutions():
    """지원하는 비디오 해상도 목록"""
    return {
        "available_resolutions": {
            "720p": {
                "size": "1280x720",
                "description": "HD 720p",
                "recommended_for": "일반 용도"
            },
            "1080p": {
                "size": "1920x1080", 
                "description": "Full HD 1080p",
                "recommended_for": "유튜브 권장 (기본값)",
                "default": True
            },
            "1440p": {
                "size": "2560x1440",
                "description": "2K QHD",
                "recommended_for": "고화질 선호"
            },
            "4k": {
                "size": "3840x2160",
                "description": "4K UHD",
                "recommended_for": "최고 화질 (용량 큼)"
            }
        },
        "default_resolution": "1080p",
        "youtube_optimized": ["1080p", "1440p", "4k"]
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
    video_resolution: str = "1080p",  # 🆕 해상도 선택 옵션
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
        print(f"🎬 {final_stage_num}단계: 비디오 생성 중... ({video_resolution})")
        srt_content = generate_srt(final_result["segments"], video_resolution)  # 해상도 매개변수 추가
        
        # 🔍 디버깅용: SRT 내용 저장
        debug_srt_path = OUTPUTS_DIR / f"{file_id}_advanced_subtitled_debug.srt"
        with open(debug_srt_path, 'w', encoding='utf-8') as f:
            f.write(srt_content)
        print(f"🔍 디버깅용 SRT 저장: {debug_srt_path}")
        
        create_video_with_subtitles(str(input_file), srt_content, str(output_file), background_color, video_resolution)
        
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
            "video_resolution": video_resolution,  # 🆕 사용된 해상도 정보
            "gpt_postprocessing_enabled": enable_gpt_postprocessing,
            "message": f"Phase 2 고급 처리로 한국어 자막 비디오가 성공적으로 생성되었습니다. ({video_resolution})"
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


@app.get("/test-smart-line-breaks")
async def test_smart_line_breaks():
    """🤖 GPT 스마트 줄바꿈 기능 테스트"""
    
    # 문제가 있는 테스트 케이스들
    problem_cases = [
        {
            "name": "핵심 문제: 내용을이 혼자 남는 경우",
            "text": "성경을 잘 알지 못하는 분들이나 예수 그리스도에 대한 믿음의 주요 내용을 더 잘 알고 싶은 분들을 위하여 성경의 줄거리와 내용을 읽기 쉽게 정리하였습니다",
            "max_length": 35,
            "expected_problem": "내용을이 혼자 한 줄에 남을 가능성"
        },
        {
            "name": "불균형한 줄 길이",
            "text": "이것은 매우 긴 텍스트로서 여러 줄로 나누어져야 하는 내용입니다만 균형을 맞추기 어렵습니다",
            "max_length": 30,
            "expected_problem": "첫 줄은 길고 둘째 줄은 짧을 가능성"
        },
        {
            "name": "조사 분리 위험",
            "text": "컨사이스 바이블은 성경 공부에 관심이 있는 분들을 위해 준비된 것을 알려드립니다",
            "max_length": 25,
            "expected_problem": "조사가 분리될 위험"
        }
    ]
    
    results = []
    
    for case in problem_cases:
        print(f"\n🧪 테스트: {case['name']}")
        print(f"📝 원본: {case['text']}")
        print(f"📏 최대 길이: {case['max_length']}자")
        
        # A방식 (기존) 적용
        basic_result = apply_word_based_line_breaks(case['text'], case['max_length'])
        
        # 문제점 감지
        needs_improvement = needs_smart_improvement(case['text'], basic_result, case['max_length'])
        
        # GPT 스마트 분할 적용 (필요시)
        smart_result = basic_result
        if needs_improvement:
            smart_result = await gpt_smart_line_breaks(case['text'], case['max_length'])
        
        basic_lines = basic_result.split('\n')
        smart_lines = smart_result.split('\n')
        
        result = {
            "test_name": case['name'],
            "original_text": case['text'],
            "expected_problem": case['expected_problem'],
            "max_length": case['max_length'],
            "basic_result": {
                "text": basic_result,
                "lines": basic_lines,
                "line_lengths": [len(line) for line in basic_lines],
                "needs_improvement": needs_improvement
            },
            "smart_result": {
                "text": smart_result,
                "lines": smart_lines,
                "line_lengths": [len(line) for line in smart_lines],
                "improved": smart_result != basic_result
            },
            "improvement_applied": smart_result != basic_result
        }
        
        results.append(result)
    
    return {
        "message": "🤖 GPT 스마트 줄바꿈 테스트 완료",
        "test_results": results,
        "summary": {
            "total_cases": len(problem_cases),
            "improved_cases": sum(1 for r in results if r['improvement_applied']),
            "gpt_available": api_available
        }
    }


@app.get("/test-line-breaks")
async def test_line_breaks():
    """단어 단위 줄바꿈 기능 테스트"""
    
    # 테스트 케이스들
    test_cases = [
        {
            "name": "기본 케이스",
            "text": "분들을 위하여 성경의 줄거리와 내용을 읽기 쉽게 정리하였습니다",
            "max_length": 35
        },
        {
            "name": "긴 텍스트",
            "text": "이것은 매우 긴 텍스트로서 여러 줄로 나누어져야 하는 내용입니다 그리고 단어의 완전성을 보장해야 합니다",
            "max_length": 40
        },
        {
            "name": "짧은 텍스트",
            "text": "짧은 텍스트",
            "max_length": 35
        },
        {
            "name": "단일 긴 단어",
            "text": "초장편대서사시급초특급전문용어",
            "max_length": 20
        }
    ]
    
    results = []
    
    for case in test_cases:
        print(f"\n🧪 테스트: {case['name']}")
        print(f"📝 원본: {case['text']}")
        print(f"📏 최대 길이: {case['max_length']}자")
        
        # 줄바꿈 적용
        formatted = apply_word_based_line_breaks(case['text'], case['max_length'])
        lines = formatted.split('\n')
        
        result = {
            "test_name": case['name'],
            "original_text": case['text'],
            "max_length": case['max_length'],
            "formatted_text": formatted,
            "line_count": len(lines),
            "lines": lines,
            "line_lengths": [len(line) for line in lines],
            "word_integrity_maintained": '위\n하여' not in formatted and '줄거\n리' not in formatted
        }
        
        results.append(result)
    
    return {
        "message": "단어 단위 줄바꿈 테스트 완료",
        "test_results": results,
        "supported_resolutions": {
            "720p": "35자 이하",
            "1080p": "45자 이하", 
            "1440p": "55자 이하",
            "4k": "70자 이하"
        }
    }
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
