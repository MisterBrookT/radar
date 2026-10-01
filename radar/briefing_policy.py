"""Project-owned editorial contract, independent of topic and video duration."""
VERSION = 1
RHYTHM = "Title and whole-picture idea → only necessary detail → evidence, boundaries and takeaway"
STYLE = {
    'version': VERSION,
    'rhythm': RHYTHM,
    'captions': ['en', 'zh-CN'],
    'voice': 'English; local Piper preferred',
    'visuals': 'Original source figures with narration-timed focus; minimal verified count plots',
    'duration': 'Content-driven; no fixed minutes, word quota or silence padding',
    'detail_test': 'Would removing this detail prevent understanding the core idea? If not, remove it.',
}
from .topics import load_topic

# Compatibility name only; actual classification receives the selected preset.
GENUI_SCOPE = load_topic('genui')['scope']


def validate_weekly_script(script, selected):
    """Fail closed rather than silently returning to the legacy slide/word-quota renderer."""
    from .minimal_video import validate_script
    validate_script(script)
    profile = script.get('briefing', {})
    if profile.get('policy_version') != VERSION or profile.get('cadence') != 'weekly':
        raise ValueError('Weekly script must declare the approved briefing policy')
    if script.get('language') != 'en' or script.get('caption_languages') != ['en', 'zh-CN']:
        raise ValueError('Weekly briefing needs English speech and aligned bilingual captions')
    stories = script.get('stories', [])
    if not stories or script['scenes'][0].get('role') != 'overview':
        raise ValueError('Start with the title and whole-picture overview')
    for scene in script['scenes']:
        if not scene.get('purpose'):
            raise ValueError('Each scene must explain why it is necessary')
        if any(not e.get('segments') for e in scene['events']):
            raise ValueError('Every event needs complete bilingual semantic units')
        owner = scene.get('story')
        if owner is not None and (type(owner) is not int or not 0 <= owner < len(stories)):
            raise ValueError('Unknown story reference')
    for index, story in enumerate(stories):
        sources = story.get('sources', [])
        if not sources or any(type(i) is not int or not 0 <= i < len(selected) for i in sources):
            raise ValueError('Invalid story source references')
        if any(selected[i].get('topic_role') != 'direct' for i in sources):
            raise ValueError('Adjacent work cannot become a core topic headline')
        scenes = [s for s in script['scenes'] if s.get('story') == index]
        if not scenes or scenes[0].get('role') != 'overview':
            raise ValueError('Introduce each work before diving into its details')
        if not any(s.get('role') == 'evidence' for s in scenes):
            raise ValueError('Each story needs source-grounded evidence')
        if not any(s.get('role') == 'boundary' or s.get('contains_boundary') for s in scenes):
            raise ValueError('Each story must state what has not been demonstrated')
