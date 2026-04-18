Prompting best practices

Copy page

Comprehensive guide to prompt engineering techniques for Claude's latest models, covering clarity, examples, XML structuring, thinking, and agentic systems.
This is the single reference for prompt engineering with Claude's latest models, including Claude Opus 4.7, Claude Opus 4.6, Claude Sonnet 4.6, and Claude Haiku 4.5. It covers foundational techniques, output control, tool use, thinking, and agentic systems. Jump to the section that matches your situation.

For an overview of model capabilities, see the models overview. For details on what's new in Claude Opus 4.7, see What's new in Claude Opus 4.7. For migration guidance, see the Migration guide.
Prompting Claude Opus 4.7
Claude Opus 4.7 is our most capable generally available model, with particular strengths in long-horizon agentic work, knowledge work, vision, and memory tasks. It performs well out of the box on existing Claude Opus 4.6 prompts. The patterns below cover the behaviors that most often require tuning.

For API parameter changes when migrating from Claude Opus 4.6 (effort levels, task budgets, thinking configuration, sampling-parameter removal, and tokenization), see the migration guide.
Response length and verbosity
Claude Opus 4.7 calibrates response length to how complex it judges the task to be, rather than defaulting to a fixed verbosity. This usually means shorter answers on simple lookups and much longer ones on open-ended analysis.

If your product depends on a certain style or verbosity of output, you may need to tune your prompts. As an example, to decrease verbosity, you might add:

Provide concise, focused responses. Skip non-essential context, and keep examples minimal.
If you see specific examples of kinds of verbosity (i.e. over-explaining), you can add additional instructions in your prompt to prevent them. Positive examples showing how Claude can communicate with the appropriate level of concision tend to be more effective than negative examples or instructions that tell the model what not to do.

Calibrating effort and thinking depth
The effort parameter allows you to tune Claude's intelligence vs. token spend, trading off capability for faster speed and lower costs. Start with the new xhigh effort level for coding and agentic use cases, and use a minimum of high effort for most intelligence-sensitive use cases. Experiment with other effort levels to further tune token usage and intelligence:

max: Max effort can deliver performance gains in some use cases, but may show diminishing returns from increased token usage. This setting can also sometimes be prone to overthinking. We recommend testing max effort for intelligence-demanding tasks.
xhigh (new): Extra high effort is the best setting for most coding and agentic use cases.
high: This setting balances token usage and intelligence. For most intelligence-sensitive use cases, we recommend a minimum of high effort.
medium: Good for cost-sensitive use cases that need to reduce token usage while trading off intelligence.
low: Reserve for short, scoped tasks and latency-sensitive workloads that are not intelligence-sensitive.
Meaningfully changing from Claude Opus 4.6, Claude Opus 4.7 respects effort levels strictly, especially at the low end. At low and medium, the model scopes its work to what was asked rather than going above and beyond. This is good for latency and cost, but on moderately complex tasks running at low effort there is some risk of under-thinking.

If you observe shallow reasoning on complex problems, raise effort to high or xhigh rather than prompting around it. If you need to keep effort at low for latency, add targeted guidance:

This task involves multi-step reasoning. Think carefully through the problem before responding.
We expect effort to be more important for this model than for any prior Opus, and recommend experimenting with it actively when you upgrade.

The triggering behavior for adaptive thinking is steerable. If you find the model thinking more often than you'd like — which can happen with large or complex system prompts — add guidance to steer it. As always, measure the effect of any prompting changes on performance. Example:

Thinking adds latency and should only be used when it will meaningfully improve answer quality — typically for problems that require multi-step reasoning. When in doubt, respond directly.
Conversely, if you're running hard workloads at medium and seeing under-thinking, the first lever is to raise effort. If you need finer control, prompt for it directly.

If you are running Claude Opus 4.7 at max or xhigh effort, set a large max output token budget so the model has room to think and act across its subagents and tool calls. We recommend starting at 64k tokens and tuning from there.
Tool use triggering
Claude Opus 4.7 has a tendency to use tools less often than Claude Opus 4.6 and to use reasoning more. This produces better results in most cases. However, increasing the effort setting is a useful lever to increase the level of tool usage, especially in knowledge work. high or xhigh effort settings show substantially more tool usage in agentic search and coding. For scenarios where you want more tool use, you can also adjust your prompt to explicitly instruct the model about when and how to properly use its tools. For instance, if you find that the model is not using your web search tools, clearly describe why and how it should.

User-facing progress updates
Claude Opus 4.7 provides more regular, higher-quality updates to the user throughout long agentic traces. If you've added scaffolding to force interim status messages ("After every 3 tool calls, summarize progress"), try removing it. If you find that the length or contents of Claude Opus 4.7's user-facing updates are not well-calibrated to your use case, explicitly describe what these updates should look like in the prompt and provide examples.

