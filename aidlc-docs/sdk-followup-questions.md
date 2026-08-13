# SDK Follow-Up Questions

Your answers indicated you want `claude-agent-sdk` with a higher-level abstraction.
After researching that package, I found it is the Claude Code CLI harness — designed for
autonomous multi-step tool-use loops, not single-turn document extraction.

Before I update any plans or code, please clarify your intent.

---

## Question 1
Now that you know what `claude-agent-sdk` is, what would you like to do?

A) Proceed with `claude-agent-sdk` anyway — I understand the CLI subprocess overhead and want the agent-loop abstraction for this pipeline

B) Stay with the `anthropic` package (`anthropic>=0.25`, already a dep) but use its **tool use / function calling** feature — let the model dispatch typed tool calls for parse, classify, stage-images actions

C) Stay with the current plan (`anthropic` package, raw `messages.create`) — my original intent was just consistency with the `anthropic` package, which is already correct

D) Other (please describe after [Answer]: tag below)

[Answer]:  B, not vanilla tool calls but using MCPs
