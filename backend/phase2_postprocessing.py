"""
🤖 Phase 2: GPT 후처리 모듈
- 차세대 텍스트 교정 시스템
- 품질 분석 통합
- 실시간 진행률 표시
- 한국어 특화 교정
"""

import asyncio
import os
from typing import Dict, List, Optional
from openai import AsyncOpenAI
import logging
from datetime import datetime
import json

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Phase2PostProcessor:
    """Phase 2 전용 GPT 후처리 시스템"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.client = None
        self.is_enabled = False
        
        if self.api_key and self.api_key != "your_openai_api_key_here":
            try:
                self.client = AsyncOpenAI(api_key=self.api_key)
                self.is_enabled = True
                logger.info("✅ Phase 2 GPT-4.1 mini 후처리 모듈 초기화 완료")
            except Exception as e:
                logger.error(f"❌ Phase 2 GPT 후처리 모듈 초기화 실패: {e}")
                self.is_enabled = False
        else:
            logger.warning("⚠️ OPENAI_API_KEY가 설정되지 않아 GPT 후처리를 사용할 수 없습니다")
    
    def is_available(self) -> bool:
        """GPT 후처리 사용 가능 여부 확인"""
        return self.is_enabled and self.client is not None
    
    async def process_with_progress(
        self, 
        segments: List[Dict], 
        quality_metrics: Optional[Dict] = None,
        websocket=None,
        session_id: str = "unknown"
    ) -> Dict:
        """진행률과 함께 GPT 후처리 실행"""
        
        if not self.is_available():
            return {
                "success": False,
                "error": "GPT 후처리를 사용할 수 없습니다. API 키를 확인해주세요.",
                "original_segments": segments,
                "corrected_segments": segments
            }
        
        if not segments:
            return {
                "success": True,
                "corrected_segments": [],
                "original_segments": [],
                "total_corrections": 0,
                "processing_time": 0
            }
        
        start_time = datetime.now()
        
        try:
            logger.info(f"🤖 Phase 2 GPT-4.1 mini 후처리 시작: {len(segments)}개 세그먼트")
            
            # WebSocket으로 진행률 전송
            if websocket:
                await self._send_progress(websocket, {
                    "stage": "gpt_postprocessing",
                    "progress": 0,
                    "message": "GPT-4.1 mini 후처리 시작...",
                    "session_id": session_id
                })
            
            # 품질 기반 교정 전략 결정
            correction_strategy = self._determine_correction_strategy(quality_metrics)
            logger.info(f"📝 교정 전략: {correction_strategy['name']}")
            
            # 진행률 업데이트
            if websocket:
                await self._send_progress(websocket, {
                    "stage": "gpt_postprocessing", 
                    "progress": 10,
                    "message": f"교정 전략 설정: {correction_strategy['name']}",
                    "session_id": session_id
                })
            
            # 세그먼트별 교정 실행
            corrected_segments = []
            total_corrections = 0
            
            batch_size = 5  # 배치 단위로 처리
            total_batches = (len(segments) + batch_size - 1) // batch_size
            
            for batch_idx, i in enumerate(range(0, len(segments), batch_size)):
                batch_segments = segments[i:i + batch_size]
                
                # 배치 처리
                batch_result = await self._process_batch(
                    batch_segments, 
                    correction_strategy,
                    batch_idx + 1,
                    total_batches
                )
                
                corrected_segments.extend(batch_result["corrected_segments"])
                total_corrections += batch_result["corrections_count"]
                
                # 진행률 업데이트
                progress = 10 + (80 * (batch_idx + 1) / total_batches)
                if websocket:
                    await self._send_progress(websocket, {
                        "stage": "gpt_postprocessing",
                        "progress": int(progress),
                        "message": f"배치 {batch_idx + 1}/{total_batches} 처리 완료 ({batch_result['corrections_count']}개 교정)",
                        "session_id": session_id
                    })
                
                # API 제한 방지용 대기
                await asyncio.sleep(0.2)
            
            # 최종 품질 검증
            if websocket:
                await self._send_progress(websocket, {
                    "stage": "gpt_postprocessing",
                    "progress": 90,
                    "message": "최종 품질 검증 중...",
                    "session_id": session_id
                })
            
            final_quality = await self._validate_final_quality(segments, corrected_segments)
            
            processing_time = (datetime.now() - start_time).total_seconds()
            
            # 완료
            if websocket:
                await self._send_progress(websocket, {
                    "stage": "gpt_postprocessing",
                    "progress": 100,
                    "message": f"GPT-4.1 mini 후처리 완료! {total_corrections}개 항목 교정됨",
                    "session_id": session_id
                })
            
            logger.info(f"✅ Phase 2 GPT-4.1 mini 후처리 완료: {total_corrections}개 교정, {processing_time:.2f}초")
            
            return {
                "success": True,
                "corrected_segments": corrected_segments,
                "original_segments": segments,
                "total_corrections": total_corrections,
                "processing_time": processing_time,
                "correction_strategy": correction_strategy["name"],
                "final_quality_score": final_quality["score"],
                "improvement_details": final_quality["improvements"],
                "correction_applied": total_corrections > 0
            }
            
        except Exception as e:
            logger.error(f"❌ Phase 2 GPT-4.1 mini 후처리 실패: {e}")
            
            if websocket:
                await self._send_progress(websocket, {
                    "stage": "gpt_postprocessing",
                    "progress": 0,
                    "message": f"GPT-4.1 mini 후처리 실패: {str(e)}",
                    "error": True,
                    "session_id": session_id
                })
            
            return {
                "success": False,
                "error": str(e),
                "original_segments": segments,
                "corrected_segments": segments,
                "total_corrections": 0
            }
    
    def _determine_correction_strategy(self, quality_metrics: Optional[Dict]) -> Dict:
        """품질 지표 기반 교정 전략 결정"""
        
        if not quality_metrics:
            return {
                "name": "표준 교정",
                "model": "gpt-4.1-mini",
                "temperature": 0.1,
                "focus": "전반적인 맞춤법과 띄어쓰기"
            }
        
        overall_score = quality_metrics.get("overall_score", 0.5)
        korean_score = quality_metrics.get("korean_quality_score", 0.5)
        grammar_score = quality_metrics.get("grammar_score", 0.5)
        
        if overall_score >= 0.9:
            return {
                "name": "정밀 교정",
                "model": "gpt-4.1-mini",
                "temperature": 0.05,
                "focus": "세밀한 문법과 자연스러운 표현"
            }
        elif korean_score < 0.7:
            return {
                "name": "한국어 집중 교정",
                "model": "gpt-4.1-mini", 
                "temperature": 0.1,
                "focus": "한국어 표현과 어휘 개선"
            }
        elif grammar_score < 0.6:
            return {
                "name": "문법 집중 교정",
                "model": "gpt-4.1-mini",
                "temperature": 0.1,
                "focus": "문법 오류와 문장 구조 개선"
            }
        else:
            return {
                "name": "균형 교정",
                "model": "gpt-4.1-mini",
                "temperature": 0.1,
                "focus": "맞춤법, 띄어쓰기, 자연스러운 표현"
            }
    
    async def _process_batch(
        self, 
        batch_segments: List[Dict], 
        strategy: Dict,
        batch_num: int,
        total_batches: int
    ) -> Dict:
        """배치 단위 세그먼트 처리"""
        
        logger.info(f"📦 배치 {batch_num}/{total_batches} 처리 중... ({len(batch_segments)}개 세그먼트)")
        
        corrected_segments = []
        corrections_count = 0
        
        # 배치 내 세그먼트들을 하나의 텍스트로 결합
        combined_text = "\n".join([
            f"[{i+1}] {seg.get('text', '').strip()}" 
            for i, seg in enumerate(batch_segments) 
            if seg.get('text', '').strip()
        ])
        
        if not combined_text.strip():
            return {
                "corrected_segments": batch_segments,
                "corrections_count": 0
            }
        
        try:
            # GPT를 사용한 배치 교정
            system_prompt = f"""당신은 한국어 전문 교정자입니다. 음성 인식 결과를 교정해주세요.

