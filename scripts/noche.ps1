<#
Noche del 3 al 4 de noviembre de 2026 (configs/noche.yaml).

1) Entrena rgb_100ep y hace commit y push de reports/fase5b/rgb_100ep/, la bitácora y el log.
2) Entrena termico_100ep y hace commit y push. Si los tres modelos terminaron, también las curvas de los tres.
3) Si los tres terminaron, guarda las predicciones crudas (confianza >= 0.001) de validación y de prueba de los tres
   modelos (evaluar.py --solo-predecir), sin calcular ninguna métrica: los umbrales por modelo se fijan después en
   validación (CLAUDE.md, 3 de noviembre de 2026). Luego commit y push de la bitácora y el log.

- Si falla la comprobación de potencia, espera y reintenta (configs/noche.yaml).
- Si un paso falla, lo anota, hace commit y push de lo que haya y sigue con lo que no depende de él.
- Todo queda, con hora, en el log de configs/noche.yaml. La salida completa de cada comando va a runs/noche/.
- Con -Seco solo comprueba rutas, git, los datos de la prueba, las aplicaciones, la potencia y la energía. No entrena,
  no evalúa ni toca git.

Uso:
  powershell -NoProfile -ExecutionPolicy Bypass -File scripts\noche.ps1 -Config configs\noche.yaml -Python .venv\Scripts\python.exe
  powershell -NoProfile -ExecutionPolicy Bypass -File scripts\noche.ps1 -Config configs\noche.yaml -Python .venv\Scripts\python.exe -Seco
#>
param(
    [Parameter(Mandatory = $true)][string]$Config,
    [Parameter(Mandatory = $true)][string]$Python,
    [switch]$Seco
)

$ErrorActionPreference = 'Continue'
$raiz = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $raiz
$utf8 = New-Object System.Text.UTF8Encoding($false)
$inv = [System.Globalization.CultureInfo]::InvariantCulture
$env:PYTHONIOENCODING = 'utf-8'
$env:GIT_TERMINAL_PROMPT = '0'   # git no pregunta nada: si no puede, falla y se anota
$env:GCM_INTERACTIVE = 'never'
$python = (Resolve-Path -LiteralPath $Python -ErrorAction Stop).Path

function Leer-Yaml([string]$ruta) {
    $codigo = "import json,sys,yaml; print(json.dumps(yaml.safe_load(open(sys.argv[1], encoding='utf-8'))))"
    $json = & $python -c $codigo $ruta
    if ($LASTEXITCODE -ne 0 -or -not $json) { throw "No se pudo leer $ruta" }
    return (($json -join "`n") | ConvertFrom-Json)
}

$cfg = Leer-Yaml $Config
$rutasCfg = Leer-Yaml $cfg.rutas
$cfg5 = Leer-Yaml $cfg.entrenar.config
$cfg6 = Leer-Yaml $cfg.evaluar.config
$dirPasos = Join-Path $raiz $cfg.pasos
New-Item -ItemType Directory -Force -Path $dirPasos | Out-Null
if ($Seco) { $log = Join-Path $raiz $cfg.log_seco } else { $log = Join-Path $raiz $cfg.log }
$bitacora = $rutasCfg.bitacora
$carpetaCorridas = Join-Path $rutasCfg.runs $cfg5.base.carpeta
$codPotencia = [int]$cfg5.codigos_salida.potencia
$nombreCodigo = @{}
foreach ($p in $cfg5.codigos_salida.PSObject.Properties) { $nombreCodigo[[int]$p.Value] = $p.Name }
$part = $cfg6.particiones.($cfg.evaluar.particion)
$salidasEval = @($part.salidas.resultados, $part.salidas.mcnemar, $part.salidas.grafico)
$carpetaPred = Join-Path (Join-Path $rutasCfg.runs $cfg6.carpeta) $cfg.evaluar.particion

function Anotar([string]$mensaje) {
    $linea = '[{0}] {1}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $mensaje
    Write-Host $linea
    [System.IO.File]::AppendAllText($log, $linea + "`r`n", $utf8)
}

