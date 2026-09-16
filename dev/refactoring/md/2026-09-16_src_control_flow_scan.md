# Control-flow scan of src/ — 2026-09-16

Independent scan for places where code can produce a result via more than one route, or keeps going after something failed. This file states facts only: no classification, no recommendation. Entries are grouped by directory under `src/`, in file:line order.

## src/

### src/pane_error_log.py:18
**Code:**
```python
    except Exception:
        pass
```
**Second path:** swallows the exception and continues with no substitute value, no signal, and no re-raise
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/utils.py:27
**Code:**
```python
    except ValueError:
        return '00:00:00'
```
**Second path:** returns `'00:00:00'`
**Names its path:** no
**Fails loudly outside the observed case:** no


### src/monitor_janitor.py:52-55
**Code:**
```python
def _resolve_monitor_cc_root() -> Path:
    env_root = os.environ.get("MONITOR_CC_ROOT")
    if env_root:
        return Path(env_root)
    return Path(__file__).resolve().parent.parent
```
**Second path:** if `MONITOR_CC_ROOT` is unset or empty, returns a path computed from `__file__` instead
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/proxy_addon.py:9-21
**Code:**
```python
if '_live_' in _stem:
    _session_id = _stem.split('_live_', 1)[-1]
    _live_dir = _here / f'.proxy_live_{_session_id}'
    if (_live_dir / 'proxy').is_dir():
        _src_dir = str(_live_dir)

if _src_dir is None:
    for _candidate in [_here, _here.parent, _here.parent.parent]:
        if (_candidate / 'proxy').is_dir():
            _src_dir = str(_candidate)
            break
    else:
        _src_dir = str(_here)
```
**Second path:** four routes to `_src_dir` in priority order (live-session dir, then three ancestor candidates checked in a loop), and if none of the `proxy`-subdir checks succeed, the `for...else` falls back to `_here` unconditionally with no existence check
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/tmux_launcher.py:96-99
**Code:**
```python
def get_global_history_limit() -> str:
    result = subprocess.run(["tmux", "show-options", "-gv", "history-limit"], capture_output=True, text=True)
    limit = result.stdout.strip() or "2000"
    return limit
```
**Second path:** if `tmux show-options` returns empty stdout (including on command failure, since the returncode is not checked), substitutes the literal string `"2000"`
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/tmux_launcher.py:191-194
**Code:**
```python
    for mode, split_from, pct in pane_specs[1:]:
        raw, present = _list_pane_modes(session_name, win_idx)
        src = present.get(split_from) if split_from else _first_pane_idx(raw)
        if src is not None:
            subprocess.run([
```
**Second path:** when the named `split_from` pane isn't present, falls back to whatever `_first_pane_idx` returns instead; when neither resolves, the pane is silently never created (no `else` branch)
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/tmux_launcher.py:204-210
**Code:**
```python
    for mode, split_from, pct in pane_specs:
        if mode in present:
            continue
        src = present.get(split_from) if (split_from and split_from in present) else _first_pane_idx(raw)
        if src is None:
            continue
        subprocess.run([
            "tmux", "split-window", "-h",
```
**Second path:** same fallback-to-first-pane-index choice as `_create_missing_window`; when `src` is still `None` the loop silently skips creating that pane and moves to the next mode
**Names its path:** no
**Fails loudly outside the observed case:** no

## src/format/

### src/format/token_format.py:60-67
**Code:**
```python
def _fmt_rl_reset_time(epoch_str: str) -> str:
    try:
        ts = datetime.datetime.fromtimestamp(int(epoch_str))
        now = datetime.datetime.now()
        if ts.date() == now.date():
            return ts.strftime('%H:%M')
        return ts.strftime('%a %H:%M')
    except (ValueError, OSError):
        return epoch_str
```
**Second path:** returns the raw, unformatted `epoch_str` input unchanged when it cannot be parsed as a timestamp
**Names its path:** no
**Fails loudly outside the observed case:** no

## src/jsonl/

### src/jsonl/jsonl_parser.py:41-45
**Code:**
```python
def get_message_content(message: dict) -> List[dict]:
    if 'message' in message and isinstance(message['message'], dict):
        content = message['message'].get('content', [])
    else:
        content = message.get('content', [])
```
**Second path:** chooses between two shapes of the same message object (nested `message.message.content` vs. top-level `message.content`) based on which one is present
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/jsonl/jsonl_parser.py:33-38
**Code:**
```python
        except json.JSONDecodeError as e:
            malformed_lines.append({
                'line_number': line_number,
                'error_message': str(e),
                'raw_line': line
            })
```
**Second path:** catches a JSON decode error on one line and continues parsing the remaining lines; the failed line is recorded in a separate `malformed_lines` list returned alongside `messages`
**Names its path:** yes
**Fails loudly outside the observed case:** no

## src/input/

### src/input/click_handler.py:28
**Code:**
```python
    except Exception:
        return False
```
**Second path:** returns `False`
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/input/click_handler.py:37
**Code:**
```python
        except Exception:
            pass
```
**Second path:** swallows the exception and continues with no substitute value, no signal, and no re-raise
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/input/click_handler.py:132
**Code:**
```python
        except Exception:
            return None
```
**Second path:** returns `None`
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/input/click_handler.py:153
**Code:**
```python
    except (ValueError, IndexError):
        return None
```
**Second path:** returns `None`
**Names its path:** no
**Fails loudly outside the observed case:** no


## src/news_pane/

### src/news_pane/log_pane.py:36
**Code:**
```python
        except Exception:
            log_pane_error('news_log')
            time.sleep(LOG_POLL_INTERVAL)
```
**Second path:** catches the exception and continues (side effect only in the handler body, e.g. logging a warning or appending an error record); no value is returned/assigned by the handler itself, and no re-raise
**Names its path:** yes
**Fails loudly outside the observed case:** no

### src/news_pane/log_parser.py:37
**Code:**
```python
    except OSError:
        return None
```
**Second path:** returns `None`
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/news_pane/log_parser.py:44
**Code:**
```python
    except OSError:
        log_pane_error('news_log')
        return []
```
**Second path:** returns `[]`
**Names its path:** yes
**Fails loudly outside the observed case:** no

### src/news_pane/pane.py:62
**Code:**
```python
            except Exception:
                log_pane_error('news')
                wait_for_input(INPUT_POLL_INTERVAL)
```
**Second path:** catches the exception and continues (side effect only in the handler body, e.g. logging a warning or appending an error record); no value is returned/assigned by the handler itself, and no re-raise
**Names its path:** yes
**Fails loudly outside the observed case:** no

### src/news_pane/pane.py:169
**Code:**
```python
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
```
**Second path:** swallows the exception and continues with no substitute value, no signal, and no re-raise
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/news_pane/pane.py:184
**Code:**
```python
    except (FileNotFoundError, subprocess.TimeoutExpired, json.JSONDecodeError, ValueError):
        pass
```
**Second path:** swallows the exception and continues with no substitute value, no signal, and no re-raise
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/news_pane/pane.py:217
**Code:**
```python
    except OSError:
        return False
```
**Second path:** returns `False`
**Names its path:** no
**Fails loudly outside the observed case:** no


### src/news_pane/pane.py:199-202
**Code:**
```python
def _is_running() -> bool:
    if _pipeline_proc is not None and _pipeline_proc.poll() is None:
        return True
    return _is_running_via_log()
```
**Second path:** if the in-process `Popen` handle doesn't confirm a running process (e.g. after this process restarted and lost the handle), falls back to inferring "running" from log file markers instead
**Names its path:** no
**Fails loudly outside the observed case:** no

## src/gpu_pane/

### src/gpu_pane/errors.py:39
**Code:**
```python
    except FileNotFoundError:
        return []
```
**Second path:** returns `[]`
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/gpu_pane/errors.py:47
**Code:**
```python
            except json.JSONDecodeError:
                pass
```
**Second path:** swallows the exception and continues with no substitute value, no signal, and no re-raise
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/gpu_pane/gpu_actions.py:13
**Code:**
```python
    for key in list(_toggle_state.keys()):
        action, ts = _toggle_state[key]
        if now - ts > TOGGLE_TIMEOUT:
            del _toggle_state[key]
            continue
        if key.startswith('port-'):
            try:
                port_n = int(key[5:])
            except ValueError:
                continue
```
**Second path:** silently skips the current loop item and continues with the remaining ones
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/gpu_pane/gpu_actions.py:21
**Code:**
```python
            except ValueError:
                continue
```
**Second path:** catches the exception and continues (side effect only in the handler body, e.g. logging a warning or appending an error record); no value is returned/assigned by the handler itself, and no re-raise
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/gpu_pane/pane.py:60
**Code:**
```python
            except Exception:
                log_pane_error('gpu')
                wait_for_input(INPUT_POLL_INTERVAL)
```
**Second path:** catches the exception and continues (side effect only in the handler body, e.g. logging a warning or appending an error record); no value is returned/assigned by the handler itself, and no re-raise
**Names its path:** yes
**Fails loudly outside the observed case:** no

