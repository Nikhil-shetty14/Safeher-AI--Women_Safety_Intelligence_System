import React, { useState, useEffect, useRef } from 'react';
import { View, Text, StyleSheet, TouchableOpacity, ActivityIndicator, StyleProp, ViewStyle, Platform } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { createAudioPlayer, setAudioModeAsync, AudioPlayer } from 'expo-audio';
import { BASE_URL } from '../api/client';
import { Colors, Typography, Spacing, BorderRadius, Shadows } from '../constants/theme';

interface AudioEvidencePlayerProps {
  audioUri?: string | null;
  title?: string;
  transcript?: string;
  stressScore?: number | string;
  threatLevel?: string;
  createdAt?: string;
  style?: StyleProp<ViewStyle>;
}

export const AudioEvidencePlayer: React.FC<AudioEvidencePlayerProps> = ({
  audioUri,
  title = 'Emergency Audio Evidence',
  transcript,
  stressScore,
  threatLevel,
  createdAt,
  style,
}) => {
  const [isPlaying, setIsPlaying] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [playbackError, setPlaybackError] = useState<string | null>(null);

  const playerRef = useRef<AudioPlayer | null>(null);
  const webAudioRef = useRef<any>(null);
  const timerRef = useRef<any>(null);

  // Clean up on unmount
  useEffect(() => {
    return () => {
      stopPlayback();
    };
  }, []);

  const resolveUrl = (uri: string): string => {
    if (!uri) return '';
    if (uri.startsWith('http://') || uri.startsWith('https://') || uri.startsWith('file://') || uri.startsWith('blob:')) {
      return uri;
    }
    // Prefix with backend host
    const cleanPath = uri.startsWith('/') ? uri : `/${uri}`;
    return `${BASE_URL}${cleanPath}`;
  };

  const stopPlayback = () => {
    if (timerRef.current) clearInterval(timerRef.current);
    if (playerRef.current) {
      try {
        playerRef.current.pause();
        playerRef.current.remove();
      } catch {}
      playerRef.current = null;
    }
    if (webAudioRef.current) {
      try {
        webAudioRef.current.pause();
      } catch {}
      webAudioRef.current = null;
    }
    setIsPlaying(false);
    setCurrentTime(0);
  };

  const handlePlayPause = async () => {
    if (!audioUri) {
      setPlaybackError('No audio stream available');
      return;
    }

    if (isPlaying) {
      stopPlayback();
      return;
    }

    const fullUrl = resolveUrl(audioUri);
    setPlaybackError(null);
    setIsLoading(true);

    try {
      if (Platform.OS === 'web' && typeof Audio !== 'undefined') {
        // Standard Web Audio fallback
        stopPlayback();
        const audio = new Audio(fullUrl);
        webAudioRef.current = audio;

        audio.onloadedmetadata = () => {
          setDuration(Math.round(audio.duration) || 5);
          setIsLoading(false);
        };

        audio.onplay = () => setIsPlaying(true);
        audio.onended = () => {
          setIsPlaying(false);
          setCurrentTime(0);
        };
        audio.onerror = () => {
          setIsLoading(false);
          setIsPlaying(false);
          setPlaybackError('Could not stream audio');
        };

        await audio.play();
        setIsLoading(false);
        setIsPlaying(true);

        timerRef.current = setInterval(() => {
          if (audio && !audio.paused) {
            setCurrentTime(Math.round(audio.currentTime));
          }
        }, 500);
      } else {
        // Expo Audio Player for Native Android & iOS
        await setAudioModeAsync({
          allowsRecording: false,
          playsInSilentMode: true,
        });

        stopPlayback();
        const player = createAudioPlayer(fullUrl);
        playerRef.current = player;

        (player as any).addListener('playbackStatusUpdate', (status: any) => {
          if (status.currentTime !== undefined) {
            setCurrentTime(Math.round(status.currentTime));
          }
          if (status.duration !== undefined && status.duration > 0) {
            setDuration(Math.round(status.duration));
          }
          if (status.didJustFinish) {
            setIsPlaying(false);
            setCurrentTime(0);
          }
        });

        player.play();
        setIsLoading(false);
        setIsPlaying(true);
      }
    } catch (err: any) {
      console.warn('[AudioEvidencePlayer] Playback error:', err);
      setIsLoading(false);
      setIsPlaying(false);
      setPlaybackError('Audio playback unavailable');
    }
  };

  const formatSecs = (sec: number) => {
    const m = Math.floor(sec / 60);
    const s = Math.floor(sec % 60);
    return `${m}:${s < 10 ? '0' : ''}${s}`;
  };

  if (!audioUri && !transcript) {
    return null;
  }

  return (
    <View style={[styles.card, style]}>
      {/* Header */}
      <View style={styles.headerRow}>
        <View style={styles.titleGroup}>
          <View style={styles.micCircle}>
            <Ionicons name="mic" size={16} color="#10B981" />
          </View>
          <View>
            <Text style={styles.title}>{title}</Text>
            {createdAt ? <Text style={styles.timestamp}>{new Date(createdAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</Text> : null}
          </View>
        </View>

        {threatLevel ? (
          <View style={[styles.threatBadge, threatLevel.toLowerCase() === 'critical' ? styles.threatCritical : styles.threatHigh]}>
            <Text style={styles.threatText}>{threatLevel.toUpperCase()}</Text>
          </View>
        ) : null}
      </View>

      {/* Playback Controls & Waveform Bar */}
      {audioUri ? (
        <View style={styles.playerControlsRow}>
          <TouchableOpacity
            style={[styles.playBtn, isPlaying && styles.playBtnActive]}
            onPress={handlePlayPause}
            disabled={isLoading}
            activeOpacity={0.8}
          >
            {isLoading ? (
              <ActivityIndicator size="small" color="#FFFFFF" />
            ) : (
              <Ionicons name={isPlaying ? 'pause' : 'play'} size={18} color="#FFFFFF" />
            )}
          </TouchableOpacity>

          <View style={styles.trackInfoColumn}>
            {/* Waveform graphic simulator */}
            <View style={styles.waveformContainer}>
              {[8, 16, 24, 12, 28, 20, 14, 26, 18, 10, 22, 16, 28, 14, 8, 20].map((h, i) => (
                <View
                  key={i}
                  style={[
                    styles.waveformBar,
                    {
                      height: isPlaying ? Math.max(6, (h * ((i % 3) + 1)) % 26) : h * 0.7,
                      backgroundColor: isPlaying ? '#10B981' : '#64748B',
                      opacity: isPlaying ? 0.9 : 0.5,
                    },
                  ]}
                />
              ))}
            </View>

            <View style={styles.timeRow}>
              <Text style={styles.timeText}>
                {isPlaying ? formatSecs(currentTime) : '0:00'}
              </Text>
              <Text style={styles.timeDurationText}>
                {duration > 0 ? formatSecs(duration) : 'Recorded Audio'}
              </Text>
            </View>
          </View>
        </View>
      ) : null}

      {playbackError ? (
        <Text style={styles.errorText}>⚠️ {playbackError}</Text>
      ) : null}

      {/* AI Whisper STT Transcription */}
      {transcript ? (
        <View style={styles.transcriptCard}>
          <View style={styles.transcriptHeader}>
            <Ionicons name="chatbox-ellipses" size={13} color="#A78BFA" />
            <Text style={styles.transcriptHeaderTitle}>Whisper AI Speech-To-Text:</Text>
          </View>
          <Text style={styles.transcriptBody}>"{transcript}"</Text>
        </View>
      ) : null}

      {/* Librosa Acoustic Stress Intelligence */}
      {stressScore !== undefined && stressScore !== null ? (
        <View style={styles.stressRow}>
          <Ionicons name="pulse" size={14} color="#EF4444" />
          <Text style={styles.stressLabel}>Acoustic Distress Index:</Text>
          <Text style={styles.stressValue}>
            {typeof stressScore === 'number' ? `${Math.round(stressScore > 1 ? stressScore : stressScore * 100)}% Stress` : stressScore}
          </Text>
        </View>
      ) : null}
    </View>
  );
};

const styles = StyleSheet.create({
  card: {
    backgroundColor: 'rgba(26, 16, 51, 0.92)',
    borderRadius: BorderRadius.lg,
    padding: Spacing.md,
    borderWidth: 1,
    borderColor: 'rgba(16, 185, 129, 0.35)',
    marginVertical: 6,
    ...Shadows.card,
  },
  headerRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 10,
  },
  titleGroup: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    flex: 1,
  },
  micCircle: {
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: 'rgba(16, 185, 129, 0.15)',
    borderWidth: 1,
    borderColor: '#10B981',
    justifyContent: 'center',
    alignItems: 'center',
  },
  title: {
    fontSize: 13,
    fontWeight: '800',
    color: '#FFFFFF',
    letterSpacing: 0.2,
  },
  timestamp: {
    fontSize: 10,
    color: '#94A3B8',
    marginTop: 1,
  },
  threatBadge: {
    paddingHorizontal: 7,
    paddingVertical: 2,
    borderRadius: 8,
  },
  threatCritical: {
    backgroundColor: 'rgba(220, 38, 38, 0.2)',
    borderWidth: 1,
    borderColor: '#DC2626',
  },
  threatHigh: {
    backgroundColor: 'rgba(245, 158, 11, 0.2)',
    borderWidth: 1,
    borderColor: '#F59E0B',
  },
  threatText: {
    fontSize: 9,
    fontWeight: '800',
    color: '#FCA5A5',
  },
  playerControlsRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    backgroundColor: 'rgba(0, 0, 0, 0.25)',
    padding: 10,
    borderRadius: BorderRadius.md,
    marginBottom: 8,
  },
  playBtn: {
    width: 38,
    height: 38,
    borderRadius: 19,
    backgroundColor: '#059669',
    justifyContent: 'center',
    alignItems: 'center',
    shadowColor: '#10B981',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.4,
    shadowRadius: 4,
    elevation: 3,
  },
  playBtnActive: {
    backgroundColor: '#EF4444',
  },
  trackInfoColumn: {
    flex: 1,
    gap: 4,
  },
  waveformContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 3,
    height: 24,
  },
  waveformBar: {
    width: 3,
    borderRadius: 2,
  },
  timeRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  timeText: {
    fontSize: 10,
    color: '#10B981',
    fontWeight: '700',
  },
  timeDurationText: {
    fontSize: 10,
    color: '#94A3B8',
  },
  errorText: {
    fontSize: 11,
    color: '#EF4444',
    marginBottom: 6,
  },
  transcriptCard: {
    backgroundColor: 'rgba(139, 92, 246, 0.1)',
    borderRadius: BorderRadius.md,
    padding: 8,
    borderLeftWidth: 3,
    borderLeftColor: '#8B5CF6',
    marginTop: 6,
  },
  transcriptHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
    marginBottom: 3,
  },
  transcriptHeaderTitle: {
    fontSize: 10,
    color: '#A78BFA',
    fontWeight: '700',
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  transcriptBody: {
    fontSize: 12,
    color: '#F8F4FF',
    fontStyle: 'italic',
    lineHeight: 16,
  },
  stressRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    marginTop: 8,
    paddingTop: 6,
    borderTopWidth: 1,
    borderTopColor: 'rgba(255, 255, 255, 0.06)',
  },
  stressLabel: {
    fontSize: 11,
    color: '#94A3B8',
    fontWeight: '600',
  },
  stressValue: {
    fontSize: 11,
    color: '#EF4444',
    fontWeight: '800',
  },
});
