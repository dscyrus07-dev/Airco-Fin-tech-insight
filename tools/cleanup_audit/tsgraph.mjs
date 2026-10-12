// TS import graph via TypeScript compiler API. Entries: every page/layout/route under app/**,
// every test file, config. Output: reachable set + edges.
import { createRequire } from 'module';
const require = createRequire('X:/Airco Projects/wt-ue/frontend/package.json');
const ts = require('typescript');
import fs from 'fs';
import path from 'path';

const FE = path.resolve(process.argv[2] || '../frontend').split(path.sep).join('/');
const exts = ['.ts', '.tsx', '.js', '.jsx', '.d.ts'];
function* walk(dir) {
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, e.name);
    if (e.isDirectory() && !['node_modules', '.next', '__pycache__'].includes(e.name)) yield* walk(p);
    else if (e.isFile() && exts.includes(path.extname(e.name))) yield p;
  }
}
const allFiles = [path.join(FE, 'app'), path.join(FE, 'lib')]
  .filter(d => fs.existsSync(d))
  .flatMap(d => [...walk(d)])
  .map(p => p.split(path.sep).join('/'));
const isEntry = p => /\/(page|layout|route|loading|error|template|default|not-found)\.(tsx?|jsx?)$/.test(p)
  || p.includes('__tests__') || /\.(test|spec)\.(tsx?|ts)$/.test(p)
  || p.endsWith('middleware.ts') || p.endsWith('instrumentation.ts');
const entries = allFiles.filter(isEntry);
function resolve(spec, from) {
  const res = ts.resolveModuleName(spec, from, {
    esModuleInterop: true, allowJs: true, jsx: ts.JsxEmit.React,
    baseUrl: FE, paths: { '@/*': ['./*'] },
  }, ts.sys);
  return res.resolvedModule?.resolvedFileName?.split(path.sep).join('/');
}
const seen = new Set(); const edges = {};
const queue = [...entries];
while (queue.length) {
  const f = queue.pop();
  if (!f || seen.has(f) || !f.startsWith(FE)) continue;
  seen.add(f);
  try {
    const sf = ts.createSourceFile(f, fs.readFileSync(f, 'utf8'), ts.ScriptTarget.Latest, true);
    const specs = [];
    sf.forEachChild(n => {
      if ((ts.isImportDeclaration(n) || ts.isExportDeclaration(n)) && n.moduleSpecifier)
        specs.push(n.moduleSpecifier.text);
      if (ts.isImportEqualsDeclaration(n) && n.moduleReference?.expression)
        specs.push(n.moduleReference.expression.text);
      if (ts.isCallExpression(n) && n.expression.kind === ts.SyntaxKind.ImportKeyword && n.arguments[0])
        specs.push(n.arguments[0].text);
    });
    edges[f] = specs.map(s => resolve(s, f)).filter(Boolean);
    queue.push(...edges[f]);
  } catch {}
}
const rel = p => path.relative(FE, p).split(path.sep).join('/');
const reachable = new Set([...seen].map(rel));
const unreachable = allFiles.map(rel).filter(p => !reachable.has(p));
fs.writeFileSync(path.join(FE, '..', 'tools/cleanup_audit/tsgraph.json'),
  JSON.stringify({ entries: entries.map(rel), reachable: [...reachable].sort(), unreachable,
    edges: Object.fromEntries(Object.entries(edges).map(([k, v]) => [rel(k), v.map(rel)])) }, null, 0));
console.log('entries:', entries.length, '| reachable:', reachable.size, '| unreachable:', unreachable.length);
unreachable.forEach(u => console.log('  UNREACHABLE', u));
