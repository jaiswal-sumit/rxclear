"""Deterministic safety controls for the medication safety orchestrator.

Adapted from the workshop's steering-handler + hook patterns:
- MedicationWorkflowHandler enforces tool ordering — clinical claims must be
  grounded in FDA/RxNav tool results, never the model's memory.
- RateLimiterHook caps tool calls per request so a runaway loop can't
  hammer the drug APIs.
"""

from strands.hooks import (
    BeforeInvocationEvent,
    BeforeToolCallEvent,
    HookProvider,
    HookRegistry,
)
from strands.vended_plugins.steering import (
    Guide,
    LedgerProvider,
    Proceed,
    SteeringHandler,
    ToolSteeringAction,
)


class MedicationWorkflowHandler(SteeringHandler):
    """Enforce: verify drug facts BEFORE checking interactions or rewriting.

    The orchestrator must call lookup_drug_facts (RxNav + FDA labels) before
    it may cross-reference interactions or emit patient-facing language.
    This is enforcement, not a prompt suggestion — the model cannot skip it.
    """

    name = "medication-workflow"

    def __init__(self) -> None:
        super().__init__(context_providers=[LedgerProvider()])

    async def steer_before_tool(
        self, *, agent, tool_use, **kwargs
    ) -> ToolSteeringAction:
        name = tool_use.get("name")
        ledger = self.steering_context.data.get("ledger", {})
        tool_calls = ledger.get("tool_calls", [])
        facts_verified = any(
            c["tool_name"] == "lookup_drug_facts" and c["status"] == "success"
            for c in tool_calls
        )

        if name == "check_interactions_for" and not facts_verified:
            return Guide(
                reason=(
                    "Verify all drug names with lookup_drug_facts before "
                    "checking interactions — interaction checks must run "
                    "against verified names, never raw user input."
                )
            )
        if name == "rewrite_plain_language" and not facts_verified:
            return Guide(
                reason=(
                    "Fetch FDA label facts with lookup_drug_facts before "
                    "rewriting — never produce patient-facing clinical text "
                    "that isn't grounded in verified label data."
                )
            )
        return Proceed(reason="Medication workflow order valid")


class RateLimiterHook(HookProvider):
    """Cap each tool at max_calls per agent invocation."""

    def __init__(self, max_calls: int = 5) -> None:
        self.max_calls = max_calls
        self.counts: dict[str, int] = {}

    def register_hooks(self, registry: HookRegistry) -> None:
        registry.add_callback(BeforeInvocationEvent, self.reset)
        registry.add_callback(BeforeToolCallEvent, self.check)

    def reset(self, event: BeforeInvocationEvent) -> None:
        self.counts = {}

    def check(self, event: BeforeToolCallEvent) -> None:
        name = event.tool_use["name"]
        self.counts[name] = self.counts.get(name, 0) + 1
        if self.counts[name] > self.max_calls:
            event.cancel_tool = (
                f"'{name}' hit the {self.max_calls}-call limit. "
                "Do NOT call this tool again — answer with the data you have."
            )
