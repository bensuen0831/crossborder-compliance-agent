import fs from 'node:fs';
import process from 'node:process';
import path from 'node:path';
import ts from 'typescript';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const locales = ['zh-CN', 'zh-HK', 'en-US'];
const catalogs = Object.fromEntries(locales.map(locale => [locale, JSON.parse(fs.readFileSync(path.join(root, 'src/locales', `${locale}.json`), 'utf8'))]));
const keys = Object.keys(catalogs['en-US']).sort();
const issues = [];
const dynamicKeys = ['SUFFICIENT', 'PARTIALLY_SUFFICIENT', 'INSUFFICIENT', 'CONFLICTED',
  ...['validate', 'submit-review', 'approve', 'reject', 'publish', 'supersede', 'expire', 'archive'].map(action => `ui.action.${action}`)];
for (const key of dynamicKeys) if (!keys.includes(key)) issues.push(`missing dynamic key ${key}`);
for (const locale of locales) {
  const catalog = catalogs[locale];
  if (JSON.stringify(Object.keys(catalog).sort()) !== JSON.stringify(keys)) issues.push(`${locale}: key set differs`);
  for (const key of keys) {
    if (typeof catalog[key] !== 'string' || !catalog[key].trim()) { issues.push(`${locale}: empty ${key}`); continue; }
    const slots = text => [...text.matchAll(/{{\s*([^} ]+)\s*}}/g)].map(match => match[1]).sort().join(',');
    if (slots(catalog[key]) !== slots(catalogs['en-US'][key])) issues.push(`${locale}: placeholders differ for ${key}`);
  }
}
let files = 0;
function walk(directory) {
  for (const name of fs.readdirSync(directory)) {
    const filename = path.join(directory, name);
    if (fs.statSync(filename).isDirectory()) { walk(filename); continue; }
    if (!/\.tsx?$/.test(name) || /\.test\./.test(name) || name === 'generated.ts') continue;
    files++;
    const source = fs.readFileSync(filename, 'utf8');
    const ast = ts.createSourceFile(filename, source, ts.ScriptTarget.Latest, true, name.endsWith('.tsx') ? ts.ScriptKind.TSX : ts.ScriptKind.TS);
    function issue(node, message) {
      const line = ast.getLineAndCharacterOfPosition(node.getStart(ast)).line + 1;
      issues.push(`${path.relative(root, filename)}:${line}: ${message}`);
    }
    function visit(node) {
      if (ts.isJsxText(node) && /[\p{L}\p{N}]/u.test(node.text.trim())) issue(node, 'hard-coded visible JSX text');
      if (ts.isJsxAttribute(node) && ['aria-label', 'placeholder', 'title', 'label', 'alt'].includes(node.name.getText(ast)) && node.initializer && ts.isStringLiteral(node.initializer)) issue(node, 'hard-coded visible attribute');
      if (ts.isPropertyAssignment(node) && ['label', 'title', 'gap', 'group', 'message'].includes(node.name.getText(ast)) && ts.isStringLiteral(node.initializer) && !keys.includes(node.initializer.text)) issue(node, 'visible descriptor must contain an i18n key');
      if (ts.isJsxExpression(node) && !ts.isJsxAttribute(node.parent) && node.expression) {
        function visible(expression) {
          if (ts.isStringLiteral(expression) && /[\p{L}\p{N}]/u.test(expression.text)) issue(expression, 'hard-coded visible JSX expression');
          else if (ts.isTemplateExpression(expression) && /[\p{L}]/u.test(expression.head.text)) issue(expression, 'hard-coded visible template');
          else if (ts.isConditionalExpression(expression)) { visible(expression.whenTrue); visible(expression.whenFalse); }
          else if (ts.isBinaryExpression(expression) && [ts.SyntaxKind.PlusToken, ts.SyntaxKind.QuestionQuestionToken].includes(expression.operatorToken.kind)) { visible(expression.left); visible(expression.right); }
        }
        visible(node.expression);
      }
      if (ts.isStringLiteral(node) && node.text.startsWith('ui.') && !keys.includes(node.text)) issue(node, `missing key ${node.text}`);
      if (ts.isCallExpression(node) && /^(?:i18n\.)?t$/.test(node.expression.getText(ast)) && node.arguments[0] && ts.isStringLiteral(node.arguments[0]) && !keys.includes(node.arguments[0].text)) issue(node, `missing key ${node.arguments[0].text}`);
      // Localization must never enter comparisons against wire/domain codes.
      if (ts.isBinaryExpression(node) && [ts.SyntaxKind.EqualsEqualsEqualsToken, ts.SyntaxKind.ExclamationEqualsEqualsToken].includes(node.operatorToken.kind)) {
        if ([node.left, node.right].some(operand => ts.isCallExpression(operand) && /^(?:i18n\.)?t$/.test(operand.expression.getText(ast)))) issue(node, 'translation used as a domain comparison');
      }
      ts.forEachChild(node, visit);
    }
    visit(ast);
  }
}
walk(path.join(root, 'src'));
if (issues.length) { process.stderr.write(issues.join('\n') + '\n'); process.exitCode = 1; }
else process.stdout.write(JSON.stringify({ status: 'PASS', locales, keys_per_locale: keys.length, checked_files: files, hard_coded_ui_strings: 0, missing_keys: 0 }) + '\n');
