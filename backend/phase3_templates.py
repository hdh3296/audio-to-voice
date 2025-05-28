"""
🎬 Phase 3.2: 템플릿 기반 비디오 배경 시스템
동적 비디오 배경 템플릿 관리 및 루프 처리
"""

import os
import json
import math
import subprocess
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
                recommended_for=template_data.get("recommended_for", [])
            )
        return None
    
    def validate_template(self, template_name: str) -> bool:
        """템플릿 파일 존재 여부 검증"""
        template_path = self.get_template_path(template_name)
        if template_path and os.path.exists(template_path):
            return True
        
        print(f"❌ 템플릿 파일이 존재하지 않음: {template_path}")
        return False


def create_looped_template_video(
    audio_path: str,
    template_name: str,
    output_path: str,
    ass_content: str,
    video_resolution: str = "1080p",
    template_manager: TemplateManager = None
) -> bool:
    """템플릿 기반 루프 비디오 + 자막 생성"""
    
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
        
        # 3. 템플릿 길이 감지
        template_duration = template_manager.get_template_duration(template_name)
        template_path = template_manager.get_template_path(template_name)
        
        # 4. 루프 횟수 계산
        additional_loops = template_manager.calculate_dynamic_loops(audio_duration, template_duration)
        
        # 5. 해상도 설정
        resolution_configs = {
            "720p": {"size": "1280x720"},
            "1080p": {"size": "1920x1080"},
            "1440p": {"size": "2560x1440"},
            "4k": {"size": "3840x2160"}
        }
        
        config = resolution_configs.get(video_resolution, resolution_configs["1080p"])
        
        # 6. ASS 파일 임시 저장
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ass', delete=False, encoding='utf-8') as ass_file:
            ass_file.write(ass_content)
            ass_path = ass_file.name
        
        print(f"🎬 템플릿 기반 비디오 생성:")
        print(f"   템플릿: {template_name}")
        print(f"   해상도: {config['size']}")
        print(f"   음성 길이: {audio_duration:.2f}초")
        print(f"   템플릿 길이: {template_duration:.2f}초")
        print(f"   추가 루프: {additional_loops}회")
        
        # 7. FFmpeg 명령어 구성 (템플릿 비디오 오디오 제거, 원본 음성만 사용)
        cmd = [
            'ffmpeg',
            '-stream_loop', str(additional_loops),  # 템플릿 루프
            '-i', template_path,                    # 템플릿 비디오
            '-i', audio_path,                       # 음성 파일
            '-map', '0:v',                          # 템플릿의 비디오만 사용
            '-map', '1:a',                          # 원본 음성만 사용
            '-vf', f'ass={ass_path},scale={config["size"]}',  # 자막 + 해상도 조정
            '-c:v', 'libx264',
            '-preset', 'medium',
            '-crf', '23',
            '-c:a', 'aac',
            '-b:a', '128k',
            '-t', str(audio_duration),              # 음성 길이로 자름
            '-shortest',
            '-y',
            output_path
        ]
        
        # 8. FFmpeg 실행
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        # 9. 임시 ASS 파일 삭제
        os.unlink(ass_path)
        
        if result.returncode != 0:
            raise Exception(f"FFmpeg 오류: {result.stderr}")
        
        print(f"✅ 템플릿 기반 비디오 생성 완료: {output_path}")
        return True
        
    except Exception as e:
        # 임시 파일 정리
        if 'ass_path' in locals() and os.path.exists(ass_path):
            os.unlink(ass_path)
        
        print(f"❌ 템플릿 비디오 생성 실패: {str(e)}")
        return False


def get_audio_duration(audio_path: str) -> float:
    """오디오 길이 구하기 (기존 함수와 동일)"""
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
    # 테스트 코드
    print("🧪 템플릿 매니저 테스트")
    
    # 사용 가능한 템플릿 목록
    templates = template_manager.get_available_templates()
    print(f"📋 사용 가능한 템플릿: {templates}")
    
    # 첫 번째 템플릿 정보
    if templates:
        template_name = templates[0]
        info = template_manager.get_template_info(template_name)
        print(f"🎬 템플릿 정보: {info}")
        
        # 길이 감지 테스트 (실제 파일이 있을 때)
        duration = template_manager.get_template_duration(template_name)
        print(f"⏱️ 템플릿 길이: {duration}초")
        
        # 루프 계산 테스트
        loops = template_manager.calculate_dynamic_loops(90.0, duration)
        print(f"🔄 90초 음성에 필요한 추가 루프: {loops}회")