### src/gpu_pane/status.py:23
**Code:**
```python
    except (FileNotFoundError, subprocess.TimeoutExpired, json.JSONDecodeError, KeyError):
        pass
```
**Second path:** swallows the exception and continues with no substitute value, no signal, and no re-raise
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/gpu_pane/status.py:41
**Code:**
```python
    except OSError:
        pass
```
**Second path:** swallows the exception and continues with no substitute value, no signal, and no re-raise
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/gpu_pane/status.py:57
**Code:**
```python
    for sf in RAG_LOCKS_DIR.glob('server-port-*.json'):
        try:
            state = json.loads(sf.read_text())
        except (json.JSONDecodeError, OSError):
            _warn('malformed_json', f'malformed state file: {sf}', str(sf))
            continue
```
**Second path:** silently skips the current loop item and continues with the remaining ones
**Names its path:** yes
**Fails loudly outside the observed case:** no

### src/gpu_pane/status.py:60
**Code:**
```python
        except (json.JSONDecodeError, OSError):
            _warn('malformed_json', f'malformed state file: {sf}', str(sf))
            continue
```
**Second path:** catches the exception and continues (side effect only in the handler body, e.g. logging a warning or appending an error record); no value is returned/assigned by the handler itself, and no re-raise
**Names its path:** yes
**Fails loudly outside the observed case:** no

### src/gpu_pane/status.py:68
**Code:**
```python
            except ProcessLookupError:
                _warn('dead_pid', f'stale state file: pid {pid} dead', str(sf))
                continue
```
**Second path:** catches the exception and continues (side effect only in the handler body, e.g. logging a warning or appending an error record); no value is returned/assigned by the handler itself, and no re-raise
**Names its path:** yes
**Fails loudly outside the observed case:** no

### src/gpu_pane/status.py:71
**Code:**
```python
            except PermissionError: pass
```
**Second path:** swallows the exception and continues with no substitute value, no signal, and no re-raise
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/gpu_pane/status.py:137
**Code:**
```python
    except (FileNotFoundError, OSError):
        return None
```
**Second path:** returns `None`
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/gpu_pane/status.py:148
**Code:**
```python
    except Exception:
        return False
```
**Second path:** returns `False`
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/gpu_pane/status.py:160
**Code:**
```python
    except Exception:
        pass
```
**Second path:** swallows the exception and continues with no substitute value, no signal, and no re-raise
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/gpu_pane/status.py:173
**Code:**
```python
    except (FileNotFoundError, subprocess.TimeoutExpired, json.JSONDecodeError, ValueError):
        pass
```
**Second path:** swallows the exception and continues with no substitute value, no signal, and no re-raise
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/gpu_pane/status.py:182
**Code:**
```python
    except Exception:
        pass
```
**Second path:** swallows the exception and continues with no substitute value, no signal, and no re-raise
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/gpu_pane/status.py:200
**Code:**
```python
        except Exception:
            pass
```
**Second path:** swallows the exception and continues with no substitute value, no signal, and no re-raise
**Names its path:** no
**Fails loudly outside the observed case:** no


### src/gpu_pane/status.py:94-102
**Code:**
```python
def _status_for_preset(name: str, state: dict | None) -> dict:
    if state is None:
        return {
            'name': name, 'kind': 'preset', 'running': False,
            'port': None, 'pid': None, 'rss_mb': None, 'healthy': False,
            'idle_seconds': None, 'idle_log_missing': False,
            'log_path': None, 'model_name': None,
        }
    return _status_for_state(state, kind='preset')
```
**Second path:** when no on-disk state file was found for a preset, returns a synthetic all-`None`/`False` status dict standing in for the real one
**Names its path:** no
**Fails loudly outside the observed case:** no

## src/panes/

### src/panes/log_janitor.py:162
**Code:**
```python
            except Exception:
                pass
```
**Second path:** swallows the exception and continues with no substitute value, no signal, and no re-raise
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/panes/log_janitor.py:166
**Code:**
```python
    except Exception:
        pass
```
**Second path:** swallows the exception and continues with no substitute value, no signal, and no re-raise
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/panes/token_pane.py:77
**Code:**
```python
            except Exception:
                log_pane_error('tokens')
                wait_for_input(INPUT_POLL_INTERVAL)
```
**Second path:** catches the exception and continues (side effect only in the handler body, e.g. logging a warning or appending an error record); no value is returned/assigned by the handler itself, and no re-raise
**Names its path:** yes
**Fails loudly outside the observed case:** no

### src/panes/warnings_pane.py:84
**Code:**
```python
            except Exception:
                log_pane_error('warnings')
                wait_for_input(INPUT_POLL_INTERVAL)
```
**Second path:** catches the exception and continues (side effect only in the handler body, e.g. logging a warning or appending an error record); no value is returned/assigned by the handler itself, and no re-raise
**Names its path:** yes
**Fails loudly outside the observed case:** no

### src/panes/warnings_pane.py:249
**Code:**
```python
                except json.JSONDecodeError:
                    continue
```
**Second path:** catches the exception and continues (side effect only in the handler body, e.g. logging a warning or appending an error record); no value is returned/assigned by the handler itself, and no re-raise
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/panes/warnings_pane.py:252
**Code:**
```python
    except OSError:
        log_pane_error('warnings')
        return records, last_pos
```
**Second path:** returns `records, last_pos`
**Names its path:** yes
**Fails loudly outside the observed case:** no


## src/workers/

### src/workers/worker_selection.py:24
**Code:**
```python
    except OSError:
        return None
```
**Second path:** returns `None`
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/workers/worker_tokens_pane.py:76
**Code:**
```python
            except Exception:
                log_pane_error('worker_tokens')
                wait_for_input(INPUT_POLL_INTERVAL)
```
**Second path:** catches the exception and continues (side effect only in the handler body, e.g. logging a warning or appending an error record); no value is returned/assigned by the handler itself, and no re-raise
**Names its path:** yes
**Fails loudly outside the observed case:** no

### src/workers/worker_tokens_pane.py:249
**Code:**
```python
    except OSError:
        return None
```
**Second path:** returns `None`
**Names its path:** no
**Fails loudly outside the observed case:** no


## src/dual_log_cli/

### src/dual_log_cli/discovery.py:28-41
**Code:**
```python
def resolve_dual_log_dir() -> Path:
    env_root = os.environ.get("MONITOR_CC_ROOT")
    if env_root:
        return Path(env_root) / "src" / "logs" / "dual_log"
    here = Path(__file__).resolve()
    repo_root = here.parents[2]
    direct = repo_root / "src" / "logs" / "dual_log"
    if direct.exists():
        return direct
    if len(here.parents) > 5:
        from_worktree = here.parents[5] / "src" / "logs" / "dual_log"
        if from_worktree.exists():
            return from_worktree
    return direct
```
**Second path:** four routes to the dual-log directory in priority order (env var, direct repo-relative path, worktree-relative path); if none of the `.exists()` checks succeed, returns the unvalidated `direct` path anyway
**Names its path:** no
**Fails loudly outside the observed case:** no
### src/dual_log_cli/__main__.py:114
**Code:**
```python
    except BrokenPipeError:
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        exit_code = 0
```
**Second path:** assigns `exit_code = 0`
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/dual_log_cli/commands.py:36
**Code:**
```python
    except ValueError:
        return False
```
**Second path:** returns `False`
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/dual_log_cli/commands.py:66
**Code:**
```python
    except (AmbiguousSessionError, UnknownSessionError) as exc:
        print(str(exc), file=sys.stderr)
        return None, 2
```
**Second path:** returns `None, 2`
**Names its path:** yes
**Fails loudly outside the observed case:** no

