import type { ReactNode } from "react";

/** Safe, dependency-free Markdown presentation for model-authored text.
 * No HTML is interpreted; source markers remain visible for auditability.
 */
function inline(text: string): ReactNode[] {
  return text.split(/(\*\*[^*]+\*\*|`[^`]+`)/g).map((part, i) => {
    if (part.startsWith("**") && part.endsWith("**")) return <strong key={i}>{part.slice(2, -2)}</strong>;
    if (part.startsWith("`") && part.endsWith("`")) return <code key={i} className="rounded bg-slate-100 px-1">{part.slice(1, -1)}</code>;
    return part;
  });
}

export default function AssistantMarkdown({ content }: { content: string }) {
  const lines = content.replace(/\r\n/g, "\n").split("\n");
  const blocks: ReactNode[] = [];
  let i = 0;
  while (i < lines.length) {
    const line = lines[i].trim();
    if (!line) { i++; continue; }
    const heading = /^(#{1,4})\s+(.+)$/.exec(line);
    if (heading) {
      const cls = heading[1].length <= 2 ? "mt-4 mb-2 text-base font-semibold text-slate-900" : "mt-3 mb-1 font-semibold text-slate-900";
      blocks.push(<h4 key={i} className={cls}>{inline(heading[2])}</h4>); i++; continue;
    }
    if (line.includes("|") && i + 1 < lines.length && /^\|?[\s:|-]+\|[\s:|-]*$/.test(lines[i + 1].trim())) {
      const start = i;
      const cells = (s: string) => s.replace(/^\||\|$/g, "").split("|").map(x => x.trim());
      const headers = cells(line); i += 2;
      const rows: string[][] = [];
      while (i < lines.length && lines[i].trim().includes("|")) { rows.push(cells(lines[i].trim())); i++; }
      blocks.push(<div key={start} className="my-3 overflow-x-auto"><table className="w-full border-collapse text-left text-sm"><thead><tr>{headers.map((h, j) => <th key={j} className="border-b border-slate-300 bg-slate-50 px-3 py-2 font-semibold">{inline(h)}</th>)}</tr></thead><tbody>{rows.map((r, j) => <tr key={j}>{headers.map((_, k) => <td key={k} className="border-b border-slate-100 px-3 py-2 align-top">{inline(r[k] || "")}</td>)}</tr>)}</tbody></table></div>); continue;
    }
    if (/^([-*]|\d+\.)\s+/.test(line)) {
      const start = i; const ordered = /^\d+\./.test(line); const items: string[] = [];
      while (i < lines.length && /^([-*]|\d+\.)\s+/.test(lines[i].trim())) { items.push(lines[i].trim().replace(/^([-*]|\d+\.)\s+/, "")); i++; }
      const children = items.map((item, j) => <li key={j}>{inline(item)}</li>);
      blocks.push(ordered ? <ol key={start} className="my-2 list-decimal space-y-1 pl-6">{children}</ol> : <ul key={start} className="my-2 list-disc space-y-1 pl-6">{children}</ul>); continue;
    }
    const start = i; const paragraph: string[] = [];
    while (i < lines.length && lines[i].trim() && !/^(#{1,4}\s|[-*]\s|\d+\.\s)/.test(lines[i].trim())) { paragraph.push(lines[i].trim()); i++; }
    if (!paragraph.length) { i++; continue; }
    blocks.push(<p key={start} className="my-2 leading-7 text-slate-800">{inline(paragraph.join(" "))}</p>);
  }
  return <div className="min-w-0 break-words text-sm">{blocks}</div>;
}
