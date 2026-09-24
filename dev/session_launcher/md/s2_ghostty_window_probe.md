# s2_ghostty_window_probe report

- time: 2026-09-24 20:05:44
- home desktop: 2
- switch method: a1
- permissions of this process: {'Accessibility': True, 'PostEvent': True, 'ListenEvent': True, 'ScreenCapture': True}
- window desktop: CGSCopySpacesForWindows of the new CG window mapped to desktop index
- hit = window desktop equals target desktop and window is on screen

| variant | # | target | switch ms | script ms | visible ms | window desktop | onscreen | hit | active after script | active after settle | closed | returned |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| no_activate | 1 | 1 | 283 | 122 | 152 | [1] | True | yes | 1 | 1 | False | True |
