# s2_ghostty_window_probe report

- time: 2026-09-24 20:17:42
- home desktop: 2
- switch method: a1
- permissions of this process: {'Accessibility': True, 'PostEvent': True, 'ListenEvent': True, 'ScreenCapture': True}
- window desktop: CGSCopySpacesForWindows of the new CG window mapped to desktop index
- hit = window desktop equals target desktop and window is on screen
- closed = the Ghostty window id is gone from the AppleScript window list; the CG window may linger as an off-screen zombie with no space

| variant | # | target | switch ms | script ms | visible ms | window desktop | onscreen | hit | active after script | active after settle | closed | returned |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| no_activate | 1 | 1 | 275 | 118 | 151 | [1] | True | yes | 1 | 1 | True | True |
| no_activate | 2 | 3 | 279 | 114 | 147 | [3] | True | yes | 3 | 3 | True | True |
| no_activate | 3 | 4 | 284 | 119 | 152 | [4] | True | yes | 4 | 4 | True | True |
| no_activate | 4 | 5 | 288 | 114 | 144 | [5] | True | yes | 5 | 5 | True | True |
| no_activate | 5 | 1 | 281 | 122 | 150 | [] | False | no | 1 | 1 | True | True |
| activate | 1 | 1 | 289 | 121 | 154 | [1] | True | yes | 1 | 1 | True | True |
| activate | 2 | 3 | 270 | 123 | 154 | [3] | True | yes | 3 | 3 | True | True |
| activate | 3 | 4 | 273 | 131 | 135 | [] | False | no | 4 | 4 | True | True |
| activate | 4 | 5 | 281 | 120 | 151 | [5] | True | yes | 5 | 5 | True | True |
| activate | 5 | 1 | 266 | 127 | 158 | [1] | True | yes | 1 | 1 | True | True |
