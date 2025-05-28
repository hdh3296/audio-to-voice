"""
🎬 Phase 3.2.3: 트랜지션 효과 포함 템플릿 기반 비디오 배경 시스템
동적 비디오 배경 템플릿 관리 및 부드러운 루프 처리
"""

import os
import json
import math
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass


@dataclass
class TemplateInfo:
    """템플릿 정보 데이터 클래스"""
    name: str
    description: str
    category: str
    duration: Optional[float]  # 실제 비디오에서 감지된 길이
    resolution: str
    video_file: str
    preview_image: str
    created_at: str
    recommended_for: List[str]
    # 🆕 Phase 3.2.3: 트랜지션 설정
    recommended_transition: str = "crossfade"  # 기본 트랜지션
    optimal_transition_duration: float = 1.0  # 최적 트랜지션 길이 (초)


@dataclass
class TransitionConfig:
    """트랜지션 설정 데이터 클래스"""
    type: str = "crossfade"  # crossfade, fade, dissolve, wipe, none
    duration: float = 1.0    # 트랜지션 길이 (초)
    intensity: float = 0.8   # 트랜지션 강도 (0.0 ~ 1.0)
    
    def __post_init__(self):
        # 유효성 검사
        valid_types = ["crossfade", "fade", "dissolve", "wipe", "none"]
        if self.type not in valid_types:
            self.type = "crossfade"
        
        self.duration = max(0.1, min(5.0, self.duration))  # 0.1~5초 제한
        self.intensity = max(0.0, min(1.0, self.intensity))  # 0~1 제한