### src/dual_log_cli/commands.py:82
**Code:**
```python
    except BadClassifierError as exc:
        print(str(exc), file=sys.stderr)
        return 2
```
**Second path:** returns `2`
**Names its path:** yes
**Fails loudly outside the observed case:** no

### src/dual_log_cli/commands.py:92
**Code:**
```python
    for session in sessions:
        try:
            data = load_timeline(session)
        except Exception:
            skipped += 1
            continue
```
**Second path:** silently skips the current loop item and continues with the remaining ones
**Names its path:** yes
**Fails loudly outside the observed case:** no

### src/dual_log_cli/commands.py:121
**Code:**
```python
    for session in sessions:
        try:
            data = load_timeline(session)
        except Exception:
            skipped += 1
            continue
```
**Second path:** silently skips the current loop item and continues with the remaining ones
**Names its path:** yes
**Fails loudly outside the observed case:** no

### src/dual_log_cli/commands.py:161
**Code:**
```python
        except (UnknownRequestNumberError, AmbiguousRequestNumberError) as exc:
            print(str(exc), file=sys.stderr)
            return 2
```
**Second path:** returns `2`
**Names its path:** yes
**Fails loudly outside the observed case:** no

### src/dual_log_cli/commands.py:194
**Code:**
```python
    except BadClassifierError as exc:
        print(str(exc), file=sys.stderr)
        return 2
```
**Second path:** returns `2`
**Names its path:** yes
**Fails loudly outside the observed case:** no

### src/dual_log_cli/project_map.py:30
**Code:**
```python
    except Exception:
        return ""
```
**Second path:** returns `""`
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/dual_log_cli/project_map.py:39
**Code:**
```python
    except Exception:
        return dirs
```
**Second path:** returns `dirs`
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/dual_log_cli/project_map.py:41
**Code:**
```python
    for entry in entries:
        if not entry.is_dir():
            continue
        try:
            transcripts = sorted(
                (p for p in entry.iterdir() if p.suffix == ".jsonl"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
        except Exception:
```
**Second path:** silently skips the current loop item and continues with the remaining ones
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/dual_log_cli/reader.py:22
**Code:**
```python
    except ValueError:
        return None
```
**Second path:** returns `None`
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/dual_log_cli/reader.py:69
**Code:**
```python
        for offset, length in iter_line_offsets_reverse(original_path):
            model = sniff_model(fh, offset)
            if model and infer_family(model) == "haiku":
                skipped += 1
                continue
            fh.seek(offset)
            raw = fh.read(length)
            try:
                entry = json.loads(raw)
            except json.JSONDecodeError:
```
**Second path:** silently skips the current loop item and continues with the remaining ones
**Names its path:** yes
**Fails loudly outside the observed case:** no

### src/dual_log_cli/reader.py:91
**Code:**
```python
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue
```
**Second path:** silently skips the current loop item and continues with the remaining ones
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/dual_log_cli/usage.py:49
**Code:**
```python
    for directory in directories:
        try:
            entries = sorted(directory.iterdir())
        except Exception:
            continue
```
**Second path:** silently skips the current loop item and continues with the remaining ones
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/dual_log_cli/usage.py:54
**Code:**
```python
        for path in entries:
            if path.suffix != ".jsonl":
                continue
            if since_epoch is not None:
                try:
                    if path.stat().st_mtime < since_epoch:
                        continue
                except OSError:
                    continue
```
**Second path:** silently skips the current loop item and continues with the remaining ones
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/dual_log_cli/usage.py:64
**Code:**
```python
    for path in candidates:
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
```
**Second path:** silently skips the current loop item and continues with the remaining ones
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/dual_log_cli/usage.py:78
**Code:**
```python
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
```
**Second path:** silently skips the current loop item and continues with the remaining ones
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/dual_log_cli/usage.py:97
**Code:**
```python
    except Exception:
        return {}
```
**Second path:** returns `{}`
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/dual_log_cli/usage.py:110
**Code:**
```python
    except Exception:
        return None, {}
```
**Second path:** returns `None, {}`
**Names its path:** no
**Fails loudly outside the observed case:** no


## src/proxy_display/

### src/proxy_display/parser.py:15-17
**Code:**
```python
    root = os.environ.get("MONITOR_CC_ROOT", "")
    if not root:
        root = str(Path(__file__).parent.parent.parent)
```
**Second path:** if `MONITOR_CC_ROOT` is unset or empty, substitutes a path computed from `__file__` (in `find_worker_proxy_log`)
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/proxy_display/parser.py:31-33
**Code:**
```python
    root = os.environ.get("MONITOR_CC_ROOT", "")
    if not root:
        root = str(Path(__file__).parent.parent.parent)
```
**Second path:** same env-var-or-computed-path choice as above (in `get_proxy_session_start_ts`)
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/proxy_display/parser.py:36-42
**Code:**
```python
    if marker_file.exists():
        try:
            mtime = marker_file.stat().st_mtime
        except OSError:
            mtime = None
        if mtime is not None:
            return mtime
    return time.time()
```
**Second path:** if the marker file is missing, unreadable, or its `stat()` fails, `get_proxy_session_start_ts` returns the current wall-clock time instead of the session's real start time
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/proxy_display/parser.py:48-50
**Code:**
```python
    root = os.environ.get("MONITOR_CC_ROOT", "")
    if not root:
        root = str(Path(__file__).parent.parent.parent)
```
**Second path:** same env-var-or-computed-path choice as above (in `find_proxy_log_path`)
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/proxy_display/parser.py:75
**Code:**
```python
    root = os.environ.get('MONITOR_CC_ROOT', '') or str(Path(__file__).parent.parent.parent)
```
**Second path:** same env-var-or-computed-path choice, one-line `or` form (in `find_errors_log_path`)
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/proxy_display/parser.py:83
**Code:**
```python
    root = os.environ.get('MONITOR_CC_ROOT', '') or str(Path(__file__).parent.parent.parent)
```
**Second path:** same env-var-or-computed-path choice, one-line `or` form (in `find_response_log_path`)
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/proxy_display/forwarded_parser.py:265
**Code:**
```python
    root = os.environ.get('MONITOR_CC_ROOT', '') or str(Path(__file__).parent.parent.parent)
```
**Second path:** same env-var-or-computed-path choice, one-line `or` form (in `parse_proxy_log_forwarded`)
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/proxy_display/side_logs.py:39
**Code:**
```python
    root = os.environ.get('MONITOR_CC_ROOT', '') or str(Path(__file__).parent.parent.parent)
```
**Second path:** same env-var-or-computed-path choice, one-line `or` form (in `scan_worker_errors_logs`)
**Names its path:** no
**Fails loudly outside the observed case:** no
### src/proxy_display/dual_log_accumulator.py:27
**Code:**
```python
                except json.JSONDecodeError:
                    continue
```
**Second path:** catches the exception and continues (side effect only in the handler body, e.g. logging a warning or appending an error record); no value is returned/assigned by the handler itself, and no re-raise
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/proxy_display/dual_log_accumulator.py:39
**Code:**
```python
    except OSError:
        log_pane_error('dual_log_accumulator')
        return last_pos
```
**Second path:** returns `last_pos`
**Names its path:** yes
**Fails loudly outside the observed case:** no

### src/proxy_display/dual_log_accumulator.py:106
**Code:**
```python
                except json.JSONDecodeError:
                    continue
```
**Second path:** catches the exception and continues (side effect only in the handler body, e.g. logging a warning or appending an error record); no value is returned/assigned by the handler itself, and no re-raise
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/proxy_display/dual_log_accumulator.py:121
**Code:**
```python
    except OSError:
        log_pane_error('dual_log_accumulator')
        return last_pos
```
**Second path:** returns `last_pos`
**Names its path:** yes
**Fails loudly outside the observed case:** no

### src/proxy_display/forwarded_parser.py:200
**Code:**
```python
                except json.JSONDecodeError:
                    continue
```
**Second path:** catches the exception and continues (side effect only in the handler body, e.g. logging a warning or appending an error record); no value is returned/assigned by the handler itself, and no re-raise
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/proxy_display/forwarded_parser.py:211
**Code:**
```python
    except OSError:
        log_pane_error('forwarded_parser')
        return [], last_pos
```
**Second path:** returns `[], last_pos`
**Names its path:** yes
**Fails loudly outside the observed case:** no