function Correr([string]$paso, [string]$comando) {
    # Corre `comando` con cmd.exe y agrega su salida a runs/noche/<paso>.log; devuelve el código de salida.
    # Las rutas del proyecto no tienen espacios, así que van sin comillas.
    $salida = Join-Path $dirPasos ($paso + '.log')
    $bat = Join-Path $dirPasos ($paso + '.cmd')
    $texto = "@echo off`r`necho ===== %DATE% %TIME% $comando>> `"$salida`"`r`n$comando >> `"$salida`" 2>&1`r`nexit /b %ERRORLEVEL%`r`n"
    [System.IO.File]::WriteAllText($bat, $texto, (New-Object System.Text.ASCIIEncoding))
    & cmd.exe /d /c $bat | Out-Null
    return $LASTEXITCODE
}

function Motivo([string]$paso) {
    $salida = Join-Path $dirPasos ($paso + '.log')
    if (-not (Test-Path -LiteralPath $salida)) { return '' }
    $l = Select-String -LiteralPath $salida -Encoding UTF8 `
        -Pattern 'No se entrena|No existe|No hay|Error|Traceback|ya se evalu|No coincide|fatal:|rejected' |
        Select-Object -Last 3 | ForEach-Object { $_.Line.Trim() }
    return ($l -join ' | ')
}

function Nombre([int]$codigo) {
    if ($nombreCodigo.ContainsKey($codigo)) { return $nombreCodigo[$codigo] }
    return 'otro'
}

function Guardar([string]$titulo, [string[]]$rutas) {
    # commit y push solo de `rutas` (lo demás del árbol de trabajo no entra)
    $hay = @($rutas | Where-Object { $_ -and (Test-Path -LiteralPath $_) })
    if ($hay.Count -eq 0) { Anotar "git: nada que guardar para '$titulo'."; return }
    $lista = ($hay | ForEach-Object { $_ -replace '\\', '/' }) -join ' '
    $c = Correr 'git' "git add -- $lista"
    if ($c -ne 0) { Anotar "git add falló (código $c): $(Motivo 'git')"; return }
    $c = Correr 'git' "git diff --cached --quiet -- $lista"
    if ($c -eq 0) {
        Anotar "git: sin cambios para '$titulo'."
    } else {
        $msg = Join-Path $dirPasos 'mensaje_commit.txt'
        [System.IO.File]::WriteAllText($msg, "$titulo`n`n$($cfg.git.coautor)`n", $utf8)
        $c = Correr 'git' "git commit -q -F $msg -- $lista"
        if ($c -ne 0) { Anotar "git commit falló (código $c): $(Motivo 'git')"; return }
        Anotar "git: commit '$titulo'."
    }
    $c = Correr 'git' "git push -q $($cfg.git.remoto) $($cfg.git.rama)"
    if ($c -eq 0) { Anotar 'git: push hecho.' }
    else { Anotar "git push falló (código $c): $(Motivo 'git'). Queda para el siguiente push." }
}

function Resumir-Corrida([string]$corrida) {
    # anota el resumen de una corrida terminada; $false si no tiene resumen.json
    $res = Join-Path (Join-Path $carpetaCorridas $corrida) 'resumen.json'
    if (-not (Test-Path -LiteralPath $res)) { Anotar "FALLO: $corrida terminó sin resumen.json."; return $false }
    $r = Get-Content -LiteralPath $res -Raw -Encoding UTF8 | ConvertFrom-Json
    $bp = $r.val_best_pt
    Anotar ([string]::Format($inv, '{0} terminó: entra {1}, lote {2}, {3:0.0} min. Comprobación previa {4} W; ' +
            'límite al entrenar (mediana) {5} W; temperatura máxima {6} °C; pico de RAM {7} %. best.pt en ' +
            'validación: mAP@0.5 {8:0.000}, precisión {9:0.000}, recall {10:0.000}.', $corrida, $r.entra,
            $r.lote_final, ($r.s_total_corrida / 60), $r.potencia_antes.limite_mediana_w,
            $r.gpu_limite_aplicado_mediana_w, $r.gpu_temperatura_max, $r.ram_pico_pct,
            $bp.'metrics/mAP50(B)', $bp.'metrics/precision(B)', $bp.'metrics/recall(B)'))
    if (-not $r.entra -or [int]$r.lote_final -ne [int]$cfg5.base.ultralytics.batch) {
        Anotar "AVISO: $corrida no entró con el lote $($cfg5.base.ultralytics.batch) (lote final $($r.lote_final))."
    }
    return $true
}