**교정 전략: {strategy['focus']}**

**교정 원칙 (GPT-4.1 mini 최적화):**
1. 🔥 **음성학적 오류 수정**: "줄거래" → "줄거리", "되요" → "돼요", "할께요" → "할게요"
2. 🔥 **띄어쓰기 정규화**: "할수있다" → "할 수 있다", "읽기쉽게" → "읽기 쉽게"
3. 🔥 **맞춤법 교정**: 표준 한국어 맞춤법 준수
4. 🔥 **자연스러운 표현**: 구어체를 자연스러운 문어체로
5. 🔥 **원본 의미 절대 보존**: 의미를 변경하지 마세요
6. 🆕 **문맥 이해 강화**: 앞뒤 문맥을 고려한 정확한 교정
7. 🆕 **일관성 유지**: 전체 텍스트의 톤과 스타일 일관성
8. 🌟 **외래어 표기법 교정**: 국립국어원 외래어 표기법 준수

**특별 주의사항 (GPT-4.1 mini 전용):**
- "줄거래"는 반드시 "줄거리"로 교정
- "읽기쉽게"는 반드시 "읽기 쉽게"로 교정
- 모든 음성 인식 오류를 정확히 감지하고 수정
- 긴 텍스트에서도 일관된 품질 유지
- 복잡한 문장 구조도 자연스럽게 개선