### src/proxy_display/forwarded_parser.py:236
**Code:**
```python
                except json.JSONDecodeError:
                    continue
```
**Second path:** catches the exception and continues (side effect only in the handler body, e.g. logging a warning or appending an error record); no value is returned/assigned by the handler itself, and no re-raise
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/proxy_display/forwarded_parser.py:255
**Code:**
```python
    except OSError:
        log_pane_error('forwarded_parser')
        return False
```
**Second path:** returns `False`
**Names its path:** yes
**Fails loudly outside the observed case:** no

### src/proxy_display/pane.py:101
**Code:**
```python
            except Exception:
                log_pane_error('proxy')
                wait_for_input(INPUT_POLL_INTERVAL)
```
**Second path:** catches the exception and continues (side effect only in the handler body, e.g. logging a warning or appending an error record); no value is returned/assigned by the handler itself, and no re-raise
**Names its path:** yes
**Fails loudly outside the observed case:** no

### src/proxy_display/parser.py:39
**Code:**
```python
        except OSError:
            mtime = None
```
**Second path:** assigns `mtime = None`
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/proxy_display/side_logs.py:27
**Code:**
```python
                except json.JSONDecodeError:
                    continue
```
**Second path:** catches the exception and continues (side effect only in the handler body, e.g. logging a warning or appending an error record); no value is returned/assigned by the handler itself, and no re-raise
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/proxy_display/side_logs.py:33
**Code:**
```python
    except OSError:
        log_pane_error('side_logs')
        return {}, last_pos
```
**Second path:** returns `{}, last_pos`
**Names its path:** yes
**Fails loudly outside the observed case:** no

### src/proxy_display/side_logs.py:50
**Code:**
```python
    for fpath in sorted(dual_dir.glob(pattern)):
        try:
            if min_mtime and fpath.stat().st_mtime < min_mtime:
                continue
        except OSError:
            continue
```
**Second path:** silently skips the current loop item and continues with the remaining ones
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/proxy_display/side_logs.py:69
**Code:**
```python
                    except json.JSONDecodeError:
                        continue
```
**Second path:** catches the exception and continues (side effect only in the handler body, e.g. logging a warning or appending an error record); no value is returned/assigned by the handler itself, and no re-raise
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/proxy_display/side_logs.py:80
**Code:**
```python
        except OSError:
            continue
```
**Second path:** catches the exception and continues (side effect only in the handler body, e.g. logging a warning or appending an error record); no value is returned/assigned by the handler itself, and no re-raise
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/proxy_display/worker_proxy_pane.py:88
**Code:**
```python
            except Exception:
                log_pane_error('worker_proxy')
                wait_for_input(INPUT_POLL_INTERVAL)
```
**Second path:** catches the exception and continues (side effect only in the handler body, e.g. logging a warning or appending an error record); no value is returned/assigned by the handler itself, and no re-raise
**Names its path:** yes
**Fails loudly outside the observed case:** no

### src/proxy_display/worker_proxy_pane.py:226
**Code:**
```python
    except OSError:
        return None
```
**Second path:** returns `None`
**Names its path:** no
**Fails loudly outside the observed case:** no


## src/menubar/

### src/menubar/setup_menubar.py:9-10
**Code:**
```python
_PROJECT_ROOT    = Path(os.environ['PROJECT_ROOT']) if os.environ.get('PROJECT_ROOT') \
                   else Path(__file__).resolve().parent.parent.parent
```
**Second path:** if `PROJECT_ROOT` is unset, substitutes a path computed from `__file__` instead
**Names its path:** no
**Fails loudly outside the observed case:** no
### src/menubar/app.py:218
**Code:**
```python
            except Exception:
                pass
```
**Second path:** swallows the exception and continues with no substitute value, no signal, and no re-raise
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/menubar/app.py:256
**Code:**
```python
        except AttributeError:
            return False
```
**Second path:** returns `False`
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/menubar/app.py:300
**Code:**
```python
        except Exception:
            sessions = []
            bg_by_project = {}
```
**Second path:** assigns `sessions = []`; `bg_by_project = {}`
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/menubar/app_settings.py:19
**Code:**
```python
    except Exception:
        return False, PANEL_WIDTH, PANEL_HEIGHT
```
**Second path:** returns `False, PANEL_WIDTH, PANEL_HEIGHT`
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/menubar/app_settings.py:32
**Code:**
```python
    except Exception:
        pass
```
**Second path:** swallows the exception and continues with no substitute value, no signal, and no re-raise
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/menubar/bg_timer.py:32
**Code:**
```python
    except (ValueError, IndexError):
        pass
```
**Second path:** swallows the exception and continues with no substitute value, no signal, and no re-raise
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/menubar/bg_timer.py:71
**Code:**
```python
    except Exception:
        return {}
```
**Second path:** returns `{}`
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/menubar/bg_timer.py:123
**Code:**
```python
    except Exception:
        return None
```
**Second path:** returns `None`
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/menubar/bg_timer.py:135
**Code:**
```python
    for pid in sleep_pids:
        output_file = _resolve_pid_output_file(pid)
        try:
            os.kill(pid, signal.SIGTERM)
            killed += 1
        except (ProcessLookupError, OSError) as e:
            errors += 1
            last_err = e
            continue
```
**Second path:** silently skips the current loop item and continues with the remaining ones
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/menubar/bg_timer.py:151
**Code:**
```python
        except OSError as e:
            print(f'[abort-stamp] write error for {output_file}: {e}', file=sys.stderr)
```
**Second path:** catches the exception and continues (side effect only in the handler body, e.g. logging a warning or appending an error record); no value is returned/assigned by the handler itself, and no re-raise
**Names its path:** yes
**Fails loudly outside the observed case:** no

### src/menubar/bg_timer.py:161
**Code:**
```python
    except Exception as e:
        print(f'[abort-log] abort_action write error: {e}', file=sys.stderr)
```
**Second path:** catches the exception and continues (side effect only in the handler body, e.g. logging a warning or appending an error record); no value is returned/assigned by the handler itself, and no re-raise
**Names its path:** yes
**Fails loudly outside the observed case:** no

### src/menubar/desktop_detection.py:114
**Code:**
```python
    except Exception as exc:
        reason = repr(exc)[:80].replace('\n', ' ')
        log_menubar('detection', f'all_failed n_mains={len(cwds)} reason=error:{reason}')
```
**Second path:** assigns `reason = repr(exc)[:80].replace('\n', ' ')`
**Names its path:** yes
**Fails loudly outside the observed case:** no

### src/menubar/desktop_detection.py:290
**Code:**
```python
    except OSError as e:
        log_menubar('detection', f'osc2_write_failed tty={tty} err={repr(e)[:80]}')
        return None
```
**Second path:** returns `None`
**Names its path:** yes
**Fails loudly outside the observed case:** no

### src/menubar/desktop_detection.py:299
**Code:**
```python
    except OSError as e:
        log_menubar('detection', f'osc2_restore_failed tty={tty} err={repr(e)[:80]}')
```
**Second path:** catches the exception and continues (side effect only in the handler body, e.g. logging a warning or appending an error record); no value is returned/assigned by the handler itself, and no re-raise
**Names its path:** yes
**Fails loudly outside the observed case:** no

### src/menubar/discover.py:56
**Code:**
```python
    for project_dir in get_project_directories():
        try:
            info = _process_project_dir(project_dir, now)
            if info is not None:
                results.append(info)
        except Exception:
            continue
```
**Second path:** silently skips the current loop item and continues with the remaining ones
**Names its path:** yes
**Fails loudly outside the observed case:** no

### src/menubar/discover.py:99
**Code:**
```python
        for line in reversed(chunk.split('\n')):
            line = line.strip()
            if not line:
                continue
            count += 1
            if count > 10:
                break
            try:
                cwd = json.loads(line).get('cwd', '')
                if cwd:
```
**Second path:** silently skips the current loop item and continues with the remaining ones
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/menubar/discover.py:112
**Code:**
```python
    except Exception:
        pass
```
**Second path:** swallows the exception and continues with no substitute value, no signal, and no re-raise
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/menubar/discovery_worker.py:51
**Code:**
```python
        except Exception as e:
            print(f'[menubar] discovery-worker cycle error: {e}', file=sys.stderr)
```
**Second path:** catches the exception and continues (side effect only in the handler body, e.g. logging a warning or appending an error record); no value is returned/assigned by the handler itself, and no re-raise
**Names its path:** yes
**Fails loudly outside the observed case:** no

