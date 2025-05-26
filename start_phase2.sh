#!/bin/bash

# 🚀 Phase 2 Audio-to-Voice 시작 스크립트
# 차세대 한국어 음성 인식 시스템

echo "🚀 Phase 2: 차세대 Audio-to-Voice 시스템 시작"
echo "================================================"

# 환경 변수 확인
if [ ! -f .env ]; then
    echo "❌ .env 파일이 없습니다. .env.example을 복사하여 설정해주세요."
    exit 1
fi

# OpenAI API 키 확인
if ! grep -q "OPENAI_API_KEY=" .env || grep -q "your_openai_api_key_here" .env; then
    echo "⚠️  OpenAI API 키가 설정되지 않았습니다."
    echo "   Phase 2 기능을 사용하려면 .env 파일에 실제 API 키를 설정해주세요."
    echo "   로컬 모드만 사용할 경우 계속 진행할 수 있습니다."
    read -p "   계속하시겠습니까? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# 백엔드 가상환경 확인 및 설치
echo "🔧 백엔드 환경 설정 중..."
cd backend

if [ ! -d "venv" ]; then
    echo "📦 Python 가상환경 생성 중..."
    python3 -m venv venv
fi

echo "🔌 가상환경 활성화..."
source venv/bin/activate

# Phase 2 패키지 설치
echo "📥 Phase 2 패키지 설치 중..."
pip install -r requirements_phase2.txt

# 백엔드 서버 시작 (Phase 2)
echo "🚀 Phase 2 백엔드 서버 시작 (포트: 8002)..."
python main_phase2.py &
BACKEND_PID=$!

cd ..

# 프론트엔드 설정 및 시작
echo "🎨 프론트엔드 환경 설정 중..."
cd frontend

# 필요 패키지 설치 확인
if [ ! -d "node_modules" ]; then
    echo "📦 프론트엔드 패키지 설치 중..."
    npm install
fi

# 프론트엔드 서버 시작
echo "🚀 프론트엔드 서버 시작 (포트: 3000)..."
npm run dev &
FRONTEND_PID=$!

cd ..

# 서버 정보 출력
echo ""
echo "🎉 Phase 2 시스템이 성공적으로 시작되었습니다!"
echo "================================================"
echo "🌐 웹 인터페이스:"
echo "   • 기존 버전: http://localhost:3000"
echo "   • Phase 2:   http://localhost:3000/phase2"
echo ""
echo "🔧 API 서버:"
echo "   • 기존 API:  http://localhost:8000"
echo "   • Phase 2:   http://localhost:8002"
echo ""
echo "🆕 Phase 2 새로운 기능:"
echo "   ⚡ 실시간 스트리밍 처리"
echo "   🤖 차세대 AI 모델 (Whisper-1 최적화)"
echo "   🔍 지능형 품질 검증"
echo "   🔄 자동 재처리 시스템"
echo "   📡 WebSocket 실시간 업데이트"
echo ""
echo "⏹️  종료하려면 Ctrl+C를 누르세요"

# 종료 시그널 처리
cleanup() {
    echo ""
    echo "🛑 서버 종료 중..."
    kill $BACKEND_PID 2>/dev/null
    kill $FRONTEND_PID 2>/dev/null
    echo "✅ 모든 서버가 종료되었습니다."
    exit 0
}

trap cleanup SIGINT SIGTERM

# 서버 실행 상태 유지
wait