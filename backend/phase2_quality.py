"""
🚀 Phase 2: 지능형 품질 검증 시스템
- 신뢰도 기반 자동 품질 평가
- 자동 재처리 및 최적화
- 상세한 품질 리포트 생성
"""

import asyncio
import json
import time
import statistics
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict
from pathlib import Path
import re
import math


@dataclass
class QualityMetrics:
    """품질 평가 메트릭"""
    overall_score: float  # 0.0 ~ 1.0
    confidence_score: float
    korean_quality_score: float
    grammar_score: float
    consistency_score: float
    completeness_score: float
    
    # 세부 분석
    word_count: int
    korean_word_ratio: float
    punctuation_ratio: float
    avg_segment_confidence: float
    low_confidence_segments: int
    
    # 추천사항
    needs_reprocessing: bool
    recommended_model: Optional[str]
    improvement_suggestions: List[str]


@dataclass
class QualityIssue:
    """품질 문제점"""
    issue_type: str
    severity: str  # "low", "medium", "high", "critical"
    description: str
    segment_id: Optional[int] = None
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    suggestion: Optional[str] = None


class KoreanTextAnalyzer:
    """한국어 텍스트 품질 분석기"""
    
    # 한국어 유니코드 범위
    KOREAN_RANGE = (0xAC00, 0xD7AF)  # 완성형 한글
    KOREAN_JAMO_RANGE = (0x1100, 0x11FF)  # 한글 자모
    
    # 일반적인 한국어 문장 부호
    KOREAN_PUNCTUATION = '.,!?;:()[]{}""''「」『』…·'
    
    def analyze_korean_quality(self, text: str) -> Dict[str, float]:
        """한국어 품질 분석"""
        
        if not text.strip():
            return {
                "korean_ratio": 0.0,
                "grammar_score": 0.0,
                "naturalness_score": 0.0,
                "punctuation_score": 0.0
            }
        
        # 1. 한국어 비율 계산
        korean_chars = sum(1 for c in text if self._is_korean_char(c))
        total_chars = len(re.sub(r'\s+', '', text))  # 공백 제외
        korean_ratio = korean_chars / total_chars if total_chars > 0 else 0.0
        
        # 2. 문법 점수 (간단한 휴리스틱)
        grammar_score = self._calculate_grammar_score(text)
        
        # 3. 자연스러움 점수
        naturalness_score = self._calculate_naturalness_score(text)
        
        # 4. 문장 부호 점수
        punctuation_score = self._calculate_punctuation_score(text)
        
        return {
            "korean_ratio": korean_ratio,
            "grammar_score": grammar_score,
            "naturalness_score": naturalness_score,
            "punctuation_score": punctuation_score
        }
    
    def _is_korean_char(self, char: str) -> bool:
        """한국어 문자 판별"""
        code = ord(char)
        return (self.KOREAN_RANGE[0] <= code <= self.KOREAN_RANGE[1] or
                self.KOREAN_JAMO_RANGE[0] <= code <= self.KOREAN_JAMO_RANGE[1])
    
    def _calculate_grammar_score(self, text: str) -> float:
        """문법 점수 계산 (간단한 규칙 기반)"""
        score = 1.0
        
        # 조사 사용 패턴 확인
        particles = ['은', '는', '이', '가', '을', '를', '에', '에서', '로', '으로', '와', '과']
        particle_count = sum(text.count(p) for p in particles)
        words = len(text.split())
        
        if words > 0:
            particle_ratio = particle_count / words
            # 적절한 조사 사용 비율 (0.1~0.3이 자연스러움)
            if 0.1 <= particle_ratio <= 0.3:
                score *= 1.0
            else:
                score *= max(0.5, 1.0 - abs(particle_ratio - 0.2))
        
        return score
    
    def _calculate_naturalness_score(self, text: str) -> float:
        """자연스러움 점수"""
        score = 1.0
        
        # 반복 단어 패턴 체크
        words = text.split()
        if len(words) > 1:
            repeated_words = len(words) - len(set(words))
            repetition_ratio = repeated_words / len(words)
            score *= max(0.5, 1.0 - repetition_ratio * 2)
        
        # 문장 길이 분포 체크
        sentences = re.split(r'[.!?]\s*', text)
        if sentences:
            avg_sentence_length = statistics.mean(len(s.split()) for s in sentences if s.strip())
            # 적절한 문장 길이 (5~15 단어)
            if 5 <= avg_sentence_length <= 15:
                score *= 1.0
            else:
                score *= max(0.7, 1.0 - abs(avg_sentence_length - 10) / 20)
        
        return score
    
    def _calculate_punctuation_score(self, text: str) -> float:
        """문장 부호 점수"""
        if not text.strip():
            return 0.0
        
        punctuation_count = sum(1 for c in text if c in self.KOREAN_PUNCTUATION)
        total_chars = len(text)
        punctuation_ratio = punctuation_count / total_chars
        
        # 적절한 문장 부호 비율 (2~8%)
        if 0.02 <= punctuation_ratio <= 0.08:
            return 1.0
        else:
            return max(0.5, 1.0 - abs(punctuation_ratio - 0.05) * 10)