### src/menubar/ghostty.py:61
**Code:**
```python
        except OSError: pass
```
**Second path:** swallows the exception and continues with no substitute value, no signal, and no re-raise
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/menubar/ghostty.py:79
**Code:**
```python
    except Exception:
        return None
```
**Second path:** returns `None`
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/menubar/ghostty.py:87
**Code:**
```python
        except OSError: pass
```
**Second path:** swallows the exception and continues with no substitute value, no signal, and no re-raise
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/menubar/ghostty.py:100
**Code:**
```python
    except Exception:
        return None
```
**Second path:** returns `None`
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/menubar/ghostty.py:114
**Code:**
```python
    except Exception:
        return []
```
**Second path:** returns `[]`
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/menubar/ghostty.py:147
**Code:**
```python
    except Exception:
        return
```
**Second path:** catches the exception and continues (side effect only in the handler body, e.g. logging a warning or appending an error record); no value is returned/assigned by the handler itself, and no re-raise
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/menubar/hook_setup.py:94
**Code:**
```python
    except FileNotFoundError:
        return {}
```
**Second path:** returns `{}`
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/menubar/hook_setup.py:96
**Code:**
```python
    except json.JSONDecodeError as e:
        print(f"ERROR: cannot parse {_SETTINGS_FILE}: {e}", file=sys.stderr)
        sys.exit(1)
```
**Second path:** catches the exception and continues (side effect only in the handler body, e.g. logging a warning or appending an error record); no value is returned/assigned by the handler itself, and no re-raise
**Names its path:** yes
**Fails loudly outside the observed case:** no

### src/menubar/hook_writer.py:23
**Code:**
```python
    except Exception:
        return
```
**Second path:** catches the exception and continues (side effect only in the handler body, e.g. logging a warning or appending an error record); no value is returned/assigned by the handler itself, and no re-raise
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/menubar/hook_writer.py:55
**Code:**
```python
    except Exception:
        pass
```
**Second path:** swallows the exception and continues with no substitute value, no signal, and no re-raise
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/menubar/hook_writer.py:61
**Code:**
```python
    except Exception:
        return {}
```
**Second path:** returns `{}`
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/menubar/hotkey_arrows.py:37
**Code:**
```python
        except Exception:
            pass
```
**Second path:** swallows the exception and continues with no substitute value, no signal, and no re-raise
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/menubar/hotkey_controller.py:34
**Code:**
```python
        except Exception:
            pass
```
**Second path:** swallows the exception and continues with no substitute value, no signal, and no re-raise
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/menubar/hotkey_controller.py:62
**Code:**
```python
        except Exception:
            pass
```
**Second path:** swallows the exception and continues with no substitute value, no signal, and no re-raise
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/menubar/hotkey_digits.py:36
**Code:**
```python
        except Exception:
            pass
```
**Second path:** swallows the exception and continues with no substitute value, no signal, and no re-raise
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/menubar/menubar_log.py:16
**Code:**
```python
    except Exception:
        pass
```
**Second path:** swallows the exception and continues with no substitute value, no signal, and no re-raise
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/menubar/menubar_log.py:30
**Code:**
```python
            except Exception:
                pass
```
**Second path:** swallows the exception and continues with no substitute value, no signal, and no re-raise
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/menubar/menubar_log.py:34
**Code:**
```python
    except Exception:
        pass
```
**Second path:** swallows the exception and continues with no substitute value, no signal, and no re-raise
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/menubar/model_controller.py:127
**Code:**
```python
        except Exception as exc:
            print(f'[menubar] model cycle (main) failed: {exc}', file=sys.stderr)
```
**Second path:** catches the exception and continues (side effect only in the handler body, e.g. logging a warning or appending an error record); no value is returned/assigned by the handler itself, and no re-raise
**Names its path:** yes
**Fails loudly outside the observed case:** no

### src/menubar/model_controller.py:134
**Code:**
```python
        except Exception as exc:
            print(f'[menubar] model cycle (worker) failed: {exc}', file=sys.stderr)
```
**Second path:** catches the exception and continues (side effect only in the handler body, e.g. logging a warning or appending an error record); no value is returned/assigned by the handler itself, and no re-raise
**Names its path:** yes
**Fails loudly outside the observed case:** no

### src/menubar/model_controller.py:141
**Code:**
```python
        except Exception as exc:
            print(f'[menubar] model effort cycle (main) failed: {exc}', file=sys.stderr)
```
**Second path:** catches the exception and continues (side effect only in the handler body, e.g. logging a warning or appending an error record); no value is returned/assigned by the handler itself, and no re-raise
**Names its path:** yes
**Fails loudly outside the observed case:** no

### src/menubar/model_controller.py:148
**Code:**
```python
        except Exception as exc:
            print(f'[menubar] model max_tokens cycle (main) failed: {exc}', file=sys.stderr)
```
**Second path:** catches the exception and continues (side effect only in the handler body, e.g. logging a warning or appending an error record); no value is returned/assigned by the handler itself, and no re-raise
**Names its path:** yes
**Fails loudly outside the observed case:** no

### src/menubar/model_controller.py:155
**Code:**
```python
        except Exception as exc:
            print(f'[menubar] model effort cycle (worker) failed: {exc}', file=sys.stderr)
```
**Second path:** catches the exception and continues (side effect only in the handler body, e.g. logging a warning or appending an error record); no value is returned/assigned by the handler itself, and no re-raise
**Names its path:** yes
**Fails loudly outside the observed case:** no

### src/menubar/model_controller.py:162
**Code:**
```python
        except Exception as exc:
            print(f'[menubar] model max_tokens cycle (worker) failed: {exc}', file=sys.stderr)
```
**Second path:** catches the exception and continues (side effect only in the handler body, e.g. logging a warning or appending an error record); no value is returned/assigned by the handler itself, and no re-raise
**Names its path:** yes
**Fails loudly outside the observed case:** no

### src/menubar/model_controller.py:169
**Code:**
```python
        except Exception as exc:
            print(f'[menubar] model thinking cycle (main) failed: {exc}', file=sys.stderr)
```
**Second path:** catches the exception and continues (side effect only in the handler body, e.g. logging a warning or appending an error record); no value is returned/assigned by the handler itself, and no re-raise
**Names its path:** yes
**Fails loudly outside the observed case:** no

### src/menubar/model_controller.py:176
**Code:**
```python
        except Exception as exc:
            print(f'[menubar] model thinking cycle (worker) failed: {exc}', file=sys.stderr)
```
**Second path:** catches the exception and continues (side effect only in the handler body, e.g. logging a warning or appending an error record); no value is returned/assigned by the handler itself, and no re-raise
**Names its path:** yes
**Fails loudly outside the observed case:** no

### src/menubar/model_controller.py:183
**Code:**
```python
        except Exception as exc:
            print(f'[menubar] model selection apply failed: {exc}', file=sys.stderr)
```
**Second path:** catches the exception and continues (side effect only in the handler body, e.g. logging a warning or appending an error record); no value is returned/assigned by the handler itself, and no re-raise
**Names its path:** yes
**Fails loudly outside the observed case:** no

### src/menubar/model_controller.py:196
**Code:**
```python
        except Exception as exc:
            print(f'[menubar] apply success flash failed: {exc}', file=sys.stderr)
```
**Second path:** catches the exception and continues (side effect only in the handler body, e.g. logging a warning or appending an error record); no value is returned/assigned by the handler itself, and no re-raise
**Names its path:** yes
**Fails loudly outside the observed case:** no

### src/menubar/model_controller.py:211
**Code:**
```python
        except Exception as exc:
            print(f'[menubar] apply success revert failed: {exc}', file=sys.stderr)
```
**Second path:** catches the exception and continues (side effect only in the handler body, e.g. logging a warning or appending an error record); no value is returned/assigned by the handler itself, and no re-raise
**Names its path:** yes
**Fails loudly outside the observed case:** no

