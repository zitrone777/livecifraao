using System.Diagnostics;
using System.IO.Compression;
using System.Net.Http;
using System.Net.Http.Json;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Windows;
using System.Windows.Controls;

namespace NexivoLive.Launcher;

public partial class MainWindow : Window
{
    private const string ApiBaseUrl = "https://nexivolive.com";
    private static readonly HttpClient Http = CreateHttpClient();
    private readonly string installDirectory = Path.Combine(
        Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "NexivoLive");

    public MainWindow()
    {
        InitializeComponent();
        MouseLeftButtonDown += (_, _) => DragMove();
        KeyBox.Focus();
    }

    private static HttpClient CreateHttpClient()
    {
        var client = new HttpClient { Timeout = TimeSpan.FromSeconds(60) };
        client.DefaultRequestHeaders.UserAgent.ParseAdd("NexivoLive-Launcher/1.0");
        return client;
    }

    private void KeyBox_TextChanged(object sender, TextChangedEventArgs e)
    {
        var raw = KeyBox.Text.Replace("-", "").Replace(" ", "").ToUpperInvariant();
        if (raw.Length > 12) raw = raw[..12];
        var parts = Enumerable.Range(0, (raw.Length + 3) / 4)
            .Select(i => raw.Skip(i * 4).Take(4).ToArray())
            .Where(x => x.Length > 0)
            .Select(x => new string(x));
        var formatted = string.Join("-", parts);
        if (KeyBox.Text != formatted)
        {
            KeyBox.TextChanged -= KeyBox_TextChanged;
            KeyBox.Text = formatted;
            KeyBox.CaretIndex = KeyBox.Text.Length;
            KeyBox.TextChanged += KeyBox_TextChanged;
        }
    }

    private async void VerifyButton_Click(object sender, RoutedEventArgs e)
    {
        var key = KeyBox.Text.Trim().ToUpperInvariant();
        if (key.Length != 15)
        {
            ShowError("Digite a chave completa.");
            return;
        }

        SetBusy(true, "Verificando sua licença...");
        try
        {
            var hwid = CreateHwid();
            var validation = await PostAsync<ValidateResponse>("/api/license-validate", new { key, hwid });
            if (validation is null || !validation.valid)
            {
                ShowError(MapReason(validation?.reason));
                return;
            }

            SetStatus("Licença ativa. Preparando instalação...");
            var download = await PostAsync<DownloadResponse>("/api/license-download", new { key });
            if (download is null || string.IsNullOrWhiteSpace(download.url))
            {
                ShowError("Não foi possível iniciar a instalação.");
                return;
            }

            SetStatus("Baixando NexivoLive...");
            Directory.CreateDirectory(installDirectory);
            var zipPath = Path.Combine(Path.GetTempPath(), $"NexivoLive-\${Guid.NewGuid():N}.zip");

            using (var response = await Http.GetAsync(download.url, HttpCompletionOption.ResponseHeadersRead))
            {
                response.EnsureSuccessStatusCode();
                await using var source = await response.Content.ReadAsStreamAsync();
                await using var destination = File.Create(zipPath);
                await source.CopyToAsync(destination);
            }

            SetStatus("Instalando NexivoLive...");
            if (Directory.Exists(installDirectory))
            {
                foreach (var file in Directory.EnumerateFiles(installDirectory))
                    try { File.Delete(file); } catch { }
                foreach (var dir in Directory.EnumerateDirectories(installDirectory))
                    try { Directory.Delete(dir, true); } catch { }
            }

            ZipFile.ExtractToDirectory(zipPath, installDirectory, true);
            File.Delete(zipPath);
            SaveActivation(key);
            ShowSuccess();
        }
        catch (HttpRequestException)
        {
            ShowError("Não foi possível conectar ao servidor. Verifique sua internet.");
        }
        catch (TaskCanceledException)
        {
            ShowError("A operação demorou demais. Tente novamente.");
        }
        catch (Exception ex)
        {
            Debug.WriteLine(ex);
            ShowError("Não foi possível concluir a instalação.");
        }
        finally
        {
            SetBusy(false);
        }
    }

    private static async Task<T?> PostAsync<T>(string path, object body)
    {
        using var response = await Http.PostAsJsonAsync($"{ApiBaseUrl}{path}", body);
        var json = await response.Content.ReadAsStringAsync();
        if (!response.IsSuccessStatusCode)
            throw new HttpRequestException($"HTTP {(int)response.StatusCode}: {json}");
        return JsonSerializer.Deserialize<T>(json, new JsonSerializerOptions { PropertyNameCaseInsensitive = true });
    }

    private static string CreateHwid()
    {
        var raw = $"{Environment.MachineName}|{Environment.UserDomainName}|{Environment.OSVersion.VersionString}";
        return Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(raw)));
    }

    private void SaveActivation(string key)
    {
        Directory.CreateDirectory(installDirectory);
        File.WriteAllText(Path.Combine(installDirectory, "license.dat"), key);
    }

    private void SetBusy(bool busy, string? status = null)
    {
        VerifyButton.IsEnabled = !busy;
        KeyBox.IsEnabled = !busy;
        StatusPanel.Visibility = busy ? Visibility.Visible : Visibility.Collapsed;
        if (status is not null) StatusText.Text = status;
        ErrorText.Visibility = Visibility.Collapsed;
    }

    private void SetStatus(string text)
    {
        StatusPanel.Visibility = Visibility.Visible;
        StatusText.Text = text;
        ErrorText.Visibility = Visibility.Collapsed;
    }

    private void ShowError(string message)
    {
        StatusPanel.Visibility = Visibility.Collapsed;
        ErrorText.Text = message;
        ErrorText.Visibility = Visibility.Visible;
        VerifyButton.IsEnabled = true;
        KeyBox.IsEnabled = true;
    }

    private void ShowSuccess()
    {
        VerifyButton.Visibility = Visibility.Collapsed;
        KeyBox.Visibility = Visibility.Collapsed;
        StatusPanel.Visibility = Visibility.Collapsed;
        ErrorText.Visibility = Visibility.Collapsed;
        SuccessPanel.Visibility = Visibility.Visible;
        SubtitleText.Text = "Tudo pronto.";
    }

    private void OpenFolder_Click(object sender, RoutedEventArgs e)
    {
        Process.Start(new ProcessStartInfo
        {
            FileName = "explorer.exe",
            Arguments = $"\${installDirectory}",
            UseShellExecute = true
        });
    }

    private static string MapReason(string? reason) => reason switch
    {
        "not_found" => "Essa chave não existe.",
        "expired" => "Essa licença expirou.",
        "revoked" => "Essa licença foi revogada.",
        "device_limit" => "Essa licença já está vinculada a outro dispositivo.",
        _ => "Não foi possível validar essa licença."
    };
}

public sealed record ValidateResponse(bool valid, string? reason);
public sealed record DownloadResponse(string? url, int expires_in);
