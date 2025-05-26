#!/usr/bin/env python3
"""
로컬 Faster-Whisper 테스트 스크립트
pydub 없이 직접 테스트
"""
import os
import sys
import subprocess
from pathlib import Path

# 현재 디렉토리를 Python 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from faster_whisper import WhisperModel

def test_local_whisper(audio_file_path: str):
    """로컬 Faster-Whisper 직접 테스트"""
    
    # 파일 존재 확인
    if not os.path.exists(audio_file_path):
        print(f"❌ 오디오 파일을 찾을 수 없습니다: {audio_file_path}")
        return False
    
    file_size = os.path.getsize(audio_file_path)
    print(f"📁 파일 정보: {os.path.basename(audio_file_path)} ({file_size/1024:.1f}KB)")
    
    try:
        print("📥 Faster-Whisper 모델 로드 중: large-v3")
        
        # CPU 모드로 안전하게 로드
        model = WhisperModel(
            "large-v3", 
            device="cpu", 
            compute_type="int8"
        )
        print("✅ 모델 로드 완료")
        
        # 한국어 최적화 프롬프트
        korean_prompt = "안녕하세요. 다음은 한국어 음성입니다. 정확한 문장 부호와 자연스러운 띄어쓰기를 포함해 주세요."
        
        print("🎯 한국어 음성 인식 시작...")
        
        segments, info = model.transcribe(
            audio_file_path, 
            language="ko",
            task="transcribe",
            word_timestamps=True,
            initial_prompt=korean_prompt,
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
        
        print("✅ 로컬 음성 인식 완료!")
        print(f"🌐 감지된 언어: {info.language} (확률: {info.language_probability:.2f})")
        print(f"📝 전사 텍스트: {full_text.strip()}")
        print(f"📊 세그먼트 수: {len(segments_list)}")
        
        # 세그먼트 정보 출력 (처음 3개만)
        if segments_list:
            print("\n📋 세그먼트 미리보기 (처음 3개):")
            for i, segment in enumerate(segments_list[:3]):
                start_time = f"{int(segment['start']//60)}:{int(segment['start']%60):02d}"
                end_time = f"{int(segment['end']//60)}:{int(segment['end']%60):02d}"
                print(f"  {i+1}. [{start_time}-{end_time}] {segment['text']}")
        
        return True
        
    except Exception as e:
        print(f"❌ 로컬 전사 실패: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("사용법: python test_local_whisper.py <audio_file_path>")
        sys.exit(1)
    
    audio_path = sys.argv[1]
    print("🏠 로컬 Faster-Whisper 테스트 시작")
    print("="*50)
    
    success = test_local_whisper(audio_path)
    
    print("="*50)
    if success:
        print("🎉 테스트 성공!")
    else:
        print("💥 테스트 실패!")