### src/menubar/model_selection.py:24
**Code:**
```python
    except ValueError:
        idx = -1
```
**Second path:** assigns `idx = -1`
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/menubar/model_selection.py:47
**Code:**
```python
    except Exception:
        return _DEFAULT_MAIN, _DEFAULT_WORKER
```
**Second path:** returns `_DEFAULT_MAIN, _DEFAULT_WORKER`
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/menubar/model_selection.py:59
**Code:**
```python
    except Exception:
        return {}
```
**Second path:** returns `{}`
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/menubar/monitor_sweep_scheduler.py:37
**Code:**
```python
    except Exception:
        return 0.0
```
**Second path:** returns `0.0`
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/menubar/monitor_sweep_scheduler.py:45
**Code:**
```python
    except Exception as e:
        log_menubar('monitor_sweep', f'state-write FAILED {e}')
```
**Second path:** catches the exception and continues (side effect only in the handler body, e.g. logging a warning or appending an error record); no value is returned/assigned by the handler itself, and no re-raise
**Names its path:** yes
**Fails loudly outside the observed case:** no

### src/menubar/monitor_sweep_scheduler.py:57
**Code:**
```python
    except Exception as e:
        log_menubar('monitor_sweep', f'FAILED {e}')
```
**Second path:** catches the exception and continues (side effect only in the handler body, e.g. logging a warning or appending an error record); no value is returned/assigned by the handler itself, and no re-raise
**Names its path:** yes
**Fails loudly outside the observed case:** no

### src/menubar/panel_lifecycle.py:28
**Code:**
```python
    except Exception as e:
        print(f'[menubar] cycling {from_panel}→{to_panel} error: {e}', file=sys.stderr)
```
**Second path:** catches the exception and continues (side effect only in the handler body, e.g. logging a warning or appending an error record); no value is returned/assigned by the handler itself, and no re-raise
**Names its path:** yes
**Fails loudly outside the observed case:** no

### src/menubar/panel_lifecycle.py:56
**Code:**
```python
    except Exception as e:
        print(f'[menubar] Cmd+K deferred-block error: {e}', file=sys.stderr)
```
**Second path:** catches the exception and continues (side effect only in the handler body, e.g. logging a warning or appending an error record); no value is returned/assigned by the handler itself, and no re-raise
**Names its path:** yes
**Fails loudly outside the observed case:** no

### src/menubar/paths.py:33
**Code:**
```python
            if new.exists():
                old.unlink()
            else:
                old.rename(new)
```
**Second path:** branches on `new.exists()` to choose between two paths
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/menubar/proc_cache.py:41
**Code:**
```python
    except OSError:
        return False
```
**Second path:** returns `False`
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/menubar/proc_cache.py:56
**Code:**
```python
    except Exception:
        return
```
**Second path:** catches the exception and continues (side effect only in the handler body, e.g. logging a warning or appending an error record); no value is returned/assigned by the handler itself, and no re-raise
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/menubar/proc_cache.py:70
**Code:**
```python
    except Exception:
        return
```
**Second path:** catches the exception and continues (side effect only in the handler body, e.g. logging a warning or appending an error record); no value is returned/assigned by the handler itself, and no re-raise
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/menubar/proc_cache.py:80
**Code:**
```python
    for pid, tty in active.items():
        if pid in known_pids:
            continue
        try:
            r2 = subprocess.run(['lsof', '-a', '-d', 'cwd', '-p', pid],
                                 capture_output=True, text=True,
                                 encoding='utf-8', errors='replace', timeout=2)
            for line in r2.stdout.strip().split('\n'):
                if line.startswith('COMMAND') or not line:
                    continue
```
**Second path:** silently skips the current loop item and continues with the remaining ones
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/menubar/proc_cache.py:119
**Code:**
```python
    except Exception:
        return
```
**Second path:** catches the exception and continues (side effect only in the handler body, e.g. logging a warning or appending an error record); no value is returned/assigned by the handler itself, and no re-raise
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/menubar/proc_cache.py:135
**Code:**
```python
    except Exception:
        return 0
```
**Second path:** returns `0`
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/menubar/proc_cache.py:151
**Code:**
```python
                except OSError:
                    pass
```
**Second path:** swallows the exception and continues with no substitute value, no signal, and no re-raise
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/menubar/proc_cache.py:163
**Code:**
```python
    except Exception:
        _hook_state_cache = {}
```
**Second path:** assigns `_hook_state_cache = {}`
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/menubar/rag_controller.py:76
**Code:**
```python
    except OSError as e:
        return e.errno != errno.ESRCH
```
**Second path:** returns `e.errno != errno.ESRCH`
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/menubar/rag_controller.py:112
**Code:**
```python
    except Exception:
        return _NO_INDEXING
```
**Second path:** returns `_NO_INDEXING`
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/menubar/rag_controller.py:124
**Code:**
```python
    except Exception:
        return '?'
```
**Second path:** returns `'?'`
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/menubar/system.py:37
**Code:**
```python
    except OSError:
        fh.close()
        return None
```
**Second path:** returns `None`
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/menubar/system.py:85
**Code:**
```python
    except subprocess.TimeoutExpired:
        osascript_ms = (time.monotonic() - _t1) * 1000
        msg = f'{ts} TIMEOUT {label} lookup_ms={lookup_ms:.1f} osascript_ms={osascript_ms:.1f}\n'
```
**Second path:** assigns `osascript_ms = (time.monotonic() - _t1) * 1000`; `msg = f'{ts} TIMEOUT {label} lookup_ms={lookup_ms:.1f} osascript_ms={osascript_ms:.1f}\n'`
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/menubar/system.py:97
**Code:**
```python
    except Exception:
        return None
```
**Second path:** returns `None`
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/menubar/system.py:141
**Code:**
```python
    except subprocess.TimeoutExpired:
        pass
```
**Second path:** swallows the exception and continues with no substitute value, no signal, and no re-raise
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/menubar/system.py:155
**Code:**
```python
    except Exception:
        path_value = None
```
**Second path:** assigns `path_value = None`
**Names its path:** no
**Fails loudly outside the observed case:** no


## src/proxy/

### src/proxy/payload_helpers.py:7
**Code:**
```python
_src_dir = os.path.join(os.environ.get("MONITOR_CC_ROOT", str(Path(__file__).parent.parent.parent)), "src")
```
**Second path:** if `MONITOR_CC_ROOT` is unset, substitutes a path computed from `__file__` instead
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/proxy/rules.py:7
**Code:**
```python
_src_dir = os.path.join(os.environ.get("MONITOR_CC_ROOT", str(Path(__file__).parent.parent.parent)), "src")
```
**Second path:** same env-var-or-computed-path choice as `payload_helpers.py`
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/proxy/tools.py:7
**Code:**
```python
_src_dir = os.path.join(os.environ.get("MONITOR_CC_ROOT", str(Path(__file__).parent.parent.parent)), "src")
```
**Second path:** same env-var-or-computed-path choice as `payload_helpers.py`
**Names its path:** no
**Fails loudly outside the observed case:** no
### src/proxy/addon.py:95
**Code:**
```python
            except Exception as e:
                print(f"[proxy_addon] bg_escape trigger failed: {e}", file=sys.stderr)
```
**Second path:** catches the exception and continues (side effect only in the handler body, e.g. logging a warning or appending an error record); no value is returned/assigned by the handler itself, and no re-raise
**Names its path:** yes
**Fails loudly outside the observed case:** no

### src/proxy/addon.py:106
**Code:**
```python
        except Exception as e:
            print(f"[proxy_addon] Error: {e}", file=sys.stderr)
```
**Second path:** catches the exception and continues (side effect only in the handler body, e.g. logging a warning or appending an error record); no value is returned/assigned by the handler itself, and no re-raise
**Names its path:** yes
**Fails loudly outside the observed case:** no

### src/proxy/addon.py:117
**Code:**
```python
        except Exception as e:
            print(f"[proxy_addon] Error in responseheaders hook: {e}", file=sys.stderr)
```
**Second path:** catches the exception and continues (side effect only in the handler body, e.g. logging a warning or appending an error record); no value is returned/assigned by the handler itself, and no re-raise
**Names its path:** yes
**Fails loudly outside the observed case:** no

### src/proxy/addon.py:132
**Code:**
```python
                except Exception as e:
                    print(f"[dual_log] stripped/injected write failed: {e}", file=sys.stderr)
```
**Second path:** catches the exception and continues (side effect only in the handler body, e.g. logging a warning or appending an error record); no value is returned/assigned by the handler itself, and no re-raise
**Names its path:** yes
**Fails loudly outside the observed case:** no

### src/proxy/addon.py:134
**Code:**
```python
        except Exception as e:
            print(f"[proxy_addon] Error in response hook: {e}", file=sys.stderr)
```
**Second path:** catches the exception and continues (side effect only in the handler body, e.g. logging a warning or appending an error record); no value is returned/assigned by the handler itself, and no re-raise
**Names its path:** yes
**Fails loudly outside the observed case:** no

