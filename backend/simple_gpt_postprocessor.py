"""
간단한 GPT 후처리 모듈 (의존성 최소화)
"""
import asyncio
import os
from typing import Dict, List
from openai import AsyncOpenAI
from dotenv import load_dotenv
import logging

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SimpleGPTPostProcessor:
    def __init__(self):
        load_dotenv()
        self.api_key = os.getenv('OPENAI_API_KEY')
        self.client = None
        self.is_enabled = False
        
        if self.api_key and self.api_key != "your_openai_api_key_here":
            try:
                self.client = AsyncOpenAI(api_key=self.api_key)
                self.is_enabled = True
                logger.info("✅ 간단한 GPT 후처리 모듈 초기화 완료")
            except Exception as e:
                logger.error(f"❌ GPT 후처리 모듈 초기화 실패: {e}")
                self.is_enabled = False
        else:
            logger.warning("⚠️ OPENAI_API_KEY가 설정되지 않아 GPT 후처리를 사용할 수 없습니다")
    
    def is_available(self) -> bool:
        """GPT 후처리 사용 가능 여부 확인"""
        return self.is_enabled and self.client is not None
    
    async def correct_text(self, text: str) -> Dict:
        """단일 텍스트 교정"""
        if not self.is_available():
            return {
                "success": False,
                "error": "GPT 후처리를 사용할 수 없습니다. API 키를 확인해주세요.",
                "original_text": text,
                "corrected_text": text
            }
        
        if not text or len(text.strip()) == 0:
            return {
                "success": True,
                "corrected_text": text,
                "original_text": text,
                "correction_applied": False
            }
        
        try:
            logger.info(f"🔄 GPT로 텍스트 교정 중... (길이: {len(text)}자)")
            
            system_prompt = """당신은 한국어 전문 교정자입니다. 음성 인식 결과의 오타와 맞춤법을 교정해주세요.

**교정 원칙:**
1. **음성학적 오류 수정**: "되요" → "돼요", "웬지" → "왠지", "계시다" → "가시다"
2. **띄어쓰기 정규화**: "할수있다" → "할 수 있다", 자연스러운 한국어 띄어쓰기
3. **맞춤법 교정**: 표준 한국어 맞춤법 준수
4. **문장 부호 최적화**: 자연스러운 쉼표, 마침표 배치
5. **원본 의미 보존**: 절대 의미를 변경하지 마세요

교정된 텍스트만 출력하세요. 추가 설명 없이 결과만 제공하세요."""
            
            response = await self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"다음 텍스트를 교정해주세요:\n\n{text}"}
                ],
                temperature=0.1,
                max_tokens=1000,
                timeout=30.0
            )
            
            corrected_text = response.choices[0].message.content.strip()
            
            # 기본 품질 체크
            if len(corrected_text) < len(text) * 0.3:
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
    
    async def correct_segments(self, segments: List[Dict], context: str = "") -> Dict:
        """세그먼트별 텍스트 교정"""
        if not self.is_available():
            return {
                "success": False,
                "error": "GPT 후처리를 사용할 수 없습니다.",
                "original_segments": segments,
                "corrected_segments": segments
            }
        
        if not segments:
            return {
                "success": True,
                "corrected_segments": [],
                "original_segments": [],
                "total_corrections": 0
            }
        
        try:
            logger.info(f"🔄 {len(segments)}개 세그먼트 교정 중...")
            
            # 전체 텍스트 결합
            full_text = " ".join([seg.get("text", "") for seg in segments])
            
            if not full_text.strip():
                return {
                    "success": True,
                    "corrected_segments": segments,
                    "original_segments": segments,
                    "total_corrections": 0
                }
            
            # 전체 텍스트 교정
            correction_result = await self.correct_text(full_text)
            
            if not correction_result["success"]:
                return {
                    "success": False,
                    "error": correction_result["error"],
                    "original_segments": segments,
                    "corrected_segments": segments
                }
            
            corrected_full_text = correction_result["corrected_text"]
            
            # 교정된 텍스트를 세그먼트에 재분배 (간단한 방식)
            corrected_segments = []
            if correction_result["correction_applied"]:
                # 교정이 적용된 경우, 문장 단위로 분할하여 재분배
                sentences = self._split_sentences(corrected_full_text)
                
                for i, original_seg in enumerate(segments):
                    if i < len(sentences):
                        corrected_seg = {
                            "start": original_seg.get("start", 0),
                            "end": original_seg.get("end", 0),
                            "text": sentences[i].strip()
                        }
                    else:
                        # 문장이 부족하면 원본 유지
                        corrected_seg = original_seg.copy()
                    
                    corrected_segments.append(corrected_seg)
                
                # 남은 문장들을 마지막 세그먼트에 합치기
                if len(sentences) > len(segments):
                    remaining_text = " ".join(sentences[len(segments):])
                    if corrected_segments:
                        corrected_segments[-1]["text"] += " " + remaining_text
            else:
                # 교정이 적용되지 않은 경우 원본 유지
                corrected_segments = segments.copy()
            
            total_corrections = 1 if correction_result["correction_applied"] else 0
            
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
                "corrected_segments": segments
            }
    
    def _split_sentences(self, text: str) -> List[str]:
        """텍스트를 문장 단위로 분할 (더 정확한 분할)"""
        import re
        
        # 한국어 문장 분할 패턴 (더 정교하게)
        # 마침표, 느낌표, 물음표 뒤의 공백이나 줄바꿈
        sentence_endings = r'[.!?]\s+'
        sentences = re.split(sentence_endings, text.strip())
        
        # 빈 문장 제거 및 정리
        sentences = [s.strip() for s in sentences if s.strip()]
        
        # 문장이 너무 적으면 더 세분화
        if len(sentences) == 1 and len(text) > 100:
            # 쉼표나 세미콜론으로도 분할 시도
            comma_split = re.split(r'[,;]\s+', text.strip())
            if len(comma_split) > 1:
                sentences = [s.strip() for s in comma_split if s.strip()]
        
        return sentences
    
    async def correct_segments_preserve_timing(self, segments: List[Dict], context: str = "") -> Dict:
        """세그먼트별 교정 (타임스탬프 보존 강화)"""
        if not self.is_available() or not segments:
            return {
                "success": False if not self.is_available() else True,
                "error": "GPT 후처리를 사용할 수 없습니다." if not self.is_available() else None,
                "original_segments": segments,
                "corrected_segments": segments,
                "total_corrections": 0
            }
        
        try:
            logger.info(f"🔄 {len(segments)}개 세그먼트 개별 교정 중...")
            
            corrected_segments = []
            total_corrections = 0
            
            # 각 세그먼트를 개별적으로 교정 (타임스탬프 보존)
            for i, segment in enumerate(segments):
                original_text = segment.get("text", "").strip()
                
                if not original_text:
                    corrected_segments.append(segment.copy())
                    continue
                
                # 개별 텍스트 교정
                correction_result = await self.correct_text(original_text)
                
                if correction_result["success"] and correction_result["correction_applied"]:
                    # 교정된 텍스트로 업데이트 (타임스탬프는 그대로 유지)
                    corrected_segment = {
                        "start": segment.get("start", 0),
                        "end": segment.get("end", 0),
                        "text": correction_result["corrected_text"]
                    }
                    corrected_segments.append(corrected_segment)
                    total_corrections += 1
                    logger.info(f"  📝 세그먼트 {i+1}: '{original_text}' → '{correction_result['corrected_text']}'")
                else:
                    # 교정이 적용되지 않은 경우 원본 유지
                    corrected_segments.append(segment.copy())
                
                # API 제한 방지용 짧은 대기
                await asyncio.sleep(0.1)
            
            logger.info(f"✅ 개별 세그먼트 교정 완료: {total_corrections}개 수정됨")
            
            return {
                "success": True,
                "corrected_segments": corrected_segments,
                "original_segments": segments,
                "total_corrections": total_corrections,
                "correction_applied": total_corrections > 0
            }
            
        except Exception as e:
            logger.error(f"❌ 개별 세그먼트 교정 실패: {e}")
            return {
                "success": False,
                "error": str(e),
                "original_segments": segments,
                "corrected_segments": segments,
                "total_corrections": 0
            }

# 전역 인스턴스
simple_gpt_postprocessor = SimpleGPTPostProcessor()
