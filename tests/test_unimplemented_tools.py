from app.agent.tools.code_helper import CodeHelperTool
from app.agent.tools.dev_agent import DevAgentTool
import pytest

@pytest.mark.parametrize('action', ['explain','generate','refactor'])
def test_code_placeholder_never_claims_work(action):
    result = CodeHelperTool().execute({'action':action,'code':'print(1+1)'})
    assert not result.ok and 'Nenhum' in result.message

@pytest.mark.parametrize('task', ['review','debug','test'])
def test_dev_placeholder_never_claims_work(task):
    result = DevAgentTool().execute({'task':task})
    assert not result.ok and 'Nenhuma' in result.message
