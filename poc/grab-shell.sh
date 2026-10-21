#!/bin/bash
# Poll for the station's adbd (5555); the moment it opens, grab the root shell.
ADB=/opt/homebrew/bin/adb
ST=192.168.1.82
for i in $(seq 1 900); do
  if nc -z -G 1 $ST 5555 >/dev/null 2>&1; then
    echo "=== PORT 5555 OPEN at $(date) ==="
    $ADB kill-server >/dev/null 2>&1
    $ADB connect $ST:5555
    sleep 3
    $ADB devices
    for j in $(seq 1 20); do
      st=$($ADB get-state 2>/dev/null)
      [ "$st" = "device" ] && break
      sleep 2
      $ADB connect $ST:5555 >/dev/null 2>&1
    done
    echo "=== whoami ===";   $ADB -s $ST:5555 shell whoami
    echo "=== id ===";       $ADB -s $ST:5555 shell id
    echo "=== uname ===";    $ADB -s $ST:5555 shell uname -a
    echo "=== build ===";    $ADB -s $ST:5555 shell getprop | grep -iE "product|model|yandex|version.release" | head -8
    echo "=== /data peek ==="; $ADB -s $ST:5555 shell 'ls /data | head -5'
    echo "=== GRAB DONE ==="
    exit 0
  fi
  sleep 2
done
echo "TIMEOUT: port 5555 never opened"
