from __future__ import annotations

import re
from typing import Any, Literal

from sqlalchemy.orm import Session

from app import models, schemas
from app.services.embeddings import create_query_embedding
from app.services.ai_provider import get_ai_provider
from app.services.retrieval import retrieve_chunks
from app.prompts.case_assistant import CASE_ASSISTANT_PROMPT_VERSION, BASE_SYSTEM_PROMPT, CHAT_CONVERSATIONAL_PROMPT, TASK_PROMPTS


TaskType = Literal["question", "chronology", "evidence", "entities", "brief_evidence", "brief_outline", "brief_draft", "brief_review", "intelligence", "report"]

def retrieval_question(question: str, task_type: TaskType) -> str:
    if task_type == "chronology":
        return (
            f"{question}\n\nChronologie, Datum, Ereignis, Entwicklung, "
            "Korrespondenz, Übergabe, Frist, Handlung"
        )
    if task_type == "evidence":
        return f"{question}\n\nBeleg, Beweis, Nachweis, Dokumentstelle, Bestätigung, Widerspruch"
    if task_type == "entities":
        return f"{question}\n\nPerson, Unternehmen, Organisation, Rolle, Funktion, Absender, Empfänger"
    if task_type in {"intelligence", "report"}:
        return (f"{question}\n\nSchlüsseltatsachen, Chronologie, Beteiligte, Rollen, Beweismittel, Rechnungen, Beträge, Zahlungen, Vertragskosten, "
                "Widersprüche, Informationslücken, offene Fragen, aktueller Sachstand")
    if task_type in {"brief_evidence", "brief_outline", "brief_draft", "brief_review"}:
        return (
            f"{question}\n\nSchriftsatz, Beweispaket, maßgebliche Tatsachen, "
            "Beweismittel, Korrespondenz, Übergabe, Beteiligte, Widerspruch, offene Frage"
        )
    if "Aktuelle Frage:" in question:
        latest = question.rsplit("Aktuelle Frage:", 1)[-1].strip()
        prior = question.split("Aktuelle Frage:", 1)[0]
        user_lines = [line.split(":", 1)[-1].strip() for line in prior.splitlines() if line.startswith("user:")]
        return f"{latest}\nVorherige Nutzerfrage: {user_lines[-1][:250]}" if user_lines else latest
    return question


