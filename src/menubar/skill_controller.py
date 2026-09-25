# INFRASTRUCTURE
from AppKit import NSMenu, NSMenuItem
from Foundation import NSMakePoint

from src.menubar.menubar_log import log_menubar
from src.menubar.skill_discovery import discover_skills_workflow
from src.menubar.skill_insert import insert_skill_workflow

_EMPTY_TITLE = 'no skills'

# FUNCTIONS


class SkillController:
    def __init__(self, app) -> None:
        self.app = app
        self._menu_cwd = None

    def show_menu(self, button, cwd: str) -> None:
        if not cwd:
            log_menubar('skill', 'FAILED stage=menu detail=no_cwd_for_row')
            return
        skills = discover_skills_workflow(cwd)
        menu = _build_menu(skills, self.app._panel_controller)
        self._menu_cwd = cwd
        menu.popUpMenuPositioningItem_atLocation_inView_(
            None, NSMakePoint(0, button.bounds().size.height), button)

    def handle_choice(self, item) -> None:
        full_name = item.representedObject()
        if not full_name or not self._menu_cwd:
            log_menubar('skill', f'FAILED stage=choice detail=missing_choice skill={full_name} cwd={self._menu_cwd}')
            return
        insert_skill_workflow(self._menu_cwd, str(full_name))

def _build_menu(skills, target) -> NSMenu:
    menu = NSMenu.alloc().initWithTitle_('')
    menu.setAutoenablesItems_(False)
    if not skills:
        empty = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(_EMPTY_TITLE, None, '')
        empty.setEnabled_(False)
        menu.addItem_(empty)
        return menu
    previous_source = skills[0].source
    for skill in skills:
        if skill.source != previous_source:
            menu.addItem_(NSMenuItem.separatorItem())
            previous_source = skill.source
        item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(skill.short, 'insertSkill:', '')
        item.setTarget_(target)
        item.setRepresentedObject_(skill.full)
        menu.addItem_(item)
    return menu
