using System;
using System.Diagnostics;
using System.IO;
using System.Windows.Forms;

namespace JarvisLauncher
{
    static class Program
    {
        [STAThread]
        static void Main(string[] args)
        {
            try
            {
                // Determina o diretório do projeto
                string exeDir = AppDomain.CurrentDomain.BaseDirectory;
                string projectDir = exeDir;

                if (!File.Exists(Path.Combine(projectDir, "run_jarvis.pyw")))
                {
                    string defaultDir = @"c:\Users\maria\Desktop\Jarvis";
                    if (File.Exists(Path.Combine(defaultDir, "run_jarvis.pyw")))
                    {
                        projectDir = defaultDir;
                    }
                    else
                    {
                        MessageBox.Show(
                            "Não foi possível localizar o arquivo 'run_jarvis.pyw' do Jarvis.\nVerifique se o executável está na pasta do projeto.",
                            "Jarvis - Erro de Inicialização",
                            MessageBoxButtons.OK,
                            MessageBoxIcon.Error
                        );
                        return;
                    }
                }

                // Localiza o Python
                string pythonExe = FindPythonExecutable();
                if (string.IsNullOrEmpty(pythonExe) || !File.Exists(pythonExe))
                {
                    MessageBox.Show(
                        "O Python 3.11 não foi encontrado.\nVerifique se o Python está instalado em C:\\Users\\maria\\AppData\\Local\\Programs\\Python\\Python311.",
                        "Jarvis - Python não encontrado",
                        MessageBoxButtons.OK,
                        MessageBoxIcon.Error
                    );
                    return;
                }

                // Argumentos
                string scriptPath = Path.Combine(projectDir, "run_jarvis.pyw");
                string extraArgs = string.Join(" ", args);
                string fullArgs = "\"" + scriptPath + "\" " + extraArgs;

                ProcessStartInfo psi = new ProcessStartInfo();
                psi.FileName = pythonExe;
                psi.Arguments = fullArgs.Trim();
                psi.WorkingDirectory = projectDir;
                psi.UseShellExecute = false;
                psi.CreateNoWindow = true;

                Process.Start(psi);
            }
            catch (Exception ex)
            {
                MessageBox.Show(
                    "Erro ao iniciar o Jarvis:\n\n" + ex.Message,
                    "Jarvis - Falha",
                    MessageBoxButtons.OK,
                    MessageBoxIcon.Error
                );
            }
        }

        static string FindPythonExecutable()
        {
            // 1. Caminho preferencial do usuário
            string preferred = @"C:\Users\maria\AppData\Local\Programs\Python\Python311\pythonw.exe";
            if (File.Exists(preferred)) return preferred;

            string preferredCmd = @"C:\Users\maria\AppData\Local\Programs\Python\Python311\python.exe";
            if (File.Exists(preferredCmd)) return preferredCmd;

            // 2. Via LOCALAPPDATA
            string localApp = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
            string localPythonW = Path.Combine(localApp, @"Programs\Python\Python311\pythonw.exe");
            if (File.Exists(localPythonW)) return localPythonW;

            // 3. Pesquisa no PATH
            string pathEnv = Environment.GetEnvironmentVariable("PATH") ?? "";
            foreach (string p in pathEnv.Split(';'))
            {
                string trimmed = p.Trim();
                if (string.IsNullOrEmpty(trimmed)) continue;

                string pw = Path.Combine(trimmed, "pythonw.exe");
                if (File.Exists(pw)) return pw;

                string py = Path.Combine(trimmed, "python.exe");
                if (File.Exists(py)) return py;
            }

            return null;
        }
    }
}
