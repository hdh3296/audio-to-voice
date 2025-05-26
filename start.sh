#!/bin/bash

echo "🚀 Audio-to-Voice 프로젝트 시작!"
echo ""

# 가상환경 활성화 후 백엔드 실행 (백그라운드)
echo "📡 백엔드 서버 시작 중..."
cd backend
source venv/bin/activate && python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!
echo "백엔드 PID: $BACKEND_PID"

# 잠시 대기
sleep 3

# 프론트엔드 실행
echo "🌐 프론트엔드 서버 시작 중..."
cd ../frontend
npm run dev &
FRONTEND_PID=$!
echo "프론트엔드 PID: $FRONTEND_PID"

echo ""
echo "✅ 서버들이 시작되었습니다!"
echo "백엔드: http://localhost:8000"
echo "프론트엔드: http://localhost:3000"
echo "API 문서: http://localhost:8000/docs"
echo ""
echo "종료하려면 Ctrl+C를 누르세요."

# 종료 시그널 처리
trap 'echo ""; echo "🛑 서버들을 종료하는 중..."; kill $BACKEND_PID $FRONTEND_PID; exit' INT

# 무한 대기
wait
