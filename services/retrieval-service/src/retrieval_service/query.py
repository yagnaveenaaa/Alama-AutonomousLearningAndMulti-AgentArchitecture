from __future__ import annotations

import re

from retrieval_service.domain.models import FormulatedQuery

_SYMBOL = re.compile(r"\b[A-Za-z_][A-Za-z0-9_.]{2,}\b")
_STOP = frozenset({"the", "and", "for", "with", "from", "this", "that", "where", "what"})


class QueryFormulator:
    """Produce keyword, semantic and symbol searches (LLD §9.3)."""

    def formulate(self, text: str) -> FormulatedQuery:
        terms = [term for term in _SYMBOL.findall(text) if term.lower() not in _STOP]
        keywords = " ".join(dict.fromkeys(term.lower() for term in terms))
        symbols = tuple(dict.fromkeys(term for term in terms if "." in term or term[:1].isupper()))
        return FormulatedQuery(
            keyword_query=keywords or text.strip(),
            semantic_query=text.strip(),
            symbol_queries=symbols or tuple(terms[:5]),
        )
