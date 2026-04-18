
Of course, when limiting the number of required user interactions, it's important to specify the task, intent, and relevant constraints upfront in the first human turn. Providing well-specified, clear, and accurate task descriptions upfront can help maximize autonomy and intelligence while minimizing extra token usage after user turns. We find that because Claude Opus 4.7 is more autonomous than prior models, this usage pattern helps to maximize performance. In contrast, ambiguous or underspecified prompts conveyed progressively over multiple user turns tend to relatively reduce token efficiency and sometimes performance.

Code review harnesses
Claude Opus 4.7 is meaningfully better at finding bugs than prior models, and has both higher recall and precision in our evals — 11pp better recall in one of our hardest bug-finding evals based on real Anthropic PRs. However, if your code-review harness was tuned for an earlier model, you may initially see lower recall. This is likely a harness effect, not a capability regression. When a review prompt says things like "only report high-severity issues," "be conservative," or "don't nitpick," Claude Opus 4.7 may follow that instruction more faithfully than earlier models did — it may investigate the code just as thoroughly, identify the bugs, and then not report findings it judges to be below your stated bar. This can show up as the model doing the same depth of investigation but converting fewer investigations into reported findings, especially on lower-severity bugs. Precision typically rises, but measured recall can fall even though the model's underlying bug-finding ability has improved.

Some recommended prompt language:

Report every issue you find, including ones you are uncertain about or consider low-severity. Do not filter for importance or confidence at this stage - a separate verification step will do that. Your goal here is coverage: it is better to surface a finding that later gets filtered out than to silently drop a real bug. For each finding, include your confidence level and an estimated severity so a downstream filter can rank them.
This prompt can be used without having an actual second step, but moving confidence filtering out of the finding step often helps. If your harness has a separate verification, deduplication, or ranking stage, tell the model explicitly that its job at the finding stage is coverage rather than filtering.

If you do want the model to self-filter in a single pass, be concrete about where the bar is rather than using qualitative terms like "important" — for example, "report any bugs that could cause incorrect behavior, a test failure, or a misleading result; only omit nits like pure style or naming preferences."

We recommend iterating on prompts against a subset of your evals or test cases to validate recall or F1 score gains.

Computer use
Computer use capability works across resolutions, up to a new maximum resolution of 2576px / 3.75MP. In our computer use testing, we find that sending images at 1080p provides a good balance of performance and cost.

For particularly cost-sensitive workloads, we recommend 720p or 1366×768 as lower-cost options with strong performance. We recommend that you conduct your own testing to find the ideal settings for your use case; experimenting with effort settings can also help tune the model's behavior.

General principles
Be clear and direct
Claude responds well to clear, explicit instructions. Being specific about your desired output can help enhance results. If you want "above and beyond" behavior, explicitly request it rather than relying on the model to infer this from vague prompts.

Think of Claude as a brilliant but new employee who lacks context on your norms and workflows. The more precisely you explain what you want, the better the result.

Golden rule: Show your prompt to a colleague with minimal context on the task and ask them to follow it. If they'd be confused, Claude will be too.

Be specific about the desired output format and constraints.
Provide instructions as sequential steps using numbered lists or bullet points when the order or completeness of steps matters.

Example: Creating an analytics dashboard
Add context to improve performance
Providing context or motivation behind your instructions, such as explaining to Claude why such behavior is important, can help Claude better understand your goals and deliver more targeted responses.


Example: Formatting preferences
Claude is smart enough to generalize from the explanation.

Use examples effectively
Examples are one of the most reliable ways to steer Claude's output format, tone, and structure. A few well-crafted examples (known as few-shot or multishot prompting) can dramatically improve accuracy and consistency.

When adding examples, make them:

Relevant: Mirror your actual use case closely.
Diverse: Cover edge cases and vary enough that Claude doesn't pick up unintended patterns.
Structured: Wrap examples in <example> tags (multiple examples in <examples> tags) so Claude can distinguish them from instructions.
Include 3–5 examples for best results. You can also ask Claude to evaluate your examples for relevance and diversity, or to generate additional ones based on your initial set.
Structure prompts with XML tags
XML tags help Claude parse complex prompts unambiguously, especially when your prompt mixes instructions, context, examples, and variable inputs. Wrapping each type of content in its own tag (e.g. <instructions>, <context>, <input>) reduces misinterpretation.

Best practices:

Use consistent, descriptive tag names across your prompts.
Nest tags when content has a natural hierarchy (documents inside <documents>, each inside <document index="n">).
Give Claude a role
Setting a role in the system prompt focuses Claude's behavior and tone for your use case. Even a single sentence makes a difference:

Python
import anthropic

client = anthropic.Anthropic()

message = client.messages.create(
    model="claude-opus-4-7",
    max_tokens=1024,
    system="You are a helpful coding assistant specializing in Python.",
    messages=[
        {"role": "user", "content": "How do I sort a list of dictionaries by key?"}
    ],
)
print(message.content)
Long context prompting
When working with large documents or data-rich inputs (20k+ tokens), structure your prompt carefully to get the best results:

Put longform data at the top: Place your long documents and inputs near the top of your prompt, above your query, instructions, and examples. This can significantly improve performance across all models.

Queries at the end can improve response quality by up to 30% in tests, especially with complex, multi-document inputs.
Structure document content and metadata with XML tags: When using multiple documents, wrap each document in <document> tags with <document_content> and <source> (and other metadata) subtags for clarity.


Example multi-document structure
Ground responses in quotes: For long document tasks, ask Claude to quote relevant parts of the documents first before carrying out its task. This helps Claude cut through the noise of the rest of the document's contents.


Example quote extraction
Model self-knowledge
If you would like Claude to identify itself correctly in your application or use specific API strings:

Sample prompt for model identity
The assistant is Claude, created by Anthropic. The current model is Claude Opus 4.7.
For LLM-powered apps that need to specify model strings:

Sample prompt for model string
When an LLM is needed, please default to Claude Opus 4.7 unless the user requests otherwise. The exact model string for Claude Opus 4.7 is claude-opus-4-7.
Output and formatting
Communication style and verbosity
Claude's latest models have a more concise and natural communication style compared to previous models:

More direct and grounded: Provides fact-based progress reports rather than self-celebratory updates
More conversational: Slightly more fluent and colloquial, less machine-like
Less verbose: May skip detailed summaries for efficiency unless prompted otherwise
This means Claude may skip verbal summaries after tool calls, jumping directly to the next action. If you prefer more visibility into its reasoning:

Sample prompt
After completing a task that involves tool use, provide a quick summary of the work you've done.
Control the format of responses
There are a few particularly effective ways to steer output formatting:

Tell Claude what to do instead of what not to do

