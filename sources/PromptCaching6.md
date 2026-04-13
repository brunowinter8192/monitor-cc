

Cache keys are generated using a cryptographic hash of the prompts up to the cache control point. This means only requests with identical prompts can access a specific cache.
Caches are organization-specific. Users within the same organization can access the same cache if they use identical prompts, but caches are not shared across different organizations, even for identical prompts.
The caching mechanism is designed to maintain the integrity and privacy of each unique conversation or context.
It's safe to use cache_control anywhere in your prompts. For caching to produce reads, place the breakpoint at the end of a stable prefix: placing it on a block that changes every request (such as a timestamp or the user's arbitrary input) writes a fresh entry each time and never hits.
These measures ensure that prompt caching maintains data privacy and security while offering performance benefits.

Note: Starting February 5, 2026, caches will be isolated per workspace instead of per organization. This change applies to the Claude API and Azure AI Foundry (preview). See Cache storage and sharing for details.

Can I use prompt caching with the Batches API?
Yes, it is possible to use prompt caching with your Batches API requests. However, because asynchronous batch requests can be processed concurrently and in any order, cache hits are provided on a best-effort basis.

The 1-hour cache can help improve your cache hits. The most cost effective way of using it is the following:

Gather a set of message requests that have a shared prefix.
Send a batch request with just a single request that has this shared prefix and a 1-hour cache block. This will get written to the 1-hour cache.
As soon as this is complete, submit the rest of the requests. You will have to monitor the job to know when it completes.
This is typically better than using the 5-minute cache simply because it's common for batch requests to take between 5 minutes and 1 hour to complete. Anthropic is considering ways to improve these cache hit rates and making this process more straightforward.

Why am I seeing the error `AttributeError: 'Beta' object has no attribute 'prompt_caching'` in Python?
This error typically appears when you have upgraded your SDK or you are using outdated code examples. Prompt caching is now generally available, so you no longer need the beta prefix. Instead of:

Python
client.beta.prompt_caching.messages.create(**params)
Simply use:

Python
client.messages.create(**params)

Why am I seeing 'TypeError: Cannot read properties of undefined (reading 'messages')'?
This error typically appears when you have upgraded your SDK or you are using outdated code examples. Prompt caching is now generally available, so you no longer need the beta prefix. Instead of:

TypeScript
client.beta.promptCaching.messages.create(/* ... */);
Simply use:

client.messages.create(/* ... */);