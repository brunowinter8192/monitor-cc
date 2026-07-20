# CotEditor → Space-Jump (Markieren wirft auf anderen Desktop)

## Symptom

User markiert auf Schreibtisch 1 eine Zeile in einem CotEditor-Dokument → wird unmittelbar
auf Schreibtisch 2 geworfen, wo **Ghostty** im Vordergrund ist (NICHT CotEditor). CotEditor
liegt auf jedem Space; nach dem Sprung ist auf dem Ziel-Space Ghostty vorn. Der Auslöser
fühlt sich wie das Markieren an, ist zeitlich aber unscharf.

**Nicht reproduzierbar auf Abruf** (Stand 2026-06-12) — tritt sporadisch im normalen Arbeiten
auf. Zurückgestellt: bei nächstem Auftreten das Repro-Experiment unten fahren.

## Mechanismus-Eingrenzung

Ein Sprung-auf-Ghostty kann ausschließlich von `_focus_session(cwd)` (`src/menubar/system.py:44`)
kommen. Die Funktion baut AppleScript `tell application "Ghostty" → activate → focus terminal id "<UUID>"`.
Das `activate` ist der Sprung: holt Ghostty nach vorn, und wenn das Ziel-Terminal auf einem
anderen Space liegt, schaltet macOS dorthin.

`_focus_session` hat genau drei Aufrufer:

| Aufrufer | Stelle | Auslöser | Spur im Log |
|---|---|---|---|
| `focusSession_` | `app.py:91` | manueller Panel-Klick | nur Focus-Log-Zeile |
| digit-callback | `hotkey_controller.py:292` | cmd+Ziffer-Druck | `[hotkey] cmd+N → focus` + Focus-Log |
| auto-focus | `focus_controller.py:54` | Main-Session working→idle (+3s) | nur Focus-Log; nur wenn `_auto_focus`=true |

## Hypothesen

| Hypothese | Status | Evidenz |
|---|---|---|
| macOS auto-swoosh (App-Aktivierung springt zu App-Fenster auf anderem Space) | AUSGESCHLOSSEN | Sagt Sprung ZU einem CotEditor-Fenster voraus; User landet aber bei Ghostty |
| Veralteter Menubar-Build (gebündelter Code ohne Auto-Focus-Gate) | AUSGESCHLOSSEN | `diff` bundled vs src `focus_controller.py` = identisch; Gate `if self.app._auto_focus:` ist drin |
| `_load_settings`-Bug (lädt auto_focus=true trotz Datei) | AUSGESCHLOSSEN | `app_settings.py:_load_settings` liest `bool(d.get('auto_focus', False))` korrekt; Datei = false |
| Auto-Focus feuert trotz `_auto_focus=false` (Laufzeit-Wert divergiert) | UNVERIFIZIERT | Setting-Datei=false, Prozess startete danach → sollte false sein; nur Live-Repro klärt's |
| cmd+Ziffer wird beim Markieren ungewollt ausgelöst | UNVERIFIZIERT | Würde `[hotkey]`-Zeile loggen; bisher keine zur Sprung-Zeit gesehen |
| Sprung kommt NICHT von der Menubar (`_focus_session` feuert gar nicht) | UNVERIFIZIERT | Nur Repro mit Log-Beobachtung schließt das aus/ein |

Drei Hypothesen sind verbrannt — bei der nächsten ist Vorsicht geboten, kein Voreilen.

## Repro-Experiment (bei nächstem Auftreten)

1. Marker setzen:
   - `wc -l /tmp/monitor-cc-menubar_focus.log`
   - `wc -l ~/Library/Application\ Support/com.brunowinter.monitor-cc-menubar/menubar.log`
2. Bug reproduzieren (in CotEditor markieren bis Sprung). **Menubar dabei NICHT anfassen.**
3. Neue Zeilen ab Marker lesen und zuordnen:
   - Neue Focus-Zeile im Sprung-Moment **+ `[hotkey]`** → cmd+Ziffer.
   - Neue Focus-Zeile **ohne `[hotkey]`** (und kein Klick) → Auto-Focus ⇒ `_auto_focus` ist Laufzeit `true`.
   - **Keine** neue Focus-Zeile → Menubar unschuldig, Sprung kommt woanders her (Geste/macOS/andere App).

Focus-Log-Zeilenformat (`system.py:_focus_session`): `<ts> OK id=<UUID>` (Path A) / `OK cwd=<pfad>` (Path B) / `MISS` / `ERR` / `TIMEOUT`.

## macOS-Befunde

- `workspaces-auto-swoosh` (com.apple.dock): unset = Default. Nicht die Ursache (s.o.), aber relevant fürs Space-Verhalten generell.
- Menubar läuft als py2app-Bundle `~/Applications/monitor-cc-menubar.app` (Build 2026-06-10 03:54), liest Settings aus `~/Library/Application Support/com.brunowinter.monitor-cc-menubar/settings.json` (aktuell `auto_focus: false`).

## Verwandtes Thema — cmd+N holt Ghostty überall nach vorn

Dasselbe `activate` in `_focus_session` war der Kern des cmd+N-Foreground-Themas (cmd+N holte Ghostty
auf ALLEN Desktops in den Vordergrund statt nur auf dem Ziel-Desktop). Dort wurde das `activate`
entfernt (siehe `cmd_n_ghostty_foreground.md`) — fixt cmd+N, betrifft diesen CotEditor-Sprung aber
NICHT (s.u., der Sprung kommt gar nicht aus `_focus_session`).

## Repro-Befund 2026-06-12 — Menubar als Ursache AUSGESCHLOSSEN

Der Bug wurde live reproduziert (~22:03): User markierte auf Schreibtisch 3 eine Zeile in CotEditor
→ wurde auf Schreibtisch 1 mit Ghostty im Vordergrund geworfen. User bestätigt: **nur mit Maus/Trackpad
markiert, KEINE cmd-Ziffer gedrückt.**

Log-Auswertung (Marker-Diff): im Focus-Log gab es zum Sprung-Moment **KEINEN Eintrag** (2,5-Min-Lücke
um 22:03; das einzige Event war ein `cmd+k` = Panel-Toggle, kein Focus).

→ Fall 3 des Repro-Experiments: **keine Focus-Zeile = `_focus_session` feuerte nicht = Menubar ist
unschuldig.** Der Sprung kommt NICHT aus der Menubar-Fokus-Funktion. Hypothese "Sprung kommt NICHT von
der Menubar" → **BESTÄTIGT**; die menubar-internen Kandidaten (Auto-Focus, cmd+Ziffer) sind für diesen
Fall ausgeschlossen (kein Event geloggt).

**Konsequenz — Logging-Lücke:** unser Logging fängt nur `_focus_session`-Aufrufe (Focus-Log) und
cmd-Tastendrücke (`[hotkey]`) ab. Der echte Trigger des CotEditor-Markier-Sprungs wird aktuell GAR
NICHT geloggt. Nächster Schritt braucht einen anderen Weg, den Trigger zu fangen — Kandidaten:
macOS-Spaces-Verhalten beim Fokuswechsel, eine Trackpad-/Gesten-Quelle, ein anderer App-/System-Mechanismus
(alles außerhalb der Menubar).
