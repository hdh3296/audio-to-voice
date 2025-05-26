# 🎵 Audio-to-Voice

**m1guelpf/auto-subtitle**를 기반으로 한 오디오 파일을 자막 비디오로 변환하는 웹 애플리케이션입니다.

## ✨ 주요 기능

- 🎧 **다양한 오디오 형식 지원**: MP3, WAV, M4A, AAC, FLAC, OGG
- 🤖 **OpenAI Whisper**: 정확한 음성 인식
- 🎬 **자막 비디오 생성**: FFmpeg를 통한 고품질 비디오 생성
- 🌐 **직관적인 웹 UI**: 드래그 앤 드롭 인터페이스
- ⚙️ **다양한 설정 옵션**: 모델 크기, 언어, 배경색 등

## 🛠 기술 스택

### 백엔드
- **Python** + **FastAPI**
- **Faster-Whisper** (고성능 음성 인식)
- **FFmpeg** (비디오 처리)

### 프론트엔드
- **Next.js 14** + **TypeScript**
- **Tailwind CSS** (스타일링)
- **Lucide React** (아이콘)

## 🚀 빠른 시작

### 1. 의존성 설치

#### 백엔드 설정
```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

#### 프론트엔드 설정
```bash
cd frontend
npm install
```

#### FFmpeg 설치 (필수)
```bash
# macOS
brew install ffmpeg

# Ubuntu/Debian
sudo apt update && sudo apt install ffmpeg

# Windows (Chocolatey)
choco install ffmpeg
```

### 2. 실행

#### 방법 1: 자동 실행 스크립트 (권장)
```bash
./start.sh
```

#### 방법 2: 수동 실행
**터미널 1 (백엔드):**
```bash
cd backend
source venv/bin/activate
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

**터미널 2 (프론트엔드):**
```bash
cd frontend
npm run dev
```

### 3. 접속
- **프론트엔드**: http://localhost:3000
- **백엔드 API**: http://localhost:8000
- **API 문서**: http://localhost:8000/docs

## 📱 사용법

1. **오디오 파일 업로드**: 드래그 앤 드롭 또는 클릭하여 파일 선택
2. **옵션 설정**: 모델 크기, 언어, 작업 유형, 배경색 선택
3. **비디오 생성**: '자막 비디오 생성' 버튼 클릭
4. **다운로드**: 생성 완료 후 비디오 파일 다운로드

## ⚙️ 설정 옵션

### 모델 크기
- **Tiny**: 가장 빠른 처리 (낮은 정확도)
- **Small**: 권장 설정 (균형)
- **Large**: 가장 정확 (느린 처리)

### 작업 유형
- **전사 (transcribe)**: 원본 언어 그대로 자막 생성
- **번역 (translate)**: 영어로 번역하여 자막 생성

### 배경색
- 검정, 흰색, 파랑, 빨강 중 선택

## 🔗 API 엔드포인트

- `POST /upload-audio`: 오디오 파일 업로드
- `POST /generate-subtitles/{file_id}`: 자막 비디오 생성
- `GET /download/{filename}`: 파일 다운로드
- `GET /status/{file_id}`: 처리 상태 확인
- `DELETE /cleanup/{file_id}`: 임시 파일 정리

## 📂 프로젝트 구조

```
audio-to-voice/
├── backend/           # FastAPI 서버
│   ├── main.py       # 메인 API 서버
│   ├── auto_subtitle/ # 자막 생성 모듈
│   ├── venv/         # Python 가상환경
│   └── requirements.txt
├── frontend/          # Next.js 앱
│   ├── src/
│   │   └── app/
│   │       └── page.tsx
│   └── package.json
├── uploads/           # 업로드된 파일
├── outputs/           # 생성된 비디오
├── docs/             # 문서
├── LICENSE           # MIT 라이센스
├── start.sh          # 자동 실행 스크립트
└── README.md         # 프로젝트 설명서
```

## 🎯 주요 특징

### 🔐 보안
- CORS 설정으로 프론트엔드만 접근 허용
- 파일 형식 검증
- 임시 파일 자동 정리

### 🚀 성능
- Faster-Whisper로 빠른 음성 인식
- 비동기 처리로 빠른 응답
- 백그라운드 작업 처리
- 효율적인 메모리 관리

### 🎨 사용자 경험
- 직관적인 드래그 앤 드롭 인터페이스
- 실시간 상태 표시
- 상세한 에러 메시지
- 반응형 디자인

## 🙏 크레딧 및 라이센스

### 영감을 받은 프로젝트
이 프로젝트는 [m1guelpf/auto-subtitle](https://github.com/m1guelpf/auto-subtitle)에서 영감을 받아 개발되었습니다.
- **원본 아이디어**: 오디오를 자막 비디오로 변환
- **우리의 구현**: 웹 기반 애플리케이션으로 확장 및 UI/UX 개선

### 사용된 오픈소스 라이브러리
- **[OpenAI Whisper](https://github.com/openai/whisper)**: 음성 인식 (MIT License)
- **[Faster-Whisper](https://github.com/guillaumekln/faster-whisper)**: 고성능 Whisper 구현 (MIT License)
- **[FFmpeg](https://ffmpeg.org/)**: 비디오 처리 (LGPL/GPL)
- **[Next.js](https://nextjs.org/)**: 프론트엔드 프레임워크 (MIT License)
- **[FastAPI](https://fastapi.tiangolo.com/)**: 백엔드 API 프레임워크 (MIT License)

### 라이센스
이 프로젝트는 **MIT License** 하에 배포됩니다. 자세한 내용은 [LICENSE](LICENSE) 파일을 참조하세요.

```
MIT License - Copyright (c) 2025 동훈 (밭가는개발자)
```

---

**만든이**: 밭가는개발자 (동훈)  
**블로그**: 밭가는개발자 블로그  
**유튜브**: 밭가는개발자의 코드농장  
**브랜드**: 밭간 (batgan.com)

## 📧 문의 및 지원

프로젝트에 대한 문의사항이나 버그 리포트는 GitHub Issues를 이용해주세요.