class QualityAnalyzer:
    """통합 품질 분석기"""
    
    def __init__(self):
        self.korean_analyzer = KoreanTextAnalyzer()
        
        # 품질 임계값 설정
        self.thresholds = {
            "confidence_min": 0.7,
            "korean_ratio_min": 0.8,
            "grammar_score_min": 0.6,
            "overall_score_min": 0.75
        }
    
    async def analyze_transcription_quality(
        self,
        text: str,
        segments: List[Dict],
        processing_time: float,
        model_used: str
    ) -> QualityMetrics:
        """전사 품질 종합 분석"""
        
        start_time = time.time()
        
        # 1. 기본 메트릭 계산
        word_count = len(text.split()) if text else 0
        
        # 2. 한국어 품질 분석
        korean_analysis = self.korean_analyzer.analyze_korean_quality(text)
        
        # 3. 세그먼트 신뢰도 분석
        confidences = [seg.get('confidence', 0.5) for seg in segments if seg.get('confidence')]
        avg_confidence = statistics.mean(confidences) if confidences else 0.5
        low_confidence_segments = sum(1 for c in confidences if c < self.thresholds["confidence_min"])
        
        # 4. 완성도 점수 (세그먼트 연결성)
        completeness_score = self._calculate_completeness_score(segments, text)
        
        # 5. 일관성 점수 (시간적 연속성)
        consistency_score = self._calculate_consistency_score(segments)
        
        # 6. 전체 점수 계산
        overall_score = self._calculate_overall_score(
            avg_confidence,
            korean_analysis["korean_ratio"],
            korean_analysis["grammar_score"],
            completeness_score,
            consistency_score
        )
        
        # 7. 재처리 필요성 판단
        needs_reprocessing = self._should_reprocess(
            overall_score, avg_confidence, korean_analysis
        )
        
        # 8. 모델 추천
        recommended_model = self._recommend_model(
            overall_score, processing_time, model_used
        )
        
        # 9. 개선 제안
        improvement_suggestions = self._generate_improvement_suggestions(
            overall_score, avg_confidence, korean_analysis, low_confidence_segments
        )
        
        analysis_time = time.time() - start_time
        print(f"🔍 품질 분석 완료 - {analysis_time:.2f}초")
        
        return QualityMetrics(
            overall_score=overall_score,
            confidence_score=avg_confidence,
            korean_quality_score=(korean_analysis["korean_ratio"] + korean_analysis["grammar_score"]) / 2,
            grammar_score=korean_analysis["grammar_score"],
            consistency_score=consistency_score,
            completeness_score=completeness_score,
            
            word_count=word_count,
            korean_word_ratio=korean_analysis["korean_ratio"],
            punctuation_ratio=korean_analysis["punctuation_score"],
            avg_segment_confidence=avg_confidence,
            low_confidence_segments=low_confidence_segments,
            
            needs_reprocessing=needs_reprocessing,
            recommended_model=recommended_model,
            improvement_suggestions=improvement_suggestions
        )
    
    def _calculate_completeness_score(self, segments: List[Dict], text: str) -> float:
        """완성도 점수 계산"""
        if not segments or not text:
            return 0.0
        
        # 세그먼트 텍스트 합계와 전체 텍스트 비교
        segment_text = " ".join(seg.get("text", "") for seg in segments)
        segment_words = len(segment_text.split())
        total_words = len(text.split())
        
        if total_words == 0:
            return 0.0
        
        return min(1.0, segment_words / total_words)
    
    def _calculate_consistency_score(self, segments: List[Dict]) -> float:
        """일관성 점수 계산"""
        if len(segments) < 2:
            return 1.0
        
        # 시간 간격의 일관성 체크
        gaps = []
        overlaps = 0
        
        for i in range(len(segments) - 1):
            current_end = segments[i].get("end", 0)
            next_start = segments[i + 1].get("start", 0)
            
            if next_start > current_end:
                gaps.append(next_start - current_end)
            elif next_start < current_end:
                overlaps += 1
        
        # 큰 간격이나 겹침이 많으면 점수 감소
        score = 1.0
        
        if gaps:
            avg_gap = statistics.mean(gaps)
            if avg_gap > 2.0:  # 2초 이상 간격
                score *= max(0.5, 1.0 - (avg_gap - 2.0) / 10.0)
        
        if overlaps > 0:
            overlap_ratio = overlaps / len(segments)
            score *= max(0.5, 1.0 - overlap_ratio)
        
        return score
    
    def _calculate_overall_score(
        self,
        confidence: float,
        korean_ratio: float,
        grammar_score: float,
        completeness_score: float,
        consistency_score: float
    ) -> float:
        """전체 점수 계산 (가중 평균)"""
        
        weights = {
            "confidence": 0.3,
            "korean_ratio": 0.25,
            "grammar": 0.2,
            "completeness": 0.15,
            "consistency": 0.1
        }
        
        return (
            confidence * weights["confidence"] +
            korean_ratio * weights["korean_ratio"] +
            grammar_score * weights["grammar"] +
            completeness_score * weights["completeness"] +
            consistency_score * weights["consistency"]
        )
    
    def _should_reprocess(
        self,
        overall_score: float,
        confidence: float,
        korean_analysis: Dict[str, float]
    ) -> bool:
        """재처리 필요성 판단"""
        
        return (
            overall_score < self.thresholds["overall_score_min"] or
            confidence < self.thresholds["confidence_min"] or
            korean_analysis["korean_ratio"] < self.thresholds["korean_ratio_min"] or
            korean_analysis["grammar_score"] < self.thresholds["grammar_score_min"]
        )
    
    def _recommend_model(
        self,
        overall_score: float,
        processing_time: float,
        current_model: str
    ) -> Optional[str]:
        """모델 추천"""
        
        if overall_score >= 0.9:
            return None  # 현재 모델로 충분
        
        # 품질이 낮으면 더 강력한 모델 추천
        if overall_score < 0.7:
            if current_model == "whisper-1":
                return "gpt-4o-audio-preview"
            else:
                return "whisper-1"  # 다른 모델 시도
        
        # 처리 시간이 너무 길면 빠른 모델 추천
        if processing_time > 60:
            return "whisper-1"
        
        return None
    
    def _generate_improvement_suggestions(
        self,
        overall_score: float,
        confidence: float,
        korean_analysis: Dict[str, float],
        low_confidence_segments: int
    ) -> List[str]:
        """개선 제안 생성"""
        
        suggestions = []
        
        if confidence < 0.7:
            suggestions.append("신뢰도가 낮습니다. 더 높은 품질의 모델을 사용해보세요.")
        
        if korean_analysis["korean_ratio"] < 0.8:
            suggestions.append("한국어 비율이 낮습니다. 언어 설정을 확인하고 한국어 특화 프롬프트를 사용해보세요.")
        
        if korean_analysis["grammar_score"] < 0.6:
            suggestions.append("문법 점수가 낮습니다. GPT 후처리를 통한 교정을 권장합니다.")
        
        if low_confidence_segments > 0:
            suggestions.append(f"{low_confidence_segments}개 세그먼트의 신뢰도가 낮습니다. 해당 구간을 재처리해보세요.")
        
        if overall_score < 0.6:
            suggestions.append("전체적인 품질이 낮습니다. 오디오 파일의 품질을 확인하거나 다른 모델을 시도해보세요.")
        
        return suggestions


