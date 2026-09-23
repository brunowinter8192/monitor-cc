# INFRASTRUCTURE
from test_strip_fix_fixtures import (
    check, tool_result_str, text_block,
    _strip_pasted_content_wrapper, _apply_pasted_content_strip,
    apply_modification_rules, attribute_chunk, _MSG_CODE_TO_FN,
)

_CASE_A_WHOLE = '\n\n<pasted_content id="ffe5">\nÜberschrift für Box anlegen\n\n1. wie setze ich die überschrift\n—> Ich hätte es gerne so das man über der box generell eine statusleiste hat. Das heißt in der statusleiste wird zum einen angezeigt, wie viele bilder sind in dei box reingezogen, liegen also auf der eben direkt unterhalb der box also auf der sturktur darunter\n—> das zweite für Textfelder, und dann soll es einfach noch einen button geben oder ein label was man von blank auf grün setzen kann wenn die task erledigt ist, setzt man das label auf grün wird der hintergrund der box leicht grün\n—> und dann eben ncoh ein feld wenn ich das drücke kann ich für die box eine überschrift setzen. Soweit der plan \n</pasted_content id="ffe5">\n'

_CASE_G_TRAILING = '\n\n<pasted_content id="39da">\nok passt. also für das matter ist noch folgendes offen:\nCOKA, Controlling und Kostenanalyse\n- Ewert, Wagenhofer, Rohlfing-Bastian (2023): Interne Unternehmensrechnung,\xa09. Auflage.\n  - Die UB hat es online bei Springer, als ganzes Buch zum Herunterladen.\n- Küpper et al. (2024): Controlling. Konzeption, Aufgaben und Instrumente,\xa07. Auflage.\n  - Die UB hat es online über WISO, als ganzes Buch zum Herunterladen.\n- Coenenberg et al. (2024): Kostenrechnung und Kostenanalyse,\xa010. Auflage.\n  - Die UB hat es online über WISO und über Nomos.\n\nDie hole ich dann am 01.10 wenn ich den zugang habe. \n</pasted_content id="39da">\n\n was du mal machen kannst ist. skill websearch-pdf aktiveren du kannst auch schonmal eine collection wise2627 refernce anlegen wo das rienkommt. /Users/brunowinter2000/Documents/wise2627 von dsia und von KAI1 habe ich jetzt die literatur am start. da kannst du mir mal den commadn zum kovert geben bitte.'

_CASE_G_LEADING = 'so ein bullshit. die meinen damit wenn ich eine KI damit traineiren. rag ist komplett finde wenn cih ein cloud provider modell nutze da gibt es 0 probleme. \n\n<pasted_content id="39da">\nNun eben vllt auch die frage wo es sich lohnt schonmal in die Literatur reinzuschauen ich mein klar die uni geht in 3 wochen los es lohnt isch jetzt nicht mehr crazy und ich kenne es auch von der hka vom bachelor eehr so das die literatur nice to ahve ist aber ich hab im bachelor nie auch nur ein buch gelesen oder so was da als literatur angegeben wurde. Frage ist ob das jetzt im master genauso geht. keine ahnung. Würde mich da jetzt nicht verrückt machen und vor uni beginn 10 bücher versuchen zu lesen aber einfach das die schonmal da liegen und man mal rein kann wenn man will.\nBzw dief rage ist jetzt, wenn ich bock habe schonmal was vorzuarbeiten was würde sich wirklich lohnen. ich denke das buch in Asia und in dem kat1 zu lesen würde schonmal sinn machen aber mehr würd eich auch nicht amchen. \n</pasted_content id="39da">\n'

_CASE_G_SHORT_LEADING = 'ok frage \n\n<pasted_content id="39da">\nDie frage ist gernell wie ich mich bestmöglich vorbereite. Also cih ahbe meinen bisherigen lernablauf immer so gestaltet und war damit eig recht zufrieden. \n\n1. Foliensatz ziehen in md dokument Notizen machen\n2. foliensatz auf das eindampfen was wirklich relevant ist zb sagen wor von 500 seiten nehme ich die 200 wo ich denke das wird relevant sein der rest ist basically horseshit. \n—> am ende habe ich 200 flien inkl Überschriften\n3. zu jeder der seiten aufschriebn in bullets wie ich den inhalt erklären würde\n4. nur die üebrschriften im md stehen lassen und dann aus dem kopf erklären und gegen das halten was ich davor erklärt hatte also die mustererklärung in meinen worten\n</pasted_content id="39da">\n'

