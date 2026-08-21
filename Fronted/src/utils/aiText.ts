const GROUPED_INTERNAL_REFS =
  /[\(\[\{]\s*(?:(?:chunk\s*[- ]?\s*id|dok(?:ument)?\.?\s*[- ]?\s*id|document\s*[- ]?\s*id)\s*[:#]?\s*\d+\s*(?:[,;/|]\s*)?){1,4}[\)\]\}]/gi;

const AI_PROVENANCE_LABELS =
  /(?:Bestätigte\s+KI[- ]Management[- ]Zusammenfassung|KI[- ]Management[- ]Zusammenfassung\s+bestätigt)/gi;

const SINGLE_INTERNAL_REF =
  /(?:chunk\s*[- ]?\s*id|dok(?:ument)?\.?\s*[- ]?\s*id|document\s*[- ]?\s*id)\s*[:#]?\s*\d+/gi;

export function cleanAIText(value: string | null | undefined): string {
  if (!value) return "";

  return value
    .normalize("NFKC")
    .replace(/[\u00ad\u200b\u200c\u200d\u2060\ufeff]/g, "")
    .replace(/[\u2010\u2011\u2012\u2013\u2014\u2015\u2212]/g, "-")
    .replace(/\u00a0/g, " ")
    .replace(GROUPED_INTERNAL_REFS, "")
    .replace(AI_PROVENANCE_LABELS, "")
    .replace(SINGLE_INTERNAL_REF, "")
    .replace(/\(\s*[,;:/|\-]*\s*\)/g, "")
    .replace(/\[\s*[,;:/|\-]*\s*\]/g, "")
    .replace(/\s+([,.;:!?])/g, "$1")
    .replace(/[ \t]{2,}/g, " ")
    .trim();
}
