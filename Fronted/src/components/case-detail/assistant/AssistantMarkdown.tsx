import type { ReactNode } from "react";
import type { AssistantSource } from "../../../services/ai";

/** Safe, dependency-free Markdown presentation for model-authored text.
 * No HTML is interpreted; source markers remain visible for auditability.
 */
function inline(text: string, sources?: AssistantSource[], sourcePrefix?: string): ReactNode[] {
  const byId = new Map((sources ?? []).map((source) => [source.source_id, source]));
  return text.split(/(\*\*[^*]+\*\*|`[^`]+`|\[S\d+\])/g).map((part, i) => {
    if (part.startsWith("**") && part.endsWith("**")) return <strong key={i}>{part.slice(2, -2)}</strong>;
    if (part.startsWith("`") && part.endsWith("`")) return <code key={i} className="rounded bg-slate-100 px-1">{part.slice(1, -1)}</code>;
    const marker = /^\[(S\d+)\]$/.exec(part);
    if (marker && byId.has(marker[1]) && sourcePrefix) {
      const source = byId.get(marker[1])!;
      return <a key={i} href={`#${sourcePrefix}-source-${marker[1]}`} title={`${source.filename}${source.page_number ? ` · Seite ${source.page_number}` : ""}`} className="rounded bg-blue-50 px-1 font-semibold text-blue-800 underline underline-offset-2 hover:bg-blue-100" aria-label={`Quelle ${marker[1]}: ${source.filename}`}>{part}</a>;
    }
    return part;
  });
}

export default function AssistantMarkdown({ content, sources, sourcePrefix }: { content: string; sources?: AssistantSource[]; sourcePrefix?: string }) {
  const lines = content.replace(/\r\n/g, "\n").split("\n");
  const blocks: ReactNode[] = [];
  let i = 0;
  while (i < lines.length) {
    const line = lines[i].trim();
    if (!line) { i++; continue; }
    const heading = /^(#{1,4})\s+(.+)$/.exec(line);
    if (heading) {
      const cls = heading[1].length <= 2 ? "mt-4 mb-2 text-base font-semibold text-slate-900" : "mt-3 mb-1 font-semibold text-slate-900";
      blocks.push(<h4 key={i} className={cls}>{inline(heading[2], sources, sourcePrefix)}</h4>); i++; continue;
    }
    if (line.includes("|") && i + 1 < lines.length && /^\|?[\s:|-]+\|[\s:|-]*$/.test(lines[i + 1].trim())) {
      const start = i;
      const cells = (s: string) => s.replace(/^\||\|$/g, "").split("|").map(x => x.trim());
      const headers = cells(line); i += 2;
      const rows: string[][] = [];
      while (i < lines.length && lines[i].trim().includes("|")) { rows.push(cells(lines[i].trim())); i++; }
      blocks.push(<div key={start} className="my-4 max-w-full overflow-x-auto rounded-lg border border-slate-200"><table className="w-full min-w-[600px] border-collapse text-left text-sm"><thead><tr>{headers.map((h, j) => <th key={j} className="border-b border-slate-300 bg-slate-50 px-3 py-3 font-semibold">{inline(h, sources, sourcePrefix)}</th>)}</tr></thead><tbody>{rows.map((r, j) => <tr key={j}>{headers.map((_, k) => <td key={k} className="border-b border-slate-100 px-3 py-3 align-top leading-6">{inline(r[k] || "", sources, sourcePrefix)}</td>)}</tr>)}</tbody></table></div>); continue;
    }
    if (/^([-*]|\d+\.)\s+/.test(line)) {
      const start = i; const ordered = /^\d+\./.test(line); const items: string[] = [];
      while (i < lines.length && /^([-*]|\d+\.)\s+/.test(lines[i].trim())) { items.push(lines[i].trim().replace(/^([-*]|\d+\.)\s+/, "")); i++; }
      const children = items.map((item, j) => <li key={j}>{inline(item, sources, sourcePrefix)}</li>);
      blocks.push(ordered ? <ol key={start} className="my-2 list-decimal space-y-1 pl-6">{children}</ol> : <ul key={start} className="my-2 list-disc space-y-1 pl-6">{children}</ul>); continue;
    }
    const start = i; const paragraph: string[] = [];
    while (i < lines.length && lines[i].trim() && !/^(#{1,4}\s|[-*]\s|\d+\.\s)/.test(lines[i].trim())) { paragraph.push(lines[i].trim()); i++; }
    if (!paragraph.length) { i++; continue; }
    blocks.push(<p key={start} className="my-2 leading-7 text-slate-800">{inline(paragraph.join(" "), sources, sourcePrefix)}</p>);
  }
  return <div className="min-w-0 break-words text-sm">{blocks}</div>;
}