_CASE_FP_ASSISTANT_FENCE = '**Kein Worker hat bisher eine markierte Einfügung bekommen (Fakt).**\n- Der Worker statusbar bekam seine Nachrichten auf dem alten Weg ohne Markierung.\n    - In seinem Protokoll steht deshalb keine Hülle "pasted_content".\n- Die Hülle gab es nur in der Wegwerf-Sitzung aus dem Experiment.\n    - Deren Protokoll habe ich nach dem Test gelöscht.\n\n**Ein echtes Beispiel gibt es aber in dieser Sitzung hier.**\n- Dein Plan zur Statusleiste um 12:04 Uhr kam als Einfügung bei mir an.\n- Im Protokoll dieser Sitzung sieht er so aus:\n\n```\n<pasted_content id="ffe5">\nÜberschrift für Box anlegen\n\n1. wie setze ich die überschrift\n—> Ich hätte es gerne so das man über der box generell eine statusleiste hat. ...\n</pasted_content id="ffe5">\n```\n\n- Du siehst es im Monitor bei dieser Main-Sitzung an genau dieser Nachricht.'

_CASE_TOOL_RESULT_WELLFORMED_PAIR = ('\'hello short test 12345\'\n===\n\'\\n\\n<pasted_content id="a3db">\\nThis is filler line '
    'number 01 for a multiline paste test.\\nThis is filler line number 02 for a multiline paste test.\\n'
    'This is filler line number 03 for a multiline paste test.\\n</pasted_content id="a3db">\\n\'\n===')

_CASE_TOOL_RESULT_MALFORMED_TAG = ('Side effect found in B: CC 2.1.280 records a bracketed paste in the transcript wrapped as\n'
    '57\t`<pasted_content id="...">...</pasted_content>`. The model then treats it as pasted data, not\n'
    '58\tas the user\'s own instruction. In the probe it refused the embedded in')

_CASE_TOOL_RESULT_BARE_MENTION = ('## Decision taken by the user\n15\tBoth `worker_send` and the spawn inject use bracketed paste. '
    'The `<pasted_content>` wrapper CC then\n16\tadds is stripped by the monitor-cc proxy; that is a separate worker\'s job, not yours.\n17\t\n18\t#')

_CASE_TOOL_RESULT_WORD_MENTION = ('1\t# Worker task: strip the pasted_content wrapper in the proxy (Area: worker_message_delivery)\n'
    '2\t\n3\tYour working directory for ALL work is the monitor-cc worktree:')

# FUNCTIONS


def pc01_real_whole_message_wrap_stripped():
    open_tag = '<pasted_content id="ffe5">'
    close_tag = '</pasted_content id="ffe5">'
    expected = _CASE_A_WHOLE.replace(open_tag, '').replace(close_tag, '')
    new_content, removed = _strip_pasted_content_wrapper(_CASE_A_WHOLE)
    check('PC01_tags_removed_only', new_content == expected, repr(new_content))
    check('PC01_pasted_text_intact', 'Überschrift für Box anlegen' in new_content)
    check('PC01_no_tag_left', '<pasted_content' not in new_content and '</pasted_content' not in new_content, repr(new_content))
    check('PC01_removed_both_tags', removed == [open_tag, close_tag], removed)


def pc02_real_wrap_then_trailing_text_same_message():
    open_tag = '<pasted_content id="39da">'
    close_tag = '</pasted_content id="39da">'
    expected = _CASE_G_TRAILING.replace(open_tag, '').replace(close_tag, '')
    new_content, removed = _strip_pasted_content_wrapper(_CASE_G_TRAILING)
    check('PC02_tags_removed_only', new_content == expected, repr(new_content))
    check('PC02_trailing_text_preserved', 'was du mal machen kannst ist. skill websearch-pdf aktiveren' in new_content)
    check('PC02_removed_both_tags', removed == [open_tag, close_tag], removed)


def pc03_real_leading_text_then_wrap():
    open_tag = '<pasted_content id="39da">'
    close_tag = '</pasted_content id="39da">'
    expected = _CASE_G_LEADING.replace(open_tag, '').replace(close_tag, '')
    new_content, removed = _strip_pasted_content_wrapper(_CASE_G_LEADING)
    check('PC03_tags_removed_only', new_content == expected, repr(new_content))
    check('PC03_leading_text_preserved', new_content.startswith('so ein bullshit. die meinen damit'), repr(new_content)[:80])
    check('PC03_removed_both_tags', removed == [open_tag, close_tag], removed)


def pc04_real_short_leading_text_then_wrap():
    open_tag = '<pasted_content id="39da">'
    close_tag = '</pasted_content id="39da">'
    expected = _CASE_G_SHORT_LEADING.replace(open_tag, '').replace(close_tag, '')
    new_content, removed = _strip_pasted_content_wrapper(_CASE_G_SHORT_LEADING)
    check('PC04_tags_removed_only', new_content == expected, repr(new_content))
    check('PC04_leading_text_preserved', new_content.startswith('ok frage'), repr(new_content)[:40])
    check('PC04_removed_both_tags', removed == [open_tag, close_tag], removed)


