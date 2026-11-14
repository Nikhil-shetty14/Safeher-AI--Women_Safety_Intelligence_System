// Design system for SafeHer AI
export const Colors = {
  // Primary Purple Gradient
  primary: '#8B5CF6',
  primaryDark: '#6D28D9',
  primaryLight: '#A78BFA',

  // Accent Pink
  accent: '#EC4899',
  accentDark: '#BE185D',
  accentLight: '#F9A8D4',

  // Danger Red
  danger: '#EF4444',
  dangerDark: '#B91C1C',
  dangerLight: '#FCA5A5',

  // Warning
  warning: '#F59E0B',
  warningLight: '#FDE68A',

  // Success Green
  success: '#10B981',
  successLight: '#6EE7B7',

  // Background (dark mode)
  background: '#0F0A1E',
  backgroundSecondary: '#1A1033',
  card: '#1E1535',
  cardBorder: '#2D2050',

  // Text
  textPrimary: '#F8F4FF',
  textSecondary: '#B8A9D9',
  textMuted: '#6B5A8A',

  // Gradients (as arrays for LinearGradient)
  gradientPrimary: ['#8B5CF6', '#EC4899'] as const,
  gradientDanger: ['#EF4444', '#B91C1C'] as const,
  gradientCard: ['#1E1535', '#2D2050'] as const,
  gradientBg: ['#0F0A1E', '#1A1033'] as const,

  // SOS Severity
  severitySafe: '#10B981',
  severityLow: '#F59E0B',
  severityMedium: '#F97316',
  severityHigh: '#EF4444',
  severityCritical: '#DC2626',

  white: '#FFFFFF',
  black: '#000000',
  transparent: 'transparent',
};

export const Typography = {
  fontSizeXS: 10,
  fontSizeSM: 12,
  fontSizeMD: 14,
  fontSizeLG: 16,
  fontSizeXL: 18,
  fontSize2XL: 22,
  fontSize3XL: 28,
  fontSize4XL: 36,

  fontWeightLight: '300' as const,
  fontWeightRegular: '400' as const,
  fontWeightMedium: '500' as const,
  fontWeightSemibold: '600' as const,
  fontWeightBold: '700' as const,
  fontWeightExtrabold: '800' as const,
};

export const Spacing = {
  xs: 4,
  sm: 8,
  md: 16,
  lg: 24,
  xl: 32,
  xxl: 48,
};

export const BorderRadius = {
  sm: 8,
  md: 12,
  lg: 16,
  xl: 24,
  full: 9999,
};

export const Shadows = {
  card: {
    shadowColor: '#8B5CF6',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.15,
    shadowRadius: 12,
    elevation: 8,
  },
  danger: {
    shadowColor: '#EF4444',
    shadowOffset: { width: 0, height: 6 },
    shadowOpacity: 0.4,
    shadowRadius: 16,
    elevation: 12,
  },
};

export const getSeverityColor = (level: string): string => {
  const map: Record<string, string> = {
    safe: Colors.severitySafe,
    low: Colors.severityLow,
    medium: Colors.severityMedium,
    high: Colors.severityHigh,
    critical: Colors.severityCritical,
  };
  return map[level] ?? Colors.severityMedium;
};

