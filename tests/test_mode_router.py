"""
Testes unitários para o classificador e auto-router inteligente de modos (app.agent.mode_router).
"""

import pytest
from app.agent.mode_router import resolve_active_mode


class TestModeRouterExplicit:
    """Testa honra a escolhas explícitas do usuário."""

    def test_explicit_modes_honored(self):
        modes = ["planning", "thinking", "research", "coder", "lifeos", "tutor", "react", "swarm"]
        for m in modes:
            resolved, meta = resolve_active_mode("Qualquer texto aqui", explicit_mode=m)
            assert resolved == m
            assert meta["strategy"] == "explicit"
            assert meta["confidence"] == 1.0

    def test_only_auto_triggers_inference(self):
        resolved_auto, meta_auto = resolve_active_mode("Escreva uma função python", explicit_mode="auto")
        assert resolved_auto == "coder"
        assert meta_auto["strategy"] == "auto"

        resolved_gen, meta_gen = resolve_active_mode("Escreva uma função python", explicit_mode="general")
        assert resolved_gen == "general"
        assert meta_gen["strategy"] == "explicit"


class TestModeRouterAutoThinking:
    """Testa detecção do modo thinking (raciocínio profundo, dilemas, matemática, lógica)."""

    @pytest.mark.parametrize("prompt", [
        "Pense profundamente sobre as premissas e os trade-offs entre monólitos e microsserviços.",
        "Qual a melhor decisão estratégica para resolver este dilema ético?",
        "Demonstre que a energia se conserva na termodinâmica através de equações.",
        "/think Como planejar a arquitetura de alta disponibilidade?",
        "Faça uma análise comparativa profunda e considere cenários contra-factuais.",
        "Analise logicamente este silogismo e identifique se há alguma falácia lógica nas premissas.",
    ])
    def test_thinking_detection(self, prompt: str):
        resolved, meta = resolve_active_mode(prompt, explicit_mode="auto")
        assert resolved == "thinking"
        assert meta["strategy"] == "auto"
        assert meta["confidence"] >= 0.65


class TestModeRouterAutoResearch:
    """Testa detecção do modo research (notícias, cotações, busca na internet, comparativos)."""

    @pytest.mark.parametrize("prompt", [
        "Pesquise na internet as últimas notícias sobre o lançamento de chips quânticos.",
        "Qual a cotação do dólar hoje e a taxa selic atual no Brasil?",
        "Faça um comparativo de preços do iPhone 16 nas principais lojas.",
        "Procure na web as novidades de hoje sobre exploração espacial.",
        "/pesquisa O que aconteceu com a missão Artemis?",
    ])
    def test_research_detection(self, prompt: str):
        resolved, meta = resolve_active_mode(prompt, explicit_mode="auto")
        assert resolved == "research"
        assert meta["strategy"] == "auto"
        assert meta["confidence"] >= 0.65


class TestModeRouterAutoCoder:
    """Testa detecção do modo coder (código, refatoração, bugs, regex, APIs)."""

    @pytest.mark.parametrize("prompt", [
        "Escreva uma função em Python para calcular a sequência de Fibonacci com tipagem estrita.",
        "Como consertar este erro TypeError: 'NoneType' object is not subscriptable?",
        "Crie um endpoint FastAPI e implemente a validação com Pydantic.",
        "Refatore esta função para usar async/await e tratar exceções com segurança.",
        "Crie uma expressão regular regex para validar números de telefone no formato internacional.",
        "```typescript\ninterface User { id: string }\n```\nOtimize este código.",
        "/code Implemente um decorator em Python para medir tempo de execução.",
    ])
    def test_coder_detection(self, prompt: str):
        resolved, meta = resolve_active_mode(prompt, explicit_mode="auto")
        assert resolved == "coder"
        assert meta["strategy"] == "auto"
        assert meta["confidence"] >= 0.65


class TestModeRouterAutoLifeOS:
    """Testa detecção do modo lifeos (hábitos, água, lista de compras, finanças, treinos)."""

    @pytest.mark.parametrize("prompt", [
        "Bebi 500ml de água agora e cumpri meu hábito de leitura.",
        "Adicione leite, café e ovos na minha lista de compras do mercado.",
        "Gastei R$ 45,90 no almoço hoje, anote nas despesas.",
        "Qual o meu treino de hoje? Vou fazer supino e agachamento na academia.",
        "Me lembre de ligar para o médico amanhã às 14h.",
        "/lifeos Registre que tomei 2 litros de água hoje.",
        "Adicione a tarefa 'Revisar orçamento mensal' no meu checklist de hoje.",
    ])
    def test_lifeos_detection(self, prompt: str):
        resolved, meta = resolve_active_mode(prompt, explicit_mode="auto")
        assert resolved == "lifeos"
        assert meta["strategy"] == "auto"
        assert meta["confidence"] >= 0.65


class TestModeRouterGeneralFallback:
    """Testa fallback para general em saudações e conversas cotidianas."""

    @pytest.mark.parametrize("prompt", [
        "Olá Jarvis, tudo bem com você?",
        "Bom dia!",
        "Obrigado pela ajuda de antes.",
        "Quem é você?",
        "",
        "   ",
    ])
    def test_general_fallback(self, prompt: str):
        resolved, meta = resolve_active_mode(prompt, explicit_mode="auto")
        assert resolved == "general"


class TestModeRouterDisambiguation:
    """Testa casos compostos onde há termos de mais de uma categoria."""

    def test_research_about_python(self):
        # Usuário quer notícias/pesquisa sobre Python, não código
        prompt = "Pesquise na internet as últimas notícias sobre o lançamento do Python 3.14"
        resolved, _ = resolve_active_mode(prompt, explicit_mode="auto")
        assert resolved == "research"

    def test_code_that_searches(self):
        # Usuário quer código que faz busca, intenção primária é coder
        prompt = "Escreva um script python para pesquisar palavras-chave em arquivos"
        resolved, _ = resolve_active_mode(prompt, explicit_mode="auto")
        assert resolved == "coder"

    def test_research_news_about_person(self):
        prompt = "Pesquise na internet as últimas notícias sobre o Bluezão"
        resolved, _ = resolve_active_mode(prompt, explicit_mode="auto")
        assert resolved == "research"

    def test_video_analysis_query(self):
        prompt = "Analise o video do youtube https://www.youtube.com/watch?v=dQw4w9WgXcQ e me diga os principais tópicos em timestamps"
        resolved, _ = resolve_active_mode(prompt, explicit_mode="auto")
        assert resolved == "general"
