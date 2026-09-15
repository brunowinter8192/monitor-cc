# INFRASTRUCTURE

# FUNCTIONS

def _mk_entry(model='claude-3-opus-20240229', msg_count=1, msgs=None, **kw):
    e = {
        'model': model,
        'message_count': msg_count,
        'messages': msgs or [],
        'system_total_chars': 200,
        'tools_total_chars': 100,
        'messages_total_chars': sum(m.get('chars', 0) for m in (msgs or [])),
        'tools_count': 0, 'tools_names': [], 'tools_defs': [], 'tools_hash': '',
        'timestamp': '2024-01-01T00:00:00',
    }
    e.update(kw)
    return e


def _mk_msg(role='user', chars=50, blocks=None, **kw):
    m = {'role': role, 'type': 'text', 'chars': chars}
    if blocks is not None:
        m['blocks'] = blocks
    m.update(kw)
    return m


def _mk_blk(btype='text', chars=50, full_text='sample text\nline 2', **kw):
    b = {'type': btype, 'chars': chars}
    if btype == 'thinking':
        b['sig_chars'] = kw.pop('sig_chars', 8)
    else:
        b['full_text'] = full_text
    b.update(kw)
    return b