### src/proxy/addon.py:143
**Code:**
```python
        except Exception as e:
            print(f"[proxy_addon] Error in error hook: {e}", file=sys.stderr)
```
**Second path:** catches the exception and continues (side effect only in the handler body, e.g. logging a warning or appending an error record); no value is returned/assigned by the handler itself, and no re-raise
**Names its path:** yes
**Fails loudly outside the observed case:** no

### src/proxy/addon.py:247
**Code:**
```python
    except Exception as e:
        print(f"[dual_log] response write failed: {e}", file=sys.stderr)
```
**Second path:** catches the exception and continues (side effect only in the handler body, e.g. logging a warning or appending an error record); no value is returned/assigned by the handler itself, and no re-raise
**Names its path:** yes
**Fails loudly outside the observed case:** no

### src/proxy/addon.py:252
**Code:**
```python
        except Exception as e:
            print(f"[dual_log] model mismatch write failed: {e}", file=sys.stderr)
```
**Second path:** catches the exception and continues (side effect only in the handler body, e.g. logging a warning or appending an error record); no value is returned/assigned by the handler itself, and no re-raise
**Names its path:** yes
**Fails loudly outside the observed case:** no

### src/proxy/addon.py:298
**Code:**
```python
        except OSError:
            return None
```
**Second path:** returns `None`
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/proxy/addon.py:306
**Code:**
```python
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
```
**Second path:** returns `None`
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/proxy/addon_dual_log.py:39
**Code:**
```python
    except Exception as e:
        print(f"[dual_log] original write failed: {e}", file=sys.stderr)
```
**Second path:** catches the exception and continues (side effect only in the handler body, e.g. logging a warning or appending an error record); no value is returned/assigned by the handler itself, and no re-raise
**Names its path:** yes
**Fails loudly outside the observed case:** no

### src/proxy/addon_dual_log.py:55
**Code:**
```python
    except Exception as e:
        print(f"[dual_log] forwarded write failed: {e}", file=sys.stderr)
        return None
```
**Second path:** returns `None`
**Names its path:** yes
**Fails loudly outside the observed case:** no

### src/proxy/addon_dual_log.py:74
**Code:**
```python
    except Exception as e:
        print(f"[dual_log] errors write failed: {e}", file=sys.stderr)
        return None
```
**Second path:** returns `None`
**Names its path:** yes
**Fails loudly outside the observed case:** no

### src/proxy/addon_dual_log.py:105
**Code:**
```python
    except Exception:
        resp_body = ""
```
**Second path:** assigns `resp_body = ""`
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/proxy/addon_dual_log.py:110
**Code:**
```python
    except Exception:
        req_payload = None
```
**Second path:** assigns `req_payload = None`
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/proxy/bg_escape.py:76
**Code:**
```python
    except Exception:
        return False
```
**Second path:** returns `False`
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/proxy/bg_escape.py:97
**Code:**
```python
    except Exception as e:
        print(f"[bg_escape] event log write failed: {e}", file=sys.stderr)
```
**Second path:** catches the exception and continues (side effect only in the handler body, e.g. logging a warning or appending an error record); no value is returned/assigned by the handler itself, and no re-raise
**Names its path:** yes
**Fails loudly outside the observed case:** no

### src/proxy/inject_helpers.py:35
**Code:**
```python
    except Exception:
        return payload, False
```
**Second path:** returns `payload, False`
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/proxy/inject_helpers.py:122
**Code:**
```python
    except Exception:
        return payload, False
```
**Second path:** returns `payload, False`
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/proxy/inject_poread.py:52
**Code:**
```python
    except OSError:
        return None
```
**Second path:** returns `None`
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/proxy/rules_config.py:32
**Code:**
```python
    except Exception:
        return {}
```
**Second path:** returns `{}`
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/proxy/rules_config.py:46
**Code:**
```python
    except Exception:
        return ""
```
**Second path:** returns `""`
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/proxy/tool_injection.py:70
**Code:**
```python
    for plugin_dir in sorted(store_base.iterdir()):
        if not plugin_dir.is_dir():
            continue
        schemas = []
        for json_file in sorted(plugin_dir.glob("*.json")):
            try:
                schema = json.loads(json_file.read_text(encoding="utf-8"))
                schemas.append(schema)
            except (json.JSONDecodeError, OSError):
                continue
```
**Second path:** silently skips the current loop item and continues with the remaining ones
**Names its path:** yes
**Fails loudly outside the observed case:** no

### src/proxy/tool_injection.py:74
**Code:**
```python
        for json_file in sorted(plugin_dir.glob("*.json")):
            try:
                schema = json.loads(json_file.read_text(encoding="utf-8"))
                schemas.append(schema)
            except (json.JSONDecodeError, OSError):
                continue
```
**Second path:** silently skips the current loop item and continues with the remaining ones
**Names its path:** yes
**Fails loudly outside the observed case:** no

### src/proxy/tool_injection.py:110
**Code:**
```python
    except OSError:
        return _ACTIVE_PLUGINS_CACHE if _ACTIVE_PLUGINS_CACHE is not None else [_ALWAYS_INJECTED_PLUGIN]
```
**Second path:** returns `_ACTIVE_PLUGINS_CACHE if _ACTIVE_PLUGINS_CACHE is not None else [_ALWAYS_INJECTED_PLUGIN]`
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/proxy/tool_injection.py:126
**Code:**
```python
    except (json.JSONDecodeError, OSError):
        plugins = [_ALWAYS_INJECTED_PLUGIN]
```
**Second path:** assigns `plugins = [_ALWAYS_INJECTED_PLUGIN]`
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/proxy/tool_injection.py:152
**Code:**
```python
    except (json.JSONDecodeError, OSError):
        return False
```
**Second path:** returns `False`
**Names its path:** no
**Fails loudly outside the observed case:** no


## src/hooks/

### src/hooks/_fire_log.py:33
**Code:**
```python
    except Exception:
        return
```
**Second path:** catches the exception and continues (side effect only in the handler body, e.g. logging a warning or appending an error record); no value is returned/assigned by the handler itself, and no re-raise
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/hooks/_shell_strip.py:16
**Code:**
```python
    except Exception:
        return command
```
**Second path:** returns `command`
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/hooks/block_broad_find.py:52
**Code:**
```python
    except Exception:
        return None, None
```
**Second path:** returns `None, None`
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/hooks/block_broad_find.py:94
**Code:**
```python
    except Exception:
        return token
```
**Second path:** returns `token`
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/hooks/block_broad_grep.py:52
**Code:**
```python
    except Exception:
        return None, None
```
**Second path:** returns `None, None`
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/hooks/block_busywait_loop.py:45
**Code:**
```python
    except Exception:
        return None, None
```
**Second path:** returns `None, None`
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/hooks/block_cd_drift.py:44
**Code:**
```python
    except Exception:
        return None, None
```
**Second path:** returns `None, None`
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/hooks/block_cli_chained.py:64
**Code:**
```python
    except Exception:
        return None, None, None
```
**Second path:** returns `None, None, None`
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/hooks/block_dangerous_kill.py:47
**Code:**
```python
    except Exception:
        return None, None
```
**Second path:** returns `None, None`
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/hooks/block_dev_imports_src.py:53
**Code:**
```python
    except Exception:
        return None, None, None
```
**Second path:** returns `None, None, None`
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/hooks/block_except_pass.py:41
**Code:**
```python
    except Exception:
        return None, None, None
```
**Second path:** returns `None, None, None`
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/hooks/block_gh_cli_local_path.py:56
**Code:**
```python
    except Exception:
        return None, None
```
**Second path:** returns `None, None`
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/hooks/block_gh_cli_local_path.py:68
**Code:**
```python
    except ValueError:
        return None
```
**Second path:** returns `None`
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/hooks/block_git_add_deps.py:34
**Code:**
```python
    except Exception:
        return None, None
```
**Second path:** returns `None, None`
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/hooks/block_git_destructive.py:67
**Code:**
```python
    except Exception:
        return None, None
```
**Second path:** returns `None, None`
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/hooks/block_manual_worker_cleanup.py:47
**Code:**
```python
    except Exception:
        return None, None
```
**Second path:** returns `None, None`
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/hooks/block_noop_edit.py:35
**Code:**
```python
    except Exception:
        return None, None, None, None
```
**Second path:** returns `None, None, None, None`
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/hooks/block_path_typo.py:38
**Code:**
```python
    except Exception:
        return None
```
**Second path:** returns `None`
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/hooks/block_pipe_scraper_isolated.py:74
**Code:**
```python
    except Exception:
        return None, None
```
**Second path:** returns `None, None`
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/hooks/block_po_read.py:49
**Code:**
```python
    except Exception:
        return None, None, None
```
**Second path:** returns `None, None, None`
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/hooks/block_po_read.py:84
**Code:**
```python
    except OSError:
        return None
```
**Second path:** returns `None`
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/hooks/block_rag_cli_document_repeat.py:69
**Code:**
```python
    except Exception:
        return None, None
```
**Second path:** returns `None, None`
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/hooks/block_rag_cli_document_repeat.py:85
**Code:**
```python
    except ValueError:
        return None
```
**Second path:** returns `None`
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/hooks/block_rag_cli_document_repeat.py:119
**Code:**
```python
    except Exception:
        return 0
```
**Second path:** returns `0`
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/hooks/block_rag_cli_document_repeat.py:129
**Code:**
```python
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    ts = datetime.datetime.fromisoformat(entry.get('ts', '').replace('Z', '+00:00'))
                    if ts >= cutoff:
                        entries.append(entry)
                except Exception:
```
**Second path:** silently skips the current loop item and continues with the remaining ones
**Names its path:** yes
**Fails loudly outside the observed case:** no