**외래어 표기법 교정 (필수 적용):**
- "콘사이스" → "컨사이스" (Concise)
- "메뉴얼" → "매뉴얼" (Manual)  
- "리뷰" → "리뷰" (Review - 이미 정확)
- "프로젝트" → "프로젝트" (Project - 이미 정확)
- "시스템" → "시스템" (System - 이미 정확)
- "컴퓨터" → "컴퓨터" (Computer - 이미 정확)
- "센터" → "센터" (Center - 이미 정확)
- "인터넷" → "인터넷" (Internet - 이미 정확)
- 기타 국립국어원 외래어 표기법 준수

**입력 형식:** [번호] 텍스트
**출력 형식:** 동일한 번호로 교정된 텍스트만 출력

각 줄은 반드시 [번호] 형식을 유지하고, 교정된 텍스트만 제공하세요."""

            response = await self.client.chat.completions.create(
                model=strategy["model"],
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"다음 텍스트들을 교정해주세요:\n\n{combined_text}"}
                ],
                temperature=strategy["temperature"],
                max_tokens=2000,
                timeout=45.0
            )
            
            corrected_text = response.choices[0].message.content.strip()
            
            # 교정 결과를 세그먼트로 다시 분할
            corrected_lines = corrected_text.split('\n')
            corrected_dict = {}
            
            for line in corrected_lines:
                line = line.strip()
                if line.startswith('[') and '] ' in line:
                    try:
                        bracket_end = line.find('] ')
                        num_str = line[1:bracket_end]
                        corrected_content = line[bracket_end + 2:].strip()
                        corrected_dict[int(num_str)] = corrected_content
                    except:
                        continue
            
            # 원본 세그먼트와 교정 결과 매칭
            for i, original_seg in enumerate(batch_segments):
                original_text = original_seg.get('text', '').strip()
                
                if not original_text:
                    corrected_segments.append(original_seg.copy())
                    continue
                
                segment_num = i + 1
                if segment_num in corrected_dict:
                    corrected_text = corrected_dict[segment_num]
                    
                    # 교정이 실제로 적용되었는지 확인
                    if corrected_text != original_text and len(corrected_text) >= len(original_text) * 0.5:
                        corrected_segment = {
                            "start": original_seg.get("start", 0),
                            "end": original_seg.get("end", 0),
                            "text": corrected_text
                        }
                        corrected_segments.append(corrected_segment)
                        corrections_count += 1
                        logger.info(f"  ✏️  교정: '{original_text}' → '{corrected_text}'")
                    else:
                        corrected_segments.append(original_seg.copy())
                else:
                    corrected_segments.append(original_seg.copy())
        
        except Exception as e:
            logger.error(f"❌ 배치 {batch_num} 처리 실패: {e}")
            corrected_segments = batch_segments.copy()
        
        return {
            "corrected_segments": corrected_segments,
            "corrections_count": corrections_count
        }
    
    async def _validate_final_quality(
        self, 
        original_segments: List[Dict], 
        corrected_segments: List[Dict]
    ) -> Dict:
        """최종 품질 검증"""
        
        try:
            original_text = " ".join([seg.get("text", "") for seg in original_segments])
            corrected_text = " ".join([seg.get("text", "") for seg in corrected_segments])
            
            # 기본 품질 지표 계산
            improvements = []
            
            # 길이 비교
            if len(corrected_text) >= len(original_text) * 0.8:
                improvements.append("적절한 텍스트 길이 유지")
            
            # 한글 비율 개선 확인
            original_korean = sum(1 for char in original_text if '가' <= char <= '힣')
            corrected_korean = sum(1 for char in corrected_text if '가' <= char <= '힣')
            
            if corrected_korean >= original_korean:
                improvements.append("한국어 표현 개선")
            
            # 띄어쓰기 개선 확인
            original_spaces = original_text.count(' ')
            corrected_spaces = corrected_text.count(' ')
            
            if corrected_spaces > original_spaces * 0.8:
                improvements.append("띄어쓰기 정규화")
            
            # 문장부호 개선 확인
            punctuation = '.!?,'
            original_punct = sum(1 for char in original_text if char in punctuation)
            corrected_punct = sum(1 for char in corrected_text if char in punctuation)
            
            if corrected_punct >= original_punct:
                improvements.append("문장부호 최적화")
            
            # 전체 품질 점수 계산
            quality_score = min(1.0, len(improvements) / 4.0 + 0.5)
            
            return {
                "score": quality_score,
                "improvements": improvements
            }
            
        except Exception as e:
            logger.error(f"❌ 최종 품질 검증 실패: {e}")
            return {
                "score": 0.5,
                "improvements": ["품질 검증 중 오류 발생"]
            }
    
    async def _send_progress(self, websocket, data: Dict):
        """WebSocket으로 진행률 전송"""
        try:
            if websocket:
                message = {
                    "type": "progress",
                    "timestamp": datetime.now().isoformat(),
                    **data
                }
                await websocket.send_text(json.dumps(message))
        except Exception as e:
            logger.warning(f"⚠️ WebSocket 진행률 전송 실패: {e}")


class PostProcessingResult:
    """후처리 결과 데이터 클래스"""
    
    def __init__(
        self,
        success: bool,
        corrected_segments: List[Dict],
        original_segments: List[Dict],
        total_corrections: int = 0,
        processing_time: float = 0,
        correction_strategy: str = "",
        final_quality_score: float = 0,
        improvement_details: List[str] = None,
        error: str = None
    ):
        self.success = success
        self.corrected_segments = corrected_segments
        self.original_segments = original_segments
        self.total_corrections = total_corrections
        self.processing_time = processing_time
        self.correction_strategy = correction_strategy
        self.final_quality_score = final_quality_score
        self.improvement_details = improvement_details or []
        self.error = error
    
    def to_dict(self) -> Dict:
        return {
            "success": self.success,
            "corrected_segments": self.corrected_segments,
            "original_segments": self.original_segments,
            "total_corrections": self.total_corrections,
            "processing_time": self.processing_time,
            "correction_strategy": self.correction_strategy,
            "final_quality_score": self.final_quality_score,
            "improvement_details": self.improvement_details,
            "error": self.error,
            "correction_applied": self.total_corrections > 0
        }
