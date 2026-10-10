@echo off
rem Permite que otros celulares de la misma red Wi-Fi abran el sitio de desarrollo (puerto 5000).
rem Doble clic. Windows pedira confirmacion de administrador: responde "Si".
rem Para quitar el permiso despues: abrir-puerto-wifi.bat quitar

net session >nul 2>&1
if errorlevel 1 (
  powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -ArgumentList '%1' -Verb RunAs"
  exit /b
)

if /i "%1"=="quitar" (
  netsh advfirewall firewall delete rule name="Campo Directo 5000"
  echo.
  echo Permiso quitado.
) else (
  netsh advfirewall firewall delete rule name="Campo Directo 5000" >nul 2>&1
  netsh advfirewall firewall add rule name="Campo Directo 5000" dir=in action=allow protocol=TCP localport=5000 profile=private,public
  echo.
  echo Listo. Ahora abre en el celular: http://192.168.1.6:5000  (con http, sin la s^)
)
echo.
pause