def pc05_real_fenced_quote_in_assistant_role_preserved_whole():
    msgs = [{'role': 'assistant', 'content': text_block(_CASE_FP_ASSISTANT_FENCE)}]
    new_msgs, mods, removed_by_idx, changed, _inj, _ops = _apply_pasted_content_strip(msgs)
    check('PC05_assistant_untouched', new_msgs == msgs)
    check('PC05_no_change_recorded', changed == [])
    check('PC05_no_mod', mods == [])
    check('PC05_no_removed', removed_by_idx == {})


def pc06_real_tool_result_wellformed_pair_preserved():
    msgs = [{'role': 'user', 'content': tool_result_str(_CASE_TOOL_RESULT_WELLFORMED_PAIR)}]
    new_msgs, mods, removed_by_idx, changed, _inj, _ops = _apply_pasted_content_strip(msgs)
    check('PC06_tool_result_untouched', new_msgs[0]['content'][0]['content'] == _CASE_TOOL_RESULT_WELLFORMED_PAIR)
    check('PC06_no_change_recorded', changed == [])
    check('PC06_no_mod', mods == [])
    check('PC06_no_removed', removed_by_idx == {})


def pc07_real_tool_result_malformed_tag_mention_preserved():
    msgs = [{'role': 'user', 'content': tool_result_str(_CASE_TOOL_RESULT_MALFORMED_TAG)}]
    new_msgs, mods, removed_by_idx, changed, _inj, _ops = _apply_pasted_content_strip(msgs)
    check('PC07_tool_result_untouched', new_msgs[0]['content'][0]['content'] == _CASE_TOOL_RESULT_MALFORMED_TAG)
    check('PC07_no_change_recorded', changed == [])
    check('PC07_no_mod', mods == [])


def pc08_real_tool_result_bare_mention_preserved():
    msgs = [{'role': 'user', 'content': tool_result_str(_CASE_TOOL_RESULT_BARE_MENTION)}]
    new_msgs, mods, removed_by_idx, changed, _inj, _ops = _apply_pasted_content_strip(msgs)
    check('PC08_tool_result_untouched', new_msgs[0]['content'][0]['content'] == _CASE_TOOL_RESULT_BARE_MENTION)
    check('PC08_no_change_recorded', changed == [])
    check('PC08_no_mod', mods == [])


def pc09_real_tool_result_word_mention_preserved():
    msgs = [{'role': 'user', 'content': tool_result_str(_CASE_TOOL_RESULT_WORD_MENTION)}]
    new_msgs, mods, removed_by_idx, changed, _inj, _ops = _apply_pasted_content_strip(msgs)
    check('PC09_tool_result_untouched', new_msgs[0]['content'][0]['content'] == _CASE_TOOL_RESULT_WORD_MENTION)
    check('PC09_no_change_recorded', changed == [])
    check('PC09_no_mod', mods == [])


def pc10_pass_role_gate_and_mod_and_ops():
    msgs = [
        {'role': 'assistant', 'content': text_block(_CASE_A_WHOLE)},
        {'role': 'user', 'content': _CASE_A_WHOLE},
    ]
    new_msgs, mods, removed_by_idx, changed, _inj, ops = _apply_pasted_content_strip(msgs)
    check('PC10_assistant_untouched', new_msgs[0] == msgs[0])
    check('PC10_user_msg_changed', changed == [1])
    check('PC10_mod_name', mods == ['stripped_pasted_content_wrapper'], mods)
    check('PC10_removed_chunks', removed_by_idx[1] == ['<pasted_content id="ffe5">', '</pasted_content id="ffe5">'], removed_by_idx)
    check('PC10_ops_recorded', 0 in ops.get(1, {}), ops)


def pc11_full_pipeline_attribution_via_strip_vocab():
    payload = {
        'system': [],
        'messages': [{'role': 'user', 'content': _CASE_A_WHOLE}],
    }
    modified, modifications, _orig_sys2, _smi, _smo, stripped_msg_removed, _inj, _all_ops = apply_modification_rules(payload)
    check('PC11_mod_recorded', 'stripped_pasted_content_wrapper' in modifications, modifications)
    check('PC11_content_has_no_tags', '<pasted_content' not in modified['messages'][0]['content'], modified['messages'][0]['content'])
    removed_chunks = stripped_msg_removed.get(0, [])
    check('PC11_removed_chunks_present', len(removed_chunks) >= 2, removed_chunks)
    codes = {attribute_chunk(c) for c in removed_chunks}
    check('PC11_attributed_as_PC', codes == {'PC'}, codes)
    check('PC11_fn_map_entry', _MSG_CODE_TO_FN.get('PC') == '_apply_pasted_content_strip')
