import { afterEach, describe, expect, it } from 'vitest';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';

const fixtures: string[] = [];
afterEach(() => { for (const directory of fixtures.splice(0)) fs.rmSync(directory, { recursive: true }); });
function policy(source: string, edit?: (root: string) => void) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'stage1-i18n-policy-')); fixtures.push(root);
  fs.mkdirSync(path.join(root, 'scripts'));
  fs.mkdirSync(path.join(root, 'src/locales'), { recursive: true });
  fs.copyFileSync('scripts/check-i18n.mjs', path.join(root, 'scripts/check-i18n.mjs'));
  fs.symlinkSync(path.resolve('node_modules'), path.join(root, 'node_modules'), 'dir');
  for (const locale of ['zh-CN', 'zh-HK', 'en-US']) fs.copyFileSync(`src/locales/${locale}.json`, path.join(root, `src/locales/${locale}.json`));
  fs.writeFileSync(path.join(root, 'src/Injected.tsx'), source); edit?.(root);
  return spawnSync(process.execPath, [path.join(root, 'scripts/check-i18n.mjs')], { encoding: 'utf8' });
}
describe('build policy rejects multilingual regressions', () => {
  it('rejects a raw React UI string', () => { expect(policy('export const X = () => <p>Hard coded UI</p>;').status).toBe(1); });
  it('rejects hard-coded copy inside a React conditional expression', () => { expect(policy("export const X = () => <p>{busy ? 'Loading' : 'Ready'}</p>;").status).toBe(1); });
  it('rejects a nonexistent key', () => { expect(policy("export const X = () => <p>{t('ui.unavailableKey')}</p>;").status).toBe(1); });
  it('rejects a missing locale entry', () => {
    const result = policy("export const X = () => <p>{t('knowledge')}</p>;", root => {
      const file = path.join(root, 'src/locales/zh-HK.json'); const data = JSON.parse(fs.readFileSync(file, 'utf8')); delete data.knowledge; fs.writeFileSync(file, JSON.stringify(data));
    }); expect(result.status).toBe(1);
  });
  it('rejects inconsistent interpolation arguments', () => {
    const result = policy("export const X = () => <p>{t('ui.versionLabel')}</p>;", root => {
      const file = path.join(root, 'src/locales/zh-CN.json'); const data = JSON.parse(fs.readFileSync(file, 'utf8')); data['ui.versionLabel'] = '版本 {{wrong}}'; fs.writeFileSync(file, JSON.stringify(data));
    }); expect(result.status).toBe(1);
  });
  it('rejects localization entering a domain-code comparison', () => { expect(policy("if (action === t('ui.action.publish')) publish();").status).toBe(1); });
});
