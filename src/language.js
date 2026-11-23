function pickLanguage(preferences) {
  for (const value of preferences) {
    const base = String(value || '').toLowerCase().split(/[-_]/, 1)[0];
    if (base === 'zh') return 'zh-CN';
    if (base === 'ja' || base === 'en') return base;
  }
  return 'en';
}