function Probar-Git {
    # ciclo completo de Guardar (add, commit con el mensaje y el coautor, push) en un repositorio de prueba con su
    # propio remoto local, dentro de runs/noche/; el repositorio real no se toca
    $tmp = Join-Path $dirPasos 'seco_repo'
    if (Test-Path -LiteralPath $tmp) { Remove-Item -LiteralPath $tmp -Recurse -Force }
    New-Item -ItemType Directory -Force -Path $tmp | Out-Null
    $nombre = (& git config user.name) -join ''
    $correo = (& git config user.email) -join ''
    $remoto = Join-Path $tmp 'remoto.git'
    $copia = Join-Path $tmp 'copia'
    $c = Correr 'seco_repo' "git init -q --bare $remoto"
    $c += Correr 'seco_repo' "git clone -q $remoto $copia"
    if ($c -ne 0) { return "no se pudo crear el repositorio de prueba: $(Motivo 'seco_repo')" }
    Push-Location -LiteralPath $copia
    try {
        $c = Correr 'seco_repo' "git checkout -q -b $($cfg.git.rama)"
        $c += Correr 'seco_repo' "git config user.name $nombre"
        $c += Correr 'seco_repo' "git config user.email $correo"
        if ($cfg.git.remoto -ne 'origin') { $c += Correr 'seco_repo' "git remote rename origin $($cfg.git.remoto)" }
        if ($c -ne 0) { return "no se pudo preparar el repositorio de prueba: $(Motivo 'seco_repo')" }
        New-Item -ItemType Directory -Force -Path 'reports' | Out-Null
        [System.IO.File]::WriteAllText((Join-Path $copia 'reports\prueba.txt'), "prueba con acentos: á é ñ`r`n", $utf8)
        [System.IO.File]::WriteAllText((Join-Path $copia 'fuera.txt'), "no tiene que entrar en el commit`r`n", $utf8)
        Guardar 'Prueba en seco: commit con acentos (á é ñ)' @('reports/prueba.txt', 'reports/no_existe.txt')
    } finally { Pop-Location }
    $msg = (& git --git-dir $remoto log -1 "--format=%B" $cfg.git.rama) -join "`n"
    $archivos = @(& git --git-dir $remoto show --name-only "--format=" $cfg.git.rama)
    $esperado = 'Prueba en seco: commit con acentos (á é ñ)'
    if (-not $msg) { return 'el push al remoto de prueba no llegó' }
    if ($msg -notlike "$esperado*" -or $msg -notlike "*$($cfg.git.coautor)*") { return "mensaje del commit inesperado: $msg" }
    if (($archivos -join ',') -ne 'reports/prueba.txt') { return "el commit lleva otros archivos: $($archivos -join ', ')" }
    return ''
}

function Entrenar([string]$corrida) {
    $max = [int]$cfg.entrenar.reintentos_potencia
    $espera = [int]$cfg.entrenar.espera_reintento_s
    $paso = "entrenar_$corrida"
    for ($intento = 0; $intento -le $max; $intento++) {
        Anotar "Entrenando $corrida (intento $($intento + 1)). Salida completa en $($cfg.pasos)/$paso.log."
        $c = Correr $paso "$python $($cfg.entrenar.script) --config $($cfg.entrenar.config) --rutas $($cfg.rutas) --corrida $corrida"
        $pot = Select-String -LiteralPath (Join-Path $dirPasos "$paso.log") -Pattern '^Potencia:' -Encoding UTF8 |
            Select-Object -Last 1 | ForEach-Object { $_.Line }
        if ($c -eq 0) { return (Resumir-Corrida $corrida) }
        if ($c -eq $codPotencia) {
            Anotar "Falló la comprobación de potencia de ${corrida}: $(Motivo $paso) ($pot)"
            if ($intento -lt $max) {
                Anotar "Espero $espera s y reintento ($($intento + 1) de $max reintentos)."
                Start-Sleep -Seconds $espera
                continue
            }
            Anotar "Me rindo con ${corrida}: la potencia falló $($max + 1) veces."
            return $false
        }
        Anotar "FALLO en $corrida (código $c, $(Nombre $c)): $(Motivo $paso)"
        return $false
    }
    return $false
}

