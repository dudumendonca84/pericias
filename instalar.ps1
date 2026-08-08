# Instalacao do acervo de pericias numa maquina nova, num comando so.
#
#   irm https://raw.githubusercontent.com/dudumendonca84/pericias/claude/diagnostico-laudos-periciais-9wrgvl/instalar.ps1 | iex
#
# Descarrega o programa, instala o que falta, e liga-o ao Claude Desktop.
#
# Para trazer tambem o acervo, define a variavel antes de correr:
#
#   $env:ACERVO_URL = "https://.../acervo_pericias.sqlite"
#   irm https://.../instalar.ps1 | iex
#
# Esse link e teu e privado. O acervo nunca vive neste repositorio: tem dados
# de partes identificadas e processos em segredo de justica, e um repositorio
# publico torna isso permanente e indexavel.

$ErrorActionPreference = "Stop"

$repo    = "dudumendonca84/pericias"
$ramo    = "claude/diagnostico-laudos-periciais-9wrgvl"
$destino = Join-Path $HOME "Documents\pericias"

function Passo($n, $texto) {
    Write-Host ""
    Write-Host "[$n] $texto" -ForegroundColor Cyan
}

Write-Host ""
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "  ACERVO DE PERICIAS - instalacao" -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan

# ---------------------------------------------------------------- Python
Passo 1 "Python"
$python = $null
foreach ($candidato in @("python", "python3", "py")) {
    try {
        $versao = & $candidato --version 2>&1
        # O atalho da Microsoft Store responde ao comando mas nao e Python:
        # aceita-lo aqui faz a instalacao falhar tres passos mais a frente.
        if ($versao -match "Python 3\.(\d+)" -and [int]$Matches[1] -ge 10) {
            $python = $candidato
            Write-Host "  $versao" -ForegroundColor Green
            break
        }
    } catch { }
}

if (-not $python) {
    Write-Host "  Python 3.10 ou superior nao encontrado." -ForegroundColor Yellow
    Write-Host "  A instalar..."
    try {
        winget install --silent --accept-package-agreements --accept-source-agreements Python.Python.3.12
    } catch {
        Write-Host ""
        Write-Host "  Nao consegui instalar automaticamente." -ForegroundColor Red
        Write-Host "  Instala de https://www.python.org/downloads/"
        Write-Host "  IMPORTANTE: marca 'Add python.exe to PATH' no instalador."
        return
    }
    Write-Host ""
    Write-Host "  Python instalado. FECHA esta janela, abre outra," -ForegroundColor Yellow
    Write-Host "  e volta a correr este comando." -ForegroundColor Yellow
    Write-Host "  (o PATH so actualiza em janelas novas)" -ForegroundColor Yellow
    return
}

# ---------------------------------------------------------------- programa
Passo 2 "Programa"
$temp = Join-Path $env:TEMP "pericias-$(Get-Random).zip"
$url  = "https://github.com/$repo/archive/refs/heads/$ramo.zip"

Write-Host "  a descarregar..."
Invoke-WebRequest -Uri $url -OutFile $temp -UseBasicParsing

$extraccao = Join-Path $env:TEMP "pericias-extraccao-$(Get-Random)"
Expand-Archive -Path $temp -DestinationPath $extraccao -Force
$origem = Get-ChildItem $extraccao -Directory | Select-Object -First 1

if (Test-Path $destino) {
    # Substituir apenas o codigo: o acervo e a configuracao do utilizador
    # ficam onde estao. Copiar por cima a pasta toda apagaria o indice.
    Write-Host "  ja existia; a actualizar so o programa"
    Get-ChildItem $origem.FullName -File | ForEach-Object {
        Copy-Item $_.FullName -Destination $destino -Force
    }
    $skills = Join-Path $origem.FullName ".claude"
    if (Test-Path $skills) {
        Copy-Item $skills -Destination $destino -Recurse -Force
    }
} else {
    New-Item -ItemType Directory -Force -Path $destino | Out-Null
    Copy-Item "$($origem.FullName)\*" -Destination $destino -Recurse -Force
}

Remove-Item $temp -Force -ErrorAction SilentlyContinue
Remove-Item $extraccao -Recurse -Force -ErrorAction SilentlyContinue
Write-Host "  em $destino" -ForegroundColor Green

# ---------------------------------------------------------------- pacotes
Passo 3 "Pacotes"
Write-Host "  a instalar..."
# --trusted-host: redes com proxy corporativo (Zscaler e afins) quebram a
# verificacao TLS do pip e a instalacao falha sem razao aparente.
& $python -m pip install --quiet --disable-pip-version-check `
    --trusted-host pypi.org --trusted-host files.pythonhosted.org `
    mcp pymupdf python-docx
if ($LASTEXITCODE -ne 0) {
    Write-Host "  FALHOU. Ve a mensagem acima." -ForegroundColor Red
    return
}
Write-Host "  instalados" -ForegroundColor Green

# ---------------------------------------------------------------- Claude
Passo 4 "Ligar ao Claude Desktop"
Push-Location $destino
& $python instalar_mcp.py
Pop-Location

# ---------------------------------------------------------------- acervo
Passo 5 "Acervo"
$acervo = Join-Path $destino "acervo_pericias.sqlite"

if ($env:ACERVO_URL -and -not (Test-Path $acervo)) {
    Write-Host "  a descarregar de $($env:ACERVO_URL)"
    try {
        Invoke-WebRequest -Uri $env:ACERVO_URL -OutFile $acervo -UseBasicParsing
    } catch {
        Write-Host "  FALHOU: $_" -ForegroundColor Red
        Write-Host "  Confirma que o link e de descarga directa e esta acessivel."
        Remove-Item $acervo -Force -ErrorAction SilentlyContinue
    }
}

# Uma pagina de erro HTML guardada com o nome do acervo passaria por ficheiro
# valido e so daria erro quando alguem tentasse procurar.
if (Test-Path $acervo) {
    $bytes = [System.IO.File]::ReadAllBytes($acervo)[0..14]
    $assinatura = [System.Text.Encoding]::ASCII.GetString($bytes)
    if (-not $assinatura.StartsWith("SQLite format 3")) {
        Write-Host "  O ficheiro descarregado nao e um acervo valido." -ForegroundColor Red
        Write-Host "  (o link devolveu outra coisa -- provavelmente uma pagina de aviso)"
        Remove-Item $acervo -Force -ErrorAction SilentlyContinue
    }
}

if (Test-Path $acervo) {
    $mb = [math]::Round((Get-Item $acervo).Length / 1MB, 0)
    Write-Host "  encontrado ($mb MB)" -ForegroundColor Green
} else {
    Write-Host "  ainda nao existe." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "  Copia o ficheiro acervo_pericias.sqlite para:"
    Write-Host "    $destino" -ForegroundColor White
    Write-Host ""
    Write-Host "  Ou constroi-o a partir das pericias desta maquina:"
    Write-Host "    cd `"$destino`"" -ForegroundColor White
    Write-Host "    python configurar.py" -ForegroundColor White
}

Write-Host ""
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "  Feito. Fecha e reabre o Claude Desktop." -ForegroundColor Cyan
Write-Host "  Depois pergunta: que laudos tenho sobre infiltracao?" -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host ""
