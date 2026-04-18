Instead of: "Do not use markdown in your response"
Try: "Your response should be composed of smoothly flowing prose paragraphs."
Use XML format indicators

Try: "Write the prose sections of your response in <smoothly_flowing_prose_paragraphs> tags."
Match your prompt style to the desired output

The formatting style used in your prompt may influence Claude's response style. If you are still experiencing steerability issues with output formatting, try matching your prompt style to your desired output style as closely as possible. For example, removing markdown from your prompt can reduce the volume of markdown in the output.
Use detailed prompts for specific formatting preferences

For more control over markdown and formatting usage, provide explicit guidance:
Sample prompt to minimize markdown
<avoid_excessive_markdown_and_bullet_points>
When writing reports, documents, technical explanations, analyses, or any long-form content, write in clear, flowing prose using complete paragraphs and sentences. Use standard paragraph breaks for organization and reserve markdown primarily for `inline code`, code blocks (```...```), and simple headings (###, and ###). Avoid using **bold** and *italics*.

DO NOT use ordered lists (1. ...) or unordered lists (*) unless : a) you're presenting truly discrete items where a list format is the best option, or b) the user explicitly requests a list or ranking

Instead of listing items with bullets or numbers, incorporate them naturally into sentences. This guidance applies especially to technical writing. Using prose instead of excessive formatting will improve user satisfaction. NEVER output a series of overly short bullet points.

Your goal is readable, flowing text that guides the reader naturally through ideas rather than fragmenting information into isolated points.
</avoid_excessive_markdown_and_bullet_points>
LaTeX output
Claude Opus 4.6 defaults to LaTeX for mathematical expressions, equations, and technical explanations. If you prefer plain text, add the following instructions to your prompt:

Sample prompt
Format your response in plain text only. Do not use LaTeX, MathJax, or any markup notation such as \( \), $, or \frac{}{}. Write all math expressions using standard text characters (e.g., "/" for division, "*" for multiplication, and "^" for exponents).
Document creation
Claude's latest models excel at creating presentations, animations, and visual documents with impressive creative flair and strong instruction following. The models produce polished, usable output on the first try in most cases.

For best results with document creation:

Sample prompt
Create a professional presentation on [topic]. Include thoughtful design elements, visual hierarchy, and engaging animations where appropriate.
Migrating away from prefilled responses
Starting with Claude 4.6 models and Claude Mythos Preview, prefilled responses on the last assistant turn are no longer supported. On Mythos Preview, requests with prefilled assistant messages return a 400 error. Model intelligence and instruction following has advanced such that most use cases of prefill no longer require it. Existing models will continue to support prefills, and adding assistant messages elsewhere in the conversation is not affected.

Here are common prefill scenarios and how to migrate away from them:


Controlling output formatting

Eliminating preambles

Avoiding bad refusals

Continuations

Context hydration and role consistency
Tool use
Tool usage
Claude's latest models are trained for precise instruction following and benefit from explicit direction to use specific tools. If you say "can you suggest some changes," Claude will sometimes provide suggestions rather than implementing them, even if making changes might be what you intended.

For Claude to take action, be more explicit:


Example: Explicit instructions
To make Claude more proactive about taking action by default, you can add this to your system prompt:

Sample prompt for proactive action
<default_to_action>
By default, implement changes rather than only suggesting them. If the user's intent is unclear, infer the most useful likely action and proceed, using tools to discover any missing details instead of guessing. Try to infer the user's intent about whether a tool call (e.g., file edit or read) is intended or not, and act accordingly.
</default_to_action>
On the other hand, if you want the model to be more hesitant by default, less prone to jumping straight into implementations, and only take action if requested, you can steer this behavior with a prompt like the below:

Sample prompt for conservative action
<do_not_act_before_instructions>
Do not jump into implementatation or changes files unless clearly instructed to make changes. When the user's intent is ambiguous, default to providing information, doing research, and providing recommendations rather than taking action. Only proceed with edits, modifications, or implementations when the user explicitly requests them.
</do_not_act_before_instructions>
Claude Opus 4.5 and Claude Opus 4.6 are also more responsive to the system prompt than previous models. If your prompts were designed to reduce undertriggering on tools or skills, these models may now overtrigger. The fix is to dial back any aggressive language. Where you might have said "CRITICAL: You MUST use this tool when...", you can use more normal prompting like "Use this tool when...".

Optimize parallel tool calling
Claude's latest models excel at parallel tool execution. These models will:

Run multiple speculative searches during research
Read several files at once to build context faster
Execute bash commands in parallel (which can even bottleneck system performance)
This behavior is easily steerable. While the model has a high success rate in parallel tool calling without prompting, you can boost this to ~100% or adjust the aggression level:

Sample prompt for maximum parallel efficiency
<use_parallel_tool_calls>
If you intend to call multiple tools and there are no dependencies between the tool calls, make all of the independent tool calls in parallel. Prioritize calling tools simultaneously whenever the actions can be done in parallel rather than sequentially. For example, when reading 3 files, run 3 tool calls in parallel to read all 3 files into context at the same time. Maximize use of parallel tool calls where possible to increase speed and efficiency. However, if some tool calls depend on previous calls to inform dependent values like the parameters, do NOT call these tools in parallel and instead call them sequentially. Never use placeholders or guess missing parameters in tool calls.
</use_parallel_tool_calls>
Sample prompt to reduce parallel execution
Execute operations sequentially with brief pauses between each step to ensure stability.
Thinking and reasoning
Overthinking and excessive thoroughness
Claude Opus 4.6 does significantly more upfront exploration than previous models, especially at higher effort settings. This initial work often helps to optimize the final results, but the model may gather extensive context or pursue multiple threads of research without being prompted. If your prompts previously encouraged the model to be more thorough, you should tune that guidance for Claude Opus 4.6:

Replace blanket defaults with more targeted instructions. Instead of "Default to using [tool]," add guidance like "Use [tool] when it would enhance your understanding of the problem."
Remove over-prompting. Tools that undertriggered in previous models are likely to trigger appropriately now. Instructions like "If in doubt, use [tool]" will cause overtriggering.
Use effort as a fallback. If Claude continues to be overly aggressive, use a lower setting for effort.
In some cases, Claude Opus 4.6 may think extensively, which can inflate thinking tokens and slow down responses. If this behavior is undesirable, you can add explicit instructions to constrain its reasoning, or you can lower the effort setting to reduce overall thinking and token usage.

Sample prompt
When you're deciding how to approach a problem, choose an approach and commit to it. Avoid revisiting decisions unless you encounter new information that directly contradicts your reasoning. If you're weighing two approaches, pick one and see it through. You can always course-correct later if the chosen approach fails.
If you need a hard ceiling on thinking costs, extended thinking with a budget_tokens cap is still functional on Opus 4.6 and Sonnet 4.6 but is deprecated. Prefer lowering the effort setting or using max_tokens as a hard limit with adaptive thinking.

Leverage thinking & interleaved thinking capabilities
Claude's latest models offer thinking capabilities that can be especially helpful for tasks involving reflection after tool use or complex multi-step reasoning. You can guide its initial or interleaved thinking for better results.

Claude Opus 4.6 and Claude Sonnet 4.6 use adaptive thinking (thinking: {type: "adaptive"}), where Claude dynamically decides when and how much to think. Claude calibrates its thinking based on two factors: the effort parameter and query complexity. Higher effort elicits more thinking, and more complex queries do the same. On easier queries that don't require thinking, the model responds directly. In internal evaluations, adaptive thinking reliably drives better performance than extended thinking. Consider moving to adaptive thinking to get the most intelligent responses.