function Resumir-Evaluacion {
    $res = Import-Csv -LiteralPath $part.salidas.resultados -Encoding UTF8
    $mc = Import-Csv -LiteralPath $part.salidas.mcnemar -Encoding UTF8
    foreach ($sc in $part.subconjuntos) {
        $dud = 'con'
        if ($sc.grafico) { $dud = $cfg6.mcnemar.dudosas }
        $filas = $res | Where-Object { $_.tipo -eq 'modelo' -and $_.subconjunto -eq $sc.nombre -and $_.dudosas -eq $dud }
        $txt = ($filas | ForEach-Object {
                [string]::Format($inv, '{0} {1:0.000} [{2:0.000}, {3:0.000}]', $_.modelo, [double]::Parse($_.recall, $inv),
                    [double]::Parse($_.recall_ic_inf, $inv), [double]::Parse($_.recall_ic_sup, $inv)) }) -join '; '
        Anotar "Recall en $($sc.nombre) ($dud dudosas): $txt"
    }
    foreach ($f in $mc) {
        Anotar ([string]::Format($inv, 'McNemar {0}, {1} contra {2}: solo {1} {3}, solo {2} {4}, p Bonferroni {5:0.0000}, ' +
                'significativo {6}.', $f.subconjunto, $f.modelo_a, $f.modelo_b, $f.solo_a, $f.solo_b,
                [double]::Parse($f.p_bonferroni, $inv), $f.significativo))
    }
}

function Valor-AC([string]$sub, [string]$ajuste) {
    # índice de corriente alterna de un ajuste de energía (penúltimo valor hexadecimal de powercfg)
    $salida = (powercfg /query SCHEME_CURRENT $sub $ajuste 2>$null) -join "`n"
    $hex = @([regex]::Matches($salida, '0x[0-9a-fA-F]{8}') | ForEach-Object { $_.Value })
    if ($hex.Count -lt 2) { return $null }
    return [Convert]::ToInt64($hex[$hex.Count - 2], 16)
}

