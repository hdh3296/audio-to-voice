"""
자막 싱크 확인 도구
생성된 SRT 파일의 타임스탬프를 검증합니다.
"""
import sys
import os
import re

def parse_srt_time(time_str):
    """SRT 시간 문자열을 초로 변환"""
    # 00:00:05,500 형식을 초로 변환
    match = re.match(r'(\d{2}):(\d{2}):(\d{2}),(\d{3})', time_str)
    if match:
        hours, minutes, seconds, milliseconds = map(int, match.groups())
        total_seconds = hours * 3600 + minutes * 60 + seconds + milliseconds / 1000
        return total_seconds
    return 0

def analyze_srt_file(srt_path):
    """SRT 파일 분석"""
    if not os.path.exists(srt_path):
        print(f"❌ SRT 파일을 찾을 수 없습니다: {srt_path}")
        return
    
    print(f"📄 SRT 파일 분석: {srt_path}")
    
    with open(srt_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 타임스탬프 패턴 추출
    timestamp_pattern = r'(\d{2}:\d{2}:\d{2},\d{3}) --> (\d{2}:\d{2}:\d{2},\d{3})'
    timestamps = re.findall(timestamp_pattern, content)
    
    print(f"📊 발견된 자막 구간: {len(timestamps)}개")
    
    total_duration = 0
    for i, (start, end) in enumerate(timestamps[:5]):  # 처음 5개만 표시
        start_sec = parse_srt_time(start)
        end_sec = parse_srt_time(end)
        duration = end_sec - start_sec
        total_duration = max(total_duration, end_sec)
        
        print(f"  {i+1}: {start} → {end} (길이: {duration:.1f}초)")
    
    print(f"📏 전체 예상 길이: {total_duration:.1f}초")
    
    if len(timestamps) > 5:
        print(f"... (나머지 {len(timestamps) - 5}개 구간)")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        analyze_srt_file(sys.argv[1])
    else:
        print("사용법: python analyze_srt.py <srt_파일_경로>")
