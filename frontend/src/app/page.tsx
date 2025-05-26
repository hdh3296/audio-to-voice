'use client';

import { useState, useCallback } from 'react';
import { Upload, Download, Play, FileAudio, Film, Loader2, CheckCircle, AlertCircle } from 'lucide-react';
import axios from 'axios';

const API_BASE_URL = 'http://localhost:8000';

interface UploadResult {
  file_id: string;
  filename: string;
  original_name: string;
  size: number;
  message: string;
}

interface GenerateResult {
  file_id: string;
  output_file: string;
  download_url: string;
  transcript: string;
  segments_count: number;
  language: string;
  message: string;
}

type ProcessStatus = 'idle' | 'uploading' | 'processing' | 'completed' | 'error';

export default function HomePage() {
  const [file, setFile] = useState<File | null>(null);
  const [uploadResult, setUploadResult] = useState<UploadResult | null>(null);
  const [generateResult, setGenerateResult] = useState<GenerateResult | null>(null);
  const [status, setStatus] = useState<ProcessStatus>('idle');
  const [error, setError] = useState<string>('');
  const [dragActive, setDragActive] = useState(false);
  
  // 설정 (한국어 최적화)
  const [model, setModel] = useState('large-v3');  // 한국어 정확도를 위해 large-v3 기본값
  const [language, setLanguage] = useState('ko');   // 한국어 기본 설정
  const [task, setTask] = useState('transcribe');
  const [backgroundColor, setBackgroundColor] = useState('black');

  const handleDrag = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    
    const files = e.dataTransfer.files;
    if (files && files[0]) {
      handleFileSelect(files[0]);
    }
  }, []);

  const handleFileSelect = (selectedFile: File) => {
    // 지원 형식 검증
    const supportedFormats = ['.mp3', '.wav', '.m4a', '.aac', '.flac', '.ogg'];
    const fileExtension = '.' + selectedFile.name.split('.').pop()?.toLowerCase();
    
    if (!supportedFormats.includes(fileExtension)) {
      setError(`지원하지 않는 파일 형식입니다. 지원 형식: ${supportedFormats.join(', ')}`);
      return;
    }
    
    setFile(selectedFile);
    setError('');
    setUploadResult(null);
    setGenerateResult(null);
    setStatus('idle');
  };

  const uploadFile = async () => {
    if (!file) return;
    
    setStatus('uploading');
    setError('');
    
    try {
      const formData = new FormData();
      formData.append('file', file);
      
      const response = await axios.post<UploadResult>(
        `${API_BASE_URL}/upload-audio`,
        formData,
        {
          headers: {
            'Content-Type': 'multipart/form-data',
          },
        }
      );
      
      setUploadResult(response.data);
      setStatus('idle');
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Upload failed');
      setStatus('error');
    }
  };

  const generateSubtitles = async () => {
    if (!uploadResult) return;
    
    setStatus('processing');
    setError('');
    
    try {
      const response = await axios.post<GenerateResult>(
        `${API_BASE_URL}/generate-subtitles/${uploadResult.file_id}`,
        null,
        {
          params: {
            model,
            language: language || undefined,
            task,
            background_color: backgroundColor,
          },
        }
      );
      
      setGenerateResult(response.data);
      setStatus('completed');
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Generation failed');
      setStatus('error');
    }
  };

  const downloadVideo = () => {
    if (generateResult) {
      const link = document.createElement('a');
      link.href = `${API_BASE_URL}${generateResult.download_url}`;
      link.download = generateResult.output_file;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    }
  };

  const reset = () => {
    setFile(null);
    setUploadResult(null);
    setGenerateResult(null);
    setStatus('idle');
    setError('');
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 py-8">
      <div className="max-w-4xl mx-auto px-4">
        {/* 헤더 */}
        <div className="text-center mb-8">
          <h1 className="text-4xl font-bold text-gray-900 mb-2">
            🎵 Audio to Voice (한국어 최적화)
          </h1>
          <p className="text-lg text-gray-600">
            한국어 오디오 파일을 정확한 자막이 있는 비디오로 변환하세요
          </p>
        </div>

        {/* 메인 카드 */}
        <div className="bg-white rounded-2xl shadow-xl p-8">
          {/* 파일 업로드 영역 */}
          {!file && (
            <div
              className={`border-2 border-dashed rounded-xl p-8 text-center transition-colors ${
                dragActive
                  ? 'border-blue-500 bg-blue-50'
                  : 'border-gray-300 hover:border-gray-400'
              }`}
              onDragEnter={handleDrag}
              onDragLeave={handleDrag}
              onDragOver={handleDrag}
              onDrop={handleDrop}
            >
              <FileAudio className="mx-auto h-16 w-16 text-gray-400 mb-4" />
              <p className="text-xl font-medium text-gray-700 mb-2">
                오디오 파일을 드래그하거나 클릭하여 선택하세요
              </p>
              <p className="text-sm text-gray-500 mb-4">
                지원 형식: MP3, WAV, M4A, AAC, FLAC, OGG
              </p>
              <input
                type="file"
                accept=".mp3,.wav,.m4a,.aac,.flac,.ogg"
                onChange={(e) => e.target.files && handleFileSelect(e.target.files[0])}
                className="hidden"
                id="file-upload"
              />
              <label
                htmlFor="file-upload"
                className="inline-flex items-center px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 cursor-pointer transition-colors"
              >
                <Upload className="w-5 h-5 mr-2" />
                파일 선택
              </label>
            </div>
          )}

          {/* 선택된 파일 정보 */}
          {file && !uploadResult && (
            <div className="bg-gray-50 rounded-xl p-6">
              <div className="flex items-center justify-between">
                <div className="flex items-center">
                  <FileAudio className="w-8 h-8 text-blue-600 mr-3" />
                  <div>
                    <p className="font-medium text-gray-900">{file.name}</p>
                    <p className="text-sm text-gray-500">
                      {(file.size / 1024 / 1024).toFixed(2)} MB
                    </p>
                  </div>
                </div>
                <div className="flex space-x-3">
                  <button
                    onClick={reset}
                    className="px-4 py-2 text-gray-600 hover:text-gray-800 transition-colors"
                  >
                    취소
                  </button>
                  <button
                    onClick={uploadFile}
                    disabled={status === 'uploading'}
                    className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 flex items-center transition-colors"
                  >
                    {status === 'uploading' ? (
                      <>
                        <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                        업로드 중...
                      </>
                    ) : (
                      <>
                        <Upload className="w-4 h-4 mr-2" />
                        업로드
                      </>
                    )}
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* 업로드 완료 */}
          {uploadResult && !generateResult && (
            <div className="space-y-6">
              <div className="bg-green-50 border border-green-200 rounded-xl p-6">
                <div className="flex items-center">
                  <CheckCircle className="w-8 h-8 text-green-600 mr-3" />
                  <div>
                    <p className="font-medium text-green-800">업로드 완료!</p>
                    <p className="text-sm text-green-600">{uploadResult.message}</p>
                  </div>
                </div>
              </div>

              {/* 설정 옵션 */}
              <div className="bg-gray-50 rounded-xl p-6">
                <h3 className="text-lg font-medium text-gray-900 mb-4">생성 옵션</h3>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      모델 크기
                    </label>
                    <select
                      value={model}
                      onChange={(e) => setModel(e.target.value)}
                      className="w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    >
                      <option value="tiny">Tiny (가장 빠름, 낮은 정확도)</option>
                      <option value="base">Base (빠름, 보통 정확도)</option>
                      <option value="small">Small (보통 속도, 좋은 정확도)</option>
                      <option value="medium">Medium (느림, 높은 정확도)</option>
                      <option value="large-v3">Large-v3 (가장 정확, 한국어 추천) ⭐</option>
                      <option value="large-v3-turbo">Large-v3-turbo (빠르고 정확)</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      언어 설정
                    </label>
                    <select
                      value={language}
                      onChange={(e) => setLanguage(e.target.value)}
                      className="w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    >
                      <option value="ko">한국어 (Korean) 🇰🇷</option>
                      <option value="en">영어 (English)</option>
                      <option value="ja">일본어 (Japanese)</option>
                      <option value="zh">중국어 (Chinese)</option>
                      <option value="">자동 감지</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      작업 유형
                    </label>
                    <select
                      value={task}
                      onChange={(e) => setTask(e.target.value)}
                      className="w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    >
                      <option value="transcribe">전사</option>
                      <option value="translate">영어 번역</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      배경색
                    </label>
                    <select
                      value={backgroundColor}
                      onChange={(e) => setBackgroundColor(e.target.value)}
                      className="w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    >
                      <option value="black">검정</option>
                      <option value="white">흰색</option>
                      <option value="blue">파랑</option>
                      <option value="red">빨강</option>
                    </select>
                  </div>
                </div>
              </div>

              <button
                onClick={generateSubtitles}
                disabled={status === 'processing'}
                className="w-full py-4 bg-green-600 text-white rounded-xl hover:bg-green-700 disabled:opacity-50 flex items-center justify-center text-lg font-medium transition-colors"
              >
                {status === 'processing' ? (
                  <>
                    <Loader2 className="w-5 h-5 mr-2 animate-spin" />
                    자막 비디오 생성 중...
                  </>
                ) : (
                  <>
                    <Film className="w-5 h-5 mr-2" />
                    자막 비디오 생성
                  </>
                )}
              </button>
            </div>
          )}

          {/* 생성 완료 */}
          {generateResult && (
            <div className="space-y-6">
              <div className="bg-green-50 border border-green-200 rounded-xl p-6">
                <div className="flex items-center">
                  <CheckCircle className="w-8 h-8 text-green-600 mr-3" />
                  <div>
                    <p className="font-medium text-green-800">생성 완료!</p>
                    <p className="text-sm text-green-600">{generateResult.message}</p>
                  </div>
                </div>
              </div>

              {/* 결과 정보 */}
              <div className="bg-blue-50 rounded-xl p-6">
                <h3 className="text-lg font-medium text-gray-900 mb-4">생성 결과</h3>
                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div>
                    <span className="font-medium text-gray-700">언어:</span>
                    <span className="ml-2 text-gray-600">{generateResult.language}</span>
                  </div>
                  <div>
                    <span className="font-medium text-gray-700">자막 수:</span>
                    <span className="ml-2 text-gray-600">{generateResult.segments_count}개</span>
                  </div>
                </div>
                <div className="mt-4">
                  <span className="font-medium text-gray-700">전사 텍스트:</span>
                  <p className="mt-2 text-gray-600 bg-white p-3 rounded-lg border max-h-32 overflow-y-auto">
                    {generateResult.transcript}
                  </p>
                </div>
              </div>

              {/* 액션 버튼 */}
              <div className="flex space-x-4">
                <button
                  onClick={downloadVideo}
                  className="flex-1 py-3 bg-blue-600 text-white rounded-xl hover:bg-blue-700 flex items-center justify-center font-medium transition-colors"
                >
                  <Download className="w-5 h-5 mr-2" />
                  비디오 다운로드
                </button>
                <button
                  onClick={reset}
                  className="px-6 py-3 border border-gray-300 text-gray-700 rounded-xl hover:bg-gray-50 transition-colors"
                >
                  새로 시작
                </button>
              </div>
            </div>
          )}

          {/* 에러 메시지 */}
          {error && (
            <div className="bg-red-50 border border-red-200 rounded-xl p-6">
              <div className="flex items-center">
                <AlertCircle className="w-8 h-8 text-red-600 mr-3" />
                <div>
                  <p className="font-medium text-red-800">오류 발생</p>
                  <p className="text-sm text-red-600">{error}</p>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* 푸터 */}
        <div className="text-center mt-8 text-gray-500">
          <p>Powered by OpenAI Whisper & FFmpeg</p>
        </div>
      </div>
    </div>
  );
}
