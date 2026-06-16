from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Iterable
from reai.models import LeadKey, SourceHealth, SourceRecord


class SourceAdapter(ABC):
    name: str

    @abstractmethod
    def search(self, lead: LeadKey) -> list[SourceRecord]:
        raise NotImplementedError

    def healthcheck(self) -> SourceHealth:
        return SourceHealth(source=self.name, ok=True, message="adapter loaded")
