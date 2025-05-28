#!/bin/bash

echo "🔄 Phase 2 서버 재시작 스크립트"
echo "================================"

# 1. 기존 서버 강제 종료
echo "🛑 기존 서버 종료 중..."
pkill -f "main_phase2.py" 2>/dev/null || echo "   기존 서버가 실행중이 아님"
sleep 1

# 2. 포트 8002 사용 중인 프로세스 확인 및 종료
PORT_PID=$(lsof -ti:8002 2>/dev/null)
if [ ! -z "$PORT_PID" ]; then
    echo "🔌 포트 8002 사용 중인 프로세스 종료: $PORT_PID"
    kill -9 $PORT_PID 2>/dev/null
    sleep 1
fi

# 3. 디렉토리 이동 및 가상환경 활성화
cd "$(dirname "$0")/backend"
if [ ! -d "venv" ]; then
    echo "❌ 가상환경을 찾을 수 없습니다. start_phase2.sh를 먼저 실행해주세요."
    exit 1
fi

echo "🚀 새 서버 시작 중..."
source venv/bin/activate

# 4. 서버 백그라운드 실행
nohup python main_phase2.py > ../server_phase2.log 2>&1 &
SERVER_PID=$!

# 5. 서버 시작 대기 (스마트 대기)
echo "⏳ 서버 준비 중..."
for i in {1..15}; do
    sleep 1
    if curl -s "http://localhost:8002/health" >/dev/null 2>&1; then
        echo "✅ 서버가 성공적으로 시작되었습니다! (${i}초 소요)"
        echo "🌐 서버 주소: http://localhost:8002"
        echo "📋 PID: $SERVER_PID"
        echo "📄 로그: tail -f server_phase2.log"
        exit 0
    fi
    printf "."
done

echo ""
echo "❌ 서버 시작 시간 초과 (15초)"
echo "📄 최근 로그:"
tail -10 ../server_phase2.log
exit 1
