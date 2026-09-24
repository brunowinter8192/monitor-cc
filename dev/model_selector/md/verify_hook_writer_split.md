# hook_writer.py split verification

UserPromptSubmit -> hooks.json: {'test-session-model-selector': {'status': 'working', 'cwd': '/tmp/test-cwd'}}
Stop -> hooks.json: {'test-session-model-selector': {'status': 'idle', 'cwd': '/tmp/test-cwd'}}
msg_queue.json created: False (expected False)
queue.lock created: False (expected False)

RESULT: PASS — hook-state half intact, no queue side effects.
