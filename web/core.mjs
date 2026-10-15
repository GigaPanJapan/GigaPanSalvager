export function parseId(value) {
  const text=String(value).trim();
  if (/^[1-9]\d{0,8}$/.test(text)) return Number(text);
  try {
    const u=new URL(text), m=u.pathname.match(/^\/gigapans\/([1-9]\d{0,8})\/?$/);
    if (['http:','https:'].includes(u.protocol)&&['gigapan.com','www.gigapan.com','gigapan.org','www.gigapan.org'].includes(u.hostname)&&m) return Number(m[1]);
  } catch {}
  throw new Error('GigaPan の数値 ID またはパノラマの URL を入力してください。');
}
export function issueUrl(repository,request) {
  if (!/^[\w.-]+\/[\w.-]+$/.test(repository)) throw new Error('保存先リポジトリの設定が不正です。');
  const id=parseId(request.id);
  const body='<!-- gigapan-salvager:v1 -->\n```json\n'+JSON.stringify({...request,id},null,2)+'\n```\n\n公開されているタイルとメタデータの保存を依頼します。';
  const u=new URL(`https://github.com/${repository}/issues/new`);
  u.searchParams.set('template','salvage.md');u.searchParams.set('title',`[Salvage] GigaPan ${id}`);u.searchParams.set('body',body);
  return u.href;
}
export function statusLabel(run) {
  if (run.status!=='completed') return run.status==='queued'?'待機中':'実行中';
  return ({success:'完了',failure:'未完了・ログを確認',cancelled:'キャンセル',skipped:'スキップ',timed_out:'時間切れ'})[run.conclusion]||'終了';
}
