"use client";

import React, { useState, useEffect, useRef } from 'react';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Progress } from '@/components/ui/progress';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { 
  Upload, 
  Play, 
  Download, 
  Settings, 
  Zap, 
  Brain, 
  BarChart3, 
  Repeat,
  CheckCircle,
  AlertCircle,
  Clock,
  Cpu,
  Target
} from 'lucide-react';

interface ModelInfo {
  name: string;
  speed: string;
  quality: string;
  cost: string;
  recommended_for?: boolean;
}

interface VideoResolution {
  size: string;
  description: string;
  recommended_for: string;
  default?: boolean;
}

interface QualityMetrics {
  overall_score: number;
  confidence_score: number;
  korean_quality_score: number;
  grammar_score: number;
  consistency_score: number;
  completeness_score: number;
  needs_reprocessing: boolean;
  recommended_model?: string;
  improvement_suggestions: string[];
}

interface StreamingProgress {
  total_chunks: number;
  processed_chunks: number;
  current_chunk: number;
  progress_percent: number;
  current_text: string;
  estimated_remaining_time: number;
  status: string;
  error_message?: string;
}

const Phase2AudioProcessor = () => {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [fileId, setFileId] = useState<string>('');
  const [selectedModel, setSelectedModel] = useState<string>('whisper-1-optimized');
  const [videoResolution, setVideoResolution] = useState<string>('1080p');
  // 🆕 Phase 3.2.3: 템플릿 및 트랜지션 상태
  const [templateName, setTemplateName] = useState<string>('particles_dark');
  const [transitionType, setTransitionType] = useState<string>('fade');
  const [transitionDuration, setTransitionDuration] = useState<number>(1.2);
  const [transitionIntensity, setTransitionIntensity] = useState<number>(0.8);
  const [availableTemplates, setAvailableTemplates] = useState<any>({});
  const [useTemplateBackground, setUseTemplateBackground] = useState<boolean>(true);  // 템플릿 사용 여부
  
  const [enableGptPostprocessing, setEnableGptPostprocessing] = useState<boolean>(true);
  const [isProcessing, setIsProcessing] = useState<boolean>(false);
  const [progress, setProgress] = useState<number>(0);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState<string>('');
  const [availableModels, setAvailableModels] = useState<Record<string, ModelInfo>>({});
  const [availableResolutions, setAvailableResolutions] = useState<Record<string, VideoResolution>>({});
  const [processingMode, setProcessingMode] = useState<string>('advanced');
  const [qualityAnalysis, setQualityAnalysis] = useState<QualityMetrics | null>(null);
  const [streamingProgress, setStreamingProgress] = useState<StreamingProgress | null>(null);
  const [websocket, setWebsocket] = useState<WebSocket | null>(null);
  
  const fileInputRef = useRef<HTMLInputElement>(null);
  
  const API_BASE = 'http://localhost:8002';
  const WS_BASE = 'ws://localhost:8002';

  // 컴포넌트 마운트시 모델 정보 로드
  useEffect(() => {
    loadAvailableModels();
    loadAvailableResolutions();
    loadAvailableTemplates();  // 🆕 템플릿 정보 로드
    return () => {
      if (websocket) {
        websocket.close();
      }
    };
  }, []);

  const loadAvailableModels = async () => {
    try {
      const response = await fetch(`${API_BASE}/models`);
      const data = await response.json();
      setAvailableModels(data.available_models);
    } catch (err) {
      console.error('모델 정보 로드 실패:', err);
    }
  };

  const loadAvailableResolutions = async () => {
    try {
      const response = await fetch(`${API_BASE}/video-resolutions`);
      const data = await response.json();
      setAvailableResolutions(data.available_resolutions);
    } catch (err) {
      console.error('해상도 정보 로드 실패:', err);
    }
  };

  // 🆕 템플릿 정보 로드 함수
  const loadAvailableTemplates = async () => {
    try {
      const response = await fetch(`${API_BASE}/templates`);
      const data = await response.json();
      setAvailableTemplates(data.available_templates);
    } catch (err) {
      console.error('템플릿 정보 로드 실패:', err);
    }
  };

  const handleFileSelect = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    setSelectedFile(file);
    setError('');
    setResult(null);
    setQualityAnalysis(null);

    // 파일 업로드
    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await fetch(`${API_BASE}/upload-audio`, {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) throw new Error('파일 업로드 실패');

      const data = await response.json();
      setFileId(data.file_id);
      
      // 추천 모델이 있으면 설정
      if (data.recommended_model) {
        setSelectedModel(data.recommended_model);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : '파일 업로드 실패');
    }
  };

  const processAudio = async () => {
    if (!fileId) return;

    setIsProcessing(true);
    setProgress(0);
    setError('');
    setResult(null);

    try {
      if (processingMode === 'streaming') {
        await processWithStreaming();
      } else {
        await processWithAdvanced();
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : '처리 중 오류 발생');
    } finally {
      setIsProcessing(false);
    }
  };

  const processWithAdvanced = async () => {
    // 🆕 Phase 3.2.3: 템플릿 사용 여부에 따라 다른 API 호출
    if (useTemplateBackground) {
      const response = await fetch(`${API_BASE}/generate-subtitles-template/${fileId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          model: selectedModel,
          language: 'ko',
          template_name: templateName,
          video_resolution: videoResolution,
          transition_type: transitionType,
          transition_duration: transitionDuration,
          transition_intensity: transitionIntensity,
          enable_quality_analysis: true,
          enable_auto_reprocessing: true,
          enable_gpt_postprocessing: enableGptPostprocessing,
          target_quality: 0.8
        })
      });

      if (!response.ok) throw new Error('템플릿 처리 실패');

      const data = await response.json();
      setResult(data);

      if (data.quality_metrics) {
        setQualityAnalysis(data.quality_metrics);
      }

      setProgress(100);
    } else {
      // 기존 방식 (색상 배경)
      const response = await fetch(`${API_BASE}/generate-subtitles-advanced/${fileId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: new URLSearchParams({
          model: selectedModel,
          language: 'ko',
          background_color: 'black',
          video_resolution: videoResolution,
          enable_quality_analysis: 'true',
          enable_auto_reprocessing: 'true',
          enable_gpt_postprocessing: enableGptPostprocessing.toString(),
          target_quality: '0.8'
        })
      });

      if (!response.ok) throw new Error('처리 실패');

      const data = await response.json();
      setResult(data);

      if (data.quality_metrics) {
        setQualityAnalysis(data.quality_metrics);
      }

      setProgress(100);
    }
  };

  const processWithStreaming = async () => {
    return new Promise((resolve, reject) => {
      const ws = new WebSocket(`${WS_BASE}/ws/streaming/${fileId}`);
      setWebsocket(ws);

      ws.onopen = () => {
        ws.send(JSON.stringify({
          model: selectedModel,
          language: 'ko'
        }));
      };

      ws.onmessage = (event) => {
        const data = JSON.parse(event.data);

        switch (data.type) {
          case 'started':
            console.log('스트리밍 시작:', data.message);
            break;

          case 'progress':
            setStreamingProgress(data.data);
            setProgress(data.data.progress_percent);
            break;

          case 'video_ready':
            setResult({
              download_url: data.download_url,
              transcript: data.transcript,
              segments_count: data.segments_count,
              processing_method: 'streaming'
            });
            resolve(data);
            break;

          case 'error':
            reject(new Error(data.message));
            break;
        }
      };

      ws.onerror = (error) => {
        reject(new Error('WebSocket 연결 오류'));
      };

      ws.onclose = () => {
        setWebsocket(null);
      };
    });
  };

  const analyzeQuality = async () => {
    if (!fileId) return;

    try {
      const response = await fetch(`${API_BASE}/quality-analysis/${fileId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: new URLSearchParams({
          model: selectedModel,
          language: 'ko'
        })
      });

      if (!response.ok) throw new Error('품질 분석 실패');

      const data = await response.json();
      setQualityAnalysis(data.quality_analysis);
    } catch (err) {
      setError(err instanceof Error ? err.message : '품질 분석 실패');
    }
  };

  const getQualityColor = (score: number) => {
    if (score >= 0.8) return 'text-green-600';
    if (score >= 0.6) return 'text-yellow-600';
    return 'text-red-600';
  };

  const getQualityBadge = (score: number) => {
    if (score >= 0.9) return { label: '최고', variant: 'default' as const };
    if (score >= 0.8) return { label: '우수', variant: 'secondary' as const };
    if (score >= 0.6) return { label: '보통', variant: 'outline' as const };
    return { label: '개선필요', variant: 'destructive' as const };
  };

  return (
    <div className="max-w-6xl mx-auto p-6 space-y-6">
      {/* 헤더 */}
      <div className="text-center space-y-2">
        <h1 className="text-4xl font-bold bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent">
          🎬 Phase 3.2.3: 트랜지션 템플릿 시스템
        </h1>
        <p className="text-gray-600">
          동적 배경 템플릿 • 스무스 트랜지션 • 지능형 품질 검증 • GPT 후처리
        </p>
        <div className="flex justify-center gap-2 mt-2">
          <Badge variant="secondary" className="text-xs">실시간 스트리밍</Badge>
          <Badge variant="secondary" className="text-xs">🌟 트랜지션 효과</Badge> 
          <Badge variant="secondary" className="text-xs">템플릿 배경</Badge>
        </div>
      </div>

      {/* 파일 업로드 */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Upload className="w-5 h-5" />
            오디오 파일 업로드
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <div 
              onClick={() => fileInputRef.current?.click()}
              className="border-2 border-dashed border-gray-300 rounded-lg p-8 text-center cursor-pointer hover:border-blue-500 transition-colors"
            >
              <Upload className="w-12 h-12 mx-auto text-gray-400 mb-4" />
              <p className="text-lg font-medium">
                {selectedFile ? selectedFile.name : '오디오 파일을 선택하세요'}
              </p>
              <p className="text-sm text-gray-500 mt-2">
                MP3, WAV, M4A, AAC, FLAC, OGG 지원
              </p>
            </div>
            <input
              ref={fileInputRef}
              type="file"
              accept="audio/*"
              onChange={handleFileSelect}
              className="hidden"
            />
          </div>
        </CardContent>
      </Card>

      {/* 설정 */}
      {fileId && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Settings className="w-5 h-5" />
              처리 설정
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-2">
                <label className="text-sm font-medium">AI 모델 선택</label>
                <Select value={selectedModel} onValueChange={setSelectedModel}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {Object.entries(availableModels).map(([key, info]) => (
                      <SelectItem key={key} value={key}>
                        <div className="flex items-center justify-between w-full">
                          <span>{info.name}</span>
                          {info.recommended_for && (
                            <Badge variant="outline" className="ml-2">추천</Badge>
                          )}
                        </div>
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                {availableModels[selectedModel] && (
                  <div className="text-xs text-gray-500 space-y-1">
                    <p>⚡ 속도: {availableModels[selectedModel].speed}</p>
                    <p>🎯 품질: {availableModels[selectedModel].quality}</p>
                    <p>💰 비용: {availableModels[selectedModel].cost}</p>
                  </div>
                )}
              </div>

              <div className="space-y-2">
                <label className="text-sm font-medium">처리 모드</label>
                <Select value={processingMode} onValueChange={setProcessingMode}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="advanced">
                      <div className="flex items-center gap-2">
                        <Brain className="w-4 h-4" />
                        고급 처리 (품질 분석 + 자동 재처리)
                      </div>
                    </SelectItem>
                    <SelectItem value="streaming">
                      <div className="flex items-center gap-2">
                        <Zap className="w-4 h-4" />
                        실시간 스트리밍
                      </div>
                    </SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>

            {/* 🆕 Phase 3.2.3: 배경 및 템플릿 설정 */}
            <div className="mt-6 p-4 bg-gradient-to-r from-purple-50 to-blue-50 rounded-lg border border-purple-200">
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="text-lg font-medium text-purple-900">🎬 배경 비디오 설정</h3>
                    <p className="text-sm text-purple-700">동적 배경 템플릿으로 전문적인 영상을 만들어보세요</p>
                  </div>
                  <div className="flex items-center">
                    <input
                      type="checkbox"
                      id="use-template"
                      checked={useTemplateBackground}
                      onChange={(e) => setUseTemplateBackground(e.target.checked)}
                      className="w-4 h-4 text-purple-600 bg-white border-purple-300 rounded focus:ring-purple-500"
                    />
                    <label htmlFor="use-template" className="ml-2 text-sm font-medium text-purple-900 cursor-pointer">
                      템플릿 배경 사용
                    </label>
                  </div>
                </div>

                {useTemplateBackground && (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {/* 템플릿 선택 */}
                    <div className="space-y-2">
                      <label className="text-sm font-medium text-purple-900">배경 템플릿</label>
                      <Select value={templateName} onValueChange={setTemplateName}>
                        <SelectTrigger className="bg-white">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {Object.entries(availableTemplates).map(([key, template]: [string, any]) => (
                            <SelectItem key={key} value={key}>
                              <div className="flex items-center justify-between w-full">
                                <div>
                                  <div className="font-medium">{template.name}</div>
                                  <div className="text-xs text-gray-500">{template.description}</div>
                                </div>
                                {template.available && (
                                  <Badge variant="secondary" className="ml-2">사용가능</Badge>
                                )}
                              </div>
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                      {availableTemplates[templateName] && (
                        <div className="text-xs text-purple-600 space-y-1">
                          <p>🎭 카테고리: {availableTemplates[templateName].category}</p>
                          <p>⏱️ 길이: {availableTemplates[templateName].duration?.toFixed(1)}초</p>
                          <p>📺 해상도: {availableTemplates[templateName].resolution}</p>
                        </div>
                      )}
                    </div>

                    {/* 비디오 해상도 */}
                    <div className="space-y-2">
                      <label className="text-sm font-medium text-purple-900">비디오 해상도</label>
                      <Select value={videoResolution} onValueChange={setVideoResolution}>
                        <SelectTrigger className="bg-white">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {Object.entries(availableResolutions).map(([key, info]) => (
                            <SelectItem key={key} value={key}>
                              <div className="flex items-center justify-between w-full">
                                <span>{info.description} ({info.size})</span>
                                {info.default && (
                                  <Badge variant="outline" className="ml-2">기본값</Badge>
                                )}
                              </div>
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                      {availableResolutions[videoResolution] && (
                        <div className="text-xs text-purple-600 space-y-1">
                          <p>🎬 크기: {availableResolutions[videoResolution].size}</p>
                          <p>📺 용도: {availableResolutions[videoResolution].recommended_for}</p>
                        </div>
                      )}
                    </div>
                  </div>
                )}

                {/* 🌟 트랜지션 효과 설정 */}
                {useTemplateBackground && (
                  <div className="mt-4 p-4 bg-white rounded-lg border border-purple-100">
                    <h4 className="text-sm font-medium text-purple-900 mb-3 flex items-center gap-2">
                      🌟 트랜지션 효과 
                      <Badge variant="secondary" className="text-xs">Phase 3.2.3</Badge>
                    </h4>
                    
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                      {/* 트랜지션 타입 */}
                      <div className="space-y-2">
                        <label className="text-xs font-medium text-gray-700">전환 효과</label>
                        <Select value={transitionType} onValueChange={setTransitionType}>
                          <SelectTrigger className="h-8">
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="fade">
                              <div className="flex items-center gap-2">
                                <div className="w-2 h-2 bg-black rounded-full"></div>
                                페이드 (부드러운 전환)
                              </div>
                            </SelectItem>
                            <SelectItem value="crossfade">
                              <div className="flex items-center gap-2">
                                <div className="w-2 h-2 bg-gradient-to-r from-blue-500 to-purple-500 rounded-full"></div>
                                크로스페이드 (겹침 전환)
                              </div>
                            </SelectItem>
                            <SelectItem value="dissolve">
                              <div className="flex items-center gap-2">
                                <div className="w-2 h-2 bg-gradient-to-br from-pink-400 to-orange-400 rounded-full"></div>
                                디졸브 (용해 전환)
                              </div>
                            </SelectItem>
                            <SelectItem value="none">
                              <div className="flex items-center gap-2">
                                <div className="w-2 h-2 bg-gray-400 rounded-full"></div>
                                없음 (즉시 전환)
                              </div>
                            </SelectItem>
                          </SelectContent>
                        </Select>
                      </div>

                      {/* 트랜지션 길이 */}
                      <div className="space-y-2">
                        <label className="text-xs font-medium text-gray-700">
                          전환 길이: {transitionDuration.toFixed(1)}초
                        </label>
                        <input
                          type="range"
                          min="0.3"
                          max="3.0"
                          step="0.1"
                          value={transitionDuration}
                          onChange={(e) => setTransitionDuration(parseFloat(e.target.value))}
                          className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer"
                          disabled={transitionType === 'none'}
                        />
                        <div className="flex justify-between text-xs text-gray-500">
                          <span>빠름</span>
                          <span>느림</span>
                        </div>
                      </div>

                      {/* 트랜지션 강도 */}
                      <div className="space-y-2">
                        <label className="text-xs font-medium text-gray-700">
                          전환 강도: {(transitionIntensity * 100).toFixed(0)}%
                        </label>
                        <input
                          type="range"
                          min="0.1"
                          max="1.0"
                          step="0.1"
                          value={transitionIntensity}
                          onChange={(e) => setTransitionIntensity(parseFloat(e.target.value))}
                          className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer"
                          disabled={transitionType === 'none'}
                        />
                        <div className="flex justify-between text-xs text-gray-500">
                          <span>약함</span>
                          <span>강함</span>
                        </div>
                      </div>
                    </div>

                    {/* 트랜지션 설명 */}
                    <div className="mt-3 p-2 bg-purple-50 rounded text-xs text-purple-700">
                      {transitionType === 'fade' && '🌑 템플릿이 부드럽게 어두워졌다가 다시 밝아지며 전환됩니다'}
                      {transitionType === 'crossfade' && '🌈 이전 루프와 다음 루프가 자연스럽게 겹쳐지며 전환됩니다'}
                      {transitionType === 'dissolve' && '✨ 픽셀 단위로 서서히 용해되며 아티스틱하게 전환됩니다'}
                      {transitionType === 'none' && '⚡ 트랜지션 효과 없이 즉시 전환됩니다 (빠른 처리)'}
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* 🆕 GPT 후처리 옵션 */}
            {processingMode === 'advanced' && (
              <div className="mt-4 p-4 bg-blue-50 rounded-lg border border-blue-200">
                <div className="flex items-center justify-between">
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <label className="text-sm font-medium text-blue-900">🤖 GPT 후처리</label>
                      <Badge variant="secondary" className="text-xs">새로운 기능!</Badge>
                    </div>
                    <p className="text-xs text-blue-700">
                      AI로 맞춤법, 띄어쓰기, 자연스러운 표현을 교정합니다
                    </p>
                  </div>
                  <div className="flex items-center">
                    <input
                      type="checkbox"
                      id="gpt-postprocessing"
                      checked={enableGptPostprocessing}
                      onChange={(e) => setEnableGptPostprocessing(e.target.checked)}
                      className="w-4 h-4 text-blue-600 bg-gray-100 border-gray-300 rounded focus:ring-blue-500"
                    />
                    <label 
                      htmlFor="gpt-postprocessing" 
                      className="ml-2 text-sm font-medium text-blue-900 cursor-pointer"
                    >
                      사용
                    </label>
                  </div>
                </div>
                
                {enableGptPostprocessing && (
                  <div className="mt-3 p-3 bg-white rounded border border-blue-100">
                    <div className="text-xs text-blue-800 space-y-1">
                      <p>✅ 한국어 맞춤법 자동 교정</p>
                      <p>✅ 자연스러운 띄어쓰기 정규화</p>
                      <p>✅ 구어체 → 문어체 자연 변환</p>
                      <p>⚠️ 추가 처리 시간: +10-30초</p>
                    </div>
                  </div>
                )}
              </div>
            )}

            <div className="flex gap-2 mt-4">
              <Button 
                onClick={processAudio} 
                disabled={isProcessing}
                className="flex-1"
              >
                {isProcessing ? (
                  <>
                    <Clock className="w-4 h-4 mr-2 animate-spin" />
                    처리 중...
                  </>
                ) : (
                  <>
                    <Play className="w-4 h-4 mr-2" />
                    음성 처리 시작
                  </>
                )}
              </Button>

              <Button 
                onClick={analyzeQuality} 
                variant="outline"
                disabled={isProcessing}
              >
                <BarChart3 className="w-4 h-4 mr-2" />
                품질 분석
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* 진행률 */}
      {isProcessing && (
        <Card>
          <CardContent className="pt-6">
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium">처리 진행률</span>
                <span className="text-sm text-gray-500">{Math.round(progress)}%</span>
              </div>
              <Progress value={progress} className="w-full" />
              
              {streamingProgress && (
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span>청크 진행:</span>
                    <span>{streamingProgress.processed_chunks}/{streamingProgress.total_chunks}</span>
                  </div>
                  {streamingProgress.estimated_remaining_time > 0 && (
                    <div className="flex justify-between">
                      <span>예상 남은 시간:</span>
                      <span>{Math.round(streamingProgress.estimated_remaining_time)}초</span>
                    </div>
                  )}
                  {streamingProgress.current_text && (
                    <div className="p-2 bg-gray-50 rounded text-xs">
                      <strong>현재 텍스트:</strong> {streamingProgress.current_text.slice(0, 100)}...
                    </div>
                  )}
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      )}

      {/* 오류 표시 */}
      {error && (
        <Alert className="border-red-200 bg-red-50">
          <AlertCircle className="h-4 w-4 text-red-600" />
          <AlertDescription className="text-red-800">
            {error}
          </AlertDescription>
        </Alert>
      )}

      {/* 결과 */}
      {result && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <CheckCircle className="w-5 h-5 text-green-600" />
              처리 완료
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center justify-between p-4 bg-green-50 rounded-lg">
              <div>
                <p className="font-medium text-green-800">자막 비디오가 생성되었습니다!</p>
                <p className="text-sm text-green-600">
                  세그먼트: {result.segments_count}개 • 
                  모델: {result.model_used || selectedModel} •
                  해상도: {result.video_resolution || videoResolution}  {/* 🆕 해상도 표시 */}
                  {result.reprocessed && (
                    <Badge variant="outline" className="ml-2">재처리됨</Badge>
                  )}
                  {result.gpt_correction_applied && (
                    <Badge variant="secondary" className="ml-2">GPT교정됨</Badge>
                  )}
                </p>
                {/* 🆕 GPT 후처리 결과 표시 */}
                {result.gpt_correction_applied && (
                  <div className="mt-2 text-xs text-green-700">
                    🤖 {result.total_corrections}개 항목이 교정되었습니다 
                    ({result.correction_strategy})
                  </div>
                )}
              </div>
              <Button asChild>
                <a href={`${API_BASE}${result.download_url}`} download>
                  <Download className="w-4 h-4 mr-2" />
                  다운로드
                </a>
              </Button>
            </div>

            {result.transcript && (
              <div className="space-y-2">
                <h4 className="font-medium">전사 결과:</h4>
                <div className="p-3 bg-white border border-gray-200 rounded text-sm max-h-40 overflow-y-auto text-gray-900">
                  {result.transcript}
                </div>
              </div>
            )}

            {/* 🆕 GPT 후처리 세부 정보 */}
            {result.gpt_correction_applied && result.gpt_improvements && (
              <div className="space-y-2">
                <h4 className="font-medium flex items-center gap-2">
                  🤖 GPT 후처리 결과
                  <Badge variant="secondary" className="text-xs">
                    품질 점수: {(result.gpt_quality_score * 100).toFixed(0)}%
                  </Badge>
                </h4>
                <div className="p-3 bg-blue-50 rounded border border-blue-200">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
                    <div>
                      <p className="font-medium text-blue-900">교정 통계:</p>
                      <ul className="text-blue-800 space-y-1 mt-1">
                        <li>• 교정된 항목: {result.total_corrections}개</li>
                        <li>• 교정 전략: {result.correction_strategy}</li>
                        <li>• 처리 시간: {result.gpt_processing_time?.toFixed(1)}초</li>
                      </ul>
                    </div>
                    <div>
                      <p className="font-medium text-blue-900">개선 내용:</p>
                      <ul className="text-blue-800 space-y-1 mt-1">
                        {result.gpt_improvements.slice(0, 3).map((improvement, index) => (
                          <li key={index}>• {improvement}</li>
                        ))}
                      </ul>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* 품질 분석 결과 */}
      {qualityAnalysis && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Target className="w-5 h-5" />
              품질 분석 결과
            </CardTitle>
          </CardHeader>
          <CardContent>
            <Tabs defaultValue="overview" className="w-full">
              <TabsList className="grid w-full grid-cols-3">
                <TabsTrigger value="overview">종합</TabsTrigger>
                <TabsTrigger value="details">세부</TabsTrigger>
                <TabsTrigger value="suggestions">제안</TabsTrigger>
              </TabsList>

              <TabsContent value="overview" className="space-y-4">
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  <div className="text-center p-3 bg-gray-50 rounded">
                    <div className={`text-2xl font-bold ${getQualityColor(qualityAnalysis.overall_score)}`}>
                      {(qualityAnalysis.overall_score * 100).toFixed(0)}%
                    </div>
                    <div className="text-sm text-gray-600">전체 점수</div>
                    <Badge {...getQualityBadge(qualityAnalysis.overall_score)} className="mt-1" />
                  </div>

                  <div className="text-center p-3 bg-gray-50 rounded">
                    <div className={`text-2xl font-bold ${getQualityColor(qualityAnalysis.confidence_score)}`}>
                      {(qualityAnalysis.confidence_score * 100).toFixed(0)}%
                    </div>
                    <div className="text-sm text-gray-600">신뢰도</div>
                  </div>

                  <div className="text-center p-3 bg-gray-50 rounded">
                    <div className={`text-2xl font-bold ${getQualityColor(qualityAnalysis.korean_quality_score)}`}>
                      {(qualityAnalysis.korean_quality_score * 100).toFixed(0)}%
                    </div>
                    <div className="text-sm text-gray-600">한국어 품질</div>
                  </div>

                  <div className="text-center p-3 bg-gray-50 rounded">
                    <div className={`text-2xl font-bold ${getQualityColor(qualityAnalysis.grammar_score)}`}>
                      {(qualityAnalysis.grammar_score * 100).toFixed(0)}%
                    </div>
                    <div className="text-sm text-gray-600">문법 점수</div>
                  </div>
                </div>

                {qualityAnalysis.needs_reprocessing && (
                  <Alert className="border-orange-200 bg-orange-50">
                    <Repeat className="h-4 w-4 text-orange-600" />
                    <AlertDescription className="text-orange-800">
                      품질 향상을 위해 재처리를 권장합니다.
                      {qualityAnalysis.recommended_model && (
                        <span className="block mt-1">
                          추천 모델: <strong>{qualityAnalysis.recommended_model}</strong>
                        </span>
                      )}
                    </AlertDescription>
                  </Alert>
                )}
              </TabsContent>

              <TabsContent value="details" className="space-y-4">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <h4 className="font-medium">일관성 점수</h4>
                    <Progress value={qualityAnalysis.consistency_score * 100} />
                    <p className="text-sm text-gray-600">
                      {(qualityAnalysis.consistency_score * 100).toFixed(1)}%
                    </p>
                  </div>

                  <div className="space-y-2">
                    <h4 className="font-medium">완성도 점수</h4>
                    <Progress value={qualityAnalysis.completeness_score * 100} />
                    <p className="text-sm text-gray-600">
                      {(qualityAnalysis.completeness_score * 100).toFixed(1)}%
                    </p>
                  </div>
                </div>
              </TabsContent>

              <TabsContent value="suggestions" className="space-y-3">
                {qualityAnalysis.improvement_suggestions.length > 0 ? (
                  qualityAnalysis.improvement_suggestions.map((suggestion, index) => (
                    <Alert key={index} className="border-blue-200 bg-blue-50">
                      <AlertDescription className="text-blue-800">
                        💡 {suggestion}
                      </AlertDescription>
                    </Alert>
                  ))
                ) : (
                  <Alert className="border-green-200 bg-green-50">
                    <CheckCircle className="h-4 w-4 text-green-600" />
                    <AlertDescription className="text-green-800">
                      품질이 우수합니다! 추가 개선사항이 없습니다.
                    </AlertDescription>
                  </Alert>
                )}
              </TabsContent>
            </Tabs>
          </CardContent>
        </Card>
      )}
    </div>
  );
};

export default Phase2AudioProcessor;