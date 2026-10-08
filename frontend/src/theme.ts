import { theme, type ThemeConfig } from 'antd';

export const midnight = {
  canvas: '#0b1020', surface: '#111a2c', elevated: '#172238', line: '#27344c',
  text: '#edf3fd', muted: '#a4b3cc', accent: '#81adff', success: '#65d9b0',
};
export const enterpriseTheme: ThemeConfig = {
  algorithm: theme.darkAlgorithm,
  token: {
    colorPrimary: midnight.accent, colorSuccess: midnight.success,
    colorBgLayout: midnight.canvas, colorBgContainer: midnight.surface,
    colorBgElevated: midnight.elevated, colorBorder: midnight.line,
    colorText: midnight.text, colorTextSecondary: midnight.muted,
    borderRadius: 12, fontSize: 14,
    fontFamily: 'Inter, "Noto Sans TC", "Microsoft JhengHei", system-ui, sans-serif',
    controlHeight: 40,
  },
  components: { Layout: { siderBg: midnight.canvas, headerBg: midnight.canvas }, Card: { headerFontSize: 16 } },
};

// The result workspace uses the same governed host theme and component system.
// The canonical navy navigation stays outside this presentation-only variant.
export const resultWorkspaceTheme: ThemeConfig = {
  ...enterpriseTheme,
  algorithm: theme.defaultAlgorithm,
  token: {
    ...enterpriseTheme.token,
    colorPrimary: '#2563eb', colorSuccess: '#16885b',
    colorBgLayout: '#f3f5f9', colorBgContainer: '#ffffff', colorBgElevated: '#ffffff',
    colorBorder: '#dce3ed', colorText: '#172b4d', colorTextSecondary: '#53637a',
  },
};
