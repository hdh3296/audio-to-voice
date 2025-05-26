# OpenAI Whisper API 통합 계획서

## 🎯 목표
로컬 Faster-Whisper와 OpenAI Whisper API를 모두 지원하는 하이브리드 시스템 구축

## 📋 상세 구현 계획

### 1️⃣ 백엔드 API 확장
- **새로운 의존성 추가**
  ```bash
  pip install openai python-dotenv
  ```

- **환경변수 설정**
  ```bash
  # .env 파일
  OPENAI_API_KEY=your_api_key_here
  USE_OPENAI_API=false  # 기본값: 로컬 사용
  ```

- **하이브리드 서비스 클래스**
  ```python
  class WhisperService:
      def __init__(self):
          self.local_whisper = FasterWhisperService()
          self.api_whisper = OpenAIWhisperService()
      
      def transcribe(self, audio_path, use_api=False):
          if use_api and self.api_available():
              return self.api_whisper.transcribe(audio_path)
          else:
              return self.local_whisper.transcribe(audio_path)
  ```

### 2️⃣ OpenAI API 서비스 구현
- **API 클라이언트 초기화**
- **음성 파일 전송 및 결과 수신**
- **에러 처리 (API 한도, 네트워크 오류 등)**
- **재시도 로직 (exponential backoff)**

### 3️⃣ 프론트엔드 UI 확장
- **모드 선택 토글**
  - 로컬 모드 (무료, 느림)
  - API 모드 (유료, 빠름)
- **비용 정보 표시**
- **처리 시간 비교**

### 4️⃣ 보안 및 설정
- **API 키 보안 관리**
- **사용량 제한 설정**
- **비용 모니터링**

### 5️⃣ 성능 모니터링
- **처리 시간 측정**
- **정확도 비교**
- **비용 추적**

## 🔄 구현 순서
1. 환경 설정 (.env, requirements.txt)
2. OpenAI API 서비스 클래스 구현
3. 하이브리드 서비스 통합
4. 백엔드 API 엔드포인트 수정
5. 프론트엔드 UI 확장
6. 테스트 및 성능 비교
7. 문서화 및 배포

## 📊 예상 결과
- **속도**: API 모드에서 2-5배 빠른 처리
- **선택권**: 사용자가 비용/속도 트레이드오프 선택
- **안정성**: API 실패시 로컬로 자동 전환
- **확장성**: 대용량 처리 가능

## 💰 비용 계산
- OpenAI Whisper API: $0.006 per minute
- 1분 오디오 = 약 7원
- 10분 오디오 = 약 70원
- 사용자가 비용/속도 선택 가능

## 🔒 보안 고려사항
- API 키는 환경변수로만 관리
- .env 파일은 .gitignore에 포함
- 프론트엔드에서 API 키 노출 방지
- 사용량 제한으로 비용 제어
