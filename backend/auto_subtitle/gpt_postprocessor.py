"""
GPT 후처리 모듈 - 한국어 오타 및 맞춤법 교정
Whisper 전사 결과를 GPT-4로 후처리하여 정확도 향상
"""
import asyncio
import os
from typing import Dict, List, Optional
from openai import AsyncOpenAI
from dotenv import load_dotenv
import logging

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class GPTPostProcessor:
    def __init__(self):
        load_dotenv()
        self.api_key = os.getenv('OPENAI_API_KEY')
        self.client = None
        self.is_enabled = False
        
        if self.api_key:
            try:
                self.client = AsyncOpenAI(api_key=self.api_key)
                self.is_enabled = True
                logger.info("✅ GPT 후처리 모듈 초기화 완료")
            except Exception as e:
                logger.error(f"❌ GPT 후처리 모듈 초기화 실패: {e}")
                self.is_enabled = False
        else:
            logger.warning("⚠️ OPENAI_API_KEY가 설정되지 않아 GPT 후처리를 사용할 수 없습니다")
    
    def is_available(self) -> bool:
        """GPT 후처리 사용 가능 여부 확인"""
        return self.is_enabled and self.client is not None
    
    def get_korean_correction_prompt(self, context: str = "") -> str:
        """한국어 특화 오타 수정 시스템 프롬프트"""
        base_prompt = """당신은 한국어 전문 교정자입니다. 음성 인식 결과의 오타와 맞춤법을 교정해주세요.

**교정 원칙:**
1. **음성학적 오류 수정**: 비슷하게 들리는 단어들의 잘못된 변환 교정
   - 예: "계시다" → "가시다", "되요" → "돼요", "안되" → "안 돼"

2. **띄어쓰기 정규화**: 자연스러운 한국어 띄어쓰기 적용
   - 예: "할수있다" → "할 수 있다", "그런데" → "그런데" (유지)

3. **맞춤법 교정**: 표준 한국어 맞춤법 준수
   - 예: "웬지" → "왠지", "되" vs "돼" 구분, "던" vs "든" 구분

4. **문장 부호 최적화**: 자연스러운 문장 구조로 개선
   - 쉼표, 마침표 적절히 배치
   - 의문문, 감탄문 부호 정확히 사용

5. **전문용어 표준화**: 일반적인 용어로 통일
   - 외래어 표기법 준수
   - 브랜드명이나 고유명사는 원래 형태 유지

**중요 규칙:**
- 원본의 의미를 절대 변경하지 마세요
- 말하는 이의 어조와 문체를 유지하세요  
- 과도한 수정보다는 자연스러운 개선에 집중하세요
- 확실하지 않은 경우 원본을 유지하세요

**출력 형식:**
- 교정된 텍스트만 출력하세요
- 추가 설명이나 주석은 포함하지 마세요
- 원본과 동일한 문단 구조를 유지하세요"""

        if context:
            base_prompt += f"\n\n**맥락 정보:** {context}"
        
        return base_prompt
    
    async def correct_text(
        self, 
        text: str, 
        context: str = "",
        temperature: float = 0.1
    ) -> Dict:
        """단일 텍스트 교정"""
        if not self.is_available():
            return {
                "success": False,
                "error": "GPT 후처리를 사용할 수 없습니다. API 키를 확인해주세요.",
                "original_text": text
            }
        
        try:
            logger.info(f"🔄 GPT로 텍스트 교정 중... (길이: {len(text)}자)")
            
            system_prompt = self.get_korean_correction_prompt(context)
            
            response = await self.client.chat.completions.create(
                model="gpt-4o-mini",  # 비용 효율적인 모델 사용
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"다음 텍스트를 교정해주세요:\n\n{text}"}
                ],
                temperature=temperature,
                max_tokens=2000,
                timeout=30.0
            )
            
            corrected_text = response.choices[0].message.content.strip()
            
            # 간단한 품질 체크
            if len(corrected_text) < len(text) * 0.5:
                logger.warning("⚠️ 교정된 텍스트가 너무 짧습니다. 원본을 유지합니다.")
                return {
                    "success": True,
                    "corrected_text": text,
                    "original_text": text,
                    "correction_applied": False,
                    "reason": "교정 결과가 너무 짧아 원본 유지"
                }
            
            logger.info("✅ GPT 텍스트 교정 완료")
            return {
                "success": True,
                "corrected_text": corrected_text,
                "original_text": text,
                "correction_applied": corrected_text != text
            }
            
        except Exception as e:
            logger.error(f"❌ GPT 텍스트 교정 실패: {e}")
            return {
                "success": False,
                "error": str(e),
                "original_text": text,
                "corrected_text": text  # 실패시 원본 유지
            }
    
    async def correct_segments(
        self, 
        segments: List[Dict], 
        context: str = ""
    ) -> Dict:
        """세그먼트별 텍스트 교정 (배치 처리)"""
        if not self.is_available():
            return {
                "success": False,
                "error": "GPT 후처리를 사용할 수 없습니다.",
                "original_segments": segments
            }
        
        if not segments:
            return {
                "success": True,
                "corrected_segments": [],
                "original_segments": [],
                "total_corrections": 0
            }
        
        try:
            logger.info(f"🔄 {len(segments)}개 세그먼트 일괄 교정 중...")
            
            # 전체 텍스트 결합
            full_text = " ".join([seg.get("text", "") for seg in segments])
            
            # 텍스트가 너무 길면 청크 단위로 처리
            if len(full_text) > 3000:
                return await self._correct_segments_chunked(segments, context)
            
            # 전체 텍스트 일괄 교정
            correction_result = await self.correct_text(full_text, context)
            
            if not correction_result["success"]:
                return {
                    "success": False,
                    "error": correction_result["error"],
                    "original_segments": segments
                }
            
            corrected_full_text = correction_result["corrected_text"]
            
            # 교정된 텍스트를 세그먼트에 재분배
            corrected_segments = self._redistribute_text_to_segments(
                segments, corrected_full_text
            )
            
            total_corrections = sum(
                1 for i, seg in enumerate(corrected_segments) 
                if i < len(segments) and seg["text"] != segments[i].get("text", "")
            )
            
            logger.info(f"✅ 세그먼트 교정 완료: {total_corrections}개 수정됨")
            
            return {
                "success": True,
                "corrected_segments": corrected_segments,
                "original_segments": segments,
                "total_corrections": total_corrections,
                "correction_applied": correction_result["correction_applied"]
            }
            
        except Exception as e:
            logger.error(f"❌ 세그먼트 교정 실패: {e}")
            return {
                "success": False,
                "error": str(e),
                "original_segments": segments,
                "corrected_segments": segments  # 실패시 원본 유지
            }
    
    async def _correct_segments_chunked(
        self, 
        segments: List[Dict], 
        context: str = ""
    ) -> Dict:
        """긴 텍스트를 청크 단위로 나누어 교정"""
        logger.info("📦 긴 텍스트를 청크 단위로 처리 중...")
        
        chunk_size = 10  # 세그먼트 기준
        chunks = [segments[i:i+chunk_size] for i in range(0, len(segments), chunk_size)]
        
        corrected_chunks = []
        total_corrections = 0
        
        for i, chunk in enumerate(chunks):
            logger.info(f"🔄 청크 {i+1}/{len(chunks)} 처리 중...")
            
            chunk_text = " ".join([seg.get("text", "") for seg in chunk])
            correction_result = await self.correct_text(chunk_text, context)
            
            if correction_result["success"]:
                corrected_text = correction_result["corrected_text"]
                corrected_chunk = self._redistribute_text_to_segments(chunk, corrected_text)
                corrected_chunks.extend(corrected_chunk)
                
                if correction_result["correction_applied"]:
                    total_corrections += 1
            else:
                # 실패시 원본 유지
                corrected_chunks.extend(chunk)
            
            # API 제한 방지용 짧은 대기
            await asyncio.sleep(0.1)
        
        logger.info(f"✅ 청크 처리 완료: {total_corrections}개 청크 수정됨")
        
        return {
            "success": True,
            "corrected_segments": corrected_chunks,
            "original_segments": segments,
            "total_corrections": total_corrections
        }
    
    def _redistribute_text_to_segments(
        self, 
        original_segments: List[Dict], 
        corrected_text: str
    ) -> List[Dict]:
        """교정된 전체 텍스트를 원본 세그먼트 구조에 맞게 재분배"""
        if not original_segments:
            return []
        
        # 교정된 텍스트를 문장 단위로 분할
        corrected_sentences = self._split_into_sentences(corrected_text)
        
        # 원본 세그먼트 수와 맞춰서 재분배
        corrected_segments = []
        sentence_idx = 0
        
        for i, original_seg in enumerate(original_segments):
            if sentence_idx < len(corrected_sentences):
                corrected_seg = {
                    "start": original_seg.get("start", 0),
                    "end": original_seg.get("end", 0),
                    "text": corrected_sentences[sentence_idx].strip()
                }
                sentence_idx += 1
            else:
                # 문장이 부족하면 원본 유지
                corrected_seg = original_seg.copy()
            
            corrected_segments.append(corrected_seg)
        
        return corrected_segments
    
    def _split_into_sentences(self, text: str) -> List[str]:
        """텍스트를 자연스러운 문장 단위로 분할"""
        import re
        
        # 한국어 문장 분할 패턴
        sentence_endings = r'[.!?]\s+'
        sentences = re.split(sentence_endings, text.strip())
        
        # 빈 문장 제거
        sentences = [s.strip() for s in sentences if s.strip()]
        
        return sentences

# 전역 인스턴스
gpt_postprocessor = GPTPostProcessor()
