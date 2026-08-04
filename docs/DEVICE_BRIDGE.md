# Ponte de dispositivos do Jarvis

## O que foi implementado

O desktop agora expõe um contrato pequeno e independente de fabricante:

- `GET /api/bridge`: código de pareamento, dispositivos, estado de conexão e últimos eventos.
- `POST /api/bridge` com `action=pair` ou `register`: registra um cliente/dispositivo.
- `POST /api/bridge` com `action=heartbeat`: mantém um cliente conectado.
- `POST /api/bridge` com `action=command`: envia comandos normalizados como `turn_on`, `turn_off`, `set_brightness` e `set_color`.
- `GET /bridge`: página branca para testar o fluxo em um navegador, inclusive no celular.

O estado fica em `data/device_bridge.json`. A lâmpada de teste no painel é apenas um simulador; ela não controla a lâmpada Smart Life.

## Teste local

1. Inicie o Jarvis em modo servidor (`python -m app.main --server`) ou abra o desktop normalmente.
2. Abra a aba **Automações** e adicione a lâmpada de teste.
3. Use **Ligar** e **Desligar** para verificar o estado persistido.
4. Para testar outro dispositivo na mesma rede, abra `/bridge` no navegador.

Por segurança, o servidor continua ligado em `127.0.0.1` por padrão. Só exponha para a rede local conscientemente, definindo `APP_HOST=0.0.0.0` no `.env` e protegendo a rede doméstica. O código de pareamento não é uma autenticação completa; antes do uso remoto será necessário adicionar token por cliente, TLS/VPN e expiração de sessões.

## Próxima etapa: lâmpada real

Antes de criar o app Android, precisamos identificar se a lâmpada é Wi-Fi, BLE ou híbrida e qual família de dispositivo Smart Life ela usa. O adaptador físico será implementado atrás do `DeviceBridgeService`; a UI e o futuro app não precisarão conhecer detalhes Tuya/BLE.

O objetivo final é:

```text
PC ligado:      celular ↔ ponte Jarvis ↔ adaptador da lâmpada
PC desligado:   celular ↔ adaptador direto da lâmpada (quando suportado)
```

Assim, o celular não fica dependente do PC para ligar a lâmpada. O PC funciona como hub opcional quando estiver ativo.