// High-Definition Map Style exactly aligned with SafeHer AI Design System
// Palette: #0E0920 (Background), #160E30 (Card), #2D1F4E (Roads), #7C3AED (Highways), #FFFFFF (Labels)
export const SAFEHER_MAP_STYLE = [
  {
    elementType: 'geometry',
    stylers: [{ color: '#0E0920' }],
  },
  {
    elementType: 'labels.text.fill',
    stylers: [{ color: '#FFFFFF' }],
  },
  {
    elementType: 'labels.text.stroke',
    stylers: [{ color: '#0E0920' }, { weight: 3 }],
  },
  {
    featureType: 'administrative',
    elementType: 'geometry',
    stylers: [{ visibility: 'off' }],
  },
  {
    featureType: 'administrative.country',
    elementType: 'geometry.stroke',
    stylers: [{ color: '#4C338A' }, { visibility: 'on' }],
  },
  {
    featureType: 'administrative.province',
    elementType: 'geometry.stroke',
    stylers: [{ color: '#4C338A' }, { visibility: 'on' }],
  },
  {
    featureType: 'administrative.locality',
    elementType: 'labels.text.fill',
    stylers: [{ color: '#F8F4FF' }],
  },
  {
    featureType: 'landscape',
    elementType: 'geometry',
    stylers: [{ color: '#0E0920' }],
  },
  {
    featureType: 'landscape.man_made',
    elementType: 'geometry',
    stylers: [{ color: '#160E30' }],
  },
  {
    featureType: 'landscape.natural',
    elementType: 'geometry',
    stylers: [{ color: '#110926' }],
  },
  {
    featureType: 'poi',
    elementType: 'geometry',
    stylers: [{ color: '#1B113B' }],
  },
  {
    featureType: 'poi',
    elementType: 'labels.text.fill',
    stylers: [{ color: '#C4B5FD' }],
  },
  {
    featureType: 'poi.park',
    elementType: 'geometry',
    stylers: [{ color: '#0E2320' }],
  },
  {
    featureType: 'poi.park',
    elementType: 'labels.text.fill',
    stylers: [{ color: '#34D399' }],
  },
  {
    featureType: 'poi.medical',
    elementType: 'labels.text.fill',
    stylers: [{ color: '#F43F5E' }],
  },
  {
    featureType: 'poi.government',
    elementType: 'labels.text.fill',
    stylers: [{ color: '#A78BFA' }],
  },
  {
    featureType: 'road',
    elementType: 'geometry',
    stylers: [{ color: '#2D1F4E' }],
  },
  {
    featureType: 'road',
    elementType: 'geometry.stroke',
    stylers: [{ color: '#4A3382' }],
  },
  {
    featureType: 'road',
    elementType: 'labels.text.fill',
    stylers: [{ color: '#FFFFFF' }],
  },
  {
    featureType: 'road.arterial',
    elementType: 'geometry',
    stylers: [{ color: '#3B246C' }],
  },
  {
    featureType: 'road.arterial',
    elementType: 'geometry.stroke',
    stylers: [{ color: '#5D3B9E' }],
  },
  {
    featureType: 'road.highway',
    elementType: 'geometry',
    stylers: [{ color: '#7C3AED' }],
  },
  {
    featureType: 'road.highway',
    elementType: 'geometry.stroke',
    stylers: [{ color: '#A78BFA' }],
  },
  {
    featureType: 'road.highway',
    elementType: 'labels.text.fill',
    stylers: [{ color: '#FFFFFF' }],
  },
  {
    featureType: 'transit',
    elementType: 'geometry',
    stylers: [{ color: '#1E1438' }],
  },
  {
    featureType: 'transit.station',
    elementType: 'labels.text.fill',
    stylers: [{ color: '#C4B5FD' }],
  },
  {
    featureType: 'water',
    elementType: 'geometry',
    stylers: [{ color: '#0A182E' }],
  },
  {
    featureType: 'water',
    elementType: 'labels.text.fill',
    stylers: [{ color: '#38BDF8' }],
  },
];

// Clean Dark Base Map Style for high contrast navigation
export const CLEAN_DARK_BASE_STYLE = [
  { elementType: 'geometry', stylers: [{ color: '#0f172a' }] },
  { elementType: 'labels.text.fill', stylers: [{ color: '#f1f5f9' }] },
  { elementType: 'labels.text.stroke', stylers: [{ color: '#020617' }, { weight: 3 }] },
  { featureType: 'administrative', elementType: 'geometry', stylers: [{ color: '#475569' }] },
  { featureType: 'administrative.locality', elementType: 'labels.text.fill', stylers: [{ color: '#f8fafc' }] },
  { featureType: 'poi', elementType: 'geometry', stylers: [{ color: '#1e293b' }] },
  { featureType: 'poi', elementType: 'labels.text.fill', stylers: [{ color: '#cbd5e1' }] },
  { featureType: 'road', elementType: 'geometry', stylers: [{ color: '#2d3748' }] },
  { featureType: 'road', elementType: 'geometry.stroke', stylers: [{ color: '#4a5568' }] },
  { featureType: 'road', elementType: 'labels.text.fill', stylers: [{ color: '#ffffff' }] },
  { featureType: 'road.highway', elementType: 'geometry', stylers: [{ color: '#3b82f6' }] },
  { featureType: 'road.highway', elementType: 'geometry.stroke', stylers: [{ color: '#60a5fa' }] },
  { featureType: 'road.highway', elementType: 'labels.text.fill', stylers: [{ color: '#ffffff' }] },
  { featureType: 'road.arterial', elementType: 'geometry', stylers: [{ color: '#334155' }] },
  { featureType: 'transit', elementType: 'geometry', stylers: [{ color: '#1e293b' }] },
  { featureType: 'water', elementType: 'geometry', stylers: [{ color: '#0369a1' }] },
  { featureType: 'water', elementType: 'labels.text.fill', stylers: [{ color: '#38bdf8' }] },
];