function Prueba-En-Seco {
    $problemas = New-Object System.Collections.Generic.List[string]
    $avisos = New-Object System.Collections.Generic.List[string]
    Get-ChildItem -LiteralPath $dirPasos -Filter 'seco_*' | Remove-Item -Force   # salidas de pruebas en seco anteriores
    Anotar '=== Prueba en seco de noche.ps1 (no entrena, no evalúa, no toca git).'

    # 1. rutas que tienen que existir y las que no
    $necesarias = @($Config, $cfg.rutas, $cfg.entrenar.config, $cfg.evaluar.config, $cfg.entrenar.script,
        $cfg.entrenar.copiar, $cfg.entrenar.resumen, $cfg.evaluar.script, $cfg5.base.pesos, $cfg5.base.datos, $bitacora)
    foreach ($c in $cfg.entrenar.corridas) {
        if (-not ($cfg5.corridas.PSObject.Properties.Name -contains $c)) { $problemas.Add("la corrida $c no está en $($cfg.entrenar.config)") }
        elseif ($cfg5.corridas.$c.datos) { $necesarias += $cfg5.corridas.$c.datos }
    }
    foreach ($c in $cfg.entrenar.ya_entrenadas) {
        $necesarias += (Join-Path (Join-Path $carpetaCorridas $c) 'resumen.json')
        $necesarias += (Join-Path (Join-Path $carpetaCorridas $c) 'weights\best.pt')
    }
    foreach ($m in $cfg6.modelos.PSObject.Properties) { $necesarias += $m.Value.datos }
    foreach ($p in $necesarias) { if (-not (Test-Path -LiteralPath $p)) { $problemas.Add("falta $p") } }
    $noDeben = @($carpetaPred) + $salidasEval
    foreach ($c in $cfg.entrenar.corridas) { $noDeben += (Join-Path $carpetaCorridas $c) }
    foreach ($p in $noDeben) { if (Test-Path -LiteralPath $p) { $problemas.Add("ya existe $p") } }
    Anotar "Rutas: $($necesarias.Count) que tienen que existir y $($noDeben.Count) que no tienen que existir."

    # 2. git
    $rama = (& git rev-parse --abbrev-ref HEAD) -join ''
    if ($rama -ne $cfg.git.rama) { $problemas.Add("la rama actual es $rama, no $($cfg.git.rama)") }
    $c = Correr 'seco_git' "git push --dry-run $($cfg.git.remoto) $($cfg.git.rama)"
    if ($c -ne 0) { $problemas.Add("git push --dry-run falló (código $c): $(Motivo 'seco_git')") }
    $pend = @(& git status --porcelain)
    Anotar "Git: rama $rama; push de prueba con código $c; $($pend.Count) archivos sin commit."
    if ($pend.Count) { $avisos.Add("hay $($pend.Count) archivos sin commit; los commits de la noche solo llevan sus rutas") }
    $e = Probar-Git
    if ($e) { $problemas.Add("ciclo de commit y push en el repositorio de prueba: $e") }
    else { Anotar 'Ciclo de commit y push en un repositorio de prueba (runs/noche/seco_repo): bien.' }

    # 2b. resumen de las corridas ya entrenadas (lo mismo que se anota al terminar cada corrida de la noche)
    foreach ($c in $cfg.entrenar.ya_entrenadas) {
        if (-not (Resumir-Corrida $c)) { $problemas.Add("no se pudo leer el resumen de $c") }
    }

    # 3. datos de la prueba (sin predecir)
    $c = Correr 'seco_evaluar' "$python $($cfg.evaluar.script) --config $($cfg.evaluar.config) --rutas $($cfg.rutas) --particion $($cfg.evaluar.particion) --solo-verificar"
    if ($c -ne 0) { $problemas.Add("evaluar.py --solo-verificar falló (código $c): $(Motivo 'seco_evaluar')") }
    $ver = Select-String -LiteralPath (Join-Path $dirPasos 'seco_evaluar.log') -Pattern '^Partición' -Encoding UTF8 |
        Select-Object -Last 1 | ForEach-Object { $_.Line }
    Anotar "Datos de la prueba (código $c): $ver"

    # 4. aplicaciones y potencia (30 s con la GPU cargada)
    $primera = @($cfg.entrenar.corridas)[0]
    $c = Correr 'seco_entrenar' "$python $($cfg.entrenar.script) --config $($cfg.entrenar.config) --rutas $($cfg.rutas) --corrida $primera --solo-comprobar"
    $pot = Select-String -LiteralPath (Join-Path $dirPasos 'seco_entrenar.log') -Pattern '^Potencia:' -Encoding UTF8 |
        Select-Object -Last 1 | ForEach-Object { $_.Line }
    if ($c -ne 0) {
        $l = Select-String -LiteralPath (Join-Path $dirPasos 'seco_entrenar.log') -Pattern '^No se entrena' -Encoding UTF8 |
            Select-Object -Last 2 | ForEach-Object { $_.Line.Trim() }
        $problemas.Add("comprobación de $primera falló (código $c, $(Nombre $c)): $($l -join ' | ')")
    }
    Anotar "Aplicaciones y potencia (código $c): $pot"

    # 5. energía y Windows
    $susp = Valor-AC 'SUB_SLEEP' 'STANDBYIDLE'
    $hib = Valor-AC 'SUB_SLEEP' 'HIBERNATEIDLE'
    $tapa = Valor-AC 'SUB_BUTTONS' 'LIDACTION'
    if ($susp -ne 0) { $problemas.Add("con corriente, la laptop se suspende a los $susp s") }
    if ($hib -ne 0) { $problemas.Add("con corriente, la laptop hiberna a los $hib s") }
    if ($null -eq $tapa) { $avisos.Add('no se puede leer qué hace Windows al cerrar la tapa (está oculto en este plan; por omisión, suspende): deja la tapa abierta') }
    elseif ($tapa -ne 0) { $avisos.Add("al cerrar la tapa con corriente, Windows no se queda sin hacer nada (acción $tapa): deja la tapa abierta") }
    $reinicio = Test-Path 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\WindowsUpdate\Auto Update\RebootRequired'
    if ($reinicio) { $avisos.Add('Windows Update tiene un reinicio pendiente: puede reiniciar la laptop de noche') }
    $unidad = (Get-Item -LiteralPath $raiz).PSDrive
    $libre = [math]::Round($unidad.Free / 1GB, 1)
    if ($libre -lt [double]$cfg.seco.disco_minimo_gb) { $avisos.Add("quedan $libre GB libres en $($unidad.Name):") }
    Anotar "Energía con corriente: suspensión $susp s, hibernación $hib s, tapa $tapa (0 = nada). Reinicio pendiente: $reinicio. Libre: $libre GB."

    foreach ($a in $avisos) { Anotar "AVISO: $a" }
    if ($problemas.Count -eq 0) { Anotar 'RESULTADO: LISTO para lanzar.' }
    else {
        foreach ($p in $problemas) { Anotar "PROBLEMA: $p" }
        Anotar "RESULTADO: NO LISTO ($($problemas.Count) problemas)."
    }
}

