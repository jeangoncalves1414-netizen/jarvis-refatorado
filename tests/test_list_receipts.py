from app.agent.tools.lifestyle_tools import TaskTool, HabitTool, TaskService, HabitService


def test_task_list_names_and_state(monkeypatch):
    monkeypatch.setattr(TaskService, 'list_tasks', lambda **kw: [{'title': 'Read', 'completed': False, 'due_date': '2026-11-14'}])
    result = TaskTool().run(action='list')
    assert '[ ] Read' in result['message']
    assert '2026-11-14' in result['message']


def test_habit_list_names_and_time(monkeypatch):
    monkeypatch.setattr(HabitService, 'list_habits', lambda: [{'name': 'Walk', 'start_time': '08:00'}])
    result = HabitTool().run(action='list')
    assert 'Walk às 08:00' in result['message']
