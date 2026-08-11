"""Dedicated P4.5-3 showcase runtime and injected agent-executor seam."""

from __future__ import annotations

from typing import Protocol

from app.agent.runtime import RuntimeRequest
from app.api.context import session_context
from app.api.events import InMemoryEventBus
from app.showcase.contracts import Limitation
from app.showcase.delivery import ShowcaseDeliveryResult
from app.showcase.research import (
    LiveSourceCollector,
    ShowcaseRunResult,
    collector_context,
)


class ShowcaseAgentExecutor(Protocol):
    async def run(
        self,
        request: RuntimeRequest,
        collector: LiveSourceCollector,
    ) -> str: ...


class ShowcaseDelivery(Protocol):
    def deliver(
        self, request: RuntimeRequest, result: ShowcaseRunResult
    ) -> ShowcaseDeliveryResult: ...


class ShowcaseResearchRuntime:
    """Run one explicitly configured live research task and optional delivery."""

    def __init__(
        self,
        events: InMemoryEventBus,
        executor: ShowcaseAgentExecutor | None,
        limitations: tuple[Limitation, ...] = (),
        delivery: ShowcaseDelivery | None = None,
    ) -> None:
        self._events = events
        self._executor = executor
        self._limitations = tuple(limitations)
        self._delivery = delivery

    async def run(self, request: RuntimeRequest) -> ShowcaseRunResult:
        thread_id = request.context.thread_id
        collector = LiveSourceCollector(thread_id)
        for limitation in self._limitations:
            collector.add_limitation(limitation)

        with session_context(request.context), collector_context(collector):
            self._events.emit(
                thread_id,
                "agent_started",
                "showcase-research-agent",
                {"agent_name": "showcase-research-agent"},
            )
            if self._executor is None:
                answer = "Showcase research is unavailable."
            else:
                try:
                    answer = await self._executor.run(request, collector)
                except Exception:
                    collector.add_limitation(
                        Limitation(
                            code="agent-failed",
                            source_kind=None,
                            message="showcase agent execution failed",
                        )
                    )
                    answer = "Showcase research is unavailable."
            self._events.emit(
                thread_id,
                "agent_completed",
                "showcase-research-agent",
                {"agent_name": "showcase-research-agent"},
            )
            base_result = collector.snapshot(answer)
            if self._delivery is None:
                return base_result
            try:
                delivery_result = self._delivery.deliver(request, base_result)
            except Exception:
                collector.add_limitation(
                    Limitation(
                        code="delivery-failed",
                        source_kind=None,
                        message="showcase delivery failed",
                    )
                )
                return collector.snapshot(answer)
            for limitation in delivery_result.limitations:
                collector.add_limitation(limitation)
            return collector.snapshot(answer, delivery_result.artifacts)
