package com.example.jarvismobile

import android.app.Activity
import android.app.AlertDialog
import android.content.Intent
import android.os.Bundle
import android.provider.Settings

class RemoteControlActivity : Activity() {
    override fun onCreate(state: Bundle?) { super.onCreate(state); showControl() }

    private fun showControl(code: String? = null) {
        val enabled = RemoteControlService.isEnabled(this)
        AlertDialog.Builder(this)
            .setTitle("Controle remoto do celular")
            .setMessage(code ?: if (enabled) "Ativo. Seu PC poderá enviar comandos pela página segura do Jarvis enquanto esta notificação estiver visível." else "Ative para permitir que o seu PC pareado abra apps e envie ações básicas. O serviço fica visível em uma notificação.")
            .setPositiveButton(if (enabled) "Desativar" else "Ativar") { _, _ -> RemoteControlService.setEnabled(this, !enabled); showControl() }
            .setNeutralButton("Gerar código do PC") { _, _ ->
                if (!RemoteControlService.isEnabled(this)) RemoteControlService.setEnabled(this, true)
                RemoteControlService.pairCode(this) { value -> runOnUiThread { showControl("No PC, abra:\nhttps://jarvis-mobile-cloud.jarvis-jeangoncalves1414.workers.dev/control\n\nCódigo: $value\n\nEle expira em 10 minutos.") } }
            }
            .setNegativeButton("Acessibilidade") { _, _ -> startActivity(Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS)); finish() }
            .setOnCancelListener { finish() }
            .show()
    }
}
