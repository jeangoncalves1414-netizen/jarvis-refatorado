from app.agent.prompts import build_function_calling_system_prompt, build_marker_agent_system_prompt


def test_desktop_prompts_require_explicit_phone_target():
    prompt = build_function_calling_system_prompt("", [], "", allowed_tool_names={"mobile_adb"})

    assert "Sem indicação de dispositivo" in prompt
    assert "Só use mobile_adb" in prompt
    assert "No PC ou no celular?" in prompt


def test_marker_prompt_keeps_pc_as_the_default_target():
    prompt = build_marker_agent_system_prompt("", [])

    assert "esta conversa acontece no PC" in prompt
    assert "Só use controle de celular/Android/ADB" in prompt
