from __future__ import annotations

import re
from typing import Any, Literal

from sqlalchemy.orm import Session

from app import models, schemas
from app.services.embeddings import create_query_embedding
from app.services.openai_client import analysis_model, get_openai_client
from app.services.retrieval import retrieve_chunks


TaskType = Literal["question", "chronology", "evidence", "entities", "brief_evidence"]

CASE_ASSISTANT_PROMPT_VERSION = "case-assistant-v5f-brief-evidence"

BASE_SYSTEM_PROMPT = """
Du bist der KI-Assistent der Anwendung Case Flow.

Dir werden ausschließlich bereits durch Case Flow freigegebene Evidenzblöcke
für den ausgewählten Vorgang übergeben.

VERBINDLICHE REGELN:
1. Verwende ausschließlich die bereitgestellte Evidenz. Erfinde keine Tatsachen.
2. Jede Tatsachenbehauptung muss mindestens eine gültige Quellen-ID wie S1 oder
   S2 enthalten.
3. Nutze ausschließlich die gelieferten Quellen-IDs. Erfinde keine IDs,
   Dateinamen, Daten, Absender, Seiten, Rollen oder Abschnitte.
4. Die Freitextantwort soll die wichtigsten Quellen direkt als [S1], [S2] usw.
   nennen.
5. Widersprechen sich Quellen, erfasse den Widerspruch ausdrücklich unter
   `contradictions` und nenne die betroffenen Quellen-IDs.
6. Informationen, die zur Beantwortung fehlen, gehören in
   `missing_information`.
7. Aussagen, die anhand der Evidenz nicht belegt werden können, gehören in
   `unsupported_statements` und dürfen nicht als Tatsache formuliert werden.
8. Wenn die Evidenz keine belastbare Antwort erlaubt, sage das klar.
9. Antworte auf Deutsch.
""".strip()

TASK_PROMPTS: dict[TaskType, str] = {
    "question": """
AUFGABE: FALLFRAGE
Beantworte ausschließlich die konkrete Frage zum ausgewählten Vorgang.
Nutze `claims` für die wichtigsten belegten Tatsachenbehauptungen.
""".strip(),
    "chronology": """
AUFGABE: CHRONOLOGIE
Erstelle aus der Evidenz eine belastbare Chronologie der für die Anfrage
relevanten Ereignisse.

Zusätzliche Regeln:
- Nutze `chronology` für einzelne Ereignisse.
- `date` darf nur gesetzt werden, wenn das Datum aus der bereitgestellten
  Evidenz oder den gelieferten Quellenmetadaten hervorgeht.
- Ist nur ein ungefährer Zeitraum belegt, formuliere ihn vorsichtig als Text.
- Jedes Chronologie-Ereignis benötigt mindestens eine gültige Quellen-ID.
- Sortiere Ereignisse möglichst chronologisch. Ereignisse ohne belastbares
  Datum dürfen am Ende stehen.
- Vermische keine Interpretation mit einem dokumentierten Ereignis.
""".strip(),
    "evidence": """
AUFGABE: BEWEISMITTELÜBERSICHT
Ordne die vorhandenen Belege der angefragten Behauptung oder Fragestellung zu.

Zusätzliche Regeln:
- Nutze `evidence` für einzelne Belegzuordnungen.
- `claim` beschreibt nur die Behauptung, die durch die referenzierten Quellen
  tatsächlich gestützt wird.
- `relevance` erklärt knapp, warum der Beleg relevant ist.
- Jede Belegzuordnung benötigt mindestens eine gültige Quellen-ID.
- Gegenbelege oder widersprüchliche Belege gehören zusätzlich unter
  `contradictions`.
- Nicht belegbare Teile gehören in `missing_information` oder
  `unsupported_statements`.
""".strip(),
    "entities": """
AUFGABE: PERSONEN, UNTERNEHMEN UND ROLLEN
Identifiziere aus der Evidenz Personen, Unternehmen und Organisationen sowie
ihre belegten Rollen im Vorgang.

Zusätzliche Regeln:
- Nutze `entities` für jede identifizierte Person/Organisation.
- `role_is_explicit=true` nur wenn die Rolle ausdrücklich aus der Evidenz
  hervorgeht.
- Wenn eine Rolle nur vermutet werden könnte, erfinde sie nicht. Setze `role`
  auf null oder kennzeichne sie mit `role_is_explicit=false` und erläutere die
  Unsicherheit in `missing_information`.
- Jede Entität benötigt mindestens eine gültige Quellen-ID.
- Doppelte Entitäten möglichst zusammenführen.
""".strip(),
    "brief_evidence": """
AUFGABE: AUFGABENBEZOGENES BEWEISPAKET FÜR EINE SCHRIFTSATZVORBEREITUNG
Erstelle noch KEINEN Schriftsatz und KEINE fertige Gliederung. Stelle zuerst
ein belastbares, auf den konkreten Auftrag zugeschnittenes Beweispaket zusammen.

Zusätzliche Regeln:
- Fülle `brief_evidence_package`.
- `task_summary` fasst Ziel, Partei/Rolle, Adressat und Dokumentart knapp zusammen.
- `established_facts` enthält nur Tatsachen, die durch mindestens eine Quelle belegt sind.
- `key_evidence` ordnet die wichtigsten Belege dem Auftragsziel zu.
- `relevant_events` enthält nur Ereignisse, die für den Auftrag erkennbar relevant sind.
- `relevant_entities` enthält nur Beteiligte/Rollen, die für den Auftrag relevant sind.
- `open_issues` nennt ungeklärte Tatsachenfragen oder Punkte, die vor einem Entwurf geprüft werden sollten.
- Erstelle ausdrücklich noch keine Anträge, keine rechtliche Schlussfolgerung und keinen ausformulierten Schriftsatz.
- Jede Tatsache, jedes Ereignis und jede Rollenangabe muss gültige Quellen-IDs tragen.
""".strip(),
}


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
    if task_type == "brief_evidence":
        return (
            f"{question}\n\nSchriftsatz, Beweispaket, maßgebliche Tatsachen, "
            "Beweismittel, Korrespondenz, Übergabe, Beteiligte, Widerspruch, offene Frage"
        )
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
    query_embedding = create_query_embedding(retrieval_question(question, task_type))
    task_limit = limit if limit is not None else (30 if task_type in {"chronology", "brief_evidence"} else 20)
    task_threshold = 0.30 if task_type in {"chronology", "brief_evidence"} else 0.40
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
    if task_type != "brief_evidence" or brief_context is None:
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

    evidence_context = build_evidence_context(sources)
    request_text = build_task_request_text(
        question=question,
        task_type=task_type,
        brief_context=brief_context,
    )
    system_prompt = f"{BASE_SYSTEM_PROMPT}\n\n{TASK_PROMPTS[task_type]}"
    response = get_openai_client().responses.parse(
        model=analysis_model(),
        input=[
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": (
                    f"AUFGABENTYP\n===========\n{task_type}\n\n"
                    "ANFRAGE\n=======\n"
                    f"{request_text}\n\n"
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