class TemplateManager:
    """템플릿 비디오 관리 클래스"""
    
    def __init__(self, templates_dir: str = None):
        if templates_dir is None:
            # 현재 파일 기준으로 templates 디렉토리 경로 설정
            current_dir = Path(__file__).parent
            self.templates_dir = current_dir / "templates"
        else:
            self.templates_dir = Path(templates_dir)
        
        self.config_file = self.templates_dir / "template_config.json"
        self.templates_data = self._load_templates_config()
    
    def _load_templates_config(self) -> Dict:
        """템플릿 설정 파일 로드"""
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            else:
                print(f"⚠️ 템플릿 설정 파일을 찾을 수 없음: {self.config_file}")
                return {"templates": {}, "config": {}}
        except Exception as e:
            print(f"❌ 템플릿 설정 로드 실패: {str(e)}")
            return {"templates": {}, "config": {}}
    
    def get_template_duration(self, template_name: str) -> float:
        """FFprobe로 템플릿 비디오 길이 자동 감지"""
        try:
            template_path = self.get_template_path(template_name)
            if not template_path or not os.path.exists(template_path):
                print(f"❌ 템플릿 파일을 찾을 수 없음: {template_name}")
                return 25.0  # 기본값
            
            # FFprobe로 비디오 길이 감지
            cmd = [
                'ffprobe', 
                '-v', 'quiet', 
                '-show_entries', 'format=duration',
                '-of', 'default=noprint_wrappers=1:nokey=1',
                str(template_path)
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0 and result.stdout.strip():
                duration = float(result.stdout.strip())
                print(f"🎬 템플릿 '{template_name}' 길이 감지: {duration:.2f}초")
                
                # 설정 파일의 duration 필드 업데이트
                self._update_template_duration(template_name, duration)
                
                return duration
            else:
                print(f"⚠️ FFprobe 실행 실패: {result.stderr}")
                return 25.0  # 기본값
                
        except Exception as e:
            print(f"❌ 템플릿 길이 감지 오류: {str(e)}")
            return 25.0  # 기본값
    
    def _update_template_duration(self, template_name: str, duration: float):
        """템플릿 설정의 duration 필드 업데이트"""
        try:
            if template_name in self.templates_data.get("templates", {}):
                self.templates_data["templates"][template_name]["duration"] = duration
                # 설정 파일에 저장
                with open(self.config_file, 'w', encoding='utf-8') as f:
                    json.dump(self.templates_data, f, ensure_ascii=False, indent=2)
                print(f"✅ 템플릿 '{template_name}' 길이 정보 업데이트: {duration:.2f}초")
        except Exception as e:
            print(f"⚠️ 템플릿 길이 정보 저장 실패: {str(e)}")
    
    def calculate_dynamic_loops(self, audio_duration: float, template_duration: float) -> int:
        """음성 길이에 맞는 템플릿 루프 횟수 동적 계산"""
        if template_duration <= 0:
            print(f"⚠️ 잘못된 템플릿 길이: {template_duration}")
            return 0
        
        # 필요한 총 루프 횟수 계산 (올림)
        total_loops_needed = math.ceil(audio_duration / template_duration)
        
        # FFmpeg의 -stream_loop는 추가 루프 횟수 (원본 1회 + 추가 루프)
        additional_loops = max(0, total_loops_needed - 1)
        
        print(f"🔄 루프 계산:")
        print(f"   음성 길이: {audio_duration:.2f}초")
        print(f"   템플릿 길이: {template_duration:.2f}초")  
        print(f"   필요한 총 루프: {total_loops_needed}회")
        print(f"   FFmpeg 추가 루프: {additional_loops}회")
        
        return additional_loops
    
    def get_template_path(self, template_name: str) -> Optional[str]:
        """템플릿 비디오 파일 경로 반환"""
        template_info = self.templates_data.get("templates", {}).get(template_name)
        if template_info:
            video_file = template_info.get("video_file")
            if video_file:
                template_path = self.templates_dir / video_file
                return str(template_path)
        
        print(f"⚠️ 템플릿 '{template_name}' 정보를 찾을 수 없음")
        return None
    
    def get_available_templates(self) -> List[str]:
        """사용 가능한 템플릿 목록 반환"""
        return list(self.templates_data.get("templates", {}).keys())
    
    def get_template_info(self, template_name: str) -> Optional[TemplateInfo]:
        """템플릿 상세 정보 반환"""
        template_data = self.templates_data.get("templates", {}).get(template_name)
        if template_data:
            return TemplateInfo(
                name=template_data.get("name", template_name),
                description=template_data.get("description", ""),
                category=template_data.get("category", ""),
                duration=template_data.get("duration"),
                resolution=template_data.get("resolution", "1920x1080"),
                video_file=template_data.get("video_file", ""),
                preview_image=template_data.get("preview_image", ""),
                created_at=template_data.get("created_at", ""),
                recommended_for=template_data.get("recommended_for", []),
                # 🆕 Phase 3.2.3: 트랜지션 설정
                recommended_transition=template_data.get("recommended_transition", "crossfade"),
                optimal_transition_duration=template_data.get("optimal_transition_duration", 1.0)
            )
        return None
    
    def validate_template(self, template_name: str) -> bool:
        """템플릿 파일 존재 여부 검증"""
        template_path = self.get_template_path(template_name)
        if template_path and os.path.exists(template_path):
            return True
        
        print(f"❌ 템플릿 파일이 존재하지 않음: {template_path}")
        return False


def create_seamless_looped_video(
    template_path: str,
    audio_duration: float,
    template_duration: float,
    transition_config: TransitionConfig,
    output_temp_path: str
) -> bool:
    """🆕 Phase 3.2.3: 트랜지션 효과가 있는 심리스 루프 비디오 생성"""
    
    try:
        print(f"🌟 트랜지션 효과 적용: {transition_config.type} ({transition_config.duration}초)")
        
        if transition_config.type == "none":
            # 트랜지션 없음 - 기존 방식
            return create_basic_looped_video(template_path, audio_duration, template_duration, output_temp_path)
        
        # 필요한 총 루프 횟수 계산
        total_loops_needed = math.ceil(audio_duration / template_duration)
        
        if total_loops_needed <= 1:
            # 루프가 필요없는 경우 - 기본 방식
            return create_basic_looped_video(template_path, audio_duration, template_duration, output_temp_path)
        
        # 트랜지션 타입별 처리
        if transition_config.type == "crossfade":
            return create_crossfade_loop(template_path, audio_duration, template_duration, transition_config, output_temp_path)
        elif transition_config.type == "fade":
            return create_fade_loop(template_path, audio_duration, template_duration, transition_config, output_temp_path)
        else:
            # 기본값: fade 사용 (가장 안정적)
            return create_fade_loop(template_path, audio_duration, template_duration, transition_config, output_temp_path)
            
    except Exception as e:
        print(f"❌ 트랜지션 비디오 생성 실패: {str(e)}")
        return False


def create_fade_loop(
    template_path: str,
    audio_duration: float, 
    template_duration: float,
    transition_config: TransitionConfig,
    output_temp_path: str
) -> bool:
    """Fade 트랜지션으로 루프 비디오 생성 (안정적)"""
    
    try:
        # 필요한 총 루프 횟수 계산 (오디오 길이에 맞게)
        loops_needed = math.ceil(audio_duration / template_duration)
        fade_duration = min(transition_config.duration / 2, template_duration / 8)  # 템플릿 길이의 1/8 이하
        
        print(f"🌙 Fade 트랜지션 루프 생성:")
        print(f"   필요한 루프: {loops_needed}회")
        print(f"   페이드 길이: {fade_duration:.2f}초")
        
        # 임시 파일을 사용하여 페이드 인/아웃이 적용된 단일 루프 생성
        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as temp_single_loop:
            single_loop_path = temp_single_loop.name
        
        # 1. 먼저 페이드 인/아웃이 적용된 단일 루프 생성
        filter_complex = f"fade=t=out:st={template_duration - fade_duration}:d={fade_duration},fade=t=in:st=0:d={fade_duration}"
        
        single_loop_cmd = [
            'ffmpeg',
            '-i', template_path,
            '-vf', filter_complex,
            '-c:v', 'libx264',
            '-preset', 'medium', 
            '-crf', '23',
            '-an',  # 오디오 제거
            '-y',
            single_loop_path
        ]
        
        result = subprocess.run(single_loop_cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            print(f"⚠️ 단일 루프 생성 실패: {result.stderr}")
            if os.path.exists(single_loop_path):
                os.unlink(single_loop_path)
            return create_basic_looped_video(template_path, audio_duration, template_duration, output_temp_path)
        
        # 2. 생성된 단일 루프를 여러 번 반복하여 최종 비디오 생성
        final_cmd = [
            'ffmpeg',
            '-stream_loop', str(loops_needed - 1),  # 첫 번째 루프는 이미 포함되어 있으므로 -1
            '-i', single_loop_path,
            '-t', str(audio_duration),  # 오디오 길이로 자름
            '-c:v', 'libx264',
            '-preset', 'medium', 
            '-crf', '23',
            '-an',  # 오디오 제거 (최종 비디오에서는 원본 오디오 사용)
            '-y',
            output_temp_path
        ]
        
        result = subprocess.run(final_cmd, capture_output=True, text=True)
        
        # 임시 파일 삭제
        if os.path.exists(single_loop_path):
            os.unlink(single_loop_path)
        
        if result.returncode != 0:
            print(f"⚠️ Fade 루프 생성 실패: {result.stderr}")
            return create_basic_looped_video(template_path, audio_duration, template_duration, output_temp_path)
        
        print(f"✅ Fade 루프 비디오 생성 완료")
        return True
        
    except Exception as e:
        print(f"❌ Fade 생성 오류: {str(e)}")
        return create_basic_looped_video(template_path, audio_duration, template_duration, output_temp_path)


def create_crossfade_loop(
    template_path: str,
    audio_duration: float, 
    template_duration: float,
    transition_config: TransitionConfig,
    output_temp_path: str
) -> bool:
    """Crossfade 트랜지션으로 루프 비디오 생성 (고급)"""
    
    try:
        # Crossfade는 복잡하므로 일단 fade로 대체 (안정성 우선)
        print(f"🔄 Crossfade 요청 → Fade로 대체 (안정성 우선)")
        return create_fade_loop(template_path, audio_duration, template_duration, transition_config, output_temp_path)
        
    except Exception as e:
        print(f"❌ Crossfade 생성 오류: {str(e)}")
        return create_basic_looped_video(template_path, audio_duration, template_duration, output_temp_path)


def create_basic_looped_video(template_path: str, audio_duration: float, template_duration: float, output_temp_path: str) -> bool:
    """기본 루프 비디오 생성 (트랜지션 없음)"""
    try:
        # 필요한 총 루프 횟수 계산 (오디오 길이에 맞게)
        loops_needed = math.ceil(audio_duration / template_duration)
        
        print(f"🔄 기본 루프 비디오 생성:")
        print(f"   필요한 루프: {loops_needed}회")
        print(f"   템플릿 길이: {template_duration:.2f}초")
        print(f"   오디오 길이: {audio_duration:.2f}초")
        
        # 두 단계로 나누어 처리
        # 1. 먼저 템플릿을 복사하여 준비
        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as temp_single_loop:
            single_loop_path = temp_single_loop.name
        
        # 템플릿 복사 (트랜지션 없이)
        copy_cmd = [
            'ffmpeg',
            '-i', template_path,
            '-c:v', 'libx264',
            '-preset', 'medium',
            '-crf', '23',
            '-an',  # 오디오 제거
            '-y',
            single_loop_path
        ]
        
        result = subprocess.run(copy_cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            print(f"⚠️ 템플릿 복사 실패: {result.stderr}")
            if os.path.exists(single_loop_path):
                os.unlink(single_loop_path)
            return False
        
        # 2. 복사된 템플릿을 여러 번 반복하여 최종 비디오 생성
        loop_cmd = [
            'ffmpeg',
            '-stream_loop', str(loops_needed - 1),  # 첫 번째 루프는 이미 포함되어 있으므로 -1
            '-i', single_loop_path,
            '-t', str(audio_duration),  # 오디오 길이로 자름
            '-c:v', 'libx264',
            '-preset', 'medium',
            '-crf', '23',
            '-an',  # 오디오 제거 (최종 비디오에서는 원본 오디오 사용)
            '-y',
            output_temp_path
        ]
        
        result = subprocess.run(loop_cmd, capture_output=True, text=True)
        
        # 임시 파일 삭제
        if os.path.exists(single_loop_path):
            os.unlink(single_loop_path)
            
        if result.returncode != 0:
            print(f"⚠️ 루프 비디오 생성 실패: {result.stderr}")
            return False
            
        print(f"✅ 기본 루프 비디오 생성 완료")
        return True
        
    except Exception as e:
        print(f"❌ 기본 루프 생성 오류: {str(e)}")
        return False


def create_looped_template_video(
    audio_path: str,
    template_name: str,
    output_path: str,
    ass_content: str,
    video_resolution: str = "1080p",
    template_manager: TemplateManager = None,
    transition_config: TransitionConfig = None  # 🆕 Phase 3.2.3: 트랜지션 설정
) -> bool:
    """🆕 Phase 3.2.3: 트랜지션 효과가 포함된 템플릿 기반 루프 비디오 + 자막 생성"""
    
    if template_manager is None:
        template_manager = TemplateManager()
    
    try:
        # 1. 템플릿 검증
        if not template_manager.validate_template(template_name):
            raise Exception(f"템플릿 '{template_name}'을 사용할 수 없습니다")
        
        # 2. 음성 길이 가져오기
        audio_duration = get_audio_duration(audio_path)
        if audio_duration <= 0:
            raise Exception(f"음성 파일 길이를 확인할 수 없습니다: {audio_path}")
        
        # 3. 템플릿 정보 및 길이 감지
        template_duration = template_manager.get_template_duration(template_name)
        template_path = template_manager.get_template_path(template_name)
        template_info = template_manager.get_template_info(template_name)
        
        # 4. 🆕 트랜지션 설정 결정
        if transition_config is None:
            # 템플릿 기본 설정 사용
            if template_info:
                transition_config = TransitionConfig(
                    type=template_info.recommended_transition,
                    duration=template_info.optimal_transition_duration
                )
            else:
                transition_config = TransitionConfig()  # 기본값 사용
        
        # 5. 해상도 설정
        resolution_configs = {
            "720p": {"size": "1280x720"},
            "1080p": {"size": "1920x1080"},
            "1440p": {"size": "2560x1440"},
            "4k": {"size": "3840x2160"}
        }
        
        config = resolution_configs.get(video_resolution, resolution_configs["1080p"])
        
        print(f"🎬 트랜지션 템플릿 비디오 생성:")
        print(f"   템플릿: {template_name}")
        print(f"   해상도: {config['size']}")
        print(f"   음성 길이: {audio_duration:.2f}초")
        print(f"   템플릿 길이: {template_duration:.2f}초")
        print(f"   트랜지션: {transition_config.type} ({transition_config.duration:.1f}초)")
        
        # 6. 🆕 트랜지션 효과가 있는 루프 비디오 생성
        temp_video_path = None
        
        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as temp_video_file:
            temp_video_path = temp_video_file.name
        
        # 트랜지션 비디오 생성
        if not create_seamless_looped_video(
            template_path, audio_duration, template_duration, 
            transition_config, temp_video_path
        ):
            raise Exception("트랜지션 비디오 생성 실패")
        
        # 7. ASS 파일 임시 저장
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ass', delete=False, encoding='utf-8') as ass_file:
            ass_file.write(ass_content)
            ass_path = ass_file.name
        
        # 8. 최종 비디오 생성 (트랜지션 비디오 + 음성 + 자막)
        cmd = [
            'ffmpeg',
            '-i', temp_video_path,                  # 트랜지션 처리된 비디오
            '-i', audio_path,                       # 음성 파일
            '-vf', f'ass={ass_path},scale={config["size"]}',  # 자막 + 해상도 조정
            '-c:v', 'libx264',
            '-preset', 'medium',
            '-crf', '23',
            '-c:a', 'aac',
            '-b:a', '128k',
            '-map', '0:v',                          # 첫 번째 입력에서 비디오 스트림 사용
            '-map', '1:a',                          # 두 번째 입력에서 오디오 스트림 사용
            '-t', str(audio_duration),              # 음성 길이로 자름
            '-shortest',
            '-y',
            output_path
        ]
        
        # 9. FFmpeg 실행
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        # 10. 임시 파일 정리
        if temp_video_path and os.path.exists(temp_video_path):
            os.unlink(temp_video_path)
        if ass_path and os.path.exists(ass_path):
            os.unlink(ass_path)
        
        if result.returncode != 0:
            raise Exception(f"최종 비디오 생성 실패: {result.stderr}")
        
        print(f"✅ 트랜지션 템플릿 비디오 생성 완료: {output_path}")
        return True
        
    except Exception as e:
        # 임시 파일 정리
        if 'temp_video_path' in locals() and temp_video_path and os.path.exists(temp_video_path):
            os.unlink(temp_video_path)
        if 'ass_path' in locals() and ass_path and os.path.exists(ass_path):
            os.unlink(ass_path)
        
        print(f"❌ 트랜지션 템플릿 비디오 생성 실패: {str(e)}")
        return False


def get_audio_duration(audio_path: str) -> float:
    """오디오 길이 구하기"""
    try:
        cmd = [
            'ffprobe', 
            '-v', 'quiet', 
            '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            audio_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0 and result.stdout.strip():
            return float(result.stdout.strip())
        else:
            print(f"⚠️ 음성 길이 감지 실패: {result.stderr}")
            return 60.0  # 기본값
            
    except Exception as e:
        print(f"❌ 음성 길이 감지 오류: {str(e)}")
        return 60.0  # 기본값


# 전역 템플릿 매니저 인스턴스
template_manager = TemplateManager()


if __name__ == "__main__":
    # 🧪 Phase 3.2.3 트랜지션 테스트
    print("🧪 Phase 3.2.3 트랜지션 템플릿 매니저 테스트")
    
    # 사용 가능한 템플릿 목록
    templates = template_manager.get_available_templates()
    print(f"📋 사용 가능한 템플릿: {templates}")
    
    # 트랜지션 설정 테스트
    transition_configs = [
        TransitionConfig(type="fade", duration=1.0),
        TransitionConfig(type="crossfade", duration=1.5),
        TransitionConfig(type="none", duration=0.0)
    ]
    
    for config in transition_configs:
        print(f"🌟 트랜지션 테스트: {config.type} ({config.duration}초)")
