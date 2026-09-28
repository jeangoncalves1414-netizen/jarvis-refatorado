# Sessão de identidade

Abra o painel desktop e selecione **Identidade**.

1. No primeiro uso, informe um nome e uma senha com pelo menos oito caracteres e crie o administrador.
2. Selecione o perfil, informe a senha e grave uma amostra de voz de 3–5 segundos.
3. Abra a câmera, salve uma foto de referência e, se desejar, ative a detecção automática (a cada 5 segundos).
4. Use **Testar voz** ou **Verificar rosto** para conferir a confiança da correspondência.
5. Para adicionar outra pessoa, informe a senha administrativa no campo **Senha do administrador** e use **Adicionar pessoa**. Depois cadastre as amostras desse perfil.

Os dados são gravados em `data/identity_profiles.json`; as imagens de referência ficam em `data/identity_faces/`. A senha é armazenada somente como PBKDF2-SHA256 com salt. A verificação é local e conservadora: uma confiança abaixo do limiar não concede privilégios.

Este é um módulo de teste. Antes de usar para autenticação real, é necessário calibrar os limiares com várias amostras por pessoa e adicionar uma política de revogação/auditoria adequada.