class AutoReprocessor:
    """자동 재처리 시스템"""
    
    def __init__(self, model_manager, quality_analyzer: QualityAnalyzer):
        self.model_manager = model_manager
        self.quality_analyzer = quality_analyzer
        self.max_reprocess_attempts = 2
    
    async def auto_reprocess_if_needed(
        self,
        audio_path: str,
        initial_result: Dict,
        target_quality: float = 0.8
    ) -> Dict:
        """필요시 자동 재처리"""
        
        current_result = initial_result
        attempt = 0
        
        while attempt < self.max_reprocess_attempts:
            # 품질 분석
            quality = await self.quality_analyzer.analyze_transcription_quality(
                current_result.get("text", ""),
                current_result.get("segments", []),
                current_result.get("processing_time", 0),
                current_result.get("model_used", "unknown")
            )
            
            print(f"🔍 품질 점수: {quality.overall_score:.3f} (목표: {target_quality:.3f})")
            
            # 목표 품질 달성시 종료
            if quality.overall_score >= target_quality:
                current_result["quality_metrics"] = asdict(quality)
                print("✅ 목표 품질 달성!")
                break
            
            # 재처리 필요성 확인
            if not quality.needs_reprocessing:
                print("⚠️ 재처리가 도움이 되지 않을 것 같습니다.")
                break
            
            # 다른 모델로 재처리 시도
            if quality.recommended_model:
                print(f"🔄 {quality.recommended_model} 모델로 재처리 시도...")
                
                reprocess_result = await self.model_manager.transcribe_with_model(
                    audio_path,
                    quality.recommended_model,
                    "ko",
                    include_quality_metrics=True
                )
                
                if reprocess_result.success:
                    current_result = {
                        "text": reprocess_result.text,
                        "segments": reprocess_result.segments,
                        "processing_time": reprocess_result.processing_time,
                        "model_used": reprocess_result.model_used,
                        "reprocessed": True,
                        "reprocess_attempt": attempt + 1
                    }
                else:
                    print(f"❌ 재처리 실패: {reprocess_result.error}")
                    break
            else:
                print("⚠️ 추천할 대안 모델이 없습니다.")
                break
            
            attempt += 1
        
        # 최종 품질 분석
        final_quality = await self.quality_analyzer.analyze_transcription_quality(
            current_result.get("text", ""),
            current_result.get("segments", []),
            current_result.get("processing_time", 0),
            current_result.get("model_used", "unknown")
        )
        
        current_result["quality_metrics"] = asdict(final_quality)
        current_result["total_reprocess_attempts"] = attempt
        
        return current_result