More literal instruction following
Claude Opus 4.7 interprets prompts more literally and explicitly than Claude Opus 4.6, particularly at lower effort levels. It will not silently generalize an instruction from one item to another, and it will not infer requests you didn't make. The upside of this literalism is precision and less thrash, and it generally performs better for API use cases with carefully tuned prompts, structured extraction, and pipelines where you want predictable behavior. If you need Claude to apply an instruction broadly, state the scope explicitly (for example, "Apply this formatting to every section, not just the first one").

Tone and writing style
As with any new model, prose style on long-form writing may shift. Claude Opus 4.7 is more direct and opinionated, with less validation-forward phrasing and fewer emoji than Claude Opus 4.6's warmer style. If your product relies on a specific voice, re-evaluate style prompts against the new baseline.

For instance, if your product voice is warmer or more conversational, add:

Use a warm, collaborative tone. Acknowledge the user's framing before answering.
Controlling subagent spawning
Claude Opus 4.7 tends to spawn fewer subagents by default. However, this behavior is steerable through prompting; give Claude Opus 4.7 explicit guidance around when subagents are desirable. A toy example for a coding use case:

Do not spawn a subagent for work you can complete directly in a single response (e.g. refactoring a function you can already see).

Spawn multiple subagents in the same turn when fanning out across items or reading multiple files.
Design and frontend defaults
Claude Opus 4.7 has stronger design instincts than Claude Opus 4.6, with a consistent default house style: warm cream/off-white backgrounds (~#F4F1EA), serif display type (Georgia, Fraunces, Playfair), italic word-accents, and a terracotta/amber accent. This reads well for editorial, hospitality, and portfolio briefs, but will feel off for dashboards, dev tools, fintech, healthcare, or enterprise apps — and it appears in slide decks as well as web UIs.

This default is persistent. Generic instructions ("don't use cream," "make it clean and minimal") tend to shift the model to a different fixed palette rather than producing variety. Two approaches work reliably:

1. Specify a concrete alternative. The model follows explicit specs precisely:

Design a desktop landing page for a supplement brand called AEFRM.

The visual direction should come from a cold monochrome atmosphere using pale silver-gray tones that gradually deepen into blue-gray and near-black, similar to a misted metallic surface.

The page should feel sharp and controlled, with a strong sense of structure and restraint.

Use this tonal system across the full page instead of introducing bright accent colors.

Use the uploaded image on the hero design in black and white.

The layout should be built with clear horizontal sections and a centered max-width container. Use 4px corner radius consistently across cards, buttons, inputs, and media frames. Margins should feel generous, with enough empty space around each section so the page breathes.

Typography should use a square, angular sans-serif with wider letter spacing than usual, especially in headings and navigation, so the text feels more engineered and less compressed. Headline text can be large and uppercase, while supporting copy remains short and sparse. The sub texts should be written with Alumni Sans SC in 4-6px like tiny little texts on corners bottom centre like that.

For the structure, start with a hero section containing a strong product statement, one short supporting paragraph, and a clean product placeholder or packshot frame. Below that, add a benefit grid with three or four blocks, then a formulation or ingredients section, and finally a cta.

Buttons should be flat and precise, with subtle hover changes using transition: all 160ms ease out where brightness and border contrast shift slightly rather than using dramatic motion.

Color palette should stay within this range:
#E9ECEC, #C9D2D4, #8C9A9E, #44545B, #11171B.
2. Have the model propose options before building. This breaks the default and gives users control. If you previously relied on temperature for design variety, use this approach — it produces meaningfully different directions across runs. Example prompt:

Before building, propose 4 distinct visual directions tailored to this brief (each as: bg hex / accent hex / typeface — one-line rationale). Ask the user to pick one, then implement only that direction.
Additionally, Claude Opus 4.7 requires less frontend design prompting than previous models to avoid generic patterns that users call the "AI slop" aesthetic. With earlier models, we recommended a lengthier prompt snippet in our frontend-design skill. However, Claude Opus 4.7 generates distinctive, creative frontends with more minimal prompting guidance. This prompt snippet works well with the above prompting advice for variety:

<frontend_aesthetics>
NEVER use generic AI-generated aesthetics like overused font families (Inter, Roboto, Arial, system fonts), cliched color schemes (particularly purple gradients on white or dark backgrounds), predictable layouts and component patterns, and cookie-cutter design that lacks context-specific character. Use unique fonts, cohesive colors and themes, and animations for effects and micro-interactions.
</frontend_aesthetics>
Interactive coding products
Claude Opus 4.7's token usage and behavior can differ between autonomous, asynchronous coding agents with a single user turn and interactive, synchronous coding agents with multiple user turns. Specifically, it tends to use more tokens in interactive settings, primarily because it reasons more after user turns. This can improve long-horizon coherence, instruction following, and coding capabilities in long, interactive coding sessions, but also comes with more token usage. To maximize both performance and token efficiency in coding products, we recommend using xhigh or high effort, adding autonomous features like an auto mode, and reducing the number of human interactions required from your users.
