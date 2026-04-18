
Medium for most applications
Low for high-volume or latency-sensitive workloads
Set a large max output token budget (64k tokens recommended) at medium or high effort to give the model room to think and act
When to use Opus 4.7 instead: For the hardest, longest-horizon problems (large-scale code migrations, deep research, extended autonomous work), Opus 4.7 remains the right choice. Sonnet 4.6 is optimized for workloads where fast turnaround and cost efficiency matter most.

If you're not using extended thinking
If you're not using extended thinking on Claude Sonnet 4.5, you can continue without it on Claude Sonnet 4.6. You should explicitly set effort to the level appropriate for your use case. At low effort with thinking disabled, you can expect similar or better performance relative to Claude Sonnet 4.5 with no extended thinking.

Python
client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=8192,
    thinking={"type": "disabled"},
    output_config={"effort": "low"},
    messages=[{"role": "user", "content": "..."}],
)
If you're using extended thinking
If you're using extended thinking with budget_tokens on Claude Sonnet 4.5, it is still functional on Claude Sonnet 4.6 but is deprecated. Migrate to adaptive thinking with the effort parameter.

Migrating to adaptive thinking
Adaptive thinking is particularly well suited to the following workload patterns:

Autonomous multi-step agents: coding agents that turn requirements into working software, data analysis pipelines, and bug finding where the model runs independently across many steps. Adaptive thinking lets the model calibrate its reasoning per step, staying on path over longer trajectories. For these workloads, start at high effort. If latency or token usage is a concern, scale down to medium.
Computer use agents: Claude Sonnet 4.6 achieved best-in-class accuracy on computer use evaluations using adaptive mode.
Bimodal workloads: a mix of easy and hard tasks where adaptive skips thinking on simple queries and reasons deeply on complex ones.
When using adaptive thinking, evaluate medium and high effort on your tasks. The right level depends on your workload's tradeoff between quality, latency, and token usage.

Python
client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=64000,
    thinking={"type": "adaptive"},
    output_config={"effort": "high"},
    messages=[{"role": "user", "content": "..."}],
)
Keeping budget_tokens during migration
If you need to keep budget_tokens temporarily while migrating, a budget around 16k tokens provides headroom for harder problems without risk of runaway token usage. This configuration is deprecated and will be removed in a future model release.

For coding use cases (agentic coding, tool-heavy workflows, code generation), start with medium effort:

Python
client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=16384,
    thinking={"type": "enabled", "budget_tokens": 16384},
    output_config={"effort": "medium"},
    messages=[{"role": "user", "content": "..."}],
)
For chat and non-coding use cases (chat, content generation, search, classification), start with low effort:

Python
client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=8192,
    thinking={"type": "enabled", "budget_tokens": 16384},
    output_config={"effort": "low"},
    messages=[{"role": "user", "content": "..."}],
)
