from typing import Protocol

from app.models.pipeline_job import PipelineJob


class PipelineSource(Protocol):
    def load(self) -> list[PipelineJob]: ...