if ($Seco) {
    try { Prueba-En-Seco } catch { Anotar "Error inesperado en la prueba en seco: $_" }
    exit
}

# ------------------------------------------------------------------------------------------------------------ noche
Anotar "=== Noche: empieza. Corridas $(@($cfg.entrenar.corridas) -join ', '); luego las predicciones crudas de $(@($cfg.evaluar.predecir) -join ' y ') (sin métricas)."
$ok = @{}
foreach ($c in $cfg.entrenar.corridas) {
    try { $ok[$c] = [bool](Entrenar $c) } catch { Anotar "Error inesperado entrenando ${c}: $_"; $ok[$c] = $false }
    try {
        if ($ok[$c]) {
            $k = Correr "copiar_$c" "$python $($cfg.entrenar.copiar) --config $($cfg.entrenar.config) --rutas $($cfg.rutas) --corrida $c"
            if ($k -ne 0) { Anotar "No se pudieron copiar los archivos de $c (código $k): $(Motivo "copiar_$c")" }
            Guardar "Fase 5b: $c, 100 épocas (noche)" @("$($cfg.entrenar.carpeta_reports)/$c", $bitacora, $cfg.log)
        } else {
            Guardar "Fase 5b: falló $c (noche)" @("$($cfg.entrenar.carpeta_reports)/$c", $bitacora, $cfg.log)
        }
    } catch { Anotar "Error inesperado al guardar ${c}: $_" }
}

$faltan = @()
foreach ($c in $cfg.entrenar.ya_entrenadas) {
    if (-not (Test-Path -LiteralPath (Join-Path (Join-Path $carpetaCorridas $c) 'resumen.json'))) { $faltan += $c }
}
foreach ($c in $cfg.entrenar.corridas) { if (-not $ok[$c]) { $faltan += $c } }

if ($faltan.Count -eq 0) {
    try {
        $k = Correr 'resumen_5b' "$python $($cfg.entrenar.resumen) --config $($cfg.entrenar.config) --rutas $($cfg.rutas)"
        if ($k -eq 0) { Anotar "Curvas y tabla de los tres modelos en $($cfg.entrenar.carpeta_reports)/." }
        else { Anotar "No se pudieron hacer las curvas de los tres (código $k): $(Motivo 'resumen_5b')" }
        Guardar 'Fase 5b: curvas y tabla de los tres modelos (noche)' @($cfg.entrenar.carpeta_reports, $cfg.log)

        # 3. solo predicciones crudas (sin métricas): los umbrales se fijan mañana en validación (CLAUDE.md)
        foreach ($pp in $cfg.evaluar.predecir) {
            Anotar "Guardando las predicciones crudas de $pp con los tres modelos (sin métricas). Salida completa en $($cfg.pasos)/predecir_$pp.log."
            $k = Correr "predecir_$pp" "$python $($cfg.evaluar.script) --config $($cfg.evaluar.config) --rutas $($cfg.rutas) --particion $pp --solo-predecir"
            if ($k -eq 0) { Anotar "Predicciones de $pp guardadas en $($rutasCfg.runs)/$($cfg6.carpeta)/$pp/<modelo>/predictions.json." }
            else { Anotar "FALLO al predecir $pp (código $k): $(Motivo "predecir_$pp")" }
        }
        Guardar 'Fase 6: predicciones crudas de validación y prueba, tres modelos, sin métricas (noche)' @($bitacora, $cfg.log)
    } catch { Anotar "Error inesperado al predecir: $_" }
} else {
    Anotar "No se guardan las predicciones: no terminaron $($faltan -join ', ')."
}

$estado = ($cfg.entrenar.corridas | ForEach-Object { "$_ $(if ($ok[$_]) { 'bien' } else { 'falló' })" }) -join ', '
Anotar "=== Noche: termina. $estado. Predicciones: $(if ($faltan.Count -eq 0) { 'intentadas (ver arriba)' } else { 'no se hicieron' })."
Guardar 'Noche: registro final' @($cfg.log)
