# Evidencia de la Práctica 9: corre carga.sh (E13) impidiendo que el equipo se suspenda.
#
#   powershell -File docs\pruebas\evidencia\scripts\carga_despierto.ps1
#
# El 26/11 dos corridas de k6 quedaron partidas porque el portátil, con batería, entró
# en Modern Standby por inactividad. SetThreadExecutionState con ES_CONTINUOUS,
# ES_SYSTEM_REQUIRED y ES_DISPLAY_REQUIRED se lo impide solo mientras este hilo esté
# vivo; al terminar se restablece. No cambia ninguna configuración de energía.
Add-Type -Namespace Evidencia -Name Energia -MemberDefinition @'
[DllImport("kernel32.dll")] public static extern uint SetThreadExecutionState(uint esFlags);
'@
$continuo = [uint32]2147483648      # ES_CONTINUOUS (0x80000000)
$despierto = [uint32]2147483651     # ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED
$anterior = [Evidencia.Energia]::SetThreadExecutionState($despierto)
if ($anterior -eq 0) { throw "SetThreadExecutionState falló" }
Write-Output "Equipo impedido de suspenderse (estado anterior: $anterior)."
try {
    & "C:\Program Files\Git\bin\bash.exe" -c "bash docs/pruebas/evidencia/scripts/carga.sh"
} finally {
    [Evidencia.Energia]::SetThreadExecutionState($continuo) | Out-Null
    Write-Output "Estado de energía restablecido."
}