### src/hooks/block_rag_cli_document_repeat.py:140
**Code:**
```python
    except Exception:
        return []
```
**Second path:** returns `[]`
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/hooks/block_rag_cli_document_repeat.py:151
**Code:**
```python
    except Exception:
        return
```
**Second path:** catches the exception and continues (side effect only in the handler body, e.g. logging a warning or appending an error record); no value is returned/assigned by the handler itself, and no re-raise
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/hooks/block_rag_cli_index_isolated.py:70
**Code:**
```python
    except Exception:
        return None, None
```
**Second path:** returns `None, None`
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/hooks/block_rag_corpus_read.py:52
**Code:**
```python
    except Exception:
        return None, None
```
**Second path:** returns `None, None`
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/hooks/block_rag_docs_layer.py:57
**Code:**
```python
    except Exception:
        return None, None
```
**Second path:** returns `None, None`
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/hooks/block_rag_docs_layer.py:73
**Code:**
```python
    except ValueError:
        return False
```
**Second path:** returns `False`
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/hooks/block_read_directory.py:29
**Code:**
```python
    except Exception:
        return None, None
```
**Second path:** returns `None, None`
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/hooks/block_read_directory.py:35
**Code:**
```python
    except Exception:
        return False
```
**Second path:** returns `False`
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/hooks/block_search_subreddits_limit.py:45
**Code:**
```python
    except Exception:
        return None, None
```
**Second path:** returns `None, None`
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/hooks/block_unauthorized_background.py:39
**Code:**
```python
    except Exception:
        return None, False, None
```
**Second path:** returns `None, False, None`
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/hooks/block_venv_no_redirect.py:40
**Code:**
```python
    except Exception:
        return None, None
```
**Second path:** returns `None, None`
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/hooks/block_worker_kill_while_working.py:33
**Code:**
```python
    except Exception:
        sys.exit(0)
```
**Second path:** catches the exception and continues (side effect only in the handler body, e.g. logging a warning or appending an error record); no value is returned/assigned by the handler itself, and no re-raise
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/hooks/block_worker_kill_while_working.py:47
**Code:**
```python
        except Exception:
            status = ''
```
**Second path:** assigns `status = ''`
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/hooks/block_worker_kill_while_working.py:73
**Code:**
```python
    except Exception:
        return ''
```
**Second path:** returns `''`
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/hooks/block_worker_kill_while_working.py:81
**Code:**
```python
    except Exception:
        return None, None
```
**Second path:** returns `None, None`
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/hooks/block_worker_send_background.py:46
**Code:**
```python
    except Exception:
        return None, False, None
```
**Second path:** returns `None, False, None`
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/hooks/block_worker_send_while_working.py:33
**Code:**
```python
    except Exception:
        sys.exit(0)
```
**Second path:** catches the exception and continues (side effect only in the handler body, e.g. logging a warning or appending an error record); no value is returned/assigned by the handler itself, and no re-raise
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/hooks/block_worker_send_while_working.py:47
**Code:**
```python
        except Exception:
            status = ''
```
**Second path:** assigns `status = ''`
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/hooks/block_worker_send_while_working.py:73
**Code:**
```python
    except Exception:
        return ''
```
**Second path:** returns `''`
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/hooks/block_worker_send_while_working.py:81
**Code:**
```python
    except Exception:
        return None, None
```
**Second path:** returns `None, None`
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/hooks/block_worker_spawn_placement.py:66
**Code:**
```python
    except Exception:
        return None, None
```
**Second path:** returns `None, None`
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/hooks/hook_setup.py:129
**Code:**
```python
    except Exception:
        return False
```
**Second path:** returns `False`
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/hooks/hook_setup.py:142
**Code:**
```python
    except Exception:
        return None
```
**Second path:** returns `None`
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/hooks/hook_setup.py:198
**Code:**
```python
    except FileNotFoundError:
        return {}
```
**Second path:** returns `{}`
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/hooks/hook_setup.py:200
**Code:**
```python
    except json.JSONDecodeError as e:
        print(f"ERROR: cannot parse {_SETTINGS_FILE}: {e}", file=sys.stderr)
        sys.exit(1)
```
**Second path:** catches the exception and continues (side effect only in the handler body, e.g. logging a warning or appending an error record); no value is returned/assigned by the handler itself, and no re-raise
**Names its path:** yes
**Fails loudly outside the observed case:** no

### src/hooks/rewrite_background_sleep.py:39
**Code:**
```python
    except Exception:
        return True
```
**Second path:** returns `True`
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/hooks/rewrite_background_sleep.py:51
**Code:**
```python
    except Exception:
        return None, False, None
```
**Second path:** returns `None, False, None`
**Names its path:** no
**Fails loudly outside the observed case:** no

### src/hooks/rewrite_chained_sleep.py:58
**Code:**
```python
    except Exception:
        return None, False, None
```
**Second path:** returns `None, False, None`
**Names its path:** no
**Fails loudly outside the observed case:** no


## src/ram_audit/

### src/ram_audit/instrument.py:19
**Code:**
```python
    try:
        import psutil as _psutil
        rss = _psutil.Process(pid).memory_info().rss
        rss_src = 'psutil'
    except ImportError:
        raw = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        rss = raw if sys.platform == 'darwin' else raw * 1024
        rss_src = 'resource'
```
**Second path:** falls back to an alternate import/definition when the primary import fails
**Names its path:** yes
**Fails loudly outside the observed case:** no


### src/ram_audit/instrument.py:63-69
**Code:**
```python
def _resolve_dump_path(pane_name: str, ts: str) -> Path:
    root = os.environ.get('MONITOR_CC_ROOT', '')
    if not root:
        root = str(Path(__file__).resolve().parent.parent.parent)
    dump_dir = Path(root) / 'dev' / 'ram_audit' / 'dumps'
    dump_dir.mkdir(parents=True, exist_ok=True)
    return dump_dir / f'{ts}_{pane_name}.txt'
```
**Second path:** if `MONITOR_CC_ROOT` is unset or empty, substitutes a path computed from `__file__` instead
**Names its path:** no
**Fails loudly outside the observed case:** no

## Counts

| Directory | Findings |
|---|---|
| src/ (top-level) | 7 |
| src/format/ | 1 |
| src/jsonl/ | 2 |
| src/core/ | 0 |
| src/ccwrap/ | 0 |
| src/input/ | 4 |
| src/news_pane/ | 8 |
| src/gpu_pane/ | 18 |
| src/panes/ | 6 |
| src/workers/ | 3 |
| src/ram_audit/ | 2 |
| src/dual_log_cli/ | 21 |
| src/proxy_display/ | 25 |
| src/menubar/ | 73 |
| src/proxy/ | 30 |
| src/hooks/ | 53 |
| **Total** | **253** |

`src/core/` and `src/ccwrap/` were read in full and produced zero findings against the patterns in scope.
