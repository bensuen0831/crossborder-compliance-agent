import i18n, { currentLocale } from '../../i18n';

export function formatNumber(value: number): string {
  return new Intl.NumberFormat(currentLocale()).format(value);
}
/** Source effective dates stay unchanged; their presentation uses UTC. */
export function formatDate(value?: string | null): string {
  if (!value) return i18n.t('notAvailable');
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return i18n.t('notAvailable');
  return new Intl.DateTimeFormat(currentLocale(), {
    year: 'numeric', month: '2-digit', day: '2-digit', timeZone: 'UTC',
  }).format(date);
}