# 테스트용 함수들
async def test_quality_system():
    """품질 검증 시스템 테스트"""
    analyzer = QualityAnalyzer()
    
    # 테스트 데이터
    test_cases = [
        {
            "text": "안녕하세요. 이것은 한국어 음성 인식 테스트입니다.",
            "segments": [
                {"start": 0.0, "end": 2.0, "text": "안녕하세요.", "confidence": 0.95},
                {"start": 2.0, "end": 5.0, "text": "이것은 한국어 음성 인식 테스트입니다.", "confidence": 0.89}
            ]
        },
        {
            "text": "hello world this is english test",
            "segments": [
                {"start": 0.0, "end": 3.0, "text": "hello world this is english test", "confidence": 0.75}
            ]
        }
    ]
    
    for i, test_case in enumerate(test_cases):
        print(f"\n🧪 테스트 케이스 {i+1}:")
        print(f"📝 텍스트: {test_case['text']}")
        
        quality = await analyzer.analyze_transcription_quality(
            test_case["text"],
            test_case["segments"],
            processing_time=2.5,
            model_used="test_model"
        )
        
        print(f"📊 품질 분석 결과:")
        print(f"  🎯 전체 점수: {quality.overall_score:.3f}")
        print(f"  🤖 신뢰도: {quality.confidence_score:.3f}")
        print(f"  🇰🇷 한국어 품질: {quality.korean_quality_score:.3f}")
        print(f"  📝 문법 점수: {quality.grammar_score:.3f}")
        print(f"  🔄 재처리 필요: {'예' if quality.needs_reprocessing else '아니오'}")
        
        if quality.improvement_suggestions:
            print(f"  💡 개선 제안:")
            for suggestion in quality.improvement_suggestions:
                print(f"    - {suggestion}")


if __name__ == "__main__":
    asyncio.run(test_quality_system())