def retrieve_case_evidence(
    *,
    db: Session,
    user: models.User,
    case_id: int,
    question: str,
    task_type: TaskType = "question",
    limit: int | None = None,
) -> list[dict[str, Any]]:

    if task_type == "evidence":
        search_texts = (
            "Vertrag Angebot Rechnung Zahlung Ablöse Betrag Kosten Vereinbarung",
            "E-Mail Korrespondenz Bestätigung Forderung Termin Kündigung Abholung",
            "Nachweis Dokument Beleg Schreiben Widerspruch Sachverhalt",
        )
        candidates: dict[int, dict[str, Any]] = {}
        for search_text in search_texts:
            embedding = create_query_embedding(search_text)
            for chunk in retrieve_chunks(
                db=db, user=user, query_embedding=embedding,
                case_id=case_id, threshold=0.20, limit=16,
            ):
                chunk_id = int(chunk["chunk_id"])
                previous = candidates.get(chunk_id)
                if previous is None or float(chunk["similarity"]) > float(previous["similarity"]):
                    candidates[chunk_id] = chunk

        by_document: dict[int, list[dict[str, Any]]] = {}
        for chunk in candidates.values():
            by_document.setdefault(int(chunk["document_id"]), []).append(chunk)
        for rows in by_document.values():
            rows.sort(key=lambda row: float(row["similarity"]), reverse=True)
        selected: list[dict[str, Any]] = []
        while by_document and len(selected) < min(limit or 30, 30):
            for document_id in list(by_document):
                if len(selected) >= min(limit or 30, 30):
                    break
                rows = by_document[document_id]
                selected.append(rows.pop(0))
                if not rows:
                    del by_document[document_id]
        return selected

    if task_type == "question":
        latest_question = retrieval_question(question, task_type)[:1200]
        primary_embedding = create_query_embedding(latest_question)
        primary = retrieve_chunks(
            db=db, user=user, query_embedding=primary_embedding,
            case_id=case_id, threshold=0.30, limit=18,
        )
        candidates: dict[int, dict[str, Any]] = {
            int(chunk["chunk_id"]): chunk for chunk in primary
        }
        
        if len(primary) < 12:
            try:
                secondary_embedding = create_query_embedding(
                    f"{latest_question[:300]} Vorgeschichte Verlauf Entscheidungen "
                    "Ergebnisse Nachweise Gegenposition offene Punkte"
                )
                secondary = retrieve_chunks(
                    db=db, user=user, query_embedding=secondary_embedding,
                    case_id=case_id, threshold=0.30, limit=12,
                )
                for chunk in secondary:
                    key = int(chunk["chunk_id"])
                    if key not in candidates or float(chunk["similarity"]) > float(candidates[key]["similarity"]):
                        candidates[key] = chunk
            except Exception:
                # Primary evidence is sufficient to continue safely.
                pass
        by_document: dict[int, list[dict[str, Any]]] = {}
        for chunk in candidates.values():
            by_document.setdefault(int(chunk["document_id"]), []).append(chunk)
        for rows in by_document.values():
            rows.sort(key=lambda row: float(row["similarity"]), reverse=True)
        document_order = sorted(
            by_document,
            key=lambda doc: float(by_document[doc][0]["similarity"]),
            reverse=True,
        )
        selected: list[dict[str, Any]] = []
        max_chunks = min(limit if limit is not None else 18, 24)
        while len(selected) < max_chunks and document_order:
            for document_id in list(document_order):
                if len(selected) >= max_chunks:
                    break
                selected.append(by_document[document_id].pop(0))
                if not by_document[document_id]:
                    document_order.remove(document_id)
        return selected

    query_embedding = create_query_embedding(retrieval_question(question, task_type))
    task_limit = limit if limit is not None else (35 if task_type in {"intelligence", "report"} else (30 if task_type in {"chronology", "brief_evidence", "brief_outline", "brief_draft", "brief_review"} else 20))
    task_threshold = 0.30 if task_type in {"chronology", "brief_evidence", "brief_outline", "brief_draft", "brief_review", "intelligence", "report"} else 0.40
    return retrieve_chunks(
        db=db,
        user=user,
        query_embedding=query_embedding,
        case_id=case_id,
        threshold=task_threshold,
        limit=task_limit,
    )


def build_sources(chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = []
    for index, chunk in enumerate(chunks, start=1):
        metadata = chunk.get("metadata") or {}
        sources.append(
            {
                "source_id": f"S{index}",
                "chunk_id": int(chunk["chunk_id"]),
                "document_id": int(chunk["document_id"]),
                "filename": metadata.get("source_filename") or chunk.get("file_name") or f"Dokument {chunk['document_id']}",
                "document_date": metadata.get("document_date"),
                "sender": metadata.get("sender"),
                "page_number": chunk.get("page_number"),
                "sheet_name": chunk.get("sheet_name"),
                "email_section": chunk.get("email_section"),
                "is_attachment": bool(metadata.get("is_attachment")),
                "parent_filename": metadata.get("parent_filename"),
                "root_email_filename": metadata.get("root_email_filename"),
                "attachment_depth": int(metadata.get("attachment_depth") or 0),
                "content": chunk["content"],
            }
        )
    return sources


def _source_context(source: dict[str, Any]) -> str:
    lines = [
        f"[{source['source_id']}]",
        f"Dokument: {source['filename']}",
    ]
    if source.get("document_date"):
        lines.append(f"Datum: {source['document_date']}")
    if source.get("sender"):
        lines.append(f"Absender: {source['sender']}")
    if source.get("page_number") is not None:
        lines.append(f"Seite: {source['page_number']}")
    if source.get("sheet_name"):
        lines.append(f"Tabellenblatt: {source['sheet_name']}")
    if source.get("email_section"):
        lines.append(f"Abschnitt: {source['email_section']}")
    if source.get("is_attachment"):
        if source.get("parent_filename"):
            lines.append(f"Anhang aus: {source['parent_filename']}")
        if source.get("root_email_filename") and source.get("root_email_filename") != source.get("parent_filename"):
            lines.append(f"Ursprüngliche E-Mail: {source['root_email_filename']}")
    lines.extend(["", "Inhalt:", source["content"]])
    return "\n".join(lines)


def build_evidence_context(sources: list[dict[str, Any]]) -> str:
    return "\n\n---\n\n".join(_source_context(source) for source in sources)


def _remove_invalid_inline_citations(text: str, valid_ids: set[str]) -> str:
    def replace(match: re.Match[str]) -> str:
        source_id = match.group(1)
        return match.group(0) if source_id in valid_ids else ""

    return re.sub(r"\[(S\d+)\]", replace, text).strip()


def _valid_source_ids(source_ids: list[str], valid_ids: set[str]) -> list[str]:
    return list(dict.fromkeys(source_id for source_id in source_ids if source_id in valid_ids))


def validate_answer_sources(
    result: schemas.CaseAssistantModelAnswer,
    sources: list[dict[str, Any]],
) -> schemas.CaseAssistantModelAnswer:
    valid_ids = {source["source_id"] for source in sources}
    unsupported = list(result.unsupported_statements)

    valid_claims: list[schemas.AssistantEvidenceStatement] = []
    for claim in result.claims:
        claim.source_ids = _valid_source_ids(claim.source_ids, valid_ids)
        if claim.source_ids:
            valid_claims.append(claim)
        else:
            unsupported.append(claim.text)
    result.claims = valid_claims

    valid_contradictions: list[schemas.AssistantEvidenceStatement] = []
    for contradiction in result.contradictions:
        contradiction.source_ids = _valid_source_ids(contradiction.source_ids, valid_ids)
        if contradiction.source_ids:
            valid_contradictions.append(contradiction)
        else:
            unsupported.append(contradiction.text)
    result.contradictions = valid_contradictions

    valid_chronology: list[schemas.AssistantChronologyEvent] = []
    for event in result.chronology:
        event.source_ids = _valid_source_ids(event.source_ids, valid_ids)
        if event.source_ids:
            valid_chronology.append(event)
        else:
            unsupported.append(event.event)
    result.chronology = valid_chronology

    valid_evidence: list[schemas.AssistantEvidenceLink] = []
    for item in result.evidence:
        item.source_ids = _valid_source_ids(item.source_ids, valid_ids)
        if item.source_ids:
            if item.evidence_status == "direct" and not item.evidence_reason:
                item.evidence_status = "insufficient"
                item.limitations.append("Eine konkrete Begründung der direkten Belegwirkung fehlt.")
            valid_evidence.append(item)
        else:
            unsupported.append(item.claim)
    result.evidence = valid_evidence

    valid_entities: list[schemas.AssistantEntity] = []
    for entity in result.entities:
        entity.source_ids = _valid_source_ids(entity.source_ids, valid_ids)
        if entity.source_ids:
            valid_entities.append(entity)
        else:
            unsupported.append(
                f"Entität ohne gültigen Beleg: {entity.name}"
            )
    result.entities = valid_entities

    valid_finances: list[schemas.AssistantReportFinancialItem] = []
    for item in result.report_finances:
        item.source_ids = _valid_source_ids(item.source_ids, valid_ids)
        if item.source_ids:
            valid_finances.append(item)
        else:
            unsupported.append(item.position)
    result.report_finances = valid_finances

    valid_deadlines = []
    for item in result.report_deadlines:
        item.source_ids = _valid_source_ids(item.source_ids, valid_ids)
        if item.source_ids:
            if item.status in ("active", "completed", "historical") and not (item.status_reason or "").strip():
                item.status = "unclear"
                item.status_reason = "Status aus den belegten Angaben nicht eindeutig bestätigt."
            valid_deadlines.append(item)
        else:
            unsupported.append(item.description)
    result.report_deadlines = valid_deadlines

    valid_tasks = []
    for item in result.report_tasks:
        item.source_ids = _valid_source_ids(item.source_ids, valid_ids)
        if item.source_ids:
            valid_tasks.append(item)
        else:
            unsupported.append(item.description)
    result.report_tasks = valid_tasks

    package = result.brief_evidence_package
    if package is not None:
        valid_facts: list[schemas.AssistantEvidenceStatement] = []
        for fact in package.established_facts:
            fact.source_ids = _valid_source_ids(fact.source_ids, valid_ids)
            if fact.source_ids:
                valid_facts.append(fact)
            else:
                unsupported.append(fact.text)
        package.established_facts = valid_facts

        valid_package_evidence: list[schemas.AssistantEvidenceLink] = []
        for item in package.key_evidence:
            item.source_ids = _valid_source_ids(item.source_ids, valid_ids)
            if item.source_ids:
                valid_package_evidence.append(item)
            else:
                unsupported.append(item.claim)
        package.key_evidence = valid_package_evidence

        valid_package_events: list[schemas.AssistantChronologyEvent] = []
        for event in package.relevant_events:
            event.source_ids = _valid_source_ids(event.source_ids, valid_ids)
            if event.source_ids:
                valid_package_events.append(event)
            else:
                unsupported.append(event.event)
        package.relevant_events = valid_package_events

        valid_package_entities: list[schemas.AssistantEntity] = []
        for entity in package.relevant_entities:
            entity.source_ids = _valid_source_ids(entity.source_ids, valid_ids)
            if entity.source_ids:
                valid_package_entities.append(entity)
            else:
                unsupported.append(f"Entität ohne gültigen Beleg: {entity.name}")
        package.relevant_entities = valid_package_entities
        package.open_issues = list(
            dict.fromkeys(item.strip() for item in package.open_issues if item and item.strip())
        )
        result.brief_evidence_package = package

    outline = result.brief_outline
    if outline is not None:
        valid_sections: list[schemas.AssistantBriefOutlineSection] = []
        for section in outline.sections:
            valid_facts: list[schemas.AssistantEvidenceStatement] = []
            for fact in section.factual_basis:
                fact.source_ids = _valid_source_ids(fact.source_ids, valid_ids)
                if fact.source_ids:
                    valid_facts.append(fact)
                else:
                    unsupported.append(fact.text)
            section.factual_basis = valid_facts

            valid_notes: list[schemas.AssistantEvidenceLink] = []
            for note in section.evidence_notes:
                note.source_ids = _valid_source_ids(note.source_ids, valid_ids)
                if note.source_ids:
                    valid_notes.append(note)
                else:
                    unsupported.append(note.claim)
            section.evidence_notes = valid_notes
            valid_sections.append(section)
        outline.sections = valid_sections
        outline.open_issues = list(dict.fromkeys(x.strip() for x in outline.open_issues if x and x.strip()))
        outline.drafting_notes = list(dict.fromkeys(x.strip() for x in outline.drafting_notes if x and x.strip()))
        result.brief_outline = outline

    draft = result.brief_draft
    if draft is not None:
        def validate_draft_statements(items: list[schemas.AssistantEvidenceStatement]) -> list[schemas.AssistantEvidenceStatement]:
            valid_items: list[schemas.AssistantEvidenceStatement] = []
            for item in items:
                item.source_ids = _valid_source_ids(item.source_ids, valid_ids)
                if item.source_ids:
                    valid_items.append(item)
                else:
                    unsupported.append(item.text)
            return valid_items

        draft.draft_label = "KI-ENTWURF"
        draft.introduction = validate_draft_statements(draft.introduction)
        for section in draft.sections:
            section.paragraphs = validate_draft_statements(section.paragraphs)
        draft.conclusion = validate_draft_statements(draft.conclusion)
        draft.open_issues = list(dict.fromkeys(x.strip() for x in draft.open_issues if x and x.strip()))
        draft.review_notes = list(dict.fromkeys(x.strip() for x in draft.review_notes if x and x.strip()))
        result.brief_draft = draft

    review = result.brief_review
    if review is not None:
        review.review_label = "KI-RED-REVIEW"

        valid_counterarguments: list[schemas.AssistantBriefCounterargument] = []
        for item in review.counterarguments:
            item.source_ids = _valid_source_ids(item.source_ids, valid_ids)
            if item.source_ids:
                valid_counterarguments.append(item)
            else:
                unsupported.append(item.argument)
        review.counterarguments = valid_counterarguments

        valid_risks: list[schemas.AssistantBriefRisk] = []
        for item in review.factual_risks:
            item.source_ids = _valid_source_ids(item.source_ids, valid_ids)
            if item.source_ids:
                valid_risks.append(item)
            else:
                unsupported.append(item.risk)
        review.factual_risks = valid_risks

        valid_review_contradictions: list[schemas.AssistantEvidenceStatement] = []
        for item in review.contradictions:
            item.source_ids = _valid_source_ids(item.source_ids, valid_ids)
            if item.source_ids:
                valid_review_contradictions.append(item)
            else:
                unsupported.append(item.text)
        review.contradictions = valid_review_contradictions

        review.evidence_gaps = list(
            dict.fromkeys(x.strip() for x in review.evidence_gaps if x and x.strip())
        )
        review.legal_review_points = list(
            dict.fromkeys(x.strip() for x in review.legal_review_points if x and x.strip())
        )
        review.recommended_checks = list(
            dict.fromkeys(x.strip() for x in review.recommended_checks if x and x.strip())
        )
        result.brief_review = review

    intelligence = result.intelligence
    if intelligence is not None:
        def validate_intel_statements(items: list[schemas.AssistantEvidenceStatement]) -> list[schemas.AssistantEvidenceStatement]:
            valid_items = []
            for item in items:
                item.source_ids = _valid_source_ids(item.source_ids, valid_ids)
                if item.source_ids:
                    valid_items.append(item)
                else:
                    unsupported.append(item.text)
            return valid_items

        intelligence.executive_summary = validate_intel_statements(intelligence.executive_summary)
        intelligence.key_facts = validate_intel_statements(intelligence.key_facts)
        intelligence.contradictions = validate_intel_statements(intelligence.contradictions)

        valid_events = []
        for event in intelligence.key_events:
            event.source_ids = _valid_source_ids(event.source_ids, valid_ids)
            if event.source_ids:
                valid_events.append(event)
            else:
                unsupported.append(event.event)
        intelligence.key_events = valid_events

        valid_entities = []
        for entity in intelligence.key_entities:
            entity.source_ids = _valid_source_ids(entity.source_ids, valid_ids)
            if entity.source_ids:
                valid_entities.append(entity)
            else:
                unsupported.append(f"Entität ohne gültigen Beleg: {entity.name}")
        intelligence.key_entities = valid_entities

        valid_evidence = []
        for item in intelligence.evidence_map:
            item.source_ids = _valid_source_ids(item.source_ids, valid_ids)
            if item.source_ids:
                valid_evidence.append(item)
            else:
                unsupported.append(item.claim)
        intelligence.evidence_map = valid_evidence
        intelligence.information_gaps = list(dict.fromkeys(x.strip() for x in intelligence.information_gaps if x and x.strip()))
        intelligence.unresolved_issues = list(dict.fromkeys(x.strip() for x in intelligence.unresolved_issues if x and x.strip()))
        result.intelligence = intelligence

    result.answer = _remove_invalid_inline_citations(result.answer, valid_ids)
    result.unsupported_statements = list(
        dict.fromkeys(item.strip() for item in unsupported if item and item.strip())
    )
    result.missing_information = list(
        dict.fromkeys(
            item.strip()
            for item in result.missing_information
            if item and item.strip()
        )
    )
    return result


def build_brief_context_text(brief_context: schemas.AssistantBriefContext | None) -> str:
    if brief_context is None:
        return ""
    lines = [
        f"Mandant/Partei: {brief_context.client}",
        f"Dokumentart: {brief_context.document_type}",
        f"Ziel: {brief_context.objective}",
    ]
    if brief_context.role:
        lines.append(f"Rolle: {brief_context.role}")
    if brief_context.recipient:
        lines.append(f"Adressat: {brief_context.recipient}")
    if brief_context.additional_instructions:
        lines.append(f"Zusätzliche Hinweise: {brief_context.additional_instructions}")
    return "\n".join(lines)


def build_task_request_text(
    *,
    question: str,
    task_type: TaskType,
    brief_context: schemas.AssistantBriefContext | None = None,
) -> str:
    if task_type not in {"brief_evidence", "brief_outline", "brief_draft", "brief_review"} or brief_context is None:
        return question.strip()
    return f"{question.strip()}\n\nAUFTRAGSKONTEXT\n{build_brief_context_text(brief_context)}"


def answer_case_question(
    *,
    question: str,
    sources: list[dict[str, Any]],
    task_type: TaskType = "question",
    brief_context: schemas.AssistantBriefContext | None = None,
) -> schemas.CaseAssistantModelAnswer:
    if not sources:
        return schemas.CaseAssistantModelAnswer(
            answer=(
                "In den aktuell durchsuchbaren Dokumenten wurden keine ausreichend "
                "relevanten Belege für diese Anfrage gefunden."
            ),
            missing_information=[
                "Es wurden keine passenden Evidenzstellen aus dem freigegebenen Vorgang abgerufen."
            ],
        )

    if task_type == "question":
        evidence_context = build_evidence_context([
            {**source, "content": source["content"][:2400]}
            for source in sources[:18]
        ])
    else:
        evidence_context = build_evidence_context(sources)
    request_text = build_task_request_text(
        question=question,
        task_type=task_type,
        brief_context=brief_context,
    )
    system_prompt = (CHAT_CONVERSATIONAL_PROMPT if task_type == "question" else f"{BASE_SYSTEM_PROMPT}\n\n{TASK_PROMPTS[task_type]}")

    chat_analysis_lens = (
        "\n\nANALYSERAHMEN FÜR DEN KI-CHAT\n"
        "Erkenne das tatsächliche Thema und die Absicht der Frage; unterstelle "
        "weder einen Rechtsstreit noch eine Rechnungsfrage. "
        "Analysiere die relevanten Dokumente fallbezogen: Was ist belegt, "
        "was ist eine plausible Schlussfolgerung, was ist offen oder widersprüchlich? "
        "Unterscheide Aussagen, Absichten, Vereinbarungen, tatsächliche Handlungen "
        "und deren Nachweise. Prüfe Zeitablauf, Ursachen und Folgen nur soweit relevant. "
        "Berücksichtige wichtige Gegenbelege und alternative Erklärungen. "
        "Fehlende Nachweise sind nicht automatisch Beweise für das Gegenteil. "
        "Wenn Zahlen relevant sind, prüfe Rechnung und tatsächliche Verbuchung getrennt. "
        "Unterscheide einen dokumentierten Klärungsbedarf von einer belastbaren Einwendung. "
        "Leite aus fehlenden Worten wie netto/brutto keine Steuerrechtsfolge ab; "
        "Steuerfragen hängen von Leistungsart und Rechtsgrund ab. "
        "Unterscheide verfrühte Rechnungsstellung, vertragliche Fälligkeit und "
        "bestehende Zahlungspflicht; eine spätere Bitte um Rechnungsstellung "
        "ändert frühere Bedingungen nicht automatisch. "
        "Ordne die Stärke wesentlicher Argumente nach konkreten Belegen und "
        "berücksichtige jeweils die wichtigste Gegenposition. "
        "Bei rechtlichen, finanziellen, technischen oder organisatorischen Fragen "
        "nutze die jeweils passende fachliche Perspektive, ohne andere Themen aufzuzwingen. "
        "Beantworte komplexe Fragen substanziell und mit konkreten Details; "
        "einfache Fragen direkt und kurz. Keine erfundenen Fakten oder Quellen, "
        "keine routinemäßige Empfehlung oder Liste offener Fragen ohne Nutzerwunsch."
    ) if task_type == "question" else ""
    response = get_ai_provider().structured_parse(
                input=[
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": (
                    f"AUFGABENTYP\n===========\n{task_type}\n\n"
                    "ANFRAGE\n=======\n"
                    f"{request_text}{chat_analysis_lens}\n\n"
                    "FREIGEGEBENE EVIDENZ\n====================\n"
                    f"{evidence_context}"
                ),
            },
        ],
        text_format=schemas.CaseAssistantModelAnswer,
    )
    if response.output_parsed is None:
        raise RuntimeError("Die strukturierte KI-Antwort konnte nicht gelesen werden.")
    return validate_answer_sources(response.output_parsed, sources)


def public_sources(sources: list[dict[str, Any]]) -> list[schemas.AssistantSource]:
    return [
        schemas.AssistantSource.model_validate(
            {key: value for key, value in source.items() if key != "content"}
        )
        for source in sources
    ]
